"""Monte Carlo simulation engine for retirement planning."""

from datetime import datetime

import numpy as np

from .holdings import create_holdings_tracker
from .models import SimulationInput, SimulationResult, YearBreakdown
from .mortality import generate_alive_mask, generate_joint_alive_mask
from .returns import generate_blended_returns
from .tax import TaxCalculator

# Base year for calendar year calculations
START_YEAR = datetime.now().year


def _display_progress_year(raw_year: float, total_years: int) -> int:
    """Convert fractional internal progress into a human-readable year number."""
    if raw_year <= 0:
        return 0
    if raw_year >= total_years:
        return total_years
    if float(raw_year).is_integer():
        return int(raw_year)
    return min(total_years, int(raw_year) + 1)


def _year_progress_summary(
    paths: np.ndarray,
    year_index: int,
    age: int,
    active: np.ndarray,
    taxes: np.ndarray,
    withdrawals: np.ndarray,
) -> dict[str, float | int]:
    """Build a small progress payload from the latest completed simulated year."""
    values = paths[:, year_index]
    p25, p50, p75 = np.percentile(values, [25, 50, 75])
    return {
        "year": year_index,
        "age": age,
        "median_portfolio": float(p50),
        "p25_portfolio": float(p25),
        "p75_portfolio": float(p75),
        "active_paths": int(np.sum(active)),
        "median_tax": float(np.median(taxes)),
        "median_withdrawal": float(np.median(withdrawals)),
    }


def _household_social_security(
    n_sims: int,
    primary_scheduled: float,
    spouse_scheduled: float,
    primary_alive: np.ndarray,
    spouse_alive: np.ndarray | None,
) -> np.ndarray:
    """Household Social Security income with a survivor rule.

    Both members alive: sum of the two scheduled benefits. Exactly one alive:
    the survivor receives the larger of the two scheduled benefits (the SSA
    survivor rule, simplified). Neither alive: zero.
    """
    primary = np.full(n_sims, float(primary_scheduled))
    if spouse_alive is None:
        return np.where(primary_alive, primary, 0.0)
    spouse = np.full(n_sims, float(spouse_scheduled))
    both = primary_alive & spouse_alive
    exactly_one = primary_alive ^ spouse_alive
    return np.where(
        both,
        primary + spouse,
        np.where(exactly_one, np.maximum(primary, spouse), 0.0),
    )


