"""Monte Carlo retirement simulator — UK edition.

Skinny first cut: single person, three UK account types (ISA, SIPP, GIA),
State Pension + private income + employment, UK income tax + NI + dividend
tax via policyengine-uk-compiled. No annuities, no couples, no UC interaction
yet — those land as follow-ups.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

import numpy as np

from .models_uk import (
    UKAccountType,
    UKSimulationInput,
    UKSimulationResult,
    UKYearBreakdown,
)
from .mortality import generate_alive_mask
from .tax_uk import UKYearInputs, calculate_uk_tax

START_YEAR = datetime.now().year

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

# Withdrawal order (taxable/GIA first, then ISA, then SIPP — roughly
# tax-efficient: use the most-taxed money first, preserve tax-sheltered growth).
DEFAULT_WITHDRAWAL_ORDER: tuple[UKAccountType, ...] = ("gia", "isa", "sipp")


@dataclass
class _PathState:
    gia: np.ndarray
    isa: np.ndarray
    sipp: np.ndarray
    tfc_used: np.ndarray  # tax-free cash taken so far, capped by LSA_CAP
    depleted_year: np.ndarray  # -1 until depleted


def _simulate_returns(
    n_sims: int,
    n_years: int,
    expected_return: float,
    volatility: float,
    dividend_yield: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Simple geometric Brownian motion with a dividend split.

    Returns (price_growth, dividend_yield) arrays of shape (n_sims, n_years).
    Price growth is the capital appreciation portion; the dividend yield is
    paid out as income each year. This keeps parity with the US model's
    dividend-yield split so taxable-account treatment is straightforward.
    """
    total_returns = rng.normal(expected_return, volatility, size=(n_sims, n_years))
    price_growth = total_returns - dividend_yield
    div_yield = np.full((n_sims, n_years), dividend_yield)
    return price_growth, div_yield


def _simulate_inflation(
    n_sims: int, n_years: int, rate: float, rng: np.random.Generator
) -> np.ndarray:
    """Fixed-rate inflation with small random noise (placeholder).

    UK-specific historical CPI sampling is a follow-up.
    """
    noise = rng.normal(0.0, 0.005, size=(n_sims, n_years))
    return np.clip(rate + noise, -0.02, 0.15)


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


