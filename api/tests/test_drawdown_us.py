"""The one-year US drawdown calculator, run on a stand-in engine.

The stand-in applies simple piecewise-linear rules shaped like the real ones:
Social Security taxed in two tiers, two income tax brackets, an SSI-like
benefit that falls a dollar per dollar of income other than withdrawals from
the retirement accounts it counts as resources, a SNAP-like benefit with a
cliff, on request a benefit that falls in two small steps, and Medicare
surcharges that step up at income lines. Its kinks and cliffs sit where the
rules put them, so tests can check that the calculator finds them.
``test_drawdown_us_policyengine.py`` runs the real engine.

Invariants held for every input:

- Every amount of money comes in rounded to the cent, half a cent up, as the
  page's fields show it.
- Each band and the next $1,000 split into kept, tax and benefits that add
  to 1, however narrow the band.
- Money to spend equals income entered plus the draw, less taxes, plus
  benefits, at every point of the sweep.
- Bands tile the sweep, from nothing to its top, in order.
- A required minimum's excise tax is 25% of its shortfall, except in the
  first year a minimum is due (age 73 in 2026), when it is nothing.
- The chosen and no-draw outcomes are points of the sweep, and the account
  left is what the source holds for the draw, less the draw. For a
  traditional draw that is the owner's balance less their other traditional
  withdrawals and Roth conversion, which come out of the same accounts and
  together never exceed that balance (inputs where they do are refused).
- Every marker lies inside the sweep.
- Each Medicare marker sits where Medicare income reaches its line and
  carries that line's step alone, so the steps add up to the surcharge at the
  top of the sweep (tested on a stand-in with Medicare's five lines).
- The same inputs give the same result.

For the grid's test for intervals that may hold a jump (cliff_intervals), on
a continuous piecewise-linear series on an even grid, moving at most a dollar
per dollar, with kinks four or more intervals apart and away from the ends:

- Changes of rate alone are never flagged.
- A jump of $30 or more is flagged when no kink sits in its interval or the
  ones either side, and so are two side by side of $60 or more.

For a whole run, on a stand-in whose benefit is such a series in the draw
(the sweep steps $250 to $40,000 and $1,000 above), with kinks four or more
grid intervals apart:

- Changes of rate alone give no jump band, and each change of 5 cents a
  dollar or more lands on a band edge within $1 plus $1 divided by the change
  ($3.50 for 40 cents, $21 for 5 cents). An edge goes to an evaluated draw
  within $1 of where the lines on either side cross, and a change too small
  for the bands to notice can tilt one of those lines, but they cross close
  enough that the band's line misses the series at the change by less than
  $1.
- A jump of $30 or more gets the one jump band, holding it and no wider than
  1/24 of its grid interval, wherever it sits; within 1/12 of an interval of
  a kink it must exceed $25 plus the kink's change of rate times 1/24 of the
  interval. A smaller one there may be missed or have its band put on the
  neighbouring 24th; no jump band lies further from a jump.
- Worked cases from the review: a kink keeps its own edge beside a jump or a
  change of coverage in its interval or the next, kinks a $50,000 grid can't
  separate get their own edges, and a cliff where a phase-out ends is found.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from pydantic import ValidationError

from eggnest.citations import citations_for_keys
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
from eggnest.us_year_engine import USYearArrays, build_situation

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
        # SSI counts retirement balances as resources, so withdrawals from
        # them are not its income; SNAP and Medicaid here count them.
        withdrawals = sum(p.other_traditional_withdrawals for p in people) + (
            draws if inputs.draw_source in ("traditional", "roth") else 0.0
        )
        ssi_unearned = unearned - withdrawals
        resources = (
            inputs.cash_savings
            + inputs.taxable_balance
            + sum(p.traditional_balance + p.roth_balance for p in people)
        )
        ssi = (
            np.maximum(
                SSI_MAX * scale - np.maximum(ssi_unearned - SSI_DISREGARD, 0.0), 0.0
            )
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
    programs = sweep[0].benefits_by_program.keys()
    for point in sweep:
        taxes = point.federal_income_tax + point.state_income_tax + point.other_taxes
        assert point.money_to_spend == pytest.approx(
            cash + point.draw - taxes + point.benefits, abs=0.02
        )
        # Every outcome lists the same programs, and they make up the benefits.
        assert point.benefits_by_program.keys() == programs
        assert sum(point.benefits_by_program.values()) == pytest.approx(
            point.benefits, abs=0.005 * (len(programs) + 1)
        )
    for minimum in result.required_minimums:
        draws_here = (
            inputs.draw_source == "traditional" and inputs.draw_owner == minimum.person
        )
        assert minimum.withdrawn == pytest.approx(
            minimum.other_withdrawals + (inputs.draw_amount if draws_here else 0.0),
            abs=0.01,
        )
        assert minimum.shortfall == pytest.approx(
            max(minimum.amount - minimum.withdrawn, 0.0), abs=0.01
        )
        # No excise tax attaches to a shortfall in the first year, when the
        # minimum can wait until April 1 of the next year.
        rate = 0.0 if minimum.first_year else minimum.excise_tax_rate
        assert minimum.excise_tax_on_shortfall == pytest.approx(
            rate * minimum.shortfall, abs=0.01
        )
        assert minimum.first_year == (minimum.age == 73)
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
    if inputs.draw_source == "traditional":
        owner = inputs.person(inputs.draw_owner)
        assert source_balance(inputs) == max(
            owner.traditional_balance
            - owner.other_traditional_withdrawals
            - owner.roth_conversion,
            0.0,
        )
    for marker in result.markers:
        assert 0.0 <= marker.draw <= draws[-1] + 0.005


@st.composite
def people(draw):
    person = draw(
        st.fixed_dictionaries(
            {
                "birth_year": st.integers(1930, 1961),
                "social_security": st.floats(0, 60_000),
                "pension_income": st.floats(0, 40_000),
                "earnings": st.sampled_from([0.0, 15_000.0]),
                "roth_balance": st.floats(0, 500_000),
                "other_traditional_withdrawals": st.sampled_from([0.0, 5_000.0]),
                "other_withdrawals_account": st.sampled_from(["ira", "workplace_plan"]),
                "roth_conversion": st.sampled_from([0.0, 20_000.0]),
            }
        )
    )
    # Withdrawals and conversions come out of the traditional balance, so it
    # holds at least what they take.
    taken = person["other_traditional_withdrawals"] + person["roth_conversion"]
    person["traditional_balance"] = taken + draw(st.floats(0, 2_000_000))
    return person


@st.composite
def households(draw):
    joint = draw(st.booleans())
    values = {
        "state": draw(st.sampled_from(["TX", "CA", "NY", "WI", "DC"])),
        "filing_status": "married_filing_jointly" if joint else "single",
        "you": draw(people()),
        "spouse": draw(people()) if joint else None,
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
        "draw_account": draw(st.sampled_from(["ira", "workplace_plan"])),
    }
    inputs = USDrawdownYearInput.model_validate({**values, "draw_amount": 0.0})
    share = draw(st.floats(0, 1))
    return USDrawdownYearInput.model_validate(
        # Whole cents, rounded down so the draw stays within the balance.
        {**values, "draw_amount": np.floor(share * source_balance(inputs) * 100) / 100}
    )


@given(households())
def test_invariants_hold_for_any_household(inputs):
    _assert_invariants(inputs, _run(inputs))


@given(households(), st.floats(0, 1))
def test_each_traditional_withdrawal_reaches_its_account_kind(inputs, share):
    """Every traditional dollar reaches PolicyEngine-US once, as an IRA
    distribution or a workplace plan (401(k)) distribution by the kind of
    account it comes from; nothing else does."""
    draw = round(share * source_balance(inputs), 2)
    situation = build_situation(inputs, np.array([draw]))
    year = str(inputs.tax_year)
    for who, person in inputs.people:
        values = situation["people"][f"{who}_0"]
        expected = {"ira": 0.0, "workplace_plan": 0.0}
        expected[
            person.other_withdrawals_account
        ] += person.other_traditional_withdrawals
        if inputs.draw_source == "traditional" and inputs.draw_owner == who:
            expected[inputs.draw_account] += draw
        assert values["taxable_ira_distributions"][year] == pytest.approx(
            expected["ira"]
        )
        assert values["taxable_401k_distributions"][year] == pytest.approx(
            expected["workplace_plan"]
        )


_HOUSEHOLD_INCOME = {
    "taxable_interest_income": "taxable_interest",
    "tax_exempt_interest_income": "tax_exempt_interest",
    "qualified_dividend_income": "dividends",
}


@given(households(), st.floats(0, 1))
def test_a_couple_splits_household_income_evenly(inputs, share):
    """Interest, dividends and the gain on investments sold belong to the
    couple, as from jointly held accounts: each spouse gets half, so each
    spouse's own state exclusions apply. A single filer gets all of it."""
    draw = round(share * source_balance(inputs), 2)
    situation = build_situation(inputs, np.array([draw]))
    year = str(inputs.tax_year)
    people = [situation["people"][f"{who}_0"] for who, _ in inputs.people]
    gain = draw * inputs.taxable_gain_share if inputs.draw_source == "taxable" else 0.0
    totals = {
        **{
            variable: getattr(inputs, field)
            for variable, field in _HOUSEHOLD_INCOME.items()
        },
        "long_term_capital_gains": gain,
    }
    for variable, total in totals.items():
        for person in people:
            assert person[variable][year] == pytest.approx(total / len(people))


