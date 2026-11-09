"""The one-year US drawdown calculator, run on a stand-in engine.

The stand-in applies simple piecewise-linear rules shaped like the real ones:
Social Security taxed in two tiers, two income tax brackets, an SSI-like
benefit that falls a dollar per dollar of income, a SNAP-like benefit with a
cliff, on request a benefit that falls in two small steps, and Medicare
surcharges that step up at income lines. Its kinks and cliffs sit where the
rules put them, so tests can check that the calculator finds them.
``test_drawdown_us_policyengine.py`` runs the real engine.

Invariants held for every input:

- Each band and the next $1,000 split into kept, tax and benefits that add
  to 1.
- Money to spend equals income entered plus the draw, less taxes, plus
  benefits, at every point of the sweep.
- Bands tile the sweep, from nothing to its top, in order.
- The chosen and no-draw outcomes are points of the sweep, and the account
  left is the balance less the draw.
- Every marker lies inside the sweep.
- The same inputs give the same result.

And for the test that tells jumps from changes of rate, on any continuous
piecewise-linear series whose kinks sit apart and away from the ends:

- Changes of rate alone are never taken for jumps.
- A jump of $30 or more is found, and so are two side by side of $60 or more.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from pydantic import ValidationError

from eggnest.core.us_drawdown_year import (
    ENGINE_ID,
    OUTPUT_KEY,
    build_us_drawdown_year_result,
    build_us_drawdown_year_scenario,
    caveats_for,
    extract_us_drawdown_year_result,
)
from eggnest.drawdown_us import (
    NEXT_DRAW_STEP,
    _Evaluated,
    cash_income,
    cliff_intervals,
    run_us_drawdown_year,
    sweep_draws,
    taxable_draw,
)
from eggnest.models_us_drawdown import (
    USDrawdownYearInput,
    source_balance,
)
from eggnest.us_year_engine import USYearArrays

# Stand-in rules, single filer; a joint return doubles each line.
SS_FIRST_TIER = 25_000.0
SS_SECOND_TIER = 34_000.0
STANDARD_DEDUCTION = 18_000.0
BRACKET_TOP = 40_000.0
LOW_RATE = 0.10
HIGH_RATE = 0.22
STATE_RATE = 0.04
STATE_ALLOWANCE = 20_000.0
SSI_MAX = 11_928.0
SSI_DISREGARD = 240.0
SSI_RESOURCE_LIMIT = 2_000.0
SNAP_AMOUNT = 288.0
SNAP_LIMIT = 30_000.0
MEDICAID_LIMIT = 12_000.0
# Two steps smaller than the $287.50 a phase-out could take across a $250
# interval; with $24,000 of Social Security they sit in neighbouring
# intervals, at draws of $9,100 and $9,400.
FOOD_FIRST_STEP, FOOD_FIRST_LIMIT = 216.0, 33_100.0
FOOD_LAST_STEP, FOOD_LAST_LIMIT = 75.0, 33_400.0
MEDICARE_LINES = (109_001.0, 137_001.0)
PART_B_STEPS = (81.2 * 12, (202.9 - 81.2) * 12)
PART_D_STEPS = (14.5 * 12, (37.5 - 14.5) * 12)


class StandInEngine:
    """Piecewise-linear stand-ins for the taxes and benefits PolicyEngine-US runs."""

    name = "stand-in"

    def __init__(self, food_steps: bool = False) -> None:
        self.calls: list[np.ndarray] = []
        self.food_steps = food_steps

    def label(self) -> str:
        return "stand-in 1"

    def evaluate(self, inputs: USDrawdownYearInput, draws: np.ndarray) -> USYearArrays:
        draws = np.asarray(draws, dtype=float)
        self.calls.append(draws)
        scale = 2.0 if inputs.spouse is not None else 1.0
        people = [person for _, person in inputs.people]
        social_security = sum(p.social_security for p in people)
        ordinary = (
            sum(
                p.pension_income
                + p.government_pension_income
                + p.earnings
                + p.other_traditional_withdrawals
                + p.roth_conversion
                for p in people
            )
            + inputs.taxable_interest
            + inputs.dividends
            + taxable_draw(inputs, draws)
        )
        provisional = ordinary + inputs.tax_exempt_interest + 0.5 * social_security
        taxable_ss = np.minimum(
            0.5 * np.maximum(provisional - scale * SS_FIRST_TIER, 0.0)
            + 0.35 * np.maximum(provisional - scale * SS_SECOND_TIER, 0.0),
            0.85 * social_security,
        )
        agi = ordinary + taxable_ss
        taxable_income = np.maximum(agi - scale * STANDARD_DEDUCTION, 0.0)
        federal = LOW_RATE * taxable_income + (HIGH_RATE - LOW_RATE) * np.maximum(
            taxable_income - scale * BRACKET_TOP, 0.0
        )
        state = STATE_RATE * np.maximum(agi - scale * STATE_ALLOWANCE, 0.0)

        unearned = ordinary + social_security
        if inputs.draw_source == "roth":
            unearned = unearned + draws
        resources = (
            inputs.cash_savings
            + inputs.taxable_balance
            + sum(p.traditional_balance + p.roth_balance for p in people)
        )
        ssi = (
            np.maximum(SSI_MAX * scale - np.maximum(unearned - SSI_DISREGARD, 0.0), 0.0)
            if resources <= SSI_RESOURCE_LIMIT * scale
            else np.zeros(len(draws))
        )
        snap = np.where(unearned < SNAP_LIMIT * scale, SNAP_AMOUNT, 0.0)
        programs = {"ssi": ssi, "snap": snap}
        if self.food_steps:
            programs["food"] = np.where(
                unearned < FOOD_FIRST_LIMIT * scale, FOOD_FIRST_STEP, 0.0
            ) + np.where(unearned < FOOD_LAST_LIMIT * scale, FOOD_LAST_STEP, 0.0)
        benefits = sum(programs.values(), np.zeros(len(draws)))
        programs = {k: v for k, v in programs.items() if np.any(v > 0.005)}
        medicare_income = agi + inputs.tax_exempt_interest
        surcharge = np.zeros(len(draws))
        for line, part_b, part_d in zip(
            MEDICARE_LINES, PART_B_STEPS, PART_D_STEPS, strict=True
        ):
            surcharge += np.where(
                medicare_income >= line * scale, (part_b + part_d) * len(people), 0.0
            )
        return USYearArrays(
            federal_income_tax=federal,
            state_income_tax=state,
            other_taxes=np.zeros(len(draws)),
            benefits=benefits,
            programs=programs,
            taxable_social_security=taxable_ss,
            medicare_income=medicare_income,
            later_medicare_surcharge=surcharge,
            coverage={"medicaid": unearned < MEDICAID_LIMIT * scale},
            people_on_medicare=len(people),
            medicare_lines=[line * scale for line in MEDICARE_LINES],
            medicare_rates_year=2026,
        )


def _inputs(**overrides) -> USDrawdownYearInput:
    values = {
        "state": "TX",
        "you": {
            "birth_year": 1955,
            "social_security": 24_000.0,
            "traditional_balance": 600_000.0,
        },
        "draw_amount": 40_000.0,
    }
    values.update(overrides)
    return USDrawdownYearInput.model_validate(values)


def _run(inputs: USDrawdownYearInput):
    return run_us_drawdown_year(inputs, StandInEngine())


def _assert_invariants(inputs: USDrawdownYearInput, result) -> None:
    sweep = result.sweep
    draws = [point.draw for point in sweep]
    assert draws == sorted(set(draws))
    assert draws[0] == 0.0
    assert draws[-1] <= source_balance(inputs) + 0.005
    cash = cash_income(inputs)
    for point in sweep:
        taxes = point.federal_income_tax + point.state_income_tax + point.other_taxes
        assert point.money_to_spend == pytest.approx(
            cash + point.draw - taxes + point.benefits, abs=0.02
        )
    if draws[-1] == 0.0:
        assert result.bands == [] and result.next_1000 is None
        return
    slices = [*result.bands, *([result.next_1000] if result.next_1000 else [])]
    for piece in slices:
        assert piece.kept + piece.to_tax + piece.to_benefits == pytest.approx(
            1.0, abs=1e-9
        )
        assert piece.draw_to > piece.draw_from
    assert result.bands[0].draw_from == 0.0
    assert result.bands[-1].draw_to == pytest.approx(draws[-1], abs=0.005)
    for left, right in zip(result.bands, result.bands[1:], strict=False):
        assert left.draw_to == right.draw_from
    assert result.at_chosen_draw.draw == pytest.approx(inputs.draw_amount, abs=0.005)
    assert result.at_chosen_draw in sweep
    assert result.with_no_draw.draw == 0.0
    assert result.with_no_draw == sweep[0]
    assert result.money_to_spend == result.at_chosen_draw.money_to_spend
    assert result.account_left == pytest.approx(
        source_balance(inputs) - inputs.draw_amount, abs=0.005
    )
    for marker in result.markers:
        assert 0.0 <= marker.draw <= draws[-1] + 0.005


people = st.fixed_dictionaries(
    {
        "birth_year": st.integers(1930, 1961),
        "social_security": st.floats(0, 60_000),
        "pension_income": st.floats(0, 40_000),
        "earnings": st.sampled_from([0.0, 15_000.0]),
        "traditional_balance": st.floats(0, 2_000_000),
        "roth_balance": st.floats(0, 500_000),
        "other_traditional_withdrawals": st.sampled_from([0.0, 5_000.0]),
        "roth_conversion": st.sampled_from([0.0, 20_000.0]),
    }
)


@st.composite
def households(draw):
    joint = draw(st.booleans())
    values = {
        "state": draw(st.sampled_from(["TX", "CA", "NY", "WI", "DC"])),
        "filing_status": "married_filing_jointly" if joint else "single",
        "you": draw(people),
        "spouse": draw(people) if joint else None,
        "taxable_interest": draw(st.floats(0, 10_000)),
        "tax_exempt_interest": draw(st.floats(0, 10_000)),
        "dividends": draw(st.floats(0, 20_000)),
        "taxable_balance": draw(st.floats(0, 1_000_000)),
        "taxable_gain_share": draw(st.floats(0, 1)),
        "cash_savings": draw(st.floats(0, 100_000)),
        "draw_source": draw(
            st.sampled_from(["traditional", "roth", "taxable", "cash"])
        ),
        "draw_owner": draw(st.sampled_from(["you", "spouse"])) if joint else "you",
    }
    inputs = USDrawdownYearInput.model_validate({**values, "draw_amount": 0.0})
    share = draw(st.floats(0, 1))
    return USDrawdownYearInput.model_validate(
        {**values, "draw_amount": round(share * source_balance(inputs), 2)}
    )


@given(households())
def test_invariants_hold_for_any_household(inputs):
    _assert_invariants(inputs, _run(inputs))


@given(households())
def test_same_inputs_give_the_same_result(inputs):
    assert _run(inputs) == _run(inputs)


def test_two_engine_runs_per_request():
    engine = StandInEngine()
    run_us_drawdown_year(_inputs(), engine)
    assert len(engine.calls) == 2


def test_band_edges_land_on_the_kinks_of_piecewise_linear_rules():
    """Single, $24,000 Social Security, drawing d from a traditional IRA.

    Provisional income is d + $12,000, so Social Security starts to be taxed
    at d = $13,000, half a dollar per dollar, and the second tier starts at
    d = $22,000. AGI is 1.5d - 6,500 in the first tier, which passes the
    $18,000 deduction at d = $16,333.33 and the state's $20,000 allowance at
    d = $17,666.67. In the second tier AGI is 1.85d - 14,200: it reaches the
    $58,000 top of the 10% bracket at d = $39,027.03, and the taxable part of
    Social Security reaches its $20,400 cap at d = $40,705.88.
    """
    result = _run(_inputs(draw_amount=40_000.0))
    edges = {band.draw_from for band in result.bands}
    kinks = (13_000.0, 16_333.33, 17_666.67, 22_000.0, 39_027.03, 40_705.88)
    for kink in kinks:
        assert min(abs(edge - kink) for edge in edges) <= 0.02, kink


def test_bands_carry_the_rates_of_the_rules():
    result = _run(_inputs(draw_amount=40_000.0))
    bands = {round(b.draw_from): b for b in result.bands}
    # Inside the first tier, before any tax: all kept, half a dollar of
    # Social Security taxed per dollar.
    first_tier = bands[13_000]
    assert first_tier.kept == pytest.approx(1.0)
    assert first_tier.social_security_taxed == pytest.approx(0.5)
    # Second tier, 10% bracket, 4% state: (0.10 + 0.04) * 1.85 per dollar.
    second_tier = bands[22_000]
    assert second_tier.to_tax == pytest.approx(0.14 * 1.85, abs=1e-6)
    assert second_tier.social_security_taxed == pytest.approx(0.85)


def test_a_benefit_cliff_is_placed_to_a_few_dollars():
    """SNAP-like benefit ends once unearned income reaches $30,000.

    With $24,000 of Social Security and no other income, that's a draw of
    $6,000, inside the fine part of the grid ($250 steps), so the second run
    places it to $250 / 24.
    """
    inputs = _inputs(
        you={
            "birth_year": 1955,
            "social_security": 24_000.0,
            "traditional_balance": 600_000.0,
        },
        draw_amount=10_000.0,
    )
    result = _run(inputs)
    ends = [
        m for m in result.markers if m.kind == "benefit_ends" and m.program == "snap"
    ]
    assert len(ends) == 1
    assert 6_000.0 <= ends[0].draw <= 6_000.0 + 250.0 / 24 + 0.01
    cliff = next(b for b in result.bands if b.draw_from < 6_000.0 <= b.draw_to)
    assert cliff.draw_to - cliff.draw_from <= 250.0 / 24 + 0.01
    assert cliff.to_benefits * (cliff.draw_to - cliff.draw_from) == pytest.approx(
        SNAP_AMOUNT, abs=0.01
    )


def test_small_neighbouring_steps_are_placed_to_a_few_dollars():
    engine = StandInEngine(food_steps=True)
    result = run_us_drawdown_year(_inputs(draw_amount=20_000.0), engine)
    for at, size in ((9_100.0, FOOD_FIRST_STEP), (9_400.0, FOOD_LAST_STEP)):
        band = next(b for b in result.bands if b.draw_from < at <= b.draw_to)
        width = band.draw_to - band.draw_from
        assert width <= 250.0 / 24 + 0.01
        assert band.to_benefits * width == pytest.approx(size, abs=0.01)
    (end,) = [m for m in result.markers if m.program == "food"]
    assert 9_400.0 <= end.draw <= 9_400.0 + 250.0 / 24 + 0.01
    assert len(engine.calls) == 2


def _series(draws: np.ndarray, values: np.ndarray) -> _Evaluated:
    """A sweep in which one benefit is the whole story."""
    zeros = np.zeros(len(draws))
    return _Evaluated(
        draws=draws,
        taxable_draw=zeros,
        federal_income_tax=zeros,
        state_income_tax=zeros,
        other_taxes=zeros,
        benefits=values,
        taxable_social_security=zeros,
        medicare_income=zeros,
        later_medicare_surcharge=zeros,
        money_to_spend=zeros,
        programs={"benefit": values},
    )


@st.composite
def piecewise_linear(draw):
    """A continuous series on an even grid moving between -1 and 1 per dollar,
    with kinks at least four intervals apart and three clean intervals at
    either end."""
    count = draw(st.integers(12, 60))
    width = draw(st.floats(20, 1_000))
    rate = draw(st.floats(-1, 1))
    kinks: dict[int, tuple[float, float]] = {}
    at = draw(st.integers(3, 7))
    while at <= count - 4:
        kinks[at] = (draw(st.floats(0.01, 0.99)), draw(st.floats(-1, 1)))
        at += draw(st.integers(4, 12))
    values = [draw(st.floats(0, 10_000))]
    for i in range(count):
        share, after = kinks.get(i, (1.0, rate))
        values.append(values[-1] + width * (share * rate + (1 - share) * after))
        rate = after
    return np.arange(count + 1) * width, np.array(values), set(kinks)


def _jump(size) -> st.SearchStrategy[float]:
    return st.tuples(st.floats(size, 5_000), st.sampled_from([-1.0, 1.0])).map(
        lambda pair: pair[0] * pair[1]
    )


@given(piecewise_linear())
def test_changes_of_rate_alone_are_never_taken_for_jumps(series):
    draws, values, _ = series
    assert cliff_intervals(_series(draws, values)) == []


@given(piecewise_linear(), st.data())
def test_a_jump_is_found_however_small_beside_the_interval(series, data):
    draws, values, kinks = series
    clean = [i for i in range(1, len(draws) - 2) if not kinks & {i - 1, i, i + 1}]
    assume(clean)
    at = data.draw(st.sampled_from(clean))
    jumped = values + np.where(np.arange(len(values)) > at, data.draw(_jump(30)), 0.0)
    assert (draws[at], draws[at + 1]) in cliff_intervals(_series(draws, jumped))


@given(piecewise_linear(), st.data())
def test_neighbouring_jumps_are_both_found(series, data):
    draws, values, kinks = series
    clean = [
        i for i in range(1, len(draws) - 3) if not kinks & {i - 1, i, i + 1, i + 2}
    ]
    assume(clean)
    at = data.draw(st.sampled_from(clean))
    index = np.arange(len(values))
    jumped = (
        values
        + np.where(index > at, data.draw(_jump(60)), 0.0)
        + np.where(index > at + 1, data.draw(_jump(60)), 0.0)
    )
    found = cliff_intervals(_series(draws, jumped))
    assert (draws[at], draws[at + 1]) in found
    assert (draws[at + 1], draws[at + 2]) in found


def test_ssi_falls_a_dollar_per_dollar_drawn():
    """$4,000 Social Security and $1,900 in a traditional IRA, under the
    $2,000 resource limit: SSI is 11,928 - (4,000 - 240) = $8,168 and each
    dollar drawn takes a dollar of it. The IRA holds too little to end it."""
    inputs = _inputs(
        you={
            "birth_year": 1950,
            "social_security": 4_000.0,
            "traditional_balance": 1_900.0,
        },
        draw_amount=1_000.0,
    )
    result = _run(inputs)
    assert result.benefits_by_program_with_no_draw["ssi"] == pytest.approx(8_168.0)
    assert result.benefits_by_program["ssi"] == pytest.approx(7_168.0)
    assert result.next_1000.to_benefits == pytest.approx(1.0)
    assert result.next_1000.kept == pytest.approx(0.0, abs=1e-9)
    assert not [m for m in result.markers if m.program == "ssi"]


def test_medicare_steps_sit_where_income_crosses_each_line():
    """$24,000 Social Security, all of its taxable part ($20,400) taxed by
    then, so Medicare income is draw + 20,400 and crosses $109,001 at a draw
    of $88,601 and $137,001 at $116,601."""
    result = _run(_inputs(draw_amount=120_000.0))
    steps = [m for m in result.markers if m.kind == "medicare_surcharge_step"]
    assert [m.draw for m in steps] == pytest.approx([88_601.0, 116_601.0], abs=0.01)
    assert [m.amount for m in steps] == pytest.approx(
        [PART_B_STEPS[0] + PART_D_STEPS[0], PART_B_STEPS[1] + PART_D_STEPS[1]]
    )
    surcharge = result.medicare_surcharge
    assert surcharge.premium_year == 2028
    assert surcharge.rates_year == 2026
    assert surcharge.at_chosen_draw == pytest.approx(sum(m.amount for m in steps))
    assert surcharge.with_no_draw == 0.0


def test_required_minimum_is_marked_and_a_shortfall_is_costed():
    # Age 75 in 2026: Uniform Lifetime Table divisor 24.6.
    inputs = _inputs(
        you={
            "birth_year": 1951,
            "social_security": 24_000.0,
            "traditional_balance": 246_000.0,
        },
        draw_amount=4_000.0,
    )
    result = _run(inputs)
    (minimum,) = result.required_minimums
    assert minimum.divisor == 24.6
    assert minimum.amount == pytest.approx(10_000.0)
    assert minimum.shortfall == pytest.approx(6_000.0)
    assert minimum.excise_tax_on_shortfall == pytest.approx(1_500.0)
    marker = next(m for m in result.markers if m.kind == "required_minimum_reached")
    assert marker.draw == pytest.approx(10_000.0)
    assert marker.amount == pytest.approx(10_000.0)


def test_other_withdrawals_count_toward_the_required_minimum():
    inputs = _inputs(
        you={
            "birth_year": 1951,
            "social_security": 24_000.0,
            "traditional_balance": 246_000.0,
            "other_traditional_withdrawals": 3_000.0,
        },
        draw_amount=4_000.0,
    )
    result = _run(inputs)
    (minimum,) = result.required_minimums
    assert minimum.withdrawn == pytest.approx(7_000.0)
    marker = next(m for m in result.markers if m.kind == "required_minimum_reached")
    assert marker.draw == pytest.approx(7_000.0)


def test_no_required_minimum_before_73():
    result = _run(_inputs())  # 71 in 2026
    assert result.required_minimums == []
    assert not [m for m in result.markers if m.kind == "required_minimum_reached"]


def test_a_cash_draw_is_all_kept_and_changes_no_tax():
    inputs = _inputs(cash_savings=50_000.0, draw_source="cash", draw_amount=20_000.0)
    result = _run(inputs)
    assert result.at_chosen_draw.taxable_draw == 0.0
    assert [(b.kept, b.to_tax, b.to_benefits) for b in result.bands] == [
        (1.0, 0.0, 0.0)
    ]
    assert result.money_to_spend - result.with_no_draw.money_to_spend == pytest.approx(
        20_000.0
    )


def test_a_taxable_sale_counts_only_its_gain():
    inputs = _inputs(
        taxable_balance=200_000.0,
        taxable_gain_share=0.25,
        draw_source="taxable",
        draw_amount=40_000.0,
    )
    result = _run(inputs)
    assert result.at_chosen_draw.taxable_draw == pytest.approx(10_000.0)
    assert result.assumptions.taxable_gain_share_applied == 0.25


def test_coverage_end_is_marked():
    """Medicaid-like coverage ends once unearned income reaches $12,000."""
    inputs = _inputs(
        you={
            "birth_year": 1950,
            "social_security": 6_000.0,
            "traditional_balance": 50_000.0,
        },
        draw_amount=10_000.0,
    )
    result = _run(inputs)
    assert result.coverage_with_no_draw == {"medicaid": True}
    assert result.coverage_at_chosen_draw == {"medicaid": False}
    (marker,) = [m for m in result.markers if m.kind == "coverage_ends"]
    assert marker.program == "medicaid"
    assert 6_000.0 <= marker.draw <= 6_000.0 + 250.0 / 24 + 0.01


def test_next_1000_stops_at_the_end_of_the_account():
    inputs = _inputs(
        you={
            "birth_year": 1955,
            "social_security": 24_000.0,
            "traditional_balance": 40_500.0,
        },
        draw_amount=40_000.0,
    )
    result = _run(inputs)
    assert result.next_1000.draw_from == 40_000.0
    assert result.next_1000.draw_to == 40_500.0
    emptied = _run(inputs.model_copy(update={"draw_amount": 40_500.0}))
    assert emptied.next_1000 is None
    assert emptied.account_left == 0.0


def test_next_1000_is_the_next_thousand():
    result = _run(_inputs(draw_amount=30_000.0))
    assert result.next_1000.draw_to - result.next_1000.draw_from == NEXT_DRAW_STEP


def test_sweep_reaches_past_the_draw():
    inputs = _inputs(draw_amount=400_000.0)
    grid = sweep_draws(inputs)
    assert grid[-1] == pytest.approx(500_000.0)
    assert len(grid) <= 400 + 200


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"filing_status": "married_filing_jointly"}, "spouse"),
        (
            {"spouse": {"birth_year": 1955}},
            "Only a joint return",
        ),
        ({"draw_owner": "spouse"}, "spouse"),
        ({"draw_amount": 700_000.0}, "exceeds"),
        ({"state": "ZZ"}, "Unknown state"),
        ({"you": {"birth_year": 1962}}, "less than or equal"),
    ],
)
def test_inputs_are_checked(overrides, message):
    with pytest.raises(ValidationError, match=message):
        _inputs(**overrides)


def test_state_codes_are_normalized():
    assert _inputs(state=" ny ").state == "NY"


def test_envelope_round_trips_the_result():
    inputs = _inputs()
    result = _run(inputs)
    scenario = build_us_drawdown_year_scenario(inputs)
    assert scenario.engine == ENGINE_ID
    envelope = build_us_drawdown_year_result(scenario, inputs, result)
    assert extract_us_drawdown_year_result(envelope) == result
    assert OUTPUT_KEY in envelope.outputs
    assert envelope.citations
    assert envelope.caveats == caveats_for(inputs, result)


def test_caveats_follow_the_inputs():
    plain = caveats_for(_inputs(), _run(_inputs()))
    assert not [c for c in plain if "Roth" in c]
    assert not [c for c in plain if "required minimum" in c]
    older = _inputs(
        you={
            "birth_year": 1951,
            "social_security": 24_000.0,
            "traditional_balance": 246_000.0,
        },
        draw_amount=4_000.0,
    )
    caveats = caveats_for(older, _run(older))
    assert [c for c in caveats if "Uniform Lifetime Table" in c]
    assert [c for c in caveats if "excise tax" in c]
    roth = _inputs(
        you={"birth_year": 1955, "social_security": 24_000.0, "roth_balance": 50_000.0},
        draw_source="roth",
        draw_amount=10_000.0,
    )
    assert [c for c in caveats_for(roth, _run(roth)) if "408A" in c]