class MonteCarloSimulator:
    """
    Monte Carlo simulator for retirement planning.

    Features:
    - Vectorized calculations for performance
    - Tax-aware withdrawal modeling using PolicyEngine-US
    - Mortality-adjusted outcomes
    - Spouse/joint modeling
    - Multiple income sources (employment, SS, pension, annuity)
    """

    def __init__(
        self,
        params: SimulationInput,
        return_paths: tuple[np.ndarray, np.ndarray] | None = None,
    ):
        """Initialize simulator with input parameters."""
        self.params = params
        self._rng = np.random.default_rng(params.random_seed)
        self.tax_calc = TaxCalculator(state=params.state)
        self.return_paths: tuple[np.ndarray, np.ndarray] | None = None

        # Create holdings tracker if holdings are provided
        n_years = params.max_age - params.current_age
        self.tracker = create_holdings_tracker(
            params=params,
            n_simulations=params.n_simulations,
            n_years=n_years,
            rng=self._rng,
        )
        if return_paths is not None:
            if self.tracker:
                raise ValueError(
                    "return_paths are only supported for simple portfolio mode"
                )
            price_growth, div_yields = (
                np.asarray(return_paths[0], dtype=float),
                np.asarray(return_paths[1], dtype=float),
            )
            expected_shape = (params.n_simulations, n_years)
            if (
                price_growth.shape != expected_shape
                or div_yields.shape != expected_shape
            ):
                raise ValueError(
                    "return_paths must have shape "
                    f"{expected_shape}; got {price_growth.shape} and {div_yields.shape}"
                )
            self.return_paths = (price_growth, div_yields)

    def _simulate_core(self):
        """
        Core simulation generator that yields progress and final result.

        Yields:
            ("progress", year, total_years) tuples during simulation.
            ("result", SimulationResult) as the final yield.
        """
        p = self.params
        n_years = p.max_age - p.current_age
        n_sims = p.n_simulations

        annual_spending = p.annual_spending

        # Initialize paths
        paths = np.zeros((n_sims, n_years + 1))
        if self.tracker:
            # Use tracker for holdings-based portfolio
            paths[:, 0] = self.tracker.total_balance
        else:
            # Legacy mode: single total_capital
            paths[:, 0] = p.total_capital

        # Track withdrawals and taxes
        total_withdrawn = np.zeros(n_sims)
        total_taxes = np.zeros(n_sims)
        failure_year = np.full(n_sims, n_years + 1, dtype=float)

        # Generate market returns using selected model and allocation
        # Only needed if NOT using tracker (tracker has its own returns)
        if not self.tracker:
            if self.return_paths is not None:
                price_growth, div_yields = self.return_paths
            else:
                price_growth, div_yields = generate_blended_returns(
                    n_simulations=n_sims,
                    n_years=n_years,
                    stock_allocation=p.stock_allocation,
                    method=p.return_model,
                    expected_stock_return=p.expected_return,
                    stock_volatility=p.return_volatility,
                    stock_index=p.stock_index,
                    bond_index=p.bond_index,
                    dividend_yield=p.dividend_yield,
                    rng=self._rng,
                )
        # Generate mortality masks
        if p.include_mortality:
            if p.has_spouse and p.spouse:
                primary_alive, spouse_alive, either_alive = generate_joint_alive_mask(
                    n_sims,
                    n_years,
                    p.current_age,
                    p.gender,
                    p.spouse.age,
                    p.spouse.gender,
                    self._rng,
                )
            else:
                either_alive = generate_alive_mask(
                    n_sims, n_years, p.current_age, p.gender, self._rng
                )
                primary_alive = either_alive
                spouse_alive = None
        else:
            either_alive = np.ones((n_sims, n_years + 1), dtype=bool)
            primary_alive = either_alive
            # Without mortality the spouse is always alive; a None mask would
            # silently drop spouse income from the household.
            spouse_alive = either_alive if (p.has_spouse and p.spouse) else None

        # Calculate initial withdrawal rate for reporting
        guaranteed_income = (
            p.social_security_monthly * 12
            + p.pension_annual
            + (p.employment_income if p.current_age < p.retirement_age else 0)
        )
        if p.has_spouse and p.spouse:
            guaranteed_income += (
                p.spouse.social_security_monthly * 12
                + p.spouse.pension_annual
                + (
                    p.spouse.employment_income
                    if p.spouse.age < p.spouse.retirement_age
                    else 0
                )
            )
        if p.has_annuity and p.annuity:
            guaranteed_income += p.annuity.monthly_payment * 12

        initial_net_need = max(0, annual_spending - guaranteed_income)
        initial_withdrawal_rate = (
            (initial_net_need / p.total_capital * 100) if p.total_capital > 0 else 0
        )

        # Yield initial progress
        yield ("progress", 0, n_years, "Preparing simulation")

        # Track year-by-year data for detailed breakdown
        yearly_employment = np.zeros((n_sims, n_years))
        yearly_ss = np.zeros((n_sims, n_years))
        yearly_pension = np.zeros((n_sims, n_years))
        yearly_dividends = np.zeros((n_sims, n_years))
        yearly_annuity = np.zeros((n_sims, n_years))
        yearly_withdrawal = np.zeros((n_sims, n_years))
        yearly_federal_tax = np.zeros((n_sims, n_years))
        yearly_state_tax = np.zeros((n_sims, n_years))
        yearly_total_tax = np.zeros((n_sims, n_years))

        # Process year by year
        for year in range(n_years):
            current_age = p.current_age + year
            current_value = paths[:, year]

            # Skip dead or depleted paths, carrying balances forward so
            # frozen estates are not zeroed out.
            active = (current_value > 0) & either_alive[:, year]
            if not np.any(active):
                paths[:, year + 1] = current_value
                yield ("progress", year + 1, n_years, "Year complete")
                continue

            yield ("progress", year + 0.15, n_years, "Preparing yearly cash flows")

            alive = either_alive[:, year]
            primary_alive_col = primary_alive[:, year]
            spouse_alive_col = (
                spouse_alive[:, year] if spouse_alive is not None else None
            )
            inflation_factor = (1.0 + p.inflation_rate) ** year

            # Spending grows with assumed inflation (the engine is nominal)
            spending_need = annual_spending * inflation_factor

            # Calculate income for this year
            # Primary person; income stops at death
            employment = 0.0
            if p.employment_income > 0 and current_age < p.retirement_age:
                years_worked = min(year, p.retirement_age - p.current_age)
                employment = p.employment_income * (
                    (1 + p.employment_growth_rate) ** years_worked
                )
            employment = np.where(primary_alive_col, employment, 0.0)

            ss_start_age = getattr(p, "social_security_start_age", 67)
            # Social Security receives a COLA at the assumed inflation rate
            social_security = (
                p.social_security_monthly * 12 * inflation_factor
                if current_age >= ss_start_age
                else 0.0
            )
            pension = np.where(primary_alive_col, p.pension_annual, 0.0)

            # Spouse income; stops at death (no survivor pension continuation)
            spouse_employment = 0.0
            spouse_ss_scheduled = 0.0
            spouse_pension = 0.0
            if p.has_spouse and p.spouse:
                spouse_current_age = p.spouse.age + year
                if (
                    p.spouse.employment_income > 0
                    and spouse_current_age < p.spouse.retirement_age
                ):
                    years_worked = min(year, p.spouse.retirement_age - p.spouse.age)
                    spouse_employment = p.spouse.employment_income * (
                        (1 + p.spouse.employment_growth_rate) ** years_worked
                    )
                spouse_ss_start = getattr(p.spouse, "social_security_start_age", 67)
                if spouse_current_age >= spouse_ss_start:
                    spouse_ss_scheduled = (
                        p.spouse.social_security_monthly * 12 * inflation_factor
                    )
                spouse_pension = p.spouse.pension_annual
                if spouse_alive_col is not None:
                    spouse_employment = np.where(
                        spouse_alive_col, spouse_employment, 0.0
                    )
                    spouse_pension = np.where(spouse_alive_col, spouse_pension, 0.0)

            # Household Social Security with the survivor rule applied
            ss_income = _household_social_security(
                n_sims,
                social_security,
                spouse_ss_scheduled,
                primary_alive_col,
                spouse_alive_col,
            )

            # Annuity income
            annuity_income = 0.0
            if p.has_annuity and p.annuity:
                if p.annuity.annuity_type == "fixed_period":
                    if year < p.annuity.guarantee_years:
                        annuity_income = p.annuity.monthly_payment * 12
                elif p.annuity.annuity_type == "life_with_guarantee":
                    # Pay if within guarantee period OR primary is alive
                    annuity_income = p.annuity.monthly_payment * 12
                    if year >= p.annuity.guarantee_years:
                        # Only pay if primary alive after guarantee
                        annuity_income = np.where(
                            primary_alive[:, year], annuity_income, 0
                        )
                else:  # life_only
                    annuity_income = np.where(
                        primary_alive[:, year], p.annuity.monthly_payment * 12, 0
                    )

            # Portfolio dividend income
            if self.tracker:
                # Only taxable-account dividends are distributed as cash;
                # traditional and Roth dividends reinvest inside their
                # accounts (via apply_growth) without a taxable event.
                div_by_account = self.tracker.get_dividends(year)
                dividends = np.where(alive, div_by_account["taxable"], 0.0)
            else:
                # Legacy mode: single taxable portfolio pays out its yield
                dividends = np.where(alive, current_value * div_yields[:, year], 0.0)

            employment_total = employment + spouse_employment
            pension_total = pension + spouse_pension

            # Total guaranteed income (not including dividends)
            total_guaranteed = (
                employment_total + ss_income + pension_total + annuity_income
            )

            # Total income including dividends reduces withdrawal needs
            total_income_for_spending = total_guaranteed + dividends

            # Net withdrawal needed from portfolio; dead paths stop spending
            # so estates freeze at their value at death.
            net_need = np.where(
                alive,
                np.maximum(0.0, spending_need - total_income_for_spending),
                0.0,
            )

            # Handle withdrawals and taxes
            if self.tracker:
                # Use tracker to withdraw with proper tax treatment
                withdrawal_result = self.tracker.withdraw(
                    net_need, current_age, alive=alive
                )

                # Traditional withdrawals are ordinary income (add to employment income)
                trad_withdrawals = (
                    withdrawal_result["traditional"]
                    + withdrawal_result["traditional_rmd"]
                )
                ordinary_income = employment_total + trad_withdrawals

                yield (
                    "progress",
                    year + 0.35,
                    n_years,
                    "Calculating PolicyEngine taxes",
                )
                tax_results = self.tax_calc.calculate_batch_taxes(
                    capital_gains_array=np.asarray(
                        withdrawal_result["taxable"]
                    ).flatten(),
                    social_security_array=np.asarray(ss_income).flatten(),
                    ages=np.full(n_sims, current_age),
                    filing_status=p.filing_status,
                    dividend_income_array=np.asarray(dividends).flatten(),
                    employment_income_array=np.asarray(ordinary_income).flatten(),
                    year=START_YEAR + year,
                )

                estimated_taxes = np.asarray(tax_results["total_tax"]).flatten()
                estimated_taxes = np.where(alive, np.maximum(0, estimated_taxes), 0.0)

                # Taxes are paid from the portfolio: take a second withdrawal
                # pass for the tax bill (without re-applying RMDs). The tax on
                # this second withdrawal is approximated as zero, a standard
                # one-iteration simplification.
                tax_withdrawal = self.tracker.withdraw(
                    estimated_taxes, current_age, alive=alive, apply_rmd=False
                )
                gross_withdrawal = withdrawal_result["total"] + tax_withdrawal["total"]

                # Apply growth and update portfolio value
                self.tracker.apply_growth(year, alive=alive)
                new_value = self.tracker.total_balance

            else:
                # Legacy mode: simplified tax treatment (all withdrawals as capital gains)
                yield (
                    "progress",
                    year + 0.35,
                    n_years,
                    "Calculating PolicyEngine taxes",
                )
                tax_results = self.tax_calc.calculate_batch_taxes(
                    capital_gains_array=np.asarray(net_need).flatten(),
                    social_security_array=np.asarray(ss_income).flatten(),
                    ages=np.full(n_sims, current_age),
                    filing_status=p.filing_status,
                    dividend_income_array=np.asarray(dividends).flatten(),
                    employment_income_array=np.asarray(employment_total).flatten(),
                    year=START_YEAR + year,
                )
                estimated_taxes = np.asarray(tax_results["total_tax"]).flatten()
                estimated_taxes = np.where(alive, np.maximum(0, estimated_taxes), 0.0)

                net_need = np.asarray(net_need).flatten()
                dividends = np.asarray(dividends).flatten()
                gross_withdrawal = net_need + estimated_taxes

                # Portfolio dynamics - price returns only, dividends are income
                # not growth. Dead paths freeze at their value at death.
                growth = np.where(alive, current_value * price_growth[:, year], 0.0)
                new_value = current_value + growth - gross_withdrawal

            # Track depletion
            depleted = (current_value > 0) & (new_value <= 0)
            depleted_mask = depleted & (failure_year > year)
            failure_year[depleted_mask] = year + 1

            # Update paths
            paths[:, year + 1] = np.maximum(0, new_value)
            total_withdrawn[active] += gross_withdrawal[active]
            total_taxes[active] += estimated_taxes[active]

            # Store yearly breakdown data
            yearly_employment[:, year] = employment_total
            yearly_ss[:, year] = ss_income
            yearly_pension[:, year] = pension_total
            yearly_dividends[:, year] = dividends
            yearly_annuity[:, year] = (
                np.broadcast_to(annuity_income, n_sims)
                if isinstance(annuity_income, np.ndarray)
                else annuity_income
            )
            yearly_withdrawal[:, year] = gross_withdrawal
            yearly_federal_tax[:, year] = np.asarray(
                tax_results["federal_income_tax"]
            ).flatten()
            yearly_state_tax[:, year] = np.asarray(
                tax_results["state_income_tax"]
            ).flatten()
            yearly_total_tax[:, year] = estimated_taxes

            # Yield progress after each year, including a small partial result
            # so clients can show useful output while the full run continues.
            yield (
                "progress",
                year + 1,
                n_years,
                "Year complete",
                _year_progress_summary(
                    paths=paths,
                    year_index=year + 1,
                    age=current_age + 1,
                    active=active,
                    taxes=estimated_taxes,
                    withdrawals=gross_withdrawal,
                ),
            )

        # Store per-path arrays for downstream use (e.g., annuity comparison)
        self._total_withdrawn = total_withdrawn
        self._total_taxes = total_taxes

        # Calculate results
        final_values = paths[:, -1]

        # Dead paths stop spending, so depletion can only happen while the
        # household is alive: success = never depleted before death or horizon.
        success_mask = failure_year > n_years

        self._paths = paths
        self._failure_year = failure_year
        self._success_mask = success_mask
        self._final_values = final_values

        success_rate = float(np.mean(success_mask))

        # Percentile paths for charting (sampled at yearly intervals)
        path_bands = np.percentile(paths, [5, 25, 50, 75, 95], axis=0)
        percentile_paths = {
            key: [float(value) for value in band]
            for key, band in zip(
                ["p5", "p25", "p50", "p75", "p95"], path_bands, strict=True
            )
        }

        # Median depletion age
        depleted_sims = failure_year[failure_year <= n_years]
        median_depletion_age = (
            int(p.current_age + np.median(depleted_sims))
            if len(depleted_sims) > 0
            else None
        )

        # 10-year failure probability
        prob_10_year_failure = float(np.mean(failure_year <= 10))

        # Build year-by-year breakdown for median scenario
        year_breakdown = []
        for year in range(n_years):
            current_age = p.current_age + year
            portfolio_start = float(np.median(paths[:, year]))
            portfolio_end = float(np.median(paths[:, year + 1]))

            # Get median values for this year
            employment = float(np.median(yearly_employment[:, year]))
            ss = float(np.median(yearly_ss[:, year]))
            pension_val = float(np.median(yearly_pension[:, year]))
            divs = float(np.median(yearly_dividends[:, year]))
            annuity_val = float(np.median(yearly_annuity[:, year]))
            withdrawal = float(np.median(yearly_withdrawal[:, year]))
            fed_tax = float(np.median(yearly_federal_tax[:, year]))
            state_tax = float(np.median(yearly_state_tax[:, year]))
            total_tax = float(np.median(yearly_total_tax[:, year]))

            total_income = employment + ss + pension_val + divs + annuity_val
            net_income = total_income + withdrawal - total_tax
            effective_rate = total_tax / total_income if total_income > 0 else 0
            portfolio_return = (
                (portfolio_end - portfolio_start + withdrawal) / portfolio_start
                if portfolio_start > 0
                else 0
            )

            year_breakdown.append(
                YearBreakdown(
                    age=current_age,
                    year_index=year,
                    portfolio_start=portfolio_start,
                    portfolio_end=portfolio_end,
                    portfolio_return=portfolio_return,
                    employment_income=employment,
                    social_security=ss,
                    pension=pension_val,
                    dividends=divs,
                    annuity=annuity_val,
                    total_income=total_income,
                    withdrawal=withdrawal,
                    federal_tax=fed_tax,
                    state_tax=state_tax,
                    total_tax=total_tax,
                    effective_tax_rate=effective_rate,
                    net_income=net_income,
                )
            )

        result = SimulationResult(
            success_rate=success_rate,
            median_final_value=float(np.median(final_values)),
            mean_final_value=float(np.mean(final_values)),
            percentiles={
                "p5": float(np.percentile(final_values, 5)),
                "p25": float(np.percentile(final_values, 25)),
                "p50": float(np.percentile(final_values, 50)),
                "p75": float(np.percentile(final_values, 75)),
                "p95": float(np.percentile(final_values, 95)),
            },
            median_depletion_age=median_depletion_age,
            median_depletion_year=(
                float(np.median(depleted_sims)) if len(depleted_sims) > 0 else None
            ),
            total_withdrawn_median=float(np.median(total_withdrawn)),
            total_taxes_median=float(np.median(total_taxes)),
            percentile_paths=percentile_paths,
            year_breakdown=year_breakdown,
            initial_withdrawal_rate=initial_withdrawal_rate,
            prob_10_year_failure=prob_10_year_failure,
        )

        # Yield final result
        yield ("result", result)

    def run_with_progress(self):
        """
        Run the Monte Carlo simulation with progress updates.

        Yields progress events during simulation and a complete event at the end.
        Each progress event includes an integer display year plus a fractional
        progress value.
        Final complete event: {"type": "complete", "result": SimulationResult}
        """
        for event in self._simulate_core():
            if event[0] == "progress":
                raw_year = float(event[1])
                progress = raw_year / event[2] if event[2] else 0
                yield {
                    "type": "progress",
                    "year": _display_progress_year(raw_year, event[2]),
                    "total_years": event[2],
                    "progress": max(0, min(1, progress)),
                    "message": event[3] if len(event) > 3 else None,
                    "year_summary": event[4] if len(event) > 4 else None,
                }
            elif event[0] == "result":
                yield {"type": "complete", "result": event[1].model_dump()}

    def run(self) -> SimulationResult:
        """Run the Monte Carlo simulation."""
        for event in self._simulate_core():
            if event[0] == "result":
                return event[1]
        # Should never reach here, but satisfy type checker
        raise RuntimeError("Simulation did not produce a result")