def test_a_workplace_plan_draw_reaches_taxable_401k_distributions():
    inputs = _inputs(
        you={
            "birth_year": 1956,
            "social_security": 24_000.0,
            "traditional_balance": 300_000.0,
            "other_traditional_withdrawals": 5_000.0,
        },
        draw_account="workplace_plan",
        draw_amount=20_000.0,
    )
    (person,) = build_situation(inputs, np.array([20_000.0]))["people"].values()
    assert person["taxable_401k_distributions"]["2026"] == 20_000.0
    assert person["taxable_ira_distributions"]["2026"] == 5_000.0
    assert _inputs().draw_account == "ira"


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


class FunctionEngine:
    """A stand-in whose federal tax, benefits and coverage are plain functions
    of the draw, so a test can put a kink and a jump wherever it likes."""

    name = "functions"

    def __init__(self, tax=None, programs=None, coverage=None) -> None:
        self.tax = tax or (lambda d: np.zeros(len(d)))
        self.programs = programs or {}
        self.coverage = coverage or {}
        self.calls: list[np.ndarray] = []

    def label(self) -> str:
        return "functions 1"

    def evaluate(self, inputs: USDrawdownYearInput, draws: np.ndarray) -> USYearArrays:
        draws = np.asarray(draws, dtype=float)
        self.calls.append(draws)
        zeros = np.zeros(len(draws))
        programs = {name: f(draws) for name, f in self.programs.items()}
        return USYearArrays(
            federal_income_tax=self.tax(draws),
            state_income_tax=zeros,
            other_taxes=zeros,
            benefits=sum(programs.values(), zeros),
            programs=programs,
            taxable_social_security=zeros,
            medicare_income=draws,
            later_medicare_surcharge=zeros,
            coverage={name: f(draws) for name, f in self.coverage.items()},
            people_on_medicare=1,
            medicare_lines=[],
            medicare_rates_year=2026,
        )


def _function_run(engine: FunctionEngine, balance=600_000.0, draw=40_000.0):
    """A traditional draw, so the sweep steps $250 to $40,000 and $1,000 above
    for a $600,000 balance (and $50,000 for $12m)."""
    inputs = _inputs(
        you={"birth_year": 1955, "traditional_balance": balance}, draw_amount=draw
    )
    result = run_us_drawdown_year(inputs, engine)
    _assert_invariants(inputs, result)
    return result


def _edge_near(result, draw: float) -> float:
    edges = [band.draw_from for band in result.bands] + [result.bands[-1].draw_to]
    return min(edges, key=lambda edge: abs(edge - draw))


def _band_at(result, draw: float):
    return next(b for b in result.bands if b.draw_from < draw <= b.draw_to)


@pytest.mark.parametrize(
    ("kink", "coverage_ends"),
    [(30_200.0, 30_100.0), (100_700.0, 100_200.0)],
)
def test_a_change_of_coverage_leaves_the_kink_in_its_interval_on_its_edge(
    kink, coverage_ends
):
    """us-jumps-1: tax of 20% from the kink; Medicaid ends earlier in the same
    grid interval ($250 wide, then $1,000). A change of coverage moves no
    money, so the kink keeps its edge."""
    engine = FunctionEngine(
        tax=lambda d: 0.2 * np.maximum(d - kink, 0.0),
        coverage={"medicaid": lambda d: d < coverage_ends},
    )
    result = _function_run(engine)
    assert _edge_near(result, kink) == pytest.approx(kink, abs=0.01)
    assert _band_at(result, kink).to_tax == pytest.approx(0.0, abs=1e-6)
    assert _band_at(result, kink + 1.0).to_tax == pytest.approx(0.2, abs=1e-6)
    assert not any(band.jump for band in result.bands)


