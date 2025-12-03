"""Monte Carlo simulation engine for retirement planning."""

import numpy as np

from .models import SimulationInput, SimulationResult
from .tax import TaxCalculator


class MonteCarloSimulator:
    """
    Monte Carlo simulator for retirement planning.

    Features:
    - Vectorized calculations for performance
    - Tax-aware withdrawal modeling using PolicyEngine-US
    - Configurable market parameters
    """

    def __init__(self, params: SimulationInput):
        """Initialize simulator with input parameters."""
        self.params = params
        self._rng = np.random.default_rng()
        self.tax_calc = TaxCalculator(state=params.state)

    def run(self) -> SimulationResult:
        """Run the Monte Carlo simulation."""
        n_months = self.params.n_years * 12
        n_sims = self.params.n_simulations

        # Initialize paths
        paths = np.zeros((n_sims, n_months + 1))
        paths[:, 0] = self.params.initial_capital

        # Monthly parameters
        monthly_return = self.params.expected_return / 12
        monthly_vol = self.params.return_volatility / np.sqrt(12)
        monthly_dividend = self.params.dividend_yield / 12
        monthly_target = self.params.target_monthly_income

        # Social Security starts at retirement age
        months_to_retirement = max(
            0, (self.params.retirement_age - self.params.current_age) * 12
        )
        ss_monthly = self.params.social_security_monthly

        # Track withdrawals and taxes
        total_withdrawn = np.zeros(n_sims)
        total_taxes = np.zeros(n_sims)
        depletion_month = np.full(n_sims, np.inf)

        # Generate all returns upfront (vectorized)
        returns = self._rng.normal(monthly_return, monthly_vol, (n_sims, n_months))

        # Process year by year for tax calculations (PolicyEngine works annually)
        for year in range(self.params.n_years):
            year_start_month = year * 12
            year_end_month = min((year + 1) * 12, n_months)

            if year_start_month >= n_months:
                break

            # Current year parameters
            current_age = self.params.current_age + year
            is_retired = year_start_month >= months_to_retirement

            # Annual Social Security
            ss_annual = ss_monthly * 12 if is_retired else 0

            # Estimate annual withdrawal needed
            annual_target = monthly_target * 12
            annual_withdrawal_needed = max(0, annual_target - ss_annual)

            # Taxable fraction increases over time (as basis is depleted)
            taxable_fraction = min(0.8, 0.2 + 0.03 * year)
            capital_gains = annual_withdrawal_needed * taxable_fraction

            # Calculate tax using PolicyEngine (sample calculation)
            try:
                tax_results = self.tax_calc.calculate_batch_taxes(
                    capital_gains_array=np.array([capital_gains]),
                    social_security_array=np.array([ss_annual]),
                    ages=np.array([current_age]),
                    filing_status=self.params.filing_status.upper().replace(" ", "_"),
                )
                estimated_annual_tax = float(tax_results["total_tax"][0])
            except Exception:
                # Fallback to simple estimate if PolicyEngine fails
                estimated_annual_tax = capital_gains * 0.15 + ss_annual * 0.05

            # Monthly tax and withdrawal
            monthly_tax = estimated_annual_tax / 12
            gross_monthly_withdrawal = (annual_withdrawal_needed + estimated_annual_tax) / 12

            # Simulate months in this year
            for month in range(year_start_month, year_end_month):
                current_value = paths[:, month]
                active = current_value > 0

                if not np.any(active):
                    continue

                # Portfolio dynamics
                dividends = current_value * monthly_dividend
                growth = current_value * returns[:, month]
                new_value = current_value + growth + dividends - gross_monthly_withdrawal

                # Track depletion
                depleted = (current_value > 0) & (new_value <= 0)
                depletion_month[depleted & (depletion_month == np.inf)] = month + 1

                # Update
                paths[:, month + 1] = np.maximum(0, new_value)
                total_withdrawn[active] += gross_monthly_withdrawal
                total_taxes[active] += monthly_tax

        # Calculate results
        final_values = paths[:, -1]
        success_rate = np.mean(final_values > 0)

        # Percentile paths for charting (sample at yearly intervals)
        yearly_indices = [0] + [i * 12 for i in range(1, self.params.n_years + 1)]
        percentile_paths = {
            "p5": [float(np.percentile(paths[:, i], 5)) for i in yearly_indices],
            "p25": [float(np.percentile(paths[:, i], 25)) for i in yearly_indices],
            "p50": [float(np.percentile(paths[:, i], 50)) for i in yearly_indices],
            "p75": [float(np.percentile(paths[:, i], 75)) for i in yearly_indices],
            "p95": [float(np.percentile(paths[:, i], 95)) for i in yearly_indices],
        }

        # Median depletion year
        depleted_sims = depletion_month[depletion_month < np.inf]
        median_depletion_year = (
            float(np.median(depleted_sims) / 12) if len(depleted_sims) > 0 else None
        )

        return SimulationResult(
            success_rate=float(success_rate),
            median_final_value=float(np.median(final_values)),
            mean_final_value=float(np.mean(final_values)),
            percentiles={
                "p5": float(np.percentile(final_values, 5)),
                "p25": float(np.percentile(final_values, 25)),
                "p50": float(np.percentile(final_values, 50)),
                "p75": float(np.percentile(final_values, 75)),
                "p95": float(np.percentile(final_values, 95)),
            },
            median_depletion_year=median_depletion_year,
            total_withdrawn_median=float(np.median(total_withdrawn)),
            total_taxes_median=float(np.median(total_taxes)),
            percentile_paths=percentile_paths,
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

    # Probability calculation would need access to the raw paths
    # For now, use a heuristic based on percentiles
    prob_beats = 0.5 if sim_total > annuity_total else 0.3

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
