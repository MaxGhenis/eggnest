"""Net-income identity for the household calculator.

PolicyEngine-US defines household net income as

    household_net_income = household_market_income
                           + household_benefits
                           + household_refundable_tax_credits
                           - household_tax_before_refundable_credits
                           - household_health_costs

where federal ``income_tax`` already nets out refundable credits and
``income_tax_before_refundable_credits`` already nets out the non-refundable
credits that were used. EggNest reports Social Security inside
``total_income`` (the user enters it) and excludes health coverage, so its net
income must equal PolicyEngine's with health benefits and costs removed:

    net_income = market income + Social Security
                 + non-credit benefits other than Social Security and health
                 + refundable credits (federal and state, counted once)
                 - tax before refundable credits

These tests compare EggNest against PolicyEngine-US aggregates computed in a
separate simulation, so any credit counted twice, or any tax or benefit that
EggNest drops, shows up as a gap.
"""

import copy
import os

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from policyengine_us import Simulation

from eggnest.constants import STATE_FIPS
from eggnest.household import HouseholdCalculator
from eggnest.models import HouseholdInput, HouseholdResult, PersonInput

REFERENCE_VARIABLES = [
    "household_net_income",
    "household_market_income",
    "household_benefits",
    "household_health_benefits",
    "household_health_costs",
    "household_refundable_tax_credits",
    "household_tax_before_refundable_credits",
    "social_security",
    "income_tax",
    "income_tax_before_refundable_credits",
    "income_tax_refundable_credits",
    "eitc",
    "refundable_ctc",
]

# Tolerance for float32 aggregation inside PolicyEngine.
DOLLAR = 1.0
CENTS = 0.01

# Keys the calculator uses for amounts it could not attribute to a program.
UNITEMIZED_KEYS = {
    "other_benefits",
    "other_computed_income",
    "other_federal_refundable_credits",
    "other_taxes",
}


def _reference(situation: dict, year: int) -> dict[str, float]:
    """PolicyEngine-US aggregates for a situation, from a fresh simulation."""
    sim = Simulation(situation=situation)
    return {
        variable: float(sim.calculate(variable, year).sum())
        for variable in REFERENCE_VARIABLES
    }


def _expected_net_income(ref: dict[str, float]) -> float:
    """PolicyEngine household net income with health coverage excluded."""
    return (
        ref["household_net_income"]
        - ref["household_health_benefits"]
        + ref["household_health_costs"]
    )


def assert_net_income_identity(
    household: HouseholdInput, result: HouseholdResult, ref: dict[str, float]
) -> None:
    """Every invariant that ties EggNest's rows to PolicyEngine-US."""
    social_security = sum(p.social_security for p in household.people)
    entered_income = sum(
        p.employment_income
        + p.self_employment_income
        + p.social_security
        + p.pension_income
        + p.investment_income
        + p.capital_gains
        for p in household.people
    )
    # Market income PolicyEngine adds on its own (the Alaska Permanent Fund
    # Dividend); EggNest reports it as a benefit line.
    computed_income = ref["household_market_income"] - (
        entered_income - social_security
    )
    # PolicyEngine's non-credit benefits, less Social Security (in total_income)
    # and health coverage (excluded).
    non_credit_benefits = (
        ref["household_benefits"]
        - ref["social_security"]
        - ref["household_health_benefits"]
    )

    # 1. Net income equals PolicyEngine's household net income (health excluded).
    assert result.net_income == pytest.approx(_expected_net_income(ref), abs=DOLLAR)

    # 2. The identity, term by term.
    identity = (
        ref["household_market_income"]
        + social_security
        + non_credit_benefits
        + ref["household_refundable_tax_credits"]
        - ref["household_tax_before_refundable_credits"]
    )
    assert result.net_income == pytest.approx(identity, abs=DOLLAR)

    # 3. The displayed rows reconcile exactly.
    assert result.net_income == pytest.approx(
        result.total_income - result.total_taxes + result.total_benefits, abs=1e-6
    )
    assert result.total_income == pytest.approx(entered_income, abs=1e-6)
    # Every dollar is attributed to a named PolicyEngine variable: no
    # unitemized remainder under current law.
    assert not UNITEMIZED_KEYS & set(result.benefits)
    assert not UNITEMIZED_KEYS & set(result.tax_breakdown)
    assert result.total_taxes == pytest.approx(
        result.federal_income_tax
        + result.state_income_tax
        + result.payroll_tax
        + result.other_taxes,
        abs=1e-6,
    )
    # Sub-cent remainders are dropped from the breakdown.
    assert result.total_taxes == pytest.approx(
        sum(result.tax_breakdown.values()), abs=CENTS
    )
    assert result.total_benefits == pytest.approx(
        sum(result.benefits.values()), abs=1e-6
    )

    # 4. Taxes are measured before refundable credits ...
    assert result.federal_income_tax == pytest.approx(
        ref["income_tax_before_refundable_credits"], abs=DOLLAR
    )
    assert result.total_taxes == pytest.approx(
        ref["household_tax_before_refundable_credits"], abs=DOLLAR
    )

    # 5. ... and refundable credits are counted once, inside benefits.
    assert result.refundable_tax_credits == pytest.approx(
        ref["household_refundable_tax_credits"], abs=DOLLAR
    )
    assert result.total_benefits == pytest.approx(
        non_credit_benefits + computed_income + ref["household_refundable_tax_credits"],
        abs=DOLLAR,
    )
    # Federal tax net of the federal refundable credits is PolicyEngine's income_tax.
    assert result.federal_income_tax - ref[
        "income_tax_refundable_credits"
    ] == pytest.approx(ref["income_tax"], abs=DOLLAR)