def test_a_jump_leaves_a_kink_in_its_interval_on_its_edge():
    """us-jumps-1 with money: a benefit of $300 ends at a draw of $100,200 and
    tax of 20% starts at $100,700, both in the grid interval from $100,000 to
    $101,000. The jump gets a band of its own and the kink keeps its edge."""
    engine = FunctionEngine(
        tax=lambda d: 0.2 * np.maximum(d - 100_700.0, 0.0),
        programs={"snap": lambda d: np.where(d < 100_200.0, 300.0, 0.0)},
    )
    result = _function_run(engine)
    assert _edge_near(result, 100_700.0) == pytest.approx(100_700.0, abs=0.01)
    (jump,) = [band for band in result.bands if band.jump]
    assert jump.draw_from < 100_200.0 <= jump.draw_to
    assert jump.draw_to - jump.draw_from <= 1_000.0 / 24 + 0.01
    assert jump.to_benefits * (jump.draw_to - jump.draw_from) == pytest.approx(300.0)


@pytest.mark.parametrize(
    ("kink", "cliff"),
    [
        (30_000.0, 30_400.0),
        (60_000.0, 61_500.0),
        (60_300.0, 61_500.0),
        (61_500.0, 60_500.0),
    ],
)
def test_a_kink_beside_a_jump_keeps_its_own_edge(kink, cliff):
    """us-jumps-7: a benefit falls half a dollar per dollar until it ends at
    the kink, and tax jumps by $200 at the cliff, in the grid interval next to
    the kink's (or the kink's own). The band before the kink loses half of
    each dollar to benefits; the one after loses nothing."""
    engine = FunctionEngine(
        tax=lambda d: np.where(d >= cliff, 200.0, 0.0),
        programs={"snap": lambda d: 0.5 * np.maximum(kink - d, 0.0)},
    )
    result = _function_run(engine)
    assert _edge_near(result, kink) == pytest.approx(kink, abs=0.01)
    assert _band_at(result, kink).to_benefits == pytest.approx(0.5, abs=1e-6)
    after = _band_at(result, kink + 1.0)
    assert after.jump or after.to_benefits == pytest.approx(0.0, abs=1e-6)
    (jump,) = [band for band in result.bands if band.jump]
    assert jump.draw_from < cliff <= jump.draw_to
    assert jump.to_tax * (jump.draw_to - jump.draw_from) == pytest.approx(200.0)


def test_close_kinks_on_a_coarse_grid_get_their_own_edges():
    """us-jumps-8: drawing up to $10m of a $12m balance steps the grid
    $50,000. Federal-style rates of 22% to $149,500, 22.56% to $194,000, 32%
    to $249,000, 35% to $633,250 and 37% after: each change gets its edge,
    and each band its rate."""
    knots = [
        (0.0, 0.22),
        (149_500.0, 0.2256),
        (194_000.0, 0.32),
        (249_000.0, 0.35),
        (633_250.0, 0.37),
    ]

    def tax(d):
        total = np.zeros(len(d))
        for (start, rate), (stop, _) in zip(
            knots, [*knots[1:], (np.inf, 0.0)], strict=True
        ):
            total += rate * np.clip(d - start, 0.0, stop - start)
        return total

    result = _function_run(
        FunctionEngine(tax=tax), balance=12_000_000.0, draw=10_000_000.0
    )
    for start, rate in knots[1:]:
        assert _edge_near(result, start) == pytest.approx(start, abs=0.01)
        assert _band_at(result, start + 1.0).to_tax == pytest.approx(rate, abs=1e-6)


@pytest.mark.parametrize("cliff", [60_020.0, 60_500.0, 60_980.0])
@pytest.mark.parametrize("size", [50.0, 100.0])
def test_a_cliff_where_a_phase_out_ends_is_located(cliff, size):
    """us-jumps-2: a benefit of $700 falls 30 cents per dollar to `size`, then
    drops to nothing at the cliff, inside a $1,000 interval of the grid. From
    the grid alone that looks like a phase-out that runs to zero; the
    interval where the benefit reaches zero gets a closer look."""
    start = cliff - (700.0 - size) / 0.3
    engine = FunctionEngine(
        programs={
            "snap": lambda d: np.where(
                d < start, 700.0, np.where(d < cliff, 700.0 - 0.3 * (d - start), 0.0)
            )
        }
    )
    result = _function_run(engine)
    (jump,) = [band for band in result.bands if band.jump]
    width = jump.draw_to - jump.draw_from
    assert jump.draw_from < cliff <= jump.draw_to
    assert width <= 1_000.0 / 24 + 0.01
    assert jump.to_benefits * width == pytest.approx(
        size + 0.3 * (cliff - jump.draw_from), abs=0.01
    )
    (end,) = [m for m in result.markers if m.kind == "benefit_ends"]
    assert cliff <= end.draw <= cliff + 1_000.0 / 24 + 0.01
    # The phase-out's own band, its start rounded to the cent.
    assert _band_at(result, cliff - width - 1.0).to_benefits == pytest.approx(
        0.3, abs=1e-5
    )


def test_a_jump_where_a_phase_out_flattens_is_located():
    """us-words-2: a benefit falls a dollar per dollar to a draw of $2,625,
    the middle of the grid interval from $2,500 to $2,750, then runs flat; it
    also drops $30 there. The grid sees what a phase-out ending a little later
    would give; the interval holding the change of rate gets a closer look."""
    engine = FunctionEngine(
        programs={
            "ssi": lambda d: 10_000.0
            - np.minimum(d, 2_625.0)
            - np.where(d >= 2_625.0, 30.0, 0.0)
        }
    )
    result = _function_run(engine)
    (jump,) = [band for band in result.bands if band.jump]
    assert jump.draw_from < 2_625.0 <= jump.draw_to
    assert jump.draw_to - jump.draw_from <= 250.0 / 24 + 0.01


# The grid _function_run sweeps: $250 steps to $40,000, $1,000 steps to
# $250,000.
def _grid_step(draw: float) -> float:
    return 250.0 if draw <= 40_000.0 else 1_000.0


@st.composite
def kinked_benefit(draw):
    """A benefit continuous and piecewise linear in the draw, falling or
    rising at most a dollar per dollar, with changes of rate at least four
    grid intervals apart."""
    kinks: list[float] = []
    at = draw(st.floats(500.0, 3_000.0))
    while at < 240_000.0:
        kinks.append(round(at, 2))
        at += draw(st.floats(4.0, 40.0)) * _grid_step(at) + _grid_step(at)
    rates = [draw(st.floats(-1.0, 1.0)) for _ in range(len(kinks) + 1)]
    return kinks, rates


