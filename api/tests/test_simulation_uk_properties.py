"""Property-based tests for the UK simulator's accounting invariants.

Most properties run the simulator against ``progressive_tax``, a fast
deterministic stand-in for PolicyEngine with the same shape (a tapered
personal allowance, rising bands, dividend rates, employee NI, rounding to
the penny), so Hypothesis can explore hundreds of scenarios. The accounting
identities hold for any tax function; the tests marked ``real engine`` check
the ones that depend on the actual UK rules against policyengine-uk-compiled.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from eggnest.models_uk import UKSimulationInput
from eggnest.simulation_uk import (
    _SIPP_SOLVER_TOLERANCE,
    LSA_CAP,
    MPA,
    TFC_FRACTION,
    UNMET_TOLERANCE,
    _solve_sipp_draw,
    iterate_uk_year_flows,
    run_uk_simulation,
)
from eggnest.tax_uk import UKYearInputs, UKYearResults, calculate_uk_tax

REGIONS = [
    "London",
    "South East",
    "North West",
    "Scotland",
    "Wales",
    "Northern Ireland",
]

# Float noise allowed in identities that sum a handful of £ amounts up to a
# few million.
ATOL = 1e-6
RTOL = 1e-9


def progressive_tax(inputs: UKYearInputs) -> UKYearResults:
    """UK-shaped test double for calculate_uk_tax (not the law)."""
    non_savings = (
        inputs.state_pension + inputs.private_pension_income + inputs.employment_income
    ).astype(float)
    savings = inputs.savings_interest.astype(float)
    dividends = inputs.dividend_income.astype(float)
    total = non_savings + savings + dividends
    allowance = np.maximum(12570.0 - np.maximum(total - 100000.0, 0.0) / 2.0, 0.0)
    taxable_ns = np.maximum(non_savings - allowance, 0.0)
    allowance_left = np.maximum(allowance - non_savings, 0.0)
    basic_band, higher_top = 37700.0, 125140.0
    tax_ns = (
        0.20 * np.minimum(taxable_ns, basic_band)
        + 0.40 * np.clip(taxable_ns - basic_band, 0.0, higher_top - basic_band)
        + 0.45 * np.maximum(taxable_ns - higher_top, 0.0)
    )
    taxable_div = np.maximum(dividends + savings - allowance_left - 500.0, 0.0)
    basic_left = np.maximum(basic_band - taxable_ns, 0.0)
    tax_div = 0.0875 * np.minimum(taxable_div, basic_left) + 0.3375 * np.maximum(
        taxable_div - basic_left, 0.0
    )
    income_tax = np.round(tax_ns + tax_div, 2)
    employment = inputs.employment_income.astype(float)
    employee_ni = np.round(
        0.08 * np.clip(employment - 12570.0, 0.0, 50270.0 - 12570.0)
        + 0.02 * np.maximum(employment - 50270.0, 0.0),
        2,
    )
    direct = income_tax + employee_ni
    return UKYearResults(
        net_income=total - direct,
        total_tax=direct,
        income_tax=income_tax,
        employee_ni=employee_ni,
    )


money = st.one_of(st.just(0.0), st.floats(min_value=0.0, max_value=1_500_000.0))


@st.composite
def uk_inputs(draw, max_years: int = 25) -> UKSimulationInput:
    current_age = draw(st.integers(min_value=30, max_value=95))
    max_age = draw(
        st.integers(min_value=current_age, max_value=min(current_age + max_years, 110))
    )
    return UKSimulationInput(
        current_age=current_age,
        max_age=max_age,
        gender=draw(st.sampled_from(["male", "female"])),
        region=draw(st.sampled_from(REGIONS)),
        isa_balance=draw(money),
        sipp_balance=draw(money),
        gia_balance=draw(money),
        annual_spending=draw(st.floats(min_value=0.0, max_value=150_000.0)),
        spending_mode=draw(st.sampled_from(["real", "nominal"])),
        state_pension_annual=draw(st.floats(min_value=0.0, max_value=15_000.0)),
        state_pension_start_age=draw(st.integers(min_value=60, max_value=75)),
        employment_income=draw(
            st.one_of(st.just(0.0), st.floats(min_value=0.0, max_value=200_000.0))
        ),
        retirement_age=draw(st.integers(min_value=30, max_value=80)),
        earnings_model=draw(st.sampled_from(["flat", "deterministic", "stochastic"])),
        savings_rate=draw(st.floats(min_value=0.0, max_value=0.5)),
        sipp_contribution_share=draw(st.floats(min_value=0.0, max_value=1.0)),
        return_source=draw(
            st.sampled_from(
                [
                    "gaussian",
                    "historical_bootstrap",
                    "historical_block_bootstrap",
                    "historical_sequential",
                ]
            )
        ),
        expected_return=draw(st.floats(min_value=-0.1, max_value=0.2)),
        return_volatility=draw(st.floats(min_value=0.0, max_value=0.5)),
        dividend_yield=draw(st.floats(min_value=0.0, max_value=0.15)),
        equity_weight=draw(st.floats(min_value=0.0, max_value=1.0)),
        inflation_rate=draw(st.floats(min_value=0.0, max_value=0.1)),
        n_simulations=100,
        random_seed=draw(st.integers(min_value=0, max_value=2**31 - 1)),
        include_mortality=draw(st.booleans()),
    )


PROPERTY_SETTINGS = settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


def _close(a, b) -> bool:
    return bool(np.allclose(a, b, rtol=RTOL, atol=ATOL))


@PROPERTY_SETTINGS
@given(inputs=uk_inputs())
def test_each_wrapper_conserves_money_every_year(inputs):
    """Every pound in each account is accounted for, every year, every path:
    closing = (opening + contributions - withdrawals) x growth (+ reinvested
    GIA dividends), and no balance or flow is ever negative."""
    tfc_taken = np.zeros(inputs.n_simulations)
    previous_end = None
    for f in iterate_uk_year_flows(inputs, progressive_tax):
        if previous_end is not None:
            assert _close(f.gia_start, previous_end[0])
            assert _close(f.isa_start, previous_end[1])
            assert _close(f.sipp_start, previous_end[2])
        assert _close(
            f.gia_end,
            (f.gia_start - f.withdrawal_gia) * f.gia_growth + f.reinvested_dividends,
        )
        assert _close(
            f.isa_end,
            (f.isa_start + f.contribution_isa - f.withdrawal_isa) * f.wrapper_growth,
        )
        assert _close(
            f.sipp_end,
            (f.sipp_start + f.contribution_sipp - f.withdrawal_sipp) * f.wrapper_growth,
        )
        for arr in (
            f.gia_end,
            f.isa_end,
            f.sipp_end,
            f.withdrawal_gia,
            f.withdrawal_isa,
            f.withdrawal_sipp,
            f.contribution_isa,
            f.contribution_sipp,
            f.reinvested_dividends,
            f.gia_growth,
            f.wrapper_growth,
        ):
            assert np.all(arr >= 0.0)
        # Withdrawals never exceed what the account held.
        assert np.all(f.withdrawal_gia <= f.gia_start + ATOL)
        assert np.all(f.withdrawal_isa <= f.isa_start + f.contribution_isa + ATOL)
        assert np.all(f.withdrawal_sipp <= f.sipp_start + f.contribution_sipp + ATOL)
        # SIPP rules: locked before MPA; UFPLS tax-free cash is at most 25 %
        # of each draw and never exceeds the lifetime allowance.
        if f.age < MPA:
            assert np.all(f.withdrawal_sipp == 0.0)
        assert np.all(f.sipp_tax_free_cash <= TFC_FRACTION * f.withdrawal_sipp + ATOL)
        tfc_taken = tfc_taken + f.sipp_tax_free_cash
        assert np.all(tfc_taken <= LSA_CAP + ATOL)
        previous_end = (f.gia_end, f.isa_end, f.sipp_end)


@PROPERTY_SETTINGS
@given(inputs=uk_inputs())
def test_spending_identity_holds_every_year(inputs):
    """withdrawals + net income - contributions + unmet = spending.

    Withdrawals are gross of the GIA dividends reinvested, and income above
    the target and contributions that is not dividends (``excess_income``)
    is spent, so the exact identity is
    withdrawals - reinvested + net income - contributions + unmet - excess
    = spending target. Unmet spending and a surplus never coexist, the
    solver over-draws by at most its tolerance, and spending goes unmet only
    when every account the person may draw from is empty."""
    for f in iterate_uk_year_flows(inputs, progressive_tax):
        lhs = (
            f.withdrawals
            - f.reinvested_dividends
            + f.net_income
            - f.contributions
            + f.unmet_spending
            - f.excess_income
        )
        assert _close(lhs, f.spending_target)
        # Without a surplus the identity is the plain one.
        no_surplus = (f.reinvested_dividends == 0) & (f.excess_income == 0)
        plain = f.withdrawals + f.net_income - f.contributions + f.unmet_spending
        assert _close(plain[no_surplus], f.spending_target[no_surplus])
        assert np.all(f.unmet_spending >= 0.0)
        assert np.all(f.excess_income >= 0.0)
        assert np.all(f.reinvested_dividends <= f.gia_dividends + ATOL)
        # Ignore float noise (~1e-11) where withdrawals exactly meet the
        # target.
        short = f.unmet_spending > ATOL
        assert np.all(f.reinvested_dividends[short] == 0.0)
        assert np.all(f.excess_income[short] == 0.0)
        drew = f.withdrawals > 0
        surplus = f.reinvested_dividends + f.excess_income
        assert np.all(surplus[drew] <= _SIPP_SOLVER_TOLERANCE + ATOL)
        # Net income is income less the tax the engine reported.
        assert _close(
            f.net_income,
            f.employment_income + f.state_pension + f.gia_dividends - f.total_tax,
        )
        # Unmet spending means the accessible accounts were emptied.
        gia_left = f.gia_start - f.withdrawal_gia
        isa_left = f.isa_start + f.contribution_isa - f.withdrawal_isa
        sipp_left = f.sipp_start + f.contribution_sipp - f.withdrawal_sipp
        assert np.all(gia_left[short] <= ATOL)
        assert np.all(isa_left[short] <= ATOL)
        if f.age >= MPA:
            assert np.all(sipp_left[short] <= ATOL)
        assert np.array_equal(
            f.sipp_locked,
            f.failed & (f.age < MPA) & (sipp_left > 0),
        )


@PROPERTY_SETTINGS
@given(inputs=uk_inputs())
def test_success_iff_no_living_year_has_unmet_spending(inputs):
    """success_rate is exactly the share of paths with no year, while alive,
    of more than £1 unmet spending; the strict, ten-year and SIPP-locked
    measures are the matching path-level counts."""
    flows = list(iterate_uk_year_flows(inputs, progressive_tax))
    failed = np.array([f.failed for f in flows])  # (years, sims)
    alive = np.array([f.alive for f in flows])
    locked = np.array([f.sipp_locked for f in flows])
    assert np.array_equal(
        failed, np.array([f.unmet_spending > UNMET_TOLERANCE for f in flows])
    )

    living_failure = failed & alive
    first_failure = np.where(
        living_failure.any(axis=0), living_failure.argmax(axis=0), -1
    )
    result = run_uk_simulation(inputs, progressive_tax)

    assert result.success_rate == pytest.approx(np.mean(~living_failure.any(axis=0)))
    assert result.strict_horizon_success_rate == pytest.approx(
        np.mean(~failed.any(axis=0))
    )
    assert result.prob_10_year_failure == pytest.approx(
        np.mean((first_failure != -1) & (first_failure < 10))
    )
    assert result.sipp_locked_shortfall_rate == pytest.approx(
        np.mean((locked & alive).any(axis=0))
    )
    assert result.strict_horizon_success_rate <= result.success_rate
    assert result.sipp_locked_shortfall_rate <= 1.0 - result.success_rate + 1e-12
    for year, row in zip(flows, result.year_breakdown, strict=True):
        assert row.shortfall_share == pytest.approx(np.mean(year.failed & year.alive))
        assert row.unmet_spending == pytest.approx(np.median(year.unmet_spending))
        assert row.contributions == pytest.approx(np.median(year.contributions))


@PROPERTY_SETTINGS
@given(inputs=uk_inputs(max_years=8))
def test_simulation_is_deterministic_for_a_seed(inputs):
    first = run_uk_simulation(inputs, progressive_tax)
    second = run_uk_simulation(inputs, progressive_tax)
    assert first.model_dump() == second.model_dump()


def _reference_draws(targets, balances, tfc_available, net_at):
    """Bisection for each path's smallest draw whose net proceeds cover its
    target (the whole balance when even that falls short)."""
    covered = net_at(balances) >= targets
    lo, hi = np.zeros_like(balances), balances.copy()
    for _ in range(80):
        if np.all(hi - lo < 1e-3):
            break
        mid = 0.5 * (lo + hi)
        ok = net_at(mid) >= targets
        hi = np.where(ok, mid, hi)
        lo = np.where(ok, lo, mid)
    return np.where(covered, hi, balances)


# Net proceeds per gross pound of SIPP draw never fall below this: the worst
# UK marginal rate on pension income is about 85 % (40 % tax in the personal
# allowance taper, x1.5, plus dividends pushed into the higher rate), and
# with the lump sum allowance used up none of the draw is tax-free.
MIN_NET_PER_POUND = 0.15


def _check_solver(rows, tax_fn):
    targets, balances, tfc_available, state_pension, dividends, employment = (
        np.array(column, dtype=float) for column in zip(*rows, strict=True)
    )
    n = len(targets)
    all_idx = np.arange(n)

    def tax(taxable, idx):
        return tax_fn(
            UKYearInputs(
                age=70,
                year=2026,
                state_pension=state_pension[idx],
                private_pension_income=taxable,
                savings_interest=np.zeros(len(idx)),
                dividend_income=dividends[idx],
                employment_income=employment[idx],
            )
        )

    def evaluate(draw, idx):
        return tax(draw - np.minimum(TFC_FRACTION * draw, tfc_available[idx]), idx)

    base = tax(np.zeros(n), all_idx)
    draw, income_tax, employee_ni = _solve_sipp_draw(targets, balances, base, evaluate)
    at_draw = evaluate(draw, all_idx)

    # The returned tax is the tax at the returned draw.
    assert np.allclose(income_tax, at_draw.income_tax, atol=1e-9)
    assert np.allclose(employee_ni, at_draw.employee_ni, atol=1e-9)
    assert np.all((draw >= 0) & (draw <= balances + ATOL))
    idle = (targets <= 0) | (balances <= 0)
    assert np.all(draw[idle] == 0.0)

    def net_at(d):
        return d - (evaluate(d, all_idx).total_tax - base.total_tax)

    net = net_at(draw)
    reference = _reference_draws(targets, balances, tfc_available, net_at)
    uncovered = ~idle & (draw >= balances - ATOL) & (net < targets)
    covered = ~idle & ~uncovered
    # Paths the whole balance cannot cover draw it all, and bisection agrees.
    assert np.allclose(reference[uncovered], balances[uncovered], atol=1e-3)
    # Covered paths are covered with at most the tolerance left over, and
    # sit within tolerance / (min net per pound) of the smallest such draw.
    surplus = net[covered] - targets[covered]
    assert np.all(surplus >= -ATOL)
    assert np.all(surplus <= _SIPP_SOLVER_TOLERANCE + ATOL)
    gap = draw[covered] - reference[covered]
    assert np.all(gap >= -2e-3)
    assert np.all(gap <= _SIPP_SOLVER_TOLERANCE / MIN_NET_PER_POUND + 0.01)


solver_rows = st.lists(
    st.tuples(
        st.floats(min_value=0.0, max_value=250_000.0),  # target net
        money,  # balance
        st.floats(min_value=0.0, max_value=LSA_CAP),  # tfc available
        st.floats(min_value=0.0, max_value=15_000.0),  # state pension
        st.floats(min_value=0.0, max_value=20_000.0),  # dividends
        st.one_of(st.just(0.0), st.floats(min_value=0.0, max_value=150_000.0)),
    ),
    min_size=1,
    max_size=12,
)


@settings(max_examples=200, deadline=None)
@given(rows=solver_rows)
def test_sipp_solver_matches_reference_bisection(rows):
    _check_solver(rows, progressive_tax)


# --- Real engine ------------------------------------------------------------


@settings(max_examples=15, deadline=None)
@given(rows=solver_rows)
def test_sipp_solver_matches_reference_bisection_real_engine(rows):
    _check_solver(rows, calculate_uk_tax)


@settings(max_examples=20, deadline=None)
@given(
    pension=st.floats(min_value=45_000.0, max_value=300_000.0),
    year=st.integers(min_value=2025, max_value=2035),
)
def test_scotland_taxes_pension_income_above_london_real_engine(pension, year):
    """Scottish rates exceed the rest-of-UK rates above about £30,000 of
    non-savings income, so Scotland always differs from London there."""

    def tax(region):
        return calculate_uk_tax(
            UKYearInputs(
                age=70,
                year=year,
                state_pension=np.zeros(1),
                private_pension_income=np.array([pension]),
                savings_interest=np.zeros(1),
                dividend_income=np.zeros(1),
                employment_income=np.zeros(1),
                region=region,
            )
        ).total_tax[0]

    assert tax("Scotland") > tax("London")


@settings(max_examples=6, deadline=None)
@given(inputs=uk_inputs(max_years=4))
def test_spending_identity_holds_with_real_engine(inputs):
    """The identity and conservation hold with the real PolicyEngine tax."""
    for f in iterate_uk_year_flows(inputs, calculate_uk_tax):
        lhs = (
            f.withdrawals
            - f.reinvested_dividends
            + f.net_income
            - f.contributions
            + f.unmet_spending
            - f.excess_income
        )
        assert _close(lhs, f.spending_target)
        assert _close(
            f.sipp_end,
            (f.sipp_start + f.contribution_sipp - f.withdrawal_sipp) * f.wrapper_growth,
        )
        drew = f.withdrawals > 0
        surplus = f.reinvested_dividends + f.excess_income
        assert np.all(surplus[drew] <= _SIPP_SOLVER_TOLERANCE + ATOL)
