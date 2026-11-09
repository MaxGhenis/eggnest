"""The one-year US drawdown calculator on the real PolicyEngine-US engine.

- Federal tax and taxable Social Security match 2026 law worked by hand
  (Rev. Proc. 2025-32 amounts, 26 USC 86 and 151(d)(5)(C)).
- Medicare's income-related premiums step up where 2026 income crosses CMS's
  2026 lines, by CMS's 2026 amounts.
- Money to spend ties to PolicyEngine-US's own household_net_income: it is
  that figure plus the part of the draw that isn't income, with Wisconsin's
  retirement income exclusion kept (the household calculator's accounting).
- One simulation of many households gives each household the result it gets
  in a simulation of its own.
- Each kind of draw reaches the programs the way ``us_year_engine`` says.
- Benefit steps far smaller than a grid interval's width are placed to
  within 1/24 of the interval.
- Each outcome's benefits by program add up to its benefits.
- The frontend's recorded runs match what PolicyEngine-US now produces.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from policyengine_us import Simulation

from eggnest.cli import main as cli
from eggnest.core.us_drawdown_year import OUTPUT_KEY, build_us_drawdown_year_scenario
from eggnest.drawdown_us import cash_income, run_us_drawdown_year
from eggnest.models_us_drawdown import USDrawdownYearInput
from eggnest.us_year_engine import (
    CENT,
    FLOAT32_RELATIVE_ROUNDING,
    PolicyEngineUSYear,
    build_situation,
    reported_draw,
)
from main import app

ENGINE = PolicyEngineUSYear()
DOLLAR = 1.0
# The fine part of the grid steps $250 and the second run cuts a jump's
# interval into 24.
LOCATED = 250.0 / 24 + 0.01
# CMS 2026 monthly income-related amounts at the first two lines.
PART_B_FIRST, PART_B_SECOND = 81.20, 202.90
PART_D_FIRST, PART_D_SECOND = 14.50, 37.50


def _single_texan(
    draw: float = 0.0, household: dict | None = None, **person
) -> USDrawdownYearInput:
    """67 at the end of 2026, $24,000 of Social Security, $500,000 in an IRA."""
    return USDrawdownYearInput.model_validate(
        {
            "state": "TX",
            "you": {
                "birth_year": 1959,
                "social_security": 24_000.0,
                "traditional_balance": 500_000.0,
                **person,
            },
            "draw_amount": draw,
            **(household or {}),
        }
    )


@pytest.mark.parametrize(
    ("draw", "taxable_social_security", "federal_income_tax"),
    [
        # Provisional income 52,000: taxable SS = min(20,400, 0.85 x 18,000 +
        # 4,500) = 19,800. AGI 59,800 less the 16,100 + 2,050 standard
        # deduction and the full 6,000 senior deduction leaves 35,650:
        # 1,240 + 12% x 23,250 = 4,030.
        (40_000.0, 19_800.0, 4_030.00),
        # All 20,400 taxable. AGI 80,400 cuts the senior deduction by 6% of
        # 5,400 to 5,676, leaving 56,574: 1,240 + 4,560 + 22% x 6,174.
        (60_000.0, 20_400.0, 7_158.28),
    ],
)
def test_federal_tax_matches_2026_law_worked_by_hand(
    draw, taxable_social_security, federal_income_tax
):
    arrays = ENGINE.evaluate(_single_texan(draw), np.array([draw]))
    assert arrays.taxable_social_security[0] == pytest.approx(
        taxable_social_security, abs=DOLLAR
    )
    assert arrays.federal_income_tax[0] == pytest.approx(federal_income_tax, abs=DOLLAR)
    assert arrays.state_income_tax[0] == 0.0  # Texas has no income tax.


def test_medicare_steps_follow_cms_lines_and_amounts():
    """Once all $20,400 of taxable Social Security counts, Medicare income is
    the draw plus $20,400, so it reaches $109,001 at a draw of $88,601 and
    $137,001 at $116,601."""
    result = run_us_drawdown_year(_single_texan(120_000.0), ENGINE)
    steps = [m for m in result.markers if m.kind == "medicare_surcharge_step"]
    assert [m.draw for m in steps[:2]] == pytest.approx([88_601.0, 116_601.0], abs=0.01)
    assert [m.amount for m in steps[:2]] == pytest.approx(
        [
            12 * (PART_B_FIRST + PART_D_FIRST),
            12 * (PART_B_SECOND - PART_B_FIRST + PART_D_SECOND - PART_D_FIRST),
        ],
        abs=0.01,
    )
    surcharge = result.medicare_surcharge
    assert surcharge.premium_year == 2028
    assert surcharge.rates_year == 2026
    assert surcharge.people_on_medicare == 1
    assert surcharge.lines == [109_001.0, 137_001.0, 171_001.0, 205_001.0, 500_000.0]
    assert surcharge.at_chosen_draw == pytest.approx(
        12 * (PART_B_SECOND + PART_D_SECOND), abs=0.01
    )


def test_both_spouses_pay_the_surcharge():
    """$40,000 and $25,000 of Social Security (85% taxable at these
    incomes) and $20,000 of dividends: Medicare income is the draw plus
    $75,250, so it reaches the joint line of $218,001 at $142,751."""
    inputs = USDrawdownYearInput.model_validate(
        {
            "state": "FL",
            "filing_status": "married_filing_jointly",
            "you": {
                "birth_year": 1954,
                "social_security": 40_000.0,
                "traditional_balance": 2_000_000.0,
            },
            "spouse": {"birth_year": 1956, "social_security": 25_000.0},
            "dividends": 20_000.0,
            "draw_amount": 150_000.0,
        }
    )
    arrays = ENGINE.evaluate(inputs, np.array([142_750.0, 142_751.0]))
    assert arrays.people_on_medicare == 2
    assert arrays.medicare_lines[0] == 218_001.0
    assert arrays.later_medicare_surcharge[1] - arrays.later_medicare_surcharge[
        0
    ] == pytest.approx(2 * 12 * (PART_B_FIRST + PART_D_FIRST), abs=0.01)


IDENTITY_CASES = {
    "texas_single_ira": _single_texan(40_000.0),
    "wisconsin_exclusion_roth": USDrawdownYearInput.model_validate(
        {
            "state": "WI",
            "you": {
                "birth_year": 1955,
                "social_security": 20_000.0,
                "pension_income": 30_000.0,
                "roth_balance": 100_000.0,
            },
            "draw_source": "roth",
            "draw_amount": 20_000.0,
        }
    ),
    "california_ssi": USDrawdownYearInput.model_validate(
        {
            "state": "CA",
            "you": {
                "birth_year": 1950,
                "social_security": 9_000.0,
                "traditional_balance": 1_500.0,
            },
            "cash_savings": 300.0,
            "draw_amount": 1_000.0,
        }
    ),
    "new_york_couple_sale": USDrawdownYearInput.model_validate(
        {
            "state": "NY",
            "filing_status": "married_filing_jointly",
            "you": {
                "birth_year": 1955,
                "social_security": 30_000.0,
                "traditional_balance": 400_000.0,
                "roth_conversion": 10_000.0,
            },
            "spouse": {
                "birth_year": 1958,
                "social_security": 15_000.0,
                "government_pension_income": 12_000.0,
            },
            "taxable_interest": 2_000.0,
            "tax_exempt_interest": 3_000.0,
            "dividends": 5_000.0,
            "taxable_balance": 200_000.0,
            "cash_savings": 20_000.0,
            "draw_source": "taxable",
            "draw_amount": 50_000.0,
        }
    ),
    "alaska_cash": USDrawdownYearInput.model_validate(
        {
            "state": "AK",
            "you": {"birth_year": 1952, "social_security": 18_000.0},
            "cash_savings": 30_000.0,
            "draw_source": "cash",
            "draw_amount": 10_000.0,
        }
    ),
}


@pytest.mark.parametrize("name", list(IDENTITY_CASES))
def test_money_to_spend_ties_to_household_net_income(name):
    inputs = IDENTITY_CASES[name]
    draws = np.array([0.0, 1_000.0, inputs.draw_amount])
    arrays = ENGINE.evaluate(inputs, draws)
    money = cash_income(inputs) + draws - arrays.taxes + arrays.benefits

    sim = Simulation(situation=build_situation(inputs, draws))

    def household(variable: str) -> np.ndarray:
        return np.asarray(
            sim.calculate(variable, inputs.tax_year, map_to="household"), dtype=float
        )

    before = household("state_income_tax_before_refundable_credits")
    credits = household("household_refundable_state_tax_credits")
    after = household("state_income_tax")
    election = after < before - credits - (
        CENT + FLOAT32_RELATIVE_ROUNDING * np.abs(before)
    )
    # The Wisconsin household takes the exclusion path, which lowers state tax
    # below what household_net_income nets; no other case has such a path.
    assert election.all() if inputs.state == "WI" else not election.any()
    adjustment = np.where(election, before - credits - after, 0.0)
    # household_net_income nets health benefits and costs only when
    # PolicyEngine-US counts health coverage as income; money to spend never does.
    expected = (
        household("household_net_income")
        + draws
        - reported_draw(inputs, draws)
        + adjustment
        - household("household_health_benefits")
        + household("household_health_costs")
    )
    assert money == pytest.approx(expected, abs=DOLLAR)


@pytest.mark.parametrize("name", list(IDENTITY_CASES))
def test_benefits_by_program_add_up_to_benefits(name):
    result = run_us_drawdown_year(IDENTITY_CASES[name], ENGINE)
    for point in result.sweep:
        assert sum(point.benefits_by_program.values()) == pytest.approx(
            point.benefits, abs=DOLLAR
        )


def test_alaska_permanent_fund_dividend_counts_as_a_benefit():
    arrays = ENGINE.evaluate(IDENTITY_CASES["alaska_cash"], np.array([0.0]))
    assert arrays.programs["ak_permanent_fund_dividend"][0] > 0


def test_one_simulation_of_many_households_matches_each_alone():
    inputs = IDENTITY_CASES["new_york_couple_sale"]
    draws = np.array([0.0, 25_000.0, 50_000.0])
    together = ENGINE.evaluate(inputs, draws)
    for index, draw in enumerate(draws):
        alone = ENGINE.evaluate(inputs, np.array([draw]))
        for name in (
            "federal_income_tax",
            "state_income_tax",
            "other_taxes",
            "benefits",
            "taxable_social_security",
            "medicare_income",
            "later_medicare_surcharge",
        ):
            assert getattr(together, name)[index] == pytest.approx(
                getattr(alone, name)[0], abs=0.01
            ), (name, draw)


def test_a_roth_draw_changes_no_tax():
    """$40,000 of pension and $24,000 of Social Security give the same tax as
    the $40,000 IRA draw above: $4,030 on $19,800 of taxable Social Security.
    A $20,000 Roth draw on top changes neither, nor Medicare income."""
    inputs = _single_texan(
        20_000.0,
        {"draw_source": "roth"},
        pension_income=40_000.0,
        roth_balance=100_000.0,
    )
    arrays = ENGINE.evaluate(inputs, np.array([0.0, 20_000.0]))
    assert arrays.federal_income_tax == pytest.approx([4_030.0, 4_030.0], abs=DOLLAR)
    assert arrays.taxable_social_security == pytest.approx([19_800.0, 19_800.0])
    assert arrays.medicare_income[1] == pytest.approx(arrays.medicare_income[0])


def test_a_roth_draw_counts_as_income_for_snap():
    """SNAP counts retirement_distributions, taxable and tax-exempt, as
    unearned income. With $9,000 of Social Security SNAP pays at no draw and
    nothing after a $20,000 Roth draw."""
    inputs = _single_texan(
        20_000.0,
        {"draw_source": "roth"},
        social_security=9_000.0,
        traditional_balance=0.0,
        roth_balance=100_000.0,
    )
    arrays = ENGINE.evaluate(inputs, np.array([0.0, 20_000.0]))
    snap = arrays.programs["snap"]
    assert snap[0] > 0
    assert snap[1] == 0.0


def test_retirement_balances_count_for_ssi():
    """$9,000 of Social Security: with $1,500 in an IRA the person passes
    SSI's $2,000 resource test and gets 12 x ($994 - ($750 - $20)) = $3,168;
    with $3,000 they get nothing."""
    zero = np.array([0.0])
    small = ENGINE.evaluate(
        _single_texan(social_security=9_000.0, traditional_balance=1_500.0), zero
    )
    large = ENGINE.evaluate(
        _single_texan(social_security=9_000.0, traditional_balance=3_000.0), zero
    )
    assert small.programs["ssi"][0] == pytest.approx(3_168.0, abs=DOLLAR)
    assert "ssi" not in large.programs


def test_snap_leaves_retirement_accounts_out_of_its_asset_test():
    """$9,000 of Social Security. $300,000 in an IRA leaves SNAP where $30,000
    does, while $300,000 of cash ends it. Both IRA balances exceed the
    Medicare Savings Program's resource limit (msp_asset_eligible reads
    ssi_countable_resources), so the $2,434.80 Part B premium it would pay
    falls on the person and enters SNAP's excess medical deduction
    (snap_allowable_medical_expenses adds medicare_part_b_premium, net of
    msp_part_b_premium_coverage)."""
    zero = np.array([0.0])

    def snap(cash: float = 0.0, **person) -> float:
        inputs = _single_texan(
            0.0, {"cash_savings": cash}, social_security=9_000.0, **person
        )
        return float(ENGINE.evaluate(inputs, zero).programs.get("snap", [0.0])[0])

    modest = snap(traditional_balance=30_000.0)
    assert modest > 0
    assert snap(traditional_balance=300_000.0) == pytest.approx(modest)
    assert snap(cash=300_000.0, traditional_balance=30_000.0) == 0.0


def test_small_snap_steps_and_its_end_are_placed_to_a_few_dollars():
    """$9,000 of Social Security, $50,000 in an IRA and $500 of cash. SNAP
    pays its minimum, $24 a month through September and $25 from October
    ($291 for the year), then falls by $216 near a draw of $16,800 and by
    its last $75 near $17,300. A $250 grid interval can lose up to $287.50
    to a phase-out at a dollar per dollar, so neither step stands out by
    size alone."""
    inputs = _single_texan(
        30_000.0,
        {"cash_savings": 500.0},
        social_security=9_000.0,
        traditional_balance=50_000.0,
    )
    result = run_us_drawdown_year(inputs, ENGINE)
    assert result.with_no_draw.benefits_by_program["snap"] > 0
    steps = [
        round(band.to_benefits * (band.draw_to - band.draw_from))
        for band in result.bands
        if band.draw_to - band.draw_from <= LOCATED
    ]
    assert 216 in steps and 75 in steps
    (end,) = [m for m in result.markers if m.program == "snap"]
    around = ENGINE.evaluate(inputs, np.array([end.draw - LOCATED, end.draw]))
    assert around.programs["snap"][0] > 0
    assert around.programs["snap"][1] == 0.0


def test_api_runs_the_calculator():
    client = TestClient(app)
    scenario = build_us_drawdown_year_scenario(_single_texan(40_000.0))
    response = client.post("/core/simulate", json=scenario.model_dump(mode="json"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engine"] == "us_drawdown_year"
    result = body["outputs"][OUTPUT_KEY]
    assert result["federal_income_tax"]["amount"] == pytest.approx(4_030.0, abs=DOLLAR)
    assert result["at_chosen_draw"]["taxable_social_security"] == pytest.approx(
        19_800.0, abs=DOLLAR
    )
    assert body["caveats"]


def test_api_rejects_a_draw_beyond_the_balance():
    client = TestClient(app)
    scenario = build_us_drawdown_year_scenario(_single_texan(40_000.0)).model_dump(
        mode="json"
    )
    scenario["inputs"]["draw_amount"] = 600_000.0
    response = client.post("/core/simulate", json=scenario)
    assert response.status_code == 422


def test_cli_prints_the_input_schema():
    printed = CliRunner().invoke(cli, ["core", "schema", "us-drawdown-input"])
    assert printed.exit_code == 0, printed.output
    schema = json.loads(printed.output)
    assert {"state", "you", "draw_source", "draw_amount"} <= set(schema["properties"])


class TestFrontendFixture:
    """The frontend's tests read recorded runs, which must match the engine."""

    @staticmethod
    def recorder():
        path = Path(__file__).parents[1] / "scripts" / "record_us_drawdown_fixture.py"
        spec = importlib.util.spec_from_file_location("record_us_fixture", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_recorded_runs_match_the_engine(self):
        recorder = self.recorder()
        recorded = json.loads(recorder.FIXTURE.read_text())
        assert set(recorded) == set(recorder.SCENARIOS)
        for name, run in recorder.record().items():
            saved = recorded[name]
            assert saved["inputs"] == run["inputs"], name
            fresh = run["envelope"]["outputs"][OUTPUT_KEY]
            old = saved["envelope"]["outputs"][OUTPUT_KEY]
            for field in (
                "sweep",
                "at_chosen_draw",
                "with_no_draw",
                "markers",
                "required_minimums",
                "medicare_surcharge",
                "coverage_with_no_draw",
                "coverage_at_chosen_draw",
            ):
                assert fresh[field] == old[field], f"{name}: {field}"
            assert [b["draw_from"] for b in fresh["bands"]] == [
                b["draw_from"] for b in old["bands"]
            ], name
            assert run["envelope"]["caveats"] == saved["envelope"]["caveats"], name