def _piecewise(kinks: list[float], rates: list[float]):
    edges = np.array([0.0, *kinks])
    widths = np.diff(np.array([*edges, np.inf]))

    def values(d):
        pieces = np.clip(np.asarray(d)[:, None] - edges, 0.0, widths)
        return 300_000.0 + pieces @ np.asarray(rates)

    return values


def _rate_change_near(kinks, rates, draw: float, reach: float) -> float:
    return max(
        (
            abs(after - before)
            for kink, before, after in zip(kinks, rates, rates[1:], strict=False)
            if abs(kink - draw) <= reach
        ),
        default=0.0,
    )


def _assert_changes_land_on_edges(kinks, rates, result) -> None:
    """No jump band, and each change of 5 cents a dollar or more has a band
    edge within $1 plus $1 divided by the change: an edge goes to an evaluated
    draw within $1 of where the lines on either side cross, and they cross
    close enough that the band's line misses the series at the change by
    less than $1."""
    assert not any(band.jump for band in result.bands)
    edges = np.array([band.draw_from for band in result.bands])
    for kink, before, after in zip(kinks, rates, rates[1:], strict=False):
        change = abs(after - before)
        if change >= 0.05:
            assert np.min(np.abs(edges - kink)) <= 1.0 + 1.0 / change, kink


@given(kinked_benefit())
def test_a_run_takes_no_change_of_rate_for_a_jump(rules):
    """Over the whole run, with its closer looks inside intervals, changes of
    rate alone give no jump band, and each change of 5 cents a dollar or more
    lands on an edge within $1 plus $1 divided by the change. (A smaller one
    can stay within the $15 a benefit's line may stray before the bands notice
    it, and can tilt the line beside a larger one.)"""
    kinks, rates = rules
    result = _function_run(FunctionEngine(programs={"ssi": _piecewise(kinks, rates)}))
    _assert_changes_land_on_edges(kinks, rates, result)


@pytest.mark.parametrize(
    ("kinks", "rates", "kink"),
    [
        pytest.param(
            [6_062.5, 7_367.19, 11_367.19, 29_867.19, 40_117.19],
            [0.0, 0.40625, 0.00390625, 0.0, 1.0, 0.0],
            7_367.19,
            id="edge-moves-to-a-draw",
        ),
        pytest.param(
            [11_000.0, 16_500.0, 17_880.0, 20_360.0],
            [0.0, 0.10, 0.11, 0.20, 0.0],
            17_880.0,
            id="small-change-tilts-a-line",
        ),
    ],
)
def test_a_change_of_rate_lands_within_its_dollar_and_stray(kinks, rates, kink):
    """us-edge, from test_a_run_takes_no_change_of_rate_for_a_jump under the
    thorough profile (seed 11). Each change lands on an edge within $1 of where
    the lines on either side cross, which strays less than $1 from the series.

    - A benefit rises 40.6 cents a dollar from 6,062.50 to 7,367.19, then 0.4
      cents to 11,367.19, then not at all until it rises a dollar a dollar
      from 29,867.19 to 40,117.19. Between 7,367.19 and 29,867.19 the 0.4-cent
      change stays within the $15 a benefit's line may stray. The lines cross
      at 7,367.25, but the first run's edge at 7,368.24 was evaluated, within
      $1, so the edge goes there with no third run: $1.05 from the change,
      which the band's line misses by 42 cents.
    - A benefit rises 10 cents a dollar from 11,000, 11 cents from 16,500 and
      20 cents from 17,880. The 1-cent change stays within the $15 a benefit's
      line may stray, so the line before 17,880 runs from 11,000 at 10.2 cents
      and crosses the next at 17,878.74: $1.26 from the change, missed by 11
      cents.
    """
    result = _function_run(FunctionEngine(programs={"ssi": _piecewise(kinks, rates)}))
    _assert_changes_land_on_edges(kinks, rates, result)
    edge = _edge_near(result, kink)
    change = rates[kinks.index(kink) + 1] - rates[kinks.index(kink)]
    assert abs(edge - kink) * abs(change) < 1.0
    assert edge in {row.draw for row in result.sweep}


@given(kinked_benefit(), st.data(), st.floats(5.0, 2_000.0), st.booleans())
def test_a_run_locates_a_jump_wherever_it_sits(rules, data, size, falls):
    """A jump of $30 or more gets the one jump band, no wider than 1/24 of its
    grid interval, wherever it sits. Within 1/12 of an interval of a change of
    rate it needs to exceed $25 plus that change times 1/24 of the interval:
    a smaller one there moves its piece no further than a change of rate
    could, so it may be missed, or its band may go to the neighbouring 24th.
    No jump band ever lies further from a jump."""
    kinks, rates = rules
    if data.draw(st.booleans()):
        at = data.draw(st.floats(500.0, 240_000.0))
    else:  # Beside a change of rate, or on it.
        kink = data.draw(st.sampled_from(kinks))
        at = kink + data.draw(st.floats(-3.0, 3.0)) * _grid_step(kink) / 24
    at = round(at, 2)
    piece = _grid_step(at) / 24
    change = _rate_change_near(kinks, rates, at, 2 * piece)
    jump = -size if falls else size
    base = _piecewise(kinks, rates)
    engine = FunctionEngine(
        programs={"ssi": lambda d: base(d) + np.where(d >= at, jump, 0.0)}
    )
    result = _function_run(engine)
    located = [band for band in result.bands if band.jump]
    for band in located:
        assert band.draw_from - 2 * piece <= at <= band.draw_to + 2 * piece
    if size < 30.0 or size <= 25.0 + change * piece + 0.5:
        return
    (band,) = located
    width = band.draw_to - band.draw_from
    assert band.draw_from < at <= band.draw_to
    assert width <= piece + 0.01
    moved = -band.to_benefits * width
    assert abs(moved - jump) <= width + 0.01  # The jump plus at most $1 a dollar.