def _iterate_years(
    inputs: UKSimulationInput,
    rng: np.random.Generator,
) -> Iterator[tuple[int, UKYearBreakdown, _PathState]]:
    n_sims = inputs.n_simulations
    n_years = inputs.max_age - inputs.current_age + 1

    price_growth, div_yield = _simulate_returns(
        n_sims,
        n_years,
        inputs.expected_return,
        inputs.return_volatility,
        inputs.dividend_yield,
        rng,
    )
    inflation_paths = _simulate_inflation(n_sims, n_years, inputs.inflation_rate, rng)

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
        depleted_year=np.full(n_sims, -1),
    )
    cumulative_inflation = np.ones(n_sims)

    for year_idx in range(n_years):
        age = inputs.current_age + year_idx
        calendar_year = START_YEAR + year_idx

        cumulative_inflation = cumulative_inflation * (1.0 + inflation_paths[:, year_idx])
        spending_target_nominal = inputs.annual_spending * (
            cumulative_inflation if inputs.spending_mode == "real" else np.ones(n_sims)
        )

        # Employment income only until retirement_age
        employment_val = (
            float(inputs.employment_income)
            if age < inputs.retirement_age
            else 0.0
        )
        employment = np.full(n_sims, employment_val)
        # State Pension only from state_pension_start_age
        sp_val = (
            float(inputs.state_pension_annual)
            if age >= inputs.state_pension_start_age
            else 0.0
        )
        state_pension_annual = np.full(n_sims, sp_val)

        # GIA yields (dividends + savings interest are both taxable income)
        gia_dividends = state.gia * div_yield[:, year_idx]

        # Compute tax on sources that flow through income tax (not ISA):
        # employment, State Pension, GIA dividends are known. SIPP drawdown is
        # resolved iteratively once we know the shortfall.
        needed = spending_target_nominal.copy()

        tax_inputs = UKYearInputs(
            age=age,
            year=calendar_year,
            state_pension=state_pension_annual,
            private_pension_income=np.zeros(n_sims),
            savings_interest=np.zeros(n_sims),
            dividend_income=gia_dividends,
            employment_income=employment,
        )
        tax = calculate_uk_tax(tax_inputs)
        net_before_withdrawals = tax.net_income

        # Determine withdrawal needed: shortfall after net income from
        # employment/SP/GIA dividends.
        shortfall = np.maximum(needed - net_before_withdrawals, 0.0)

        # Pre-MPA paths can't access the SIPP; drop it from the withdrawal
        # order until the person reaches MPA.
        withdrawal_order: tuple[UKAccountType, ...] = (
            DEFAULT_WITHDRAWAL_ORDER
            if age >= MPA
            else tuple(a for a in DEFAULT_WITHDRAWAL_ORDER if a != "sipp")
        )
        total_withdrawn, per_account = _withdraw(state, shortfall, withdrawal_order)

        # Second pass: SIPP drawdowns are partially taxed. Under UFPLS, 25 %
        # is tax-free (subject to the lifetime LSA cap) and 75 % is income-
        # taxable. The GIA + ISA withdrawals we already took are entirely
        # tax-free, so the only gross-up we need is on the SIPP portion.
        sipp_take = per_account["sipp"]
        if np.any(sipp_take > 0):
            # Tax-free proportion of this SIPP draw, capped by the remaining
            # lifetime allowance on a per-path basis.
            tfc_avail = np.maximum(LSA_CAP - state.tfc_used, 0.0)
            tfc_cap = np.minimum(TFC_FRACTION * sipp_take, tfc_avail)
            taxable_fraction = np.where(
                sipp_take > 0,
                1.0 - tfc_cap / np.where(sipp_take > 0, sipp_take, 1.0),
                0.0,
            )
            # Simple first-cut gross-up using 20 % basic rate on the taxable
            # portion of the SIPP draw. A tax-free slice is worth £1 per £1;
            # a taxable slice is worth (1 - 0.20) = £0.80 per £1. Blend:
            #   net_per_£ = (1 - taxable_fraction) + taxable_fraction * 0.80
            net_per_pound = (1.0 - taxable_fraction) + taxable_fraction * 0.80
            gross_up = np.where(
                net_per_pound > 0,
                sipp_take / net_per_pound - sipp_take,
                0.0,
            )
            extra, extra_per = _withdraw(state, gross_up, ("sipp",))
            per_account["sipp"] = per_account["sipp"] + extra_per["sipp"]
            total_withdrawn = total_withdrawn + extra

            # Recompute tax-free cash on the FINAL SIPP draw (after gross-up),
            # and record against the lifetime allowance.
            final_sipp = per_account["sipp"]
            tfc_avail_final = np.maximum(LSA_CAP - state.tfc_used, 0.0)
            tfc_final = np.minimum(TFC_FRACTION * final_sipp, tfc_avail_final)
            taxable_sipp = final_sipp - tfc_final
            state.tfc_used = state.tfc_used + tfc_final

            # Recompute tax with only the taxable portion of SIPP drawdown.
            tax_inputs2 = UKYearInputs(
                age=age,
                year=calendar_year,
                state_pension=state_pension_annual,
                private_pension_income=taxable_sipp,
                savings_interest=np.zeros(n_sims),
                dividend_income=gia_dividends,
                employment_income=employment,
            )
            tax = calculate_uk_tax(tax_inputs2)

        # Portfolio grows on remaining balances
        growth_factor = 1.0 + price_growth[:, year_idx]
        state.gia = state.gia * growth_factor
        state.isa = state.isa * growth_factor
        state.sipp = state.sipp * growth_factor

        total_portfolio = state.gia + state.isa + state.sipp
        newly_depleted = (total_portfolio <= 0) & (state.depleted_year == -1) & alive_mask[:, year_idx]
        state.depleted_year = np.where(newly_depleted, year_idx, state.depleted_year)

        breakdown = UKYearBreakdown(
            year_index=year_idx,
            age=age,
            portfolio_start=float(
                np.median(
                    (state.gia + state.isa + state.sipp) / growth_factor + total_withdrawn
                )
            ),
            portfolio_end=float(np.median(state.gia + state.isa + state.sipp)),
            spending_target=float(np.median(spending_target_nominal)),
            total_income=float(np.median(tax.net_income + per_account["isa"])),
            withdrawal=float(np.median(total_withdrawn)),
            total_tax=float(np.median(tax.total_tax)),
            inflation_rate=float(np.median(inflation_paths[:, year_idx])),
            portfolio_return=float(np.median(price_growth[:, year_idx])),
            effective_tax_rate=float(
                np.median(
                    np.where(
                        tax.net_income + tax.total_tax > 0,
                        tax.total_tax / (tax.net_income + tax.total_tax),
                        0.0,
                    )
                )
            ),
            state_pension=float(np.median(state_pension_annual)),
            employment_income=float(np.median(employment)),
            sipp_withdrawal=float(np.median(per_account["sipp"])),
            isa_withdrawal=float(np.median(per_account["isa"])),
            gia_withdrawal=float(np.median(per_account["gia"])),
        )
        yield year_idx, breakdown, state


