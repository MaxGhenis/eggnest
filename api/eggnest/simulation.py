"""Monte Carlo simulation engine for retirement planning."""

import numpy as np

from .models import SimulationInput, SimulationResult
from .tax import TaxCalculator
from .mortality import generate_alive_mask, generate_joint_alive_mask


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

    def __init__(self, params: SimulationInput):
        """Initialize simulator with input parameters."""
        self.params = params
        self._rng = np.random.default_rng()
        self.tax_calc = TaxCalculator(state=params.state)

    def run_with_progress(self):
        """
        Run the Monte Carlo simulation with progress updates.

        Yields progress events during simulation and a complete event at the end.
        Each progress event: {"type": "progress", "year": int, "total_years": int}
        Final complete event: {"type": "complete", "result": SimulationResult}
        """
        p = self.params
        n_years = p.max_age - p.current_age
        n_sims = p.n_simulations

        # Handle backward compatibility
        annual_spending = p.annual_spending
        if annual_spending is None and p.target_monthly_income is not None:
            annual_spending = p.target_monthly_income * 12

        # Initialize paths
        paths = np.zeros((n_sims, n_years + 1))
        paths[:, 0] = p.initial_capital

        # Track withdrawals and taxes
        total_withdrawn = np.zeros(n_sims)
        total_taxes = np.zeros(n_sims)
        failure_year = np.full(n_sims, n_years + 1, dtype=float)

        # Generate market returns (real returns, already inflation-adjusted)
        annual_returns = self._rng.normal(
            p.expected_return, p.return_volatility, (n_sims, n_years)
        )

        # Generate mortality masks
        if p.include_mortality:
            if p.has_spouse and p.spouse:
                primary_alive, spouse_alive, either_alive = generate_joint_alive_mask(
                    n_sims, n_years, p.current_age, p.gender,
                    p.spouse.age, p.spouse.gender, self._rng
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
            spouse_alive = None

        # Calculate initial withdrawal rate for reporting
        guaranteed_income = (
            p.social_security_monthly * 12 +
            p.pension_annual +
            (p.employment_income if p.current_age < p.retirement_age else 0)
        )
        if p.has_spouse and p.spouse:
            guaranteed_income += (
                p.spouse.social_security_monthly * 12 +
                p.spouse.pension_annual +
                (p.spouse.employment_income if p.spouse.age < p.spouse.retirement_age else 0)
            )
        if p.has_annuity and p.annuity:
            guaranteed_income += p.annuity.monthly_payment * 12

        initial_net_need = max(0, annual_spending - guaranteed_income)
        initial_withdrawal_rate = (initial_net_need / p.initial_capital * 100) if p.initial_capital > 0 else 0

        # Yield initial progress
        yield {"type": "progress", "year": 0, "total_years": n_years}

        # Process year by year
        for year in range(n_years):
            current_age = p.current_age + year
            current_value = paths[:, year]

            # Skip dead or depleted paths
            active = (current_value > 0) & either_alive[:, year]
            if not np.any(active):
                yield {"type": "progress", "year": year + 1, "total_years": n_years}
                continue

            # Calculate income for this year
            # Primary person
            employment = 0.0
            if p.employment_income > 0 and current_age < p.retirement_age:
                years_worked = min(year, p.retirement_age - p.current_age)
                employment = p.employment_income * ((1 + p.employment_growth_rate) ** years_worked)

            ss_start_age = getattr(p, 'social_security_start_age', 67)
            social_security = p.social_security_monthly * 12 if current_age >= ss_start_age else 0
            pension = p.pension_annual

            # Spouse income
            spouse_employment = 0.0
            spouse_ss = 0.0
            spouse_pension = 0.0
            if p.has_spouse and p.spouse and spouse_alive is not None:
                spouse_current_age = p.spouse.age + year
                if p.spouse.employment_income > 0 and spouse_current_age < p.spouse.retirement_age:
                    years_worked = min(year, p.spouse.retirement_age - p.spouse.age)
                    spouse_employment = p.spouse.employment_income * ((1 + p.spouse.employment_growth_rate) ** years_worked)
                spouse_ss_start = getattr(p.spouse, 'social_security_start_age', 67)
                if spouse_current_age >= spouse_ss_start:
                    spouse_ss = p.spouse.social_security_monthly * 12
                spouse_pension = p.spouse.pension_annual

                # Zero out spouse income if spouse is dead
                spouse_dead = ~spouse_alive[:, year]
                if np.any(spouse_dead):
                    # These are arrays
                    spouse_employment = np.where(spouse_dead, 0, spouse_employment)
                    spouse_ss = np.where(spouse_dead, 0, spouse_ss)
                    spouse_pension = np.where(spouse_dead, 0, spouse_pension)

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
                        annuity_income = np.where(primary_alive[:, year], annuity_income, 0)
                else:  # life_only
                    annuity_income = np.where(primary_alive[:, year], p.annuity.monthly_payment * 12, 0)

            # Total guaranteed income
            total_guaranteed = (
                employment + social_security + pension +
                spouse_employment + spouse_ss + spouse_pension +
                annuity_income
            )

            # Make sure total_guaranteed is broadcastable
            if isinstance(total_guaranteed, (int, float)):
                total_guaranteed = np.full(n_sims, total_guaranteed)

            # Net withdrawal needed from portfolio
            net_need = annual_spending - total_guaranteed
            net_need = np.maximum(0, net_need)

            # Portfolio income
            dividends = current_value * p.dividend_yield

            # Calculate taxes using PolicyEngine
            # Withdrawal from portfolio is treated as capital gains (simplified)
            ss_income = np.full(n_sims, social_security)
            if isinstance(spouse_ss, np.ndarray):
                ss_income = ss_income + spouse_ss
            elif isinstance(spouse_ss, (int, float)) and spouse_ss > 0:
                ss_income = ss_income + spouse_ss

            employment_total = np.full(n_sims, employment)
            if isinstance(spouse_employment, np.ndarray):
                employment_total = employment_total + spouse_employment
            elif isinstance(spouse_employment, (int, float)) and spouse_employment > 0:
                employment_total = employment_total + spouse_employment

            tax_results = self.tax_calc.calculate_batch_taxes(
                capital_gains_array=np.asarray(net_need).flatten(),
                social_security_array=np.asarray(ss_income).flatten(),
                ages=np.full(n_sims, current_age),
                filing_status=p.filing_status,
                dividend_income_array=np.asarray(dividends).flatten(),
                employment_income_array=np.asarray(employment_total).flatten(),
            )
            # Convert to numpy array and ensure proper shape
            estimated_taxes = np.asarray(tax_results["total_tax"]).flatten()
            # Ensure non-negative taxes
            estimated_taxes = np.maximum(0, estimated_taxes)

            # Ensure all arrays are numpy for addition
            net_need = np.asarray(net_need).flatten()
            dividends = np.asarray(dividends).flatten()
            gross_withdrawal = net_need + estimated_taxes

            # Portfolio dynamics
            growth = current_value * annual_returns[:, year]
            new_value = current_value + growth + dividends - gross_withdrawal

            # Track depletion
            depleted = (current_value > 0) & (new_value <= 0)
            depleted_mask = depleted & (failure_year > year)
            failure_year[depleted_mask] = year + 1

            # Update paths
            paths[:, year + 1] = np.maximum(0, new_value)
            total_withdrawn[active] += gross_withdrawal[active]
            total_taxes[active] += estimated_taxes[active]

            # Yield progress after each year
            yield {"type": "progress", "year": year + 1, "total_years": n_years}

        # Calculate results
        final_values = paths[:, -1]

        # Success = either alive at end with money, or died before running out
        if p.include_mortality:
            success_mask = (failure_year > n_years) | (~either_alive[:, -1])
        else:
            success_mask = failure_year > n_years

        success_rate = float(np.mean(success_mask))

        # Percentile paths for charting (sampled at yearly intervals)
        percentile_paths = {
            "p5": [float(np.percentile(paths[:, i], 5)) for i in range(n_years + 1)],
            "p25": [float(np.percentile(paths[:, i], 25)) for i in range(n_years + 1)],
            "p50": [float(np.percentile(paths[:, i], 50)) for i in range(n_years + 1)],
            "p75": [float(np.percentile(paths[:, i], 75)) for i in range(n_years + 1)],
            "p95": [float(np.percentile(paths[:, i], 95)) for i in range(n_years + 1)],
        }

        # Median depletion age
        depleted_sims = failure_year[failure_year <= n_years]
        median_depletion_age = (
            int(p.current_age + np.median(depleted_sims)) if len(depleted_sims) > 0 else None
        )

        # 10-year failure probability
        prob_10_year_failure = float(np.mean(failure_year <= 10))

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
            median_depletion_year=float(np.median(depleted_sims)) if len(depleted_sims) > 0 else None,
            total_withdrawn_median=float(np.median(total_withdrawn)),
            total_taxes_median=float(np.median(total_taxes)),
            percentile_paths=percentile_paths,
            initial_withdrawal_rate=initial_withdrawal_rate,
            prob_10_year_failure=prob_10_year_failure,
        )

        # Yield final result
        yield {"type": "complete", "result": result.model_dump()}

    def run(self) -> SimulationResult:
        """Run the Monte Carlo simulation."""
        p = self.params
        n_years = p.max_age - p.current_age
        n_sims = p.n_simulations

        # Handle backward compatibility
        annual_spending = p.annual_spending
        if annual_spending is None and p.target_monthly_income is not None:
            annual_spending = p.target_monthly_income * 12

        # Initialize paths
        paths = np.zeros((n_sims, n_years + 1))
        paths[:, 0] = p.initial_capital

        # Track withdrawals and taxes
        total_withdrawn = np.zeros(n_sims)
        total_taxes = np.zeros(n_sims)
        failure_year = np.full(n_sims, n_years + 1, dtype=float)

        # Generate market returns (real returns, already inflation-adjusted)
        annual_returns = self._rng.normal(
            p.expected_return, p.return_volatility, (n_sims, n_years)
        )

        # Generate mortality masks
        if p.include_mortality:
            if p.has_spouse and p.spouse:
                primary_alive, spouse_alive, either_alive = generate_joint_alive_mask(
                    n_sims, n_years, p.current_age, p.gender,
                    p.spouse.age, p.spouse.gender, self._rng
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
            spouse_alive = None

        # Calculate initial withdrawal rate for reporting
        guaranteed_income = (
            p.social_security_monthly * 12 +
            p.pension_annual +
            (p.employment_income if p.current_age < p.retirement_age else 0)
        )
        if p.has_spouse and p.spouse:
            guaranteed_income += (
                p.spouse.social_security_monthly * 12 +
                p.spouse.pension_annual +
                (p.spouse.employment_income if p.spouse.age < p.spouse.retirement_age else 0)
            )
        if p.has_annuity and p.annuity:
            guaranteed_income += p.annuity.monthly_payment * 12

        initial_net_need = max(0, annual_spending - guaranteed_income)
        initial_withdrawal_rate = (initial_net_need / p.initial_capital * 100) if p.initial_capital > 0 else 0

        # Process year by year
        for year in range(n_years):
            current_age = p.current_age + year
            current_value = paths[:, year]

            # Skip dead or depleted paths
            active = (current_value > 0) & either_alive[:, year]
            if not np.any(active):
                continue

            # Calculate income for this year
            # Primary person
            employment = 0.0
            if p.employment_income > 0 and current_age < p.retirement_age:
                years_worked = min(year, p.retirement_age - p.current_age)
                employment = p.employment_income * ((1 + p.employment_growth_rate) ** years_worked)

            ss_start_age = getattr(p, 'social_security_start_age', 67)
            social_security = p.social_security_monthly * 12 if current_age >= ss_start_age else 0
            pension = p.pension_annual

            # Spouse income
            spouse_employment = 0.0
            spouse_ss = 0.0
            spouse_pension = 0.0
            if p.has_spouse and p.spouse and spouse_alive is not None:
                spouse_current_age = p.spouse.age + year
                if p.spouse.employment_income > 0 and spouse_current_age < p.spouse.retirement_age:
                    years_worked = min(year, p.spouse.retirement_age - p.spouse.age)
                    spouse_employment = p.spouse.employment_income * ((1 + p.spouse.employment_growth_rate) ** years_worked)
                spouse_ss_start = getattr(p.spouse, 'social_security_start_age', 67)
                if spouse_current_age >= spouse_ss_start:
                    spouse_ss = p.spouse.social_security_monthly * 12
                spouse_pension = p.spouse.pension_annual

                # Zero out spouse income if spouse is dead
                spouse_dead = ~spouse_alive[:, year]
                if np.any(spouse_dead):
                    # These are arrays
                    spouse_employment = np.where(spouse_dead, 0, spouse_employment)
                    spouse_ss = np.where(spouse_dead, 0, spouse_ss)
                    spouse_pension = np.where(spouse_dead, 0, spouse_pension)

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
                        annuity_income = np.where(primary_alive[:, year], annuity_income, 0)
                else:  # life_only
                    annuity_income = np.where(primary_alive[:, year], p.annuity.monthly_payment * 12, 0)

            # Total guaranteed income
            total_guaranteed = (
                employment + social_security + pension +
                spouse_employment + spouse_ss + spouse_pension +
                annuity_income
            )

            # Make sure total_guaranteed is broadcastable
            if isinstance(total_guaranteed, (int, float)):
                total_guaranteed = np.full(n_sims, total_guaranteed)

            # Net withdrawal needed from portfolio
            net_need = annual_spending - total_guaranteed
            net_need = np.maximum(0, net_need)

            # Portfolio income
            dividends = current_value * p.dividend_yield

            # Calculate taxes using PolicyEngine
            # Withdrawal from portfolio is treated as capital gains (simplified)
            ss_income = np.full(n_sims, social_security)
            if isinstance(spouse_ss, np.ndarray):
                ss_income = ss_income + spouse_ss
            elif isinstance(spouse_ss, (int, float)) and spouse_ss > 0:
                ss_income = ss_income + spouse_ss

            employment_total = np.full(n_sims, employment)
            if isinstance(spouse_employment, np.ndarray):
                employment_total = employment_total + spouse_employment
            elif isinstance(spouse_employment, (int, float)) and spouse_employment > 0:
                employment_total = employment_total + spouse_employment

            tax_results = self.tax_calc.calculate_batch_taxes(
                capital_gains_array=np.asarray(net_need).flatten(),
                social_security_array=np.asarray(ss_income).flatten(),
                ages=np.full(n_sims, current_age),
                filing_status=p.filing_status,
                dividend_income_array=np.asarray(dividends).flatten(),
                employment_income_array=np.asarray(employment_total).flatten(),
            )
            # Convert to numpy array and ensure proper shape
            estimated_taxes = np.asarray(tax_results["total_tax"]).flatten()
            # Ensure non-negative taxes
            estimated_taxes = np.maximum(0, estimated_taxes)

            # Ensure all arrays are numpy for addition
            net_need = np.asarray(net_need).flatten()
            dividends = np.asarray(dividends).flatten()
            gross_withdrawal = net_need + estimated_taxes

            # Portfolio dynamics
            growth = current_value * annual_returns[:, year]
            new_value = current_value + growth + dividends - gross_withdrawal

            # Track depletion
            depleted = (current_value > 0) & (new_value <= 0)
            depleted_mask = depleted & (failure_year > year)
            failure_year[depleted_mask] = year + 1

            # Update paths
            paths[:, year + 1] = np.maximum(0, new_value)
            total_withdrawn[active] += gross_withdrawal[active]
            total_taxes[active] += estimated_taxes[active]

        # Calculate results
        final_values = paths[:, -1]

        # Success = either alive at end with money, or died before running out
        if p.include_mortality:
            success_mask = (failure_year > n_years) | (~either_alive[:, -1])
        else:
            success_mask = failure_year > n_years

        success_rate = float(np.mean(success_mask))

        # Percentile paths for charting (sampled at yearly intervals)
        percentile_paths = {
            "p5": [float(np.percentile(paths[:, i], 5)) for i in range(n_years + 1)],
            "p25": [float(np.percentile(paths[:, i], 25)) for i in range(n_years + 1)],
            "p50": [float(np.percentile(paths[:, i], 50)) for i in range(n_years + 1)],
            "p75": [float(np.percentile(paths[:, i], 75)) for i in range(n_years + 1)],
            "p95": [float(np.percentile(paths[:, i], 95)) for i in range(n_years + 1)],
        }

        # Median depletion age
        depleted_sims = failure_year[failure_year <= n_years]
        median_depletion_age = (
            int(p.current_age + np.median(depleted_sims)) if len(depleted_sims) > 0 else None
        )

        # 10-year failure probability
        prob_10_year_failure = float(np.mean(failure_year <= 10))

        return SimulationResult(
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
            median_depletion_year=float(np.median(depleted_sims)) if len(depleted_sims) > 0 else None,
            total_withdrawn_median=float(np.median(total_withdrawn)),
            total_taxes_median=float(np.median(total_taxes)),
            percentile_paths=percentile_paths,
            initial_withdrawal_rate=initial_withdrawal_rate,
            prob_10_year_failure=prob_10_year_failure,
        )


def compare_to_annuity(
    simulation_result: SimulationResult,
    annuity_monthly_payment: float,
    annuity_guarantee_years: int,
    n_years: int,
) -> dict:
    """Compare simulation results to an annuity option."""
    annuity_total = annuity_monthly_payment * 12 * annuity_guarantee_years

    # Simulation total income (withdrawals minus taxes)
    sim_total = (
        simulation_result.total_withdrawn_median - simulation_result.total_taxes_median
    )

    # Probability calculation based on success rate and percentiles
    if simulation_result.success_rate > 0.9 and sim_total > annuity_total:
        prob_beats = 0.7
    elif simulation_result.success_rate > 0.8:
        prob_beats = 0.5
    else:
        prob_beats = 0.3

    # Generate recommendation
    if simulation_result.success_rate > 0.9 and prob_beats > 0.6:
        recommendation = "Consider investing - high probability of exceeding annuity returns with low depletion risk."
    elif simulation_result.success_rate < 0.7:
        recommendation = "Consider the annuity - simulation shows significant depletion risk."
    else:
        recommendation = "Mixed results - consider a hybrid approach or consult a financial advisor."

    return {
        "annuity_total_guaranteed": annuity_total,
        "probability_simulation_beats_annuity": prob_beats,
        "simulation_median_total_income": sim_total,
        "recommendation": recommendation,
    }