def test_ssi_keeps_paying_through_a_draw_from_a_counted_account():
    """$4,000 Social Security and $1,900 in a traditional IRA, under the
    $2,000 resource limit: SSI is 11,928 - (4,000 - 240) = $8,168. The IRA
    counts as a resource, so drawing it is a change of form, not income
    (20 CFR 416.1103(c)): SSI stays at $8,168 and the household keeps each
    dollar. A pension, which is income, still takes a dollar per dollar."""
    inputs = _inputs(
        you={
            "birth_year": 1950,
            "social_security": 4_000.0,
            "traditional_balance": 1_900.0,
        },
        draw_amount=1_000.0,
    )
    result = _run(inputs)
    assert result.with_no_draw.benefits_by_program["ssi"] == pytest.approx(8_168.0)
    assert result.at_chosen_draw.benefits_by_program["ssi"] == pytest.approx(8_168.0)
    assert result.next_1000.to_benefits == pytest.approx(0.0, abs=1e-9)
    assert result.next_1000.kept == pytest.approx(1.0)
    assert not [m for m in result.markers if m.program == "ssi"]
    pension = _run(
        inputs.model_copy(
            update={"you": inputs.you.model_copy(update={"pension_income": 1_000.0})}
        )
    )
    assert pension.with_no_draw.benefits_by_program["ssi"] == pytest.approx(7_168.0)


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


# Medicare's five 2026 lines for a single filer, and the Part B plus Part D
# amount a month above each, from PolicyEngine-US's IRMAA tables.
CMS_LINES = (109_001.0, 137_001.0, 171_001.0, 205_001.0, 500_000.0)
CMS_MONTHLY = (0.0, 95.7, 240.4, 385.0, 529.6, 578.0)


class FiveLineEngine(StandInEngine):
    """The stand-in with Medicare's five lines. Two of them, $34,000 of income
    apart, can fall in one $50,000 interval of the sweep, between steps at the
    lines on either side that make the surcharge rise much like a ramp."""

    def evaluate(self, inputs: USDrawdownYearInput, draws: np.ndarray) -> USYearArrays:
        arrays = super().evaluate(inputs, draws)
        scale = 2.0 if inputs.spouse is not None else 1.0
        lines = np.array(CMS_LINES) * scale
        tier = np.searchsorted(lines, arrays.medicare_income, side="right")
        arrays.later_medicare_surcharge = (
            12.0 * np.array(CMS_MONTHLY)[tier] * arrays.people_on_medicare
        )
        arrays.medicare_lines = [float(line) for line in lines]
        return arrays


def _medicare_steps(result) -> list[tuple[float, float]]:
    return [
        (marker.draw, marker.amount)
        for marker in result.markers
        if marker.kind == "medicare_surcharge_step"
    ]


def test_two_medicare_lines_in_one_interval_keep_their_own_steps():
    """A $20,000 pension makes Medicare income the draw plus $20,000, so it
    crosses $171,001 at a draw of $151,001 and $205,001 at $185,001, both in
    the sweep's interval from $150,000 to $200,000. Each marker carries its
    own line's step, $1,735.20 a year, not the two together."""
    inputs = _inputs(
        you={
            "birth_year": 1950,
            "pension_income": 20_000.0,
            "traditional_balance": 12_000_000.0,
        },
        draw_amount=10_000_000.0,
    )
    result = run_us_drawdown_year(inputs, FiveLineEngine())
    expected = [12.0 * (high - low) for low, high in itertools.pairwise(CMS_MONTHLY)]
    steps = _medicare_steps(result)
    assert [draw for draw, _ in steps] == pytest.approx(
        [line - 20_000.0 for line in CMS_LINES], abs=0.01
    )
    assert [amount for _, amount in steps] == pytest.approx(expected)
    assert sum(amount for _, amount in steps) == pytest.approx(
        result.medicare_surcharge.at_chosen_draw
    )


@given(
    pension=st.floats(0.0, 60_000.0),
    social_security=st.sampled_from([0.0, 30_000.0, 60_000.0]),
    joint=st.booleans(),
    balance=st.sampled_from([1_000_000.0, 4_000_000.0, 12_000_000.0, 30_000_000.0]),
)
def test_each_medicare_marker_carries_its_own_lines_step(
    pension, social_security, joint, balance
):
    """However the lines fall in the sweep, each marker sits where Medicare
    income reaches its line and carries that line's step alone, so the steps
    add up to the surcharge at the top of the sweep."""
    person = {
        "birth_year": 1952,
        "social_security": social_security,
        "pension_income": pension,
        "traditional_balance": balance,
    }
    joint_fields = (
        {"filing_status": "married_filing_jointly", "spouse": {"birth_year": 1953}}
        if joint
        else {}
    )
    inputs = _inputs(you=person, draw_amount=balance, **joint_fields)
    engine = FiveLineEngine()
    result = run_us_drawdown_year(inputs, engine)
    scale = 2.0 if joint else 1.0
    people = 2 if joint else 1
    lines = [line * scale for line in CMS_LINES]
    no_draw = result.with_no_draw.medicare_income
    top = result.sweep[-1].medicare_income
    crossed = [i for i, line in enumerate(lines) if no_draw < line <= top]
    steps = _medicare_steps(result)
    assert [amount for _, amount in steps] == pytest.approx(
        [12.0 * people * (CMS_MONTHLY[i + 1] - CMS_MONTHLY[i]) for i in crossed]
    )
    incomes = engine.evaluate(inputs, np.array([draw for draw, _ in steps]))
    assert incomes.medicare_income == pytest.approx(
        [lines[i] for i in crossed], abs=1.0
    )
    assert sum(amount for _, amount in steps) == pytest.approx(
        result.sweep[-1].later_medicare_surcharge
        - result.with_no_draw.later_medicare_surcharge
    )


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
    assert minimum.other_withdrawals == 0.0
    assert minimum.shortfall == pytest.approx(6_000.0)
    assert minimum.excise_tax_rate == 0.25
    assert minimum.excise_tax_on_shortfall == pytest.approx(1_500.0)
    marker = next(m for m in result.markers if m.kind == "required_minimum_reached")
    assert marker.draw == pytest.approx(10_000.0)
    assert marker.amount == pytest.approx(10_000.0)


def test_the_first_required_minimum_can_wait_until_april_1():
    """Born 1953, 73 at the end of 2026: 2026 is the first year a minimum is
    due, and it can wait until the required beginning date, April 1, 2027
    (26 USC 401(a)(9)(C)). No excise tax attaches to a 2026 shortfall; the
    tax for that minimum is measured in 2027 (26 CFR 54.4974-1(f)). Born 1952,
    74, the minimum is due by December 31, 2026."""
    first = _run(
        _inputs(
            you={
                "birth_year": 1953,
                "social_security": 24_000.0,
                "traditional_balance": 265_000.0,
            },
            draw_amount=0.0,
        )
    )
    (minimum,) = first.required_minimums
    assert minimum.first_year
    assert minimum.due_by.isoformat() == "2027-04-01"
    assert minimum.amount == pytest.approx(10_000.0)  # 265,000 / 26.5
    assert minimum.shortfall == pytest.approx(10_000.0)
    assert minimum.excise_tax_on_shortfall == 0.0
    later = _run(
        _inputs(
            you={
                "birth_year": 1952,
                "social_security": 24_000.0,
                "traditional_balance": 255_000.0,
            },
            draw_amount=0.0,
        )
    )
    (minimum,) = later.required_minimums
    assert not minimum.first_year
    assert minimum.due_by.isoformat() == "2026-12-31"
    assert minimum.excise_tax_on_shortfall == pytest.approx(2_500.0)


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
    assert minimum.other_withdrawals == pytest.approx(3_000.0)
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