def _ohio_single_parent() -> tuple[HouseholdInput, dict]:
    """2026 Ohio single parent, $28,000 wages, children aged 4 and 8.

    The PolicyEngine situation is written out by hand rather than through
    ``HouseholdCalculator._build_situation`` so the check does not trust the
    code under test.
    """
    year = 2026
    household = HouseholdInput(
        state="OH",
        year=year,
        people=[
            PersonInput(age=30, employment_income=28_000, is_tax_unit_head=True),
            PersonInput(age=4),
            PersonInput(age=8),
        ],
    )
    members = ["parent", "child_4", "child_8"]
    situation = {
        "people": {
            "parent": {
                "age": {year: 30},
                "employment_income": {year: 28_000},
                "is_tax_unit_head": {year: True},
            },
            "child_4": {"age": {year: 4}, "is_tax_unit_dependent": {year: True}},
            "child_8": {"age": {year: 8}, "is_tax_unit_dependent": {year: True}},
        },
        "tax_units": {
            "tax_unit": {
                "members": members,
                "filing_status": {year: "HEAD_OF_HOUSEHOLD"},
            }
        },
        "families": {"family": {"members": members}},
        "spm_units": {"spm_unit": {"members": members}},
        "marital_units": {
            "parent": {"members": ["parent"]},
            "child_4": {"members": ["child_4"]},
            "child_8": {"members": ["child_8"]},
        },
        "households": {"household": {"members": members, "state_code": {year: "OH"}}},
    }
    return household, situation


class TestCreditsCountedOnce:
    """Refundable credits must not reduce tax and also be added as benefits."""

    def test_ohio_single_parent_net_income_matches_policyengine(self):
        household, situation = _ohio_single_parent()
        ref = _reference(situation, household.year)
        # Guard: the example only tests something if credits are in play.
        assert ref["eitc"] > 0
        assert ref["refundable_ctc"] > 0

        result = HouseholdCalculator().calculate(household)

        assert_net_income_identity(household, result, ref)

    def test_ohio_single_parent_reports_each_credit_once(self):
        household, situation = _ohio_single_parent()
        ref = _reference(situation, household.year)

        result = HouseholdCalculator().calculate(household)

        # The EITC and refundable CTC each appear once, at PolicyEngine's value.
        assert result.benefits["eitc"] == pytest.approx(ref["eitc"], abs=DOLLAR)
        assert result.benefits["refundable_ctc"] == pytest.approx(
            ref["refundable_ctc"], abs=DOLLAR
        )
        # The federal tax row has not already subtracted them.
        assert result.federal_income_tax >= 0
        assert result.federal_income_tax == pytest.approx(
            ref["income_tax"] + ref["income_tax_refundable_credits"], abs=DOLLAR
        )


