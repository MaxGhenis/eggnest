"""Monte Carlo retirement simulator — UK edition.

Skinny first cut: single person, three UK account types (ISA, SIPP, GIA),
State Pension + private income + employment, UK income tax + NI + dividend
tax via policyengine-uk-compiled. No annuities, no couples, no UC interaction
yet — those land as follow-ups.

Each simulated year, per path:

1. Pension and ISA contributions (``savings_rate`` of gross earnings) move
   from pay into the SIPP and ISA.
2. Income tax and employee NI are computed on employment income, State
   Pension, GIA dividends and the taxable part of any SIPP draw.
3. Any shortfall between that net income (less contributions) and the
   spending target is withdrawn from the GIA, then the ISA, then (from
   Minimum Pension Age) the SIPP. SIPP draws are sized against the actual tax
   they trigger.
4. Spending the accounts cannot cover is recorded as unmet spending. A path
   fails in the first year it is alive with more than ``UNMET_TOLERANCE`` of
   unmet spending.
5. GIA dividends not needed for spending are reinvested in the GIA. ISA and
   SIPP balances earn the total return (price growth plus dividends, which
   reinvest inside the wrapper); the GIA earns price growth, because its
   dividends are paid out as taxable cash in step 2.

Paths keep simulating after death so the strict-horizon measures can ignore
mortality; mortality only decides which years count toward ``success_rate``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from .earnings_uk import sample_earnings_paths
from .historical_returns_uk import sample_historical_returns
from .models_uk import (
    UKAccountType,
    UKSimulationInput,
    UKSimulationResult,
    UKYearBreakdown,
)
from .mortality import generate_alive_mask
from .tax_uk import UKYearInputs, UKYearResults, calculate_uk_tax

UKTaxCalculator = Callable[[UKYearInputs], UKYearResults]

# Minimum Pension Age — earliest age at which SIPP funds can be accessed.
# Currently 55 in the UK, rising to 57 from April 2028. We use 55 as a simple
# default; the rise affects only paths where current_age is 55/56 in 2028+.
MPA = 55

# Lifetime Lump Sum Allowance — total tax-free cash a person can take across
# their whole retirement (2024/25 figure, £268,275). Cross-path accumulation
# is tracked per path in _PathState.tfc_used.
LSA_CAP = 268_275.0

# Fraction of an uncrystallised SIPP drawdown that can be taken tax-free
# (UFPLS): 25 % tax-free, 75 % subject to income tax.
TFC_FRACTION = 0.25

# Basic-rate UK income tax. Only the opening guess for the SIPP draw size;
# the draw is then solved against the tax PolicyEngine actually computes.
BASIC_RATE = 0.20

# A year with more than this much unmet spending (nominal £) is a failed
# year; smaller gaps are rounding in the SIPP draw solver.
UNMET_TOLERANCE = 1.0

# The SIPP draw solver accepts a draw whose net proceeds cover the shortfall
# with at most this much (£) left over, trying at most
# _SIPP_SOLVER_MAX_ITERATIONS draw sizes per year. PolicyEngine rounds tax to
# the penny, so a tighter window only costs extra tax runs.
_SIPP_SOLVER_TOLERANCE = 0.5
_SIPP_SOLVER_MAX_ITERATIONS = 12


@dataclass
class _PathState:
    gia: np.ndarray
    isa: np.ndarray
    sipp: np.ndarray
    tfc_used: np.ndarray  # tax-free cash taken so far, capped by LSA_CAP
    # First year a living path had unmet spending, -1 if none.
    failure_year: np.ndarray
    # First year with unmet spending, ignoring mortality, -1 if none.
    horizon_failure_year: np.ndarray
    # Whether a living path ever had unmet spending while its SIPP held
    # money it could not yet draw (before Minimum Pension Age).
    sipp_locked_shortfall: np.ndarray


@dataclass
class UKYearFlows:
    """Per-path cash flows for one simulated year, all nominal £.

    Balances satisfy, for every path::

        gia_end  = (gia_start - withdrawal_gia) * gia_growth + reinvested_dividends
        isa_end  = (isa_start + contribution_isa - withdrawal_isa) * wrapper_growth
        sipp_end = (sipp_start + contribution_sipp - withdrawal_sipp) * wrapper_growth

    and spending is fully accounted for::

        withdrawals - reinvested_dividends + net_income - contributions
            + unmet_spending - excess_income == spending_target

    where ``withdrawals`` is the gross total taken from all three accounts,
    ``net_income`` is employment income, State Pension and GIA dividends less
    all income tax and employee NI (including the tax on SIPP draws), and
    ``excess_income`` is income above the spending target and contributions
    that is not GIA dividends. Excess income is treated as spent, matching
    the US simulator.
    """

    year_index: int
    age: int
    alive: np.ndarray
    spending_target: np.ndarray
    employment_income: np.ndarray
    state_pension: np.ndarray
    gia_dividends: np.ndarray
    gia_start: np.ndarray
    isa_start: np.ndarray
    sipp_start: np.ndarray
    contribution_isa: np.ndarray
    contribution_sipp: np.ndarray
    withdrawal_gia: np.ndarray
    withdrawal_isa: np.ndarray
    withdrawal_sipp: np.ndarray
    sipp_tax_free_cash: np.ndarray
    income_tax: np.ndarray
    employee_ni: np.ndarray
    total_tax: np.ndarray
    net_income: np.ndarray
    unmet_spending: np.ndarray
    reinvested_dividends: np.ndarray
    excess_income: np.ndarray
    sipp_locked: np.ndarray  # unmet spending while the SIPP was locked
    gia_growth: np.ndarray  # 1 + price growth
    wrapper_growth: np.ndarray  # 1 + total return
    gia_end: np.ndarray
    isa_end: np.ndarray
    sipp_end: np.ndarray

    @property
    def contributions(self) -> np.ndarray:
        return self.contribution_isa + self.contribution_sipp

    @property
    def withdrawals(self) -> np.ndarray:
        return self.withdrawal_gia + self.withdrawal_isa + self.withdrawal_sipp

    @property
    def portfolio_start(self) -> np.ndarray:
        return self.gia_start + self.isa_start + self.sipp_start

    @property
    def portfolio_end(self) -> np.ndarray:
        return self.gia_end + self.isa_end + self.sipp_end

    @property
    def failed(self) -> np.ndarray:
        """Paths with more than ``UNMET_TOLERANCE`` of unmet spending."""
        return self.unmet_spending > UNMET_TOLERANCE


def _simulate_returns_gaussian(
    n_sims: int,
    n_years: int,
    expected_return: float,
    volatility: float,
    dividend_yield: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Gaussian IID total returns split into (price_growth, dividend_yield)."""
    total_returns = rng.normal(expected_return, volatility, size=(n_sims, n_years))
    price_growth = total_returns - dividend_yield
    div_yield = np.full((n_sims, n_years), dividend_yield)
    return price_growth, div_yield