def test_other_withdrawals_and_conversions_come_out_of_the_traditional_balance():
    """$50,000 in traditional accounts, $20,000 of other withdrawals and a
    $20,000 Roth conversion leave $10,000 to draw: a $5,000 draw leaves
    $5,000, the sweep stops at $10,000 and a larger draw is refused."""
    person = {
        "birth_year": 1950,
        "social_security": 24_000.0,
        "traditional_balance": 50_000.0,
        "other_traditional_withdrawals": 20_000.0,
        "roth_conversion": 20_000.0,
        "roth_balance": 30_000.0,
    }
    inputs = _inputs(you=person, draw_amount=5_000.0)
    assert source_balance(inputs) == 10_000.0
    result = _run(inputs)
    assert result.account_left == 5_000.0
    assert result.sweep[-1].draw == 10_000.0
    with pytest.raises(ValidationError, match="exceeds"):
        _inputs(you=person, draw_amount=10_000.01)
    # A Roth draw leaves the traditional withdrawals aside.
    roth = _inputs(you=person, draw_source="roth", draw_amount=0.0)
    assert source_balance(roth) == 30_000.0
    # Withdrawals that take the whole balance leave nothing to draw.
    spent = _inputs(you={**person, "roth_conversion": 30_000.0}, draw_amount=0.0)
    assert source_balance(spent) == 0.0


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


class Float32Engine(StandInEngine):
    """The stand-in with its taxes rounded to float32, as PolicyEngine-US
    returns them."""

    def evaluate(self, inputs: USDrawdownYearInput, draws: np.ndarray) -> USYearArrays:
        arrays = super().evaluate(inputs, draws)
        for name in ("federal_income_tax", "state_income_tax"):
            values = getattr(arrays, name)
            setattr(arrays, name, values.astype(np.float32).astype(float))
        return arrays


@pytest.mark.parametrize(
    ("draw", "slice_to"), [(40_499.99, None), (40_499.5, None), (40_499.0, 40_500.0)]
)
def test_next_1000_needs_a_dollar_left_to_give_a_rate(draw, slice_to):
    """Under $1 left in the account, rounding swamps the rate of what's left,
    as it does for a band, so there's no next step to report."""
    inputs = _inputs(
        you={
            "birth_year": 1955,
            "social_security": 24_000.0,
            "traditional_balance": 40_500.0,
        },
        draw_amount=draw,
    )
    result = run_us_drawdown_year(inputs, Float32Engine())
    if slice_to is None:
        assert result.next_1000 is None
    else:
        assert result.next_1000.draw_to == slice_to


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


@pytest.mark.parametrize(
    ("typed", "kept"),
    [(0.125, 0.13), (1.005, 1.01), (2.675, 2.68), (0.0078125, 0.01), (0.004, 0.0)],
)
def test_amounts_round_to_the_cent_as_the_page_shows_them(typed, kept):
    """P2-a: every amount of money comes in rounded to the cent, half a cent
    up, on the decimal the number prints as, which is what the page's fields
    show (Intl.NumberFormat with two decimals gives 1.01 for 1.005)."""
    inputs = _inputs(
        you={
            "birth_year": 1955,
            "social_security": typed,
            "traditional_balance": typed,
        },
        cash_savings=typed,
        draw_source="cash",
        draw_amount=typed,
    )
    assert inputs.you.social_security == kept
    assert inputs.you.traditional_balance == kept
    assert inputs.cash_savings == kept
    assert inputs.draw_amount == kept


@pytest.mark.parametrize(
    ("you", "spouse"),
    [
        pytest.param({"birth_year": 1930, "traditional_balance": 0.125}, None, id="1"),
        pytest.param(
            {
                "birth_year": 1930,
                "social_security": 1_552.0,
                "pension_income": 31_980.0,
                "traditional_balance": 0.0078125,
            },
            {
                "birth_year": 1930,
                "pension_income": 31_963.0,
                "traditional_balance": 5_000.0,
                "other_traditional_withdrawals": 5_000.0,
            },
            id="2",
        ),
        pytest.param(
            {
                "birth_year": 1930,
                "social_security": 1_234.56,
                "pension_income": 39_999.99,
                "traditional_balance": 0.01,
            },
            {
                "birth_year": 1930,
                "pension_income": 39_999.99,
                "traditional_balance": 5_000.0,
                "other_traditional_withdrawals": 5_000.0,
            },
            id="3",
        ),
    ],
)
def test_an_account_under_a_cent_or_a_band_a_cent_wide_keeps_its_invariants(
    you, spouse
):
    """P2-a, from test_invariants_hold_for_any_household under the thorough
    profile (seed 7349). Before, (1) a balance of 12.5 cents left an account
    of 12 cents, and (2) a balance under a cent beside $65,495 of income gave
    a band from nothing to a cent whose shares added to 0.9999999987. (3) A
    whole cent beside $81,234.54 gave 0.9999999986: each share divided a
    difference of figures near $80,000 by a cent, so float noise of a
    hundred-billionth of a dollar showed. Balances now come in as 13 cents
    and 1 cent, and kept is what tax and benefits leave of each dollar, so
    the shares add to 1 however narrow the band."""
    inputs = _inputs(
        filing_status="married_filing_jointly" if spouse else "single",
        you=you,
        spouse=spouse,
        draw_amount=0.0,
    )
    result = _run(inputs)
    _assert_invariants(inputs, result)
    assert result.account_left == inputs.you.traditional_balance
    assert result.bands[-1].draw_to == inputs.you.traditional_balance


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


class ItemizingEngine(StandInEngine):
    """The stand-in plus a use tax of 0.1% of the draw, itemized as
    PolicyEngine-US itemizes other taxes."""

    def evaluate(self, inputs: USDrawdownYearInput, draws: np.ndarray) -> USYearArrays:
        arrays = super().evaluate(inputs, draws)
        use_tax = 0.001 * np.asarray(draws, dtype=float)
        zeros = np.zeros(len(draws))
        arrays.other_taxes = use_tax
        arrays.other_tax_parts = {
            "payroll_tax": zeros,
            "state_use_tax": use_tax,
            "other_taxes": zeros,
        }
        return arrays