def run_uk_simulation(inputs: UKSimulationInput) -> UKSimulationResult:
    """Run the full UK Monte Carlo simulation and return aggregated result."""
    rng = np.random.default_rng(inputs.random_seed)

    year_breakdown: list[UKYearBreakdown] = []
    final_state: _PathState | None = None
    portfolio_paths: list[np.ndarray] = []

    for year_idx, breakdown, state in _iterate_years(inputs, rng):
        year_breakdown.append(breakdown)
        portfolio_paths.append(state.gia + state.isa + state.sipp)
        final_state = state

    assert final_state is not None
    portfolio_over_time = np.stack(portfolio_paths, axis=1)  # (n_sims, n_years)

    depleted = final_state.depleted_year != -1
    success_rate = float(np.mean(~depleted))

    final_portfolio = final_state.gia + final_state.isa + final_state.sipp
    percentiles = {
        p: float(np.percentile(final_portfolio, int(p[1:])))
        for p in ("p5", "p25", "p50", "p75", "p95")
    }

    # Real (today's £) by deflating final nominal by cumulative median inflation
    median_inflation_path = float(
        np.prod([1.0 + b.inflation_rate for b in year_breakdown])
    )
    percentiles_real = {k: v / median_inflation_path for k, v in percentiles.items()}

    percentile_paths = {
        f"p{p}": np.percentile(portfolio_over_time, p, axis=0).tolist()
        for p in (5, 25, 50, 75, 95)
    }

    total_portfolio_start = (
        inputs.gia_balance + inputs.isa_balance + inputs.sipp_balance
    )
    initial_withdrawal_rate = (
        (inputs.annual_spending / total_portfolio_start * 100.0)
        if total_portfolio_start > 0
        else 0.0
    )

    # 10-year failure probability (approximate: depleted within first 10 years)
    horizon = min(10, len(year_breakdown))
    first_10_depleted = (final_state.depleted_year != -1) & (
        final_state.depleted_year < horizon
    )
    prob_10_year_failure = float(np.mean(first_10_depleted))

    return UKSimulationResult(
        metadata={
            "n_simulations": inputs.n_simulations,
            "current_age": inputs.current_age,
            "max_age": inputs.max_age,
            "random_seed": inputs.random_seed,
        },
        success_rate=success_rate,
        median_final_value=float(np.median(final_portfolio)),
        median_final_value_real=float(np.median(final_portfolio) / median_inflation_path),
        percentiles=percentiles,
        percentiles_real=percentiles_real,
        percentile_paths=percentile_paths,
        year_breakdown=year_breakdown,
        initial_withdrawal_rate=initial_withdrawal_rate,
        prob_10_year_failure=prob_10_year_failure,
    )


def run_uk_simulation_with_progress(inputs: UKSimulationInput):
    """Generator variant that yields progress events for SSE streaming."""
    rng = np.random.default_rng(inputs.random_seed)
    n_years = inputs.max_age - inputs.current_age + 1

    year_breakdown: list[UKYearBreakdown] = []
    final_state: _PathState | None = None
    portfolio_paths: list[np.ndarray] = []

    for year_idx, breakdown, state in _iterate_years(inputs, rng):
        year_breakdown.append(breakdown)
        portfolio_paths.append(state.gia + state.isa + state.sipp)
        final_state = state
        yield {"type": "progress", "current_year": year_idx + 1, "total_years": n_years}

    assert final_state is not None
    portfolio_over_time = np.stack(portfolio_paths, axis=1)

    depleted = final_state.depleted_year != -1
    success_rate = float(np.mean(~depleted))
    final_portfolio = final_state.gia + final_state.isa + final_state.sipp

    percentiles = {
        f"p{p}": float(np.percentile(final_portfolio, p))
        for p in (5, 25, 50, 75, 95)
    }
    median_inflation_path = float(
        np.prod([1.0 + b.inflation_rate for b in year_breakdown])
    )
    percentiles_real = {k: v / median_inflation_path for k, v in percentiles.items()}

    percentile_paths = {
        f"p{p}": np.percentile(portfolio_over_time, p, axis=0).tolist()
        for p in (5, 25, 50, 75, 95)
    }

    total_portfolio_start = (
        inputs.gia_balance + inputs.isa_balance + inputs.sipp_balance
    )
    initial_withdrawal_rate = (
        (inputs.annual_spending / total_portfolio_start * 100.0)
        if total_portfolio_start > 0
        else 0.0
    )
    horizon = min(10, len(year_breakdown))
    first_10_depleted = (final_state.depleted_year != -1) & (
        final_state.depleted_year < horizon
    )
    prob_10_year_failure = float(np.mean(first_10_depleted))

    result = UKSimulationResult(
        metadata={
            "n_simulations": inputs.n_simulations,
            "current_age": inputs.current_age,
            "max_age": inputs.max_age,
            "random_seed": inputs.random_seed,
        },
        success_rate=success_rate,
        median_final_value=float(np.median(final_portfolio)),
        median_final_value_real=float(np.median(final_portfolio) / median_inflation_path),
        percentiles=percentiles,
        percentiles_real=percentiles_real,
        percentile_paths=percentile_paths,
        year_breakdown=year_breakdown,
        initial_withdrawal_rate=initial_withdrawal_rate,
        prob_10_year_failure=prob_10_year_failure,
    )
    yield {"type": "result", "result": result.model_dump()}