def _simulate_inflation_gaussian(
    n_sims: int, n_years: int, rate: float, rng: np.random.Generator
) -> np.ndarray:
    """Fixed-rate inflation with small noise (only used when return_source='gaussian')."""
    noise = rng.normal(0.0, 0.005, size=(n_sims, n_years))
    return np.clip(rate + noise, -0.02, 0.15)


def _build_return_paths(
    inputs: UKSimulationInput,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
    """Return (price_growth, dividend_yield, inflation, start_years).

    Arrays are shaped ``(n_sims, n_years)`` except ``start_years`` which is
    ``(n_sims,)`` and only populated for ``return_source=='historical_sequential'``;
    it is ``None`` for gaussian / shuffled bootstrap / block bootstrap since
    those don't have a single interpretable start year per path.

    For historical sources: blended equity/gilt total return is split into a
    capital-growth component (total minus the portfolio's effective dividend
    yield) and an income component ``effective_yield = dividend_yield *
    equity_weight``. Price growth plus yield is always the total return.
    """
    n_sims = inputs.n_simulations
    n_years = inputs.max_age - inputs.current_age + 1

    if inputs.return_source == "gaussian":
        price_growth, div_yield = _simulate_returns_gaussian(
            n_sims,
            n_years,
            inputs.expected_return,
            inputs.return_volatility,
            inputs.dividend_yield,
            rng,
        )
        inflation = _simulate_inflation_gaussian(
            n_sims, n_years, inputs.inflation_rate, rng
        )
        return price_growth, div_yield, inflation, None

    equity_ret, bond_ret, inflation, start_years = sample_historical_returns(
        inputs.return_source, n_sims, n_years, rng
    )
    w = inputs.equity_weight
    total_return = w * equity_ret + (1.0 - w) * bond_ret
    effective_div_yield = w * inputs.dividend_yield  # gilts don't pay dividends
    price_growth = total_return - effective_div_yield
    div_yield = np.full((n_sims, n_years), effective_div_yield)
    return price_growth, div_yield, inflation, start_years


def _withdraw(
    state: _PathState,
    needed: np.ndarray,
    order: tuple[UKAccountType, ...],
) -> tuple[np.ndarray, dict[UKAccountType, np.ndarray]]:
    """Pull ``needed`` from accounts in order, return (withdrawn, per-account)."""
    withdrawn_per_account: dict[UKAccountType, np.ndarray] = {
        "gia": np.zeros_like(needed),
        "isa": np.zeros_like(needed),
        "sipp": np.zeros_like(needed),
    }
    remaining = needed.copy()
    for account in order:
        if account == "gia":
            balance = state.gia
        elif account == "isa":
            balance = state.isa
        else:
            balance = state.sipp
        take = np.minimum(remaining, balance)
        withdrawn_per_account[account] = take
        if account == "gia":
            state.gia = state.gia - take
        elif account == "isa":
            state.isa = state.isa - take
        else:
            state.sipp = state.sipp - take
        remaining = remaining - take
    total_withdrawn = needed - remaining
    return total_withdrawn, withdrawn_per_account


def _tax_free_cash(draw: np.ndarray, tfc_available: np.ndarray) -> np.ndarray:
    """UFPLS tax-free cash on a gross SIPP draw, capped by the remaining LSA."""
    return np.minimum(TFC_FRACTION * draw, tfc_available)


@dataclass
class _YearTax:
    """One year's tax for each path, as a function of its taxable SIPP draw."""

    calculator: UKTaxCalculator
    age: int
    year: int
    region: str
    state_pension: np.ndarray
    dividends: np.ndarray
    employment: np.ndarray

    def __call__(
        self, taxable_sipp: np.ndarray, idx: np.ndarray | None = None
    ) -> UKYearResults:
        sel = slice(None) if idx is None else idx
        return self.calculator(
            UKYearInputs(
                age=self.age,
                year=self.year,
                state_pension=self.state_pension[sel],
                private_pension_income=taxable_sipp,
                savings_interest=np.zeros(len(taxable_sipp)),
                dividend_income=self.dividends[sel],
                employment_income=self.employment[sel],
                region=self.region,
            )
        )

    def sipp_draw_evaluator(
        self, tfc_available: np.ndarray
    ) -> Callable[[np.ndarray, np.ndarray], UKYearResults]:
        """Tax for paths ``idx`` drawing ``draw`` gross from the SIPP."""

        def evaluate(draw: np.ndarray, idx: np.ndarray) -> UKYearResults:
            return self(draw - _tax_free_cash(draw, tfc_available[idx]), idx)

        return evaluate


def _solve_sipp_draw(
    target_net: np.ndarray,
    balance: np.ndarray,
    base_tax: UKYearResults,
    evaluate: Callable[[np.ndarray, np.ndarray], UKYearResults],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Size the gross SIPP draw whose after-tax proceeds cover ``target_net``.

    ``evaluate(draw, idx)`` returns the tax for paths ``idx`` when they draw
    ``draw`` gross from the SIPP; ``base_tax`` is the tax with no draw. Net
    proceeds ``g(D) = D - (tax(D) - base_tax)`` rise with the draw because
    marginal tax is below 100 %, and are piecewise linear because UK tax is.
    Each step is a secant through the two latest draws (the first assumes
    the basic-rate slope), which lands exactly once both draws sit on one
    linear piece; a step that leaves the bracket known to hold the answer
    bisects instead. The accepted draw over-covers the target by at most
    ``_SIPP_SOLVER_TOLERANCE``, so solver error never shows up as unmet
    spending. Paths whose whole balance cannot cover the target draw it all.

    Returns ``(draw, income_tax, employee_ni)`` for every path; the tax
    arrays hold the tax at the returned draw.
    """
    draw = np.zeros_like(target_net)
    income_tax = base_tax.income_tax.copy()
    employee_ni = base_tax.employee_ni.copy()
    active = np.flatnonzero((target_net > 0) & (balance > 0))
    if active.size == 0:
        return draw, income_tax, employee_ni

    cap = balance[active]
    base = base_tax.total_tax[active]
    # Aim at the middle of the acceptance window [0, tolerance] of surplus.
    half_tol = 0.5 * _SIPP_SOLVER_TOLERANCE
    aim = target_net[active] + half_tol
    # Net proceeds per gross pound when 75 % of the draw is taxed at basic
    # rate: the slope assumed for the first step.
    basic_slope = 1.0 - (1.0 - TFC_FRACTION) * BASIC_RATE

    m = active.size
    lo = np.zeros(m)  # largest draw known to under-cover
    hi = cap.copy()  # smallest draw known (or assumed) to over-cover
    hi_known = np.zeros(m, dtype=bool)
    prev_x = np.full(m, np.nan)
    prev_h = np.full(m, np.nan)
    best = np.full(m, np.nan)
    open_ = np.ones(m, dtype=bool)
    x = np.minimum(aim / basic_slope, cap)

    def record(rows: np.ndarray, x_rows: np.ndarray, res: UKYearResults, mask):
        best[rows[mask]] = x_rows[mask]
        income_tax[active[rows[mask]]] = res.income_tax[mask]
        employee_ni[active[rows[mask]]] = res.employee_ni[mask]

    for _ in range(_SIPP_SOLVER_MAX_ITERATIONS):
        run = np.flatnonzero(open_)
        if run.size == 0:
            break
        x_run = x[run]
        res = evaluate(x_run, active[run])
        h = x_run - (res.total_tax - base[run]) - aim[run]

        accepted = np.abs(h) <= half_tol
        short_at_cap = (h < -half_tol) & (x_run >= cap[run])
        above = h > half_tol
        # Accepted, whole-balance and over-covering draws are all usable;
        # the latest over-covering draw is the fallback if the budget runs
        # out.
        record(run, x_run, res, accepted | short_at_cap | above)
        open_[run[accepted | short_at_cap]] = False
        hi[run[above]] = x_run[above]
        hi_known[run[above]] = True
        below = (h < -half_tol) & ~short_at_cap
        lo[run[below]] = x_run[below]

        dx = x_run - prev_x[run]
        slope = np.where(
            np.isnan(dx) | (dx == 0.0), basic_slope, (h - prev_h[run]) / dx
        )
        step = x_run - h / np.where(slope > 0, slope, basic_slope)
        # Stay strictly inside the bracket, bisecting when a step would not.
        # A step past the whole balance before any draw has over-covered
        # tries the whole balance, which settles paths that cannot be
        # covered in one tax run.
        inside = (step > lo[run]) & (step < hi[run])
        try_cap = ~inside & ~hi_known[run] & (step >= hi[run])
        x[run] = np.where(
            inside, step, np.where(try_cap, cap[run], 0.5 * (lo[run] + hi[run]))
        )
        prev_x[run] = x_run
        prev_h[run] = h
        open_[run] &= (hi[run] - lo[run]) > 1e-6

    # Paths that never over-covered within the iteration budget draw their
    # whole balance (rare: only a pathologically flat tax response).
    unresolved = np.flatnonzero(np.isnan(best))
    if unresolved.size:
        res = evaluate(cap[unresolved], active[unresolved])
        record(unresolved, cap[unresolved], res, np.ones(unresolved.size, dtype=bool))

    draw[active] = best
    return draw, income_tax, employee_ni


def _iterate_years(
    inputs: UKSimulationInput,
    rng: np.random.Generator,
    tax_calculator: UKTaxCalculator,
) -> Iterator[tuple[UKYearBreakdown, _PathState, UKYearFlows, np.ndarray | None]]:
    """Iterate year-by-year over the simulation.

    Yields ``(breakdown, state, flows, start_years)`` where ``start_years`` is
    the per-path historical-year array in sequential mode (repeated each
    yield for convenience) or ``None`` otherwise.
    """
    n_sims = inputs.n_simulations
    n_years = inputs.max_age - inputs.current_age + 1
    start_year = datetime.now().year

    price_growth, div_yield, inflation_paths, start_years = _build_return_paths(
        inputs, rng
    )

    ages_per_year = np.arange(
        inputs.current_age, inputs.current_age + n_years, dtype=np.int64
    )
    earnings_paths = sample_earnings_paths(
        n_sims=n_sims,
        ages=ages_per_year,
        starting_earnings=inputs.employment_income,
        retirement_age=inputs.retirement_age,
        model=inputs.earnings_model,
        persistent_sigma=inputs.earnings_persistent_sigma,
        transitory_sigma=inputs.earnings_transitory_sigma,
        persistence=inputs.earnings_persistence,
        peak_growth=inputs.earnings_profile_peak_growth,
        rng=rng,
    )

    alive_mask = (
        generate_alive_mask(
            n_sims,
            n_years,
            inputs.current_age,
            inputs.gender,
            rng,
        )
        if inputs.include_mortality
        else np.ones((n_sims, n_years + 1), dtype=bool)
    )

    state = _PathState(
        gia=np.full(n_sims, float(inputs.gia_balance)),
        isa=np.full(n_sims, float(inputs.isa_balance)),
        sipp=np.full(n_sims, float(inputs.sipp_balance)),
        tfc_used=np.zeros(n_sims),
        failure_year=np.full(n_sims, -1),
        horizon_failure_year=np.full(n_sims, -1),
        sipp_locked_shortfall=np.zeros(n_sims, dtype=bool),
    )
    cumulative_inflation = np.ones(n_sims)
    zeros = np.zeros(n_sims)

    for year_idx in range(n_years):
        age = inputs.current_age + year_idx
        calendar_year = start_year + year_idx
        alive = alive_mask[:, year_idx]

        cumulative_inflation = cumulative_inflation * (
            1.0 + inflation_paths[:, year_idx]
        )
        spending_target = inputs.annual_spending * (
            cumulative_inflation if inputs.spending_mode == "real" else np.ones(n_sims)
        )

        gia_start = state.gia.copy()
        isa_start = state.isa.copy()
        sipp_start = state.sipp.copy()

        # Employment income per path (zero past retirement_age enforced in
        # sample_earnings_paths). Stochastic trajectories diverge across sims.
        employment = earnings_paths[:, year_idx]
        # State Pension only from state_pension_start_age
        sp_val = (
            float(inputs.state_pension_annual)
            if age >= inputs.state_pension_start_age
            else 0.0
        )
        state_pension = np.full(n_sims, sp_val)

        # GIA dividends are paid out as taxable cash on the opening balance.
        gia_dividends = state.gia * div_yield[:, year_idx]

        # Contributions: savings_rate of gross pay goes into the SIPP and
        # ISA. The money comes out of pay, so it is not available to spend.
        contributions_total = employment * inputs.savings_rate
        contribution_sipp = contributions_total * inputs.sipp_contribution_share
        contribution_isa = contributions_total - contribution_sipp
        state.sipp = state.sipp + contribution_sipp
        state.isa = state.isa + contribution_isa

        tax_for = _YearTax(
            calculator=tax_calculator,
            age=age,
            year=calendar_year,
            region=inputs.region,
            state_pension=state_pension,
            dividends=gia_dividends,
            employment=employment,
        )
        base_tax = tax_for(zeros)
        non_wrapper_income = employment + state_pension + gia_dividends
        # Cash to find from the accounts before any SIPP draw is taxed.
        shortfall = np.maximum(
            spending_target
            - (non_wrapper_income - base_tax.total_tax)
            + contributions_total,
            0.0,
        )
        # Withdrawal order: GIA, then ISA, then SIPP — use the most-taxed
        # money first and preserve tax-sheltered growth.
        _, per_account = _withdraw(state, shortfall, ("gia", "isa"))
        still_short = shortfall - per_account["gia"] - per_account["isa"]

        # SIPP is locked until Minimum Pension Age. From MPA, draw enough
        # that the proceeds after the tax the draw triggers cover the rest.
        sipp_draw = zeros.copy()
        tax_free_cash = zeros.copy()
        tax = base_tax
        if age >= MPA and np.any((still_short > 0) & (state.sipp > 0)):
            tfc_available = np.maximum(LSA_CAP - state.tfc_used, 0.0)
            sipp_draw, income_tax, employee_ni = _solve_sipp_draw(
                still_short,
                state.sipp,
                base_tax,
                tax_for.sipp_draw_evaluator(tfc_available),
            )
            sipp_draw = np.minimum(sipp_draw, state.sipp)
            tax_free_cash = _tax_free_cash(sipp_draw, tfc_available)
            state.sipp = state.sipp - sipp_draw
            state.tfc_used = state.tfc_used + tax_free_cash
            direct_tax = income_tax + employee_ni
            tax = UKYearResults(
                net_income=non_wrapper_income + sipp_draw - tax_free_cash - direct_tax,
                total_tax=direct_tax,
                income_tax=income_tax,
                employee_ni=employee_ni,
            )

        net_income = non_wrapper_income - tax.total_tax
        withdrawals = per_account["gia"] + per_account["isa"] + sipp_draw
        cash = withdrawals + net_income - contributions_total
        unmet = np.maximum(spending_target - cash, 0.0)
        surplus = np.maximum(cash - spending_target, 0.0)
        # Unspent GIA dividends go back into the GIA; any other surplus
        # (earnings or State Pension above spending plus contributions) is
        # treated as spent.
        reinvested = np.minimum(surplus, gia_dividends)
        excess_income = surplus - reinvested

        # A living year with unmet spending fails the path. It is
        # SIPP-locked when the SIPP held money the person could not draw yet.
        failed = unmet > UNMET_TOLERANCE
        sipp_locked = failed & (age < MPA) & (state.sipp > 0)
        state.horizon_failure_year = np.where(
            failed & (state.horizon_failure_year == -1),
            year_idx,
            state.horizon_failure_year,
        )
        state.failure_year = np.where(
            failed & alive & (state.failure_year == -1),
            year_idx,
            state.failure_year,
        )
        state.sipp_locked_shortfall = state.sipp_locked_shortfall | (
            sipp_locked & alive
        )

        # Growth on the balances left after this year's flows. ISA and SIPP
        # dividends reinvest inside the wrapper, so they earn the total
        # return; the GIA's dividends were paid out above. A loss can wipe
        # out a balance but never take it below zero.
        gia_growth = np.maximum(1.0 + price_growth[:, year_idx], 0.0)
        wrapper_growth = np.maximum(
            1.0 + price_growth[:, year_idx] + div_yield[:, year_idx], 0.0
        )
        # Dividends arrive through the year, so the reinvested amount joins
        # the GIA after this year's price growth.
        state.gia = state.gia * gia_growth + reinvested
        state.isa = state.isa * wrapper_growth
        state.sipp = state.sipp * wrapper_growth

        flows = UKYearFlows(
            year_index=year_idx,
            age=age,
            alive=alive,
            spending_target=spending_target,
            employment_income=employment,
            state_pension=state_pension,
            gia_dividends=gia_dividends,
            gia_start=gia_start,
            isa_start=isa_start,
            sipp_start=sipp_start,
            contribution_isa=contribution_isa,
            contribution_sipp=contribution_sipp,
            withdrawal_gia=per_account["gia"],
            withdrawal_isa=per_account["isa"],
            withdrawal_sipp=sipp_draw,
            sipp_tax_free_cash=tax_free_cash,
            income_tax=tax.income_tax,
            employee_ni=tax.employee_ni,
            total_tax=tax.total_tax,
            net_income=net_income,
            unmet_spending=unmet,
            reinvested_dividends=reinvested,
            excess_income=excess_income,
            sipp_locked=sipp_locked,
            gia_growth=gia_growth,
            wrapper_growth=wrapper_growth,
            gia_end=state.gia.copy(),
            isa_end=state.isa.copy(),
            sipp_end=state.sipp.copy(),
        )

        # Gross income: the whole SIPP draw, tax-free cash included.
        gross_income = non_wrapper_income + sipp_draw
        breakdown = UKYearBreakdown(
            year_index=year_idx,
            age=age,
            portfolio_start=float(np.median(flows.portfolio_start)),
            portfolio_end=float(np.median(flows.portfolio_end)),
            spending_target=float(np.median(spending_target)),
            total_income=float(np.median(net_income + withdrawals)),
            net_income=float(np.median(net_income)),
            withdrawal=float(np.median(withdrawals)),
            contributions=float(np.median(contributions_total)),
            unmet_spending=float(np.median(unmet)),
            shortfall_share=float(np.mean(failed & alive)),
            sipp_locked_shortfall_share=float(np.mean(sipp_locked & alive)),
            reinvested_dividends=float(np.median(reinvested)),
            total_tax=float(np.median(tax.total_tax)),
            inflation_rate=float(np.median(inflation_paths[:, year_idx])),
            portfolio_return=float(
                np.median(price_growth[:, year_idx] + div_yield[:, year_idx])
            ),
            effective_tax_rate=float(
                np.median(
                    np.divide(
                        tax.total_tax,
                        gross_income,
                        out=np.zeros(n_sims),
                        where=gross_income > 0,
                    )
                )
            ),
            state_pension=float(np.median(state_pension)),
            employment_income=float(np.median(employment)),
            sipp_withdrawal=float(np.median(sipp_draw)),
            isa_withdrawal=float(np.median(per_account["isa"])),
            gia_withdrawal=float(np.median(per_account["gia"])),
        )
        yield breakdown, state, flows, start_years


def iterate_uk_year_flows(
    inputs: UKSimulationInput,
    tax_calculator: UKTaxCalculator | None = None,
) -> Iterator[UKYearFlows]:
    """Yield each simulated year's per-path cash flows.

    Uses the same seeded random draws as ``run_uk_simulation``, so the flows
    are exactly the ones behind its aggregated result.
    """
    rng = np.random.default_rng(inputs.random_seed)
    for _, _, flows, _ in _iterate_years(
        inputs, rng, tax_calculator or calculate_uk_tax
    ):
        yield flows


def _percentile_path_start_years(
    final_portfolio: np.ndarray,
    start_years: np.ndarray,
) -> dict[str, int]:
    """For each tracked percentile, return the start year of the sim whose
    final portfolio value is closest to that percentile.

    Percentile *paths* are quantile traces across sims — no one sim owns the
    p50 line. This picks a representative cohort per percentile: the sim
    whose endpoint matches the quantile's endpoint, and reports its start
    year. Ties break on the first occurrence (lowest sim index).
    """
    out: dict[str, int] = {}
    for p in (5, 25, 50, 75, 95):
        target = float(np.percentile(final_portfolio, p))
        idx = int(np.argmin(np.abs(final_portfolio - target)))
        out[f"p{p}"] = int(start_years[idx])
    return out


_PERCENTILES = (5, 25, 50, 75, 95)


def _bands(arr: np.ndarray) -> dict[str, list[float]]:
    """Return {'p5','p25','p50','p75','p95': list[float]} for a (n_sims, n_years) array."""
    rows = np.percentile(arr, _PERCENTILES, axis=0)  # one sort per column, 5× cheaper
    return {f"p{p}": rows[i].tolist() for i, p in enumerate(_PERCENTILES)}


def _assemble_result(
    inputs: UKSimulationInput,
    year_breakdown: list[UKYearBreakdown],
    final_state: _PathState,
    portfolio_over_time: np.ndarray,
    tax_over_time: np.ndarray,
    earnings_over_time: np.ndarray,
    start_years: np.ndarray | None,
) -> UKSimulationResult:
    final_portfolio = final_state.gia + final_state.isa + final_state.sipp
    final_quantiles = np.percentile(final_portfolio, _PERCENTILES)

    median_inflation_path = float(
        np.prod([1.0 + b.inflation_rate for b in year_breakdown])
    )
    percentiles = {
        f"p{p}": float(q) for p, q in zip(_PERCENTILES, final_quantiles, strict=True)
    }
    percentiles_real = {k: v / median_inflation_path for k, v in percentiles.items()}

    total_portfolio_start = (
        inputs.gia_balance + inputs.isa_balance + inputs.sipp_balance
    )
    initial_withdrawal_rate = (
        (inputs.annual_spending / total_portfolio_start * 100.0)
        if total_portfolio_start > 0
        else 0.0
    )

    horizon = min(10, len(year_breakdown))
    first_10_failed = (final_state.failure_year != -1) & (
        final_state.failure_year < horizon
    )

    percentile_path_start_years = (
        _percentile_path_start_years(final_portfolio, start_years)
        if start_years is not None
        else None
    )

    return UKSimulationResult(
        metadata={
            "n_simulations": inputs.n_simulations,
            "current_age": inputs.current_age,
            "max_age": inputs.max_age,
            "random_seed": inputs.random_seed,
        },
        success_rate=float(np.mean(final_state.failure_year == -1)),
        strict_horizon_success_rate=float(
            np.mean(final_state.horizon_failure_year == -1)
        ),
        sipp_locked_shortfall_rate=float(np.mean(final_state.sipp_locked_shortfall)),
        median_final_value=float(np.median(final_portfolio)),
        median_final_value_real=float(
            np.median(final_portfolio) / median_inflation_path
        ),
        percentiles=percentiles,
        percentiles_real=percentiles_real,
        percentile_paths=_bands(portfolio_over_time),
        tax_percentile_paths=_bands(tax_over_time),
        earnings_percentile_paths=_bands(earnings_over_time),
        year_breakdown=year_breakdown,
        initial_withdrawal_rate=initial_withdrawal_rate,
        prob_10_year_failure=float(np.mean(first_10_failed)),
        percentile_path_start_years=percentile_path_start_years,
    )


def run_uk_simulation_with_progress(
    inputs: UKSimulationInput,
    tax_calculator: UKTaxCalculator | None = None,
):
    """Generator yielding per-year progress events then a final ``result`` event.

    ``run_uk_simulation`` is a thin wrapper around this that filters out
    progress events and returns the final ``UKSimulationResult`` — shared
    aggregation logic lives in ``_assemble_result`` so there's only one
    place to change post-loop behaviour.
    """
    rng = np.random.default_rng(inputs.random_seed)
    n_sims = inputs.n_simulations
    n_years = inputs.max_age - inputs.current_age + 1

    portfolio_over_time = np.empty((n_sims, n_years), dtype=np.float64)
    tax_over_time = np.empty((n_sims, n_years), dtype=np.float64)
    earnings_over_time = np.empty((n_sims, n_years), dtype=np.float64)

    year_breakdown: list[UKYearBreakdown] = []
    final_state: _PathState | None = None
    start_years: np.ndarray | None = None

    for breakdown, state, flows, sy in _iterate_years(
        inputs, rng, tax_calculator or calculate_uk_tax
    ):
        year_idx = flows.year_index
        year_breakdown.append(breakdown)
        portfolio_over_time[:, year_idx] = flows.portfolio_end
        tax_over_time[:, year_idx] = flows.total_tax
        earnings_over_time[:, year_idx] = flows.employment_income
        final_state = state
        start_years = sy  # stable across yields; we just need the last value
        yield {
            "type": "progress",
            "current_year": year_idx + 1,
            "total_years": n_years,
        }

    assert final_state is not None
    result = _assemble_result(
        inputs,
        year_breakdown,
        final_state,
        portfolio_over_time,
        tax_over_time,
        earnings_over_time,
        start_years,
    )
    yield {"type": "result", "result": result.model_dump()}


def run_uk_simulation(
    inputs: UKSimulationInput,
    tax_calculator: UKTaxCalculator | None = None,
) -> UKSimulationResult:
    """Run the full UK Monte Carlo simulation and return the aggregated result.

    Drains the streaming generator so all post-loop logic lives in exactly
    one place (``_assemble_result``).
    """
    result: UKSimulationResult | None = None
    for event in run_uk_simulation_with_progress(inputs, tax_calculator):
        if event["type"] == "result":
            result = UKSimulationResult.model_validate(event["result"])
    assert result is not None
    return result