def _ids(citations) -> list[str]:
    return [citation.id for citation in citations]


def test_other_taxes_cite_the_taxes_the_household_pays():
    result = run_us_drawdown_year(_inputs(), ItemizingEngine())
    assert result.other_taxes.amount == pytest.approx(40.0)
    assert _ids(result.other_taxes.citations) == _ids(
        citations_for_keys(["state_use_tax"])
    )


def test_other_taxes_cite_nothing_when_the_household_pays_none():
    result = run_us_drawdown_year(_inputs(draw_amount=0.0), ItemizingEngine())
    assert result.other_taxes.amount == 0.0
    assert result.other_taxes.citations == []


def test_an_engine_that_does_not_itemize_cites_payroll_tax_and_the_total():
    assert _ids(_run(_inputs()).other_taxes.citations) == _ids(
        citations_for_keys(["payroll_tax", "other_taxes"])
    )


class FederalPartsEngine(StandInEngine):
    """The stand-in with federal income tax itemized as PolicyEngine-US adds it
    up: a 3.8% net investment income tax on draws above $100,000, and on
    request an alternative minimum tax of $500 at every draw."""

    def __init__(self, amt: bool = False) -> None:
        super().__init__()
        self.amt = amt

    def evaluate(self, inputs: USDrawdownYearInput, draws: np.ndarray) -> USYearArrays:
        arrays = super().evaluate(inputs, draws)
        draws = np.asarray(draws, dtype=float)
        niit = 0.038 * np.maximum(draws - 100_000.0, 0.0)
        amt = np.full(len(draws), 500.0 if self.amt else 0.0)
        arrays.federal_income_tax = arrays.federal_income_tax + niit + amt
        arrays.federal_tax_parts = {
            "net_investment_income_tax": niit,
            "alternative_minimum_tax": amt,
        }
        return arrays


def _sources(citations) -> list[str]:
    return [citation.source for citation in citations]


@pytest.mark.parametrize(
    ("draw", "amt", "cited", "not_cited"),
    [
        (50_000.0, False, [], ["26 USC 1411", "26 USC 55"]),
        (150_000.0, False, ["26 USC 1411"], ["26 USC 55"]),
        (50_000.0, True, ["26 USC 55"], ["26 USC 1411"]),
    ],
)
def test_federal_tax_cites_the_net_investment_income_tax_and_amt_when_paid(
    draw, amt, cited, not_cited
):
    """Federal income tax holds the net investment income tax (26 USC 1411)
    and the alternative minimum tax (26 USC 55) as PolicyEngine-US adds them
    up; each is cited when paid at the chosen draw or with none."""
    inputs = _inputs(
        you={"birth_year": 1955, "traditional_balance": 600_000.0},
        draw_amount=draw,
    )
    result = run_us_drawdown_year(inputs, FederalPartsEngine(amt=amt))
    sources = _sources(result.federal_income_tax.citations)
    assert sources[:5] == [
        "PolicyEngine-US variable",
        "26 USC 1",
        "26 USC 63",
        "26 USC 86",
        "26 USC 151",
    ]
    for source in cited:
        assert source in sources
    for source in not_cited:
        assert source not in sources


class ElectionEngine(StandInEngine):
    """The stand-in with a state tax that a filer may elect to figure another
    way above draws of $30,000, as Wisconsin's retirement income exclusion
    lets PolicyEngine-US's state_income_tax do."""

    def evaluate(self, inputs: USDrawdownYearInput, draws: np.ndarray) -> USYearArrays:
        arrays = super().evaluate(inputs, draws)
        arrays.state_tax_election = np.asarray(draws, dtype=float) > 30_000.0
        return arrays


@pytest.mark.parametrize(
    ("state", "draw", "variable", "statute"),
    [
        ("WI", 40_000.0, "state_income_tax", True),
        ("WI", 20_000.0, "state_income_tax_before_refundable_credits", False),
        ("TX", 40_000.0, "state_income_tax", False),
    ],
)
def test_state_tax_cites_the_variable_it_comes_from(state, draw, variable, statute):
    """On the election path the state figure is PolicyEngine-US's
    state_income_tax, and in Wisconsin it cites the retirement income
    exclusion; otherwise it is the tax before refundable credits."""
    result = run_us_drawdown_year(
        _inputs(state=state, draw_amount=draw), ElectionEngine()
    )
    ids = _ids(result.state_income_tax.citations)
    assert ids[0] == f"policyengine-us:variables/{variable}"
    assert (
        "Wis. Stat. 71.05(6)(b)54m.a" in _sources(result.state_income_tax.citations)
    ) is statute


def test_the_money_to_spend_definition_names_the_wisconsin_exception():
    """household_net_income nets the usual state tax, so on Wisconsin's
    exclusion path money to spend exceeds it by the tax the path saves."""
    inputs = _inputs()
    envelope = build_us_drawdown_year_result(
        build_us_drawdown_year_scenario(inputs), inputs, _run(inputs)
    )
    definition = envelope.assumptions["money_to_spend_definition"]
    assert "Wisconsin's retirement income exclusion path" in definition


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


@pytest.mark.parametrize(
    ("you_born", "spouse_born", "expected"),
    [
        # Your spouse, 76, owes the minimum; you, 65, owe none.
        (1961, 1950, ["If your spouse names you, more than 10 years younger,"]),
        (1950, 1961, ["If you name your spouse, more than 10 years younger,"]),
        # Both owe a minimum; only the older one has a spouse 11 years younger.
        (1952, 1941, ["If your spouse names you, more than 10 years younger,"]),
        (1951, 1961, []),
    ],
)
def test_the_joint_table_caveat_names_the_owner_with_a_younger_spouse(
    you_born, spouse_born, expected
):
    """The IRS Joint and Last Survivor Table serves an owner whose sole
    beneficiary is a spouse more than 10 years younger (26 CFR
    1.401(a)(9)-9), so the caveat names whoever owes that minimum."""
    inputs = _inputs(
        filing_status="married_filing_jointly",
        you={"birth_year": you_born, "traditional_balance": 300_000.0},
        spouse={"birth_year": spouse_born, "traditional_balance": 300_000.0},
        draw_amount=0.0,
    )
    caveats = caveats_for(inputs, _run(inputs))
    found = [c for c in caveats if "Joint and Last Survivor" in c]
    assert [
        c[: len(start)] for c, start in zip(found, expected, strict=False)
    ] == expected
    assert len(found) == len(expected)