def compare_to_annuity(
    simulation_result: SimulationResult,
    annuity_monthly_payment: float,
    annuity_guarantee_years: int,
    n_years: int,
    total_withdrawn: np.ndarray | None = None,
    total_taxes: np.ndarray | None = None,
) -> dict:
    """Compare simulation results to an annuity option.

    Args:
        total_withdrawn: Per-path total withdrawal amounts from the simulator.
        total_taxes: Per-path total tax amounts from the simulator.
            When provided, the actual fraction of paths beating the annuity
            is computed instead of a heuristic estimate.
    """
    annuity_total = annuity_monthly_payment * 12 * annuity_guarantee_years

    # Simulation total income (withdrawals minus taxes)
    sim_total = (
        simulation_result.total_withdrawn_median - simulation_result.total_taxes_median
    )

    # Compute real probability from path-level data
    if total_withdrawn is not None and total_taxes is not None:
        net_income_per_path = total_withdrawn - total_taxes
        prob_beats = float(np.mean(net_income_per_path > annuity_total))
    else:
        # Fallback: simple estimate from median
        prob_beats = float(sim_total > annuity_total) * 0.5 + 0.25

    # Summarize the modeled comparison without suggesting an action.
    if simulation_result.success_rate > 0.9 and prob_beats > 0.6:
        comparison_summary = (
            "Portfolio withdrawals exceed the annuity guarantee total in "
            f"{prob_beats:.0%} of simulated paths, with low modeled depletion risk."
        )
    elif simulation_result.success_rate < 0.7:
        comparison_summary = (
            "The portfolio simulation shows material depletion risk; the annuity "
            "guarantee total is shown for comparison."
        )
    else:
        comparison_summary = (
            "The modeled comparison is mixed: portfolio outcomes vary materially "
            "across simulated market paths."
        )

    return {
        "annuity_total_guaranteed": annuity_total,
        "probability_simulation_beats_annuity": prob_beats,
        "simulation_median_total_income": sim_total,
        "comparison_summary": comparison_summary,
    }