class TestMarginalTaxRate:
    """The marginal rate is the share of an extra $1,000 of wages not kept."""

    def test_self_employed_marginal_rate_is_a_rate(self):
        # Self-employment tax used to enter the base but not the +$1,000 run,
        # which produced a marginal rate of about -1,237%.
        household = HouseholdInput(
            state="CA",
            year=2025,
            people=[
                PersonInput(
                    age=40, self_employment_income=90_000, is_tax_unit_head=True
                )
            ],
        )
        result = HouseholdCalculator().calculate(household)
        assert 0 < result.marginal_tax_rate < 1

    def test_marginal_rate_matches_net_income_change(self):
        calc = HouseholdCalculator()
        household, _ = _ohio_single_parent()
        raised = household.model_copy(
            update={
                "people": [
                    household.people[0].model_copy(
                        update={
                            "employment_income": household.people[0].employment_income
                            + 1_000
                        }
                    ),
                    *household.people[1:],
                ]
            }
        )
        base = calc.calculate(household)
        after_raise = calc.calculate(raised)
        assert base.marginal_tax_rate == pytest.approx(
            1 - (after_raise.net_income - base.net_income) / 1_000, abs=1e-6
        )

    def test_marginal_rate_matches_policyengine_net_income_change(self):
        # Compared against two fresh PolicyEngine simulations rather than the
        # PolicyEngine-US ``marginal_tax_rate`` variable: in policyengine-us
        # 2.15.16 that variable returns -4.70 for this household because its
        # branch finds $7,475 of Ohio TANF that a fresh simulation at the same
        # $29,000 of wages does not.
        household, situation = _ohio_single_parent()
        year = household.year
        raised = copy.deepcopy(situation)
        raised["people"]["parent"]["employment_income"] = {year: 29_000}
        pe_rate = (
            1
            - (
                _reference(raised, year)["household_net_income"]
                - _reference(situation, year)["household_net_income"]
            )
            / 1_000
        )

        result = HouseholdCalculator().calculate(household)

        assert result.marginal_tax_rate == pytest.approx(pe_rate, abs=2e-3)
        # The Ohio parent loses about half of a raise to phase-outs and tax.
        assert 0.3 < result.marginal_tax_rate < 0.8


# --- Property-based tests --------------------------------------------------

settings.register_profile(
    "default",
    max_examples=20,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.register_profile(
    "thorough",
    max_examples=int(os.environ.get("HYPOTHESIS_MAX_EXAMPLES", "400")),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

# The determinism and comparison properties each run four simulations per
# example, so they get a quarter of the example budget.
light = settings(max_examples=max(5, settings.default.max_examples // 4))


def _money(high: int) -> st.SearchStrategy[float]:
    """Mostly zero or low amounts, where benefits and credits phase in and out."""
    return st.one_of(
        st.just(0.0),
        st.integers(0, 40_000).map(float),
        st.integers(0, high).map(float),
    )


@st.composite
def _adult(draw, role: str) -> PersonInput:
    age = draw(st.integers(18, 90))
    return PersonInput(
        age=age,
        employment_income=draw(_money(250_000)),
        self_employment_income=draw(st.one_of(st.just(0.0), _money(100_000))),
        social_security=draw(_money(45_000)) if age >= 62 else 0.0,
        pension_income=draw(st.one_of(st.just(0.0), _money(60_000))),
        investment_income=draw(st.one_of(st.just(0.0), _money(50_000))),
        capital_gains=draw(st.one_of(st.just(0.0), _money(50_000))),
        **{role: True},
    )


@st.composite
def households(draw) -> HouseholdInput:
    people = [draw(_adult("is_tax_unit_head"))]
    if draw(st.booleans()):
        people.append(draw(_adult("is_tax_unit_spouse")))
    for _ in range(draw(st.integers(0, 3))):
        people.append(PersonInput(age=draw(st.integers(0, 17))))
    return HouseholdInput(
        state=draw(st.sampled_from(sorted(STATE_FIPS))),
        year=draw(st.sampled_from([2024, 2025, 2026])),
        people=people,
    )


class TestNetIncomeProperties:
    """For any household, EggNest's rows reconcile with PolicyEngine-US."""

    @given(household=households())
    def test_net_income_equals_policyengine_net_income(self, household):
        calc = HouseholdCalculator()
        result = calc.calculate(household)
        ref = _reference(calc._build_situation(household), household.year)

        assert_net_income_identity(household, result, ref)

    @given(household=households())
    def test_taxes_and_benefit_rows_are_non_negative(self, household):
        result = HouseholdCalculator().calculate(household)

        assert result.federal_income_tax >= -DOLLAR
        assert result.payroll_tax >= -DOLLAR
        assert result.refundable_tax_credits >= -DOLLAR
        assert all(value > 0 for value in result.benefits.values())

    @light
    @given(household=households())
    def test_calculation_is_deterministic(self, household):
        calc = HouseholdCalculator()
        assert calc.calculate(household) == calc.calculate(household)

    @light
    @given(before=households(), after=households())
    def test_comparison_changes_reconcile(self, before, after):
        comparison = HouseholdCalculator().compare(before, after)
        b, a = comparison.before_result, comparison.after_result

        assert comparison.net_income_change == pytest.approx(
            a.net_income - b.net_income, abs=1e-6
        )
        assert comparison.net_income_change == pytest.approx(
            (a.total_income - b.total_income)
            - comparison.tax_change
            + comparison.benefit_change,
            abs=1e-6,
        )