def test_rmd_caveats_follow_the_first_year_and_earnings():
    """A first-year shortfall owes no excise tax yet, so the excise caveat
    gives way to the April 1 deadline; earnings bring the still-working
    exception for a current employer's plan (26 USC 401(a)(9)(C))."""
    first = _inputs(
        you={
            "birth_year": 1953,
            "social_security": 24_000.0,
            "traditional_balance": 265_000.0,
        },
        draw_amount=0.0,
    )
    caveats = caveats_for(first, _run(first))
    assert not [c for c in caveats if "you owe an excise tax of 25%" in c]
    assert [c for c in caveats if "April 1, 2027" in c]
    assert [c for c in caveats if "each workplace plan" in c]
    assert not [c for c in caveats if "still work" in c]
    working = first.model_copy(
        update={"you": first.you.model_copy(update={"earnings": 20_000.0})}
    )
    (still,) = [c for c in caveats_for(working, _run(working)) if "still work" in c]
    assert "401(a)(9)(C)" in still and "April 1" in still


def test_medicare_caveat_expects_higher_lines_only_until_medicare_publishes_them():
    inputs = _inputs()
    result = _run(inputs)
    assert result.medicare_surcharge.rates_year < result.medicare_surcharge.premium_year
    assert [
        c for c in caveats_for(inputs, result) if "2028 lines will exceed these" in c
    ]
    published = result.model_copy(
        update={
            "medicare_surcharge": result.medicare_surcharge.model_copy(
                update={"rates_year": result.medicare_surcharge.premium_year}
            )
        }
    )
    assert [c for c in caveats_for(inputs, published) if "1395r(i)(4)" in c] == [
        "Social Security uses your 2026 income to set the extra you pay for Medicare "
        "in 2028 (42 USC 1395r(i)(4)). We apply Medicare’s 2028 income lines and amounts."
    ]


@pytest.mark.parametrize("who", ["you", "spouse"])
def test_withdrawals_beyond_the_traditional_balance_are_refused(who):
    """Other traditional withdrawals and a Roth conversion come out of the
    traditional balance, so together they can't exceed it. Otherwise SSI would
    leave out of income withdrawals that no counted resource stands behind."""
    person = {
        "birth_year": 1950,
        "social_security": 24_000.0,
        "traditional_balance": 50_000.0,
        "other_traditional_withdrawals": 30_000.0,
        "roth_conversion": 20_000.0,
    }
    plain = {"birth_year": 1950, "social_security": 24_000.0}
    couple = {"filing_status": "married_filing_jointly", "draw_amount": 0.0}
    couple = {**couple, "draw_owner": who}
    at_balance = (
        _inputs(you=person, spouse=plain, **couple)
        if who == "you"
        else _inputs(you=plain, spouse=person, **couple)
    )
    assert source_balance(at_balance) == 0.0
    over = {**person, "roth_conversion": 20_000.01}
    with pytest.raises(ValidationError, match="more than"):
        if who == "you":
            _inputs(you=over, spouse=plain, **couple)
        else:
            _inputs(you=plain, spouse=over, **couple)


def test_ssi_caveats_follow_the_inputs():
    """The SSI caveats appear where they apply: regular payments from a
    workplace plan for anyone with a traditional balance, the current-job plan
    for anyone who also works, turning 65 during the year, and the Colorado
    couple's Old Age Pension."""

    def found(text: str, inputs: USDrawdownYearInput) -> list[str]:
        return [c for c in caveats_for(inputs) if text in c]

    plain = _inputs()
    assert found("POMS SI 01120.210 B, E.1", plain)
    assert not found("SI 01120.210 C.1", plain)
    assert not found("as 65 for all of 2026", plain)
    assert not found("Old Age Pension", plain)

    no_traditional = _inputs(
        you={"birth_year": 1955, "social_security": 24_000.0, "roth_balance": 1.0},
        draw_source="roth",
        draw_amount=0.0,
    )
    assert not found("POMS SI 01120.210 B, E.1", no_traditional)

    working = _inputs(
        you={
            "birth_year": 1955,
            "social_security": 24_000.0,
            "traditional_balance": 600_000.0,
            "earnings": 20_000.0,
        }
    )
    (current_job,) = found("SI 01120.210 C.1", working)
    assert "your current job" in current_job

    spouse_works = _inputs(
        filing_status="married_filing_jointly",
        spouse={
            "birth_year": 1958,
            "traditional_balance": 10_000.0,
            "earnings": 20_000.0,
        },
    )
    (current_job,) = found("SI 01120.210 C.1", spouse_works)
    assert "your spouse’s traditional balance" in current_job

    turning_65 = _inputs(
        you={
            "birth_year": 1961,
            "social_security": 24_000.0,
            "traditional_balance": 600_000.0,
        }
    )
    (aged,) = found("as 65 for all of 2026", turning_65)
    assert aged.startswith("PolicyEngine-US treats you")

    colorado = _inputs(
        state="CO",
        filing_status="married_filing_jointly",
        spouse={"birth_year": 1956, "social_security": 6_000.0},
    )
    assert found("Old Age Pension", colorado)
    assert not found("Old Age Pension", _inputs(state="CO"))
    no_savings = _inputs(
        state="CO",
        filing_status="married_filing_jointly",
        you={"birth_year": 1956, "social_security": 6_000.0},
        spouse={"birth_year": 1956, "social_security": 6_000.0},
        draw_source="cash",
        draw_amount=0.0,
    )
    assert not found("Old Age Pension", no_savings)


def test_ssi_wording_marks_the_conversion_reading_as_eggnest_s():
    """The page says the withdrawal reading is Eggnest's, cites the texts that
    say it in words, and values retirement funds by POMS SI 01120.210 A.3."""
    caveats = caveats_for(_inputs())
    (conversion,) = [c for c in caveats if "416.1103(c)" in c]
    assert "We read a withdrawal" in conversion
    assert "SI 01120.250 B.2" in conversion
    assert "1382a(b)(23)" in conversion
    assert [c for c in caveats if "SI 01120.210 A.3, B, D.2" in c]
    assert [c for c in caveats if "416.1207(a)" in c]


def test_investment_income_with_no_savings_gets_a_caveat():
    """SSI leaves out interest and dividends only on savings it counts, so the
    page asks for the savings when someone enters such income without any."""

    def found(**overrides) -> bool:
        return any(
            "enter the savings they come from" in c
            for c in caveats_for(_inputs(**overrides))
        )

    assert found(taxable_interest=500.0)
    assert found(dividends=500.0)
    assert not found(taxable_interest=500.0, cash_savings=10_000.0)
    assert not found(dividends=500.0, taxable_balance=10_000.0)
    assert not found()
