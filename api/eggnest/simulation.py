"""Monte Carlo simulation engine for retirement planning."""

from datetime import datetime

import numpy as np

# Base year for calendar year calculations
START_YEAR = datetime.now().year

from .models import SimulationInput, SimulationResult, YearBreakdown, OutcomePaths
from .tax import TaxCalculator
from .mortality import generate_alive_mask, generate_joint_alive_mask
from .returns import generate_blended_returns
from .holdings import create_holdings_tracker

# Medicare eligibility age (IRMAA only applies at age 65+)
MEDICARE_AGE = 65


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

        # Create holdings tracker if holdings are provided
        n_years = params.max_age - params.current_age
        self.tracker = create_holdings_tracker(
            params=params,
            n_simulations=params.n_simulations,
            n_years=n_years,
            rng=self._rng,
        )

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
            price_growth, div_yields = generate_blended_returns(
                n_simulations=n_sims,
                n_years=n_years,
                stock_allocation=p.stock_allocation,
                method=p.return_model,
                expected_stock_return=p.expected_return,
                stock_volatility=p.return_volatility,
                stock_index=p.stock_index,
                bond_index=p.bond_index,
                rng=self._rng,
            )
        else:
            # Placeholder for legacy code paths
            price_growth = None
            div_yields = None

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
        initial_withdrawal_rate = (initial_net_need / p.total_capital * 100) if p.total_capital > 0 else 0

        # Yield initial progress
        yield {"type": "progress", "year": 0, "total_years": n_years}

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

        # Track AGI history for IRMAA calculation (uses income from 2 years prior)
        yearly_agi = np.zeros((n_sims, n_years))

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

            # Portfolio dividend income
            if self.tracker:
                # Get dividends by account type from tracker
                div_by_account = self.tracker.get_dividends(year)
                # Dividends from taxable and traditional accounts are taxable
                # Roth dividends grow tax-free (not included in taxable income)
                dividends = div_by_account["taxable"] + div_by_account["traditional"]
                roth_dividends = div_by_account["roth"]
            else:
                # Legacy mode: use blended returns
                dividends = current_value * div_yields[:, year]
                roth_dividends = np.zeros(n_sims)

            # Total guaranteed income (not including dividends)
            total_guaranteed = (
                employment + social_security + pension +
                spouse_employment + spouse_ss + spouse_pension +
                annuity_income
            )

            # Make sure total_guaranteed is broadcastable
            if isinstance(total_guaranteed, (int, float)):
                total_guaranteed = np.full(n_sims, total_guaranteed)

            # Total income including dividends reduces withdrawal needs
            # Roth dividends also reduce withdrawal needs (tax-free)
            total_income_for_spending = total_guaranteed + dividends + roth_dividends

            # Net withdrawal needed from portfolio (after all income including dividends)
            net_need = annual_spending - total_income_for_spending
            net_need = np.maximum(0, net_need)

            # Handle withdrawals and taxes
            if self.tracker:
                # Use tracker to withdraw with proper tax treatment
                withdrawal_result = self.tracker.withdraw(net_need, current_age)

                # Calculate taxes based on account types
                # Traditional withdrawals (including RMD) = ordinary income
                # Taxable withdrawals = capital gains
                # Roth withdrawals = tax-free (not included)
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

                # Traditional withdrawals are ordinary income (add to employment income)
                trad_withdrawals = withdrawal_result["traditional"] + withdrawal_result["traditional_rmd"]
                ordinary_income = employment_total + trad_withdrawals

                # Get prior year AGI for IRMAA (uses income from 2 years prior)
                prior_year_agi = np.zeros(n_sims)
                if year >= 2:
                    prior_year_agi = yearly_agi[:, year - 2]

                tax_results = self.tax_calc.calculate_batch_taxes(
                    capital_gains_array=np.asarray(withdrawal_result["taxable"]).flatten(),
                    social_security_array=np.asarray(ss_income).flatten(),
                    ages=np.full(n_sims, current_age),
                    filing_status=p.filing_status,
                    dividend_income_array=np.asarray(dividends).flatten(),
                    employment_income_array=np.asarray(ordinary_income).flatten(),
                    year=START_YEAR + year,
                    prior_year_agi=prior_year_agi,
                )

                estimated_taxes = np.asarray(tax_results["total_tax"]).flatten()
                estimated_taxes = np.maximum(0, estimated_taxes)

                # Get IRMAA from PolicyEngine (already calculated based on prior year AGI)
                irmaa_cost = np.zeros(n_sims)
                if p.include_irmaa and current_age >= MEDICARE_AGE:
                    irmaa_cost = np.asarray(tax_results.get("irmaa", np.zeros(n_sims))).flatten()

                # Store AGI for future IRMAA calculations
                yearly_agi[:, year] = np.asarray(tax_results.get("adjusted_gross_income", np.zeros(n_sims))).flatten()

                gross_withdrawal = withdrawal_result["total"] + estimated_taxes + irmaa_cost

                # Apply growth and update portfolio value
                self.tracker.apply_growth(year)
                new_value = self.tracker.total_balance

            else:
                # Legacy mode: simplified tax treatment (all withdrawals as capital gains)
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

                # Get prior year AGI for IRMAA (uses income from 2 years prior)
                prior_year_agi = np.zeros(n_sims)
                if year >= 2:
                    prior_year_agi = yearly_agi[:, year - 2]

                tax_results = self.tax_calc.calculate_batch_taxes(
                    capital_gains_array=np.asarray(net_need).flatten(),
                    social_security_array=np.asarray(ss_income).flatten(),
                    ages=np.full(n_sims, current_age),
                    filing_status=p.filing_status,
                    dividend_income_array=np.asarray(dividends).flatten(),
                    employment_income_array=np.asarray(employment_total).flatten(),
                    year=START_YEAR + year,
                    prior_year_agi=prior_year_agi,
                )
                estimated_taxes = np.asarray(tax_results["total_tax"]).flatten()
                estimated_taxes = np.maximum(0, estimated_taxes)

                # Get IRMAA from PolicyEngine (already calculated based on prior year AGI)
                irmaa_cost = np.zeros(n_sims)
                if p.include_irmaa and current_age >= MEDICARE_AGE:
                    irmaa_cost = np.asarray(tax_results.get("irmaa", np.zeros(n_sims))).flatten()

                # Store AGI for future IRMAA calculations
                yearly_agi[:, year] = np.asarray(tax_results.get("adjusted_gross_income", np.zeros(n_sims))).flatten()

                net_need = np.asarray(net_need).flatten()
                dividends = np.asarray(dividends).flatten()
                gross_withdrawal = net_need + estimated_taxes + irmaa_cost

                # Portfolio dynamics - price returns only, dividends are income not growth
                growth = current_value * price_growth[:, year]
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
            yearly_employment[:, year] = np.broadcast_to(employment_total, n_sims) if isinstance(employment_total, np.ndarray) else employment_total
            yearly_ss[:, year] = np.broadcast_to(ss_income, n_sims) if isinstance(ss_income, np.ndarray) else ss_income
            yearly_pension[:, year] = pension + (spouse_pension if isinstance(spouse_pension, (int, float)) else np.median(spouse_pension))
            yearly_dividends[:, year] = dividends
            yearly_annuity[:, year] = np.broadcast_to(annuity_income, n_sims) if isinstance(annuity_income, np.ndarray) else annuity_income
            yearly_withdrawal[:, year] = gross_withdrawal
            yearly_federal_tax[:, year] = np.asarray(tax_results["federal_income_tax"]).flatten()
            yearly_state_tax[:, year] = np.asarray(tax_results["state_income_tax"]).flatten()
            yearly_total_tax[:, year] = estimated_taxes

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

        # Calculate outcome paths for stacked area chart
        outcome_paths = None
        if p.include_mortality:
            died_with_money = np.zeros(n_years + 1)
            died_broke = np.zeros(n_years + 1)
            alive_with_money = np.zeros(n_years + 1)
            alive_broke = np.zeros(n_years + 1)

            for year_idx in range(n_years + 1):
                alive_at_year = either_alive[:, year_idx]
                has_money = paths[:, year_idx] > 0

                if year_idx == 0:
                    cum_died_with_money = 0
                    cum_died_broke = 0
                else:
                    died_this_year = either_alive[:, year_idx - 1] & ~alive_at_year
                    had_money_when_died = paths[:, year_idx - 1] > 0
                    died_rich_this_year = died_this_year & had_money_when_died
                    died_broke_this_year = died_this_year & ~had_money_when_died

                    if year_idx == 1:
                        cum_died_with_money = float(np.mean(died_rich_this_year)) * 100
                        cum_died_broke = float(np.mean(died_broke_this_year)) * 100
                    else:
                        cum_died_with_money = died_with_money[year_idx - 1] + float(np.mean(died_rich_this_year)) * 100
                        cum_died_broke = died_broke[year_idx - 1] + float(np.mean(died_broke_this_year)) * 100

                pct_alive_with_money = float(np.mean(alive_at_year & has_money)) * 100
                pct_alive_broke = float(np.mean(alive_at_year & ~has_money)) * 100

                died_with_money[year_idx] = cum_died_with_money if year_idx > 0 else 0
                died_broke[year_idx] = cum_died_broke if year_idx > 0 else 0
                alive_with_money[year_idx] = pct_alive_with_money
                alive_broke[year_idx] = pct_alive_broke

            outcome_paths = OutcomePaths(
                died_with_money=died_with_money.tolist(),
                died_broke=died_broke.tolist(),
                alive_with_money=alive_with_money.tolist(),
                alive_broke=alive_broke.tolist(),
            )

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
            portfolio_return = (portfolio_end - portfolio_start + withdrawal) / portfolio_start if portfolio_start > 0 else 0

            year_breakdown.append(YearBreakdown(
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
            ))

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
            outcome_paths=outcome_paths,
            year_breakdown=year_breakdown,
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
            price_growth, div_yields = generate_blended_returns(
                n_simulations=n_sims,
                n_years=n_years,
                stock_allocation=p.stock_allocation,
                method=p.return_model,
                expected_stock_return=p.expected_return,
                stock_volatility=p.return_volatility,
                stock_index=p.stock_index,
                bond_index=p.bond_index,
                rng=self._rng,
            )
        else:
            # Placeholder for legacy code paths
            price_growth = None
            div_yields = None

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
        initial_withdrawal_rate = (initial_net_need / p.total_capital * 100) if p.total_capital > 0 else 0

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

        # Track AGI history for IRMAA calculation (uses income from 2 years prior)
        yearly_agi = np.zeros((n_sims, n_years))

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

            # Portfolio dividend income
            if self.tracker:
                # Get dividends by account type from tracker
                div_by_account = self.tracker.get_dividends(year)
                # Dividends from taxable and traditional accounts are taxable
                # Roth dividends grow tax-free (not included in taxable income)
                dividends = div_by_account["taxable"] + div_by_account["traditional"]
                roth_dividends = div_by_account["roth"]
            else:
                # Legacy mode: use blended returns
                dividends = current_value * div_yields[:, year]
                roth_dividends = np.zeros(n_sims)

            # Total guaranteed income (not including dividends)
            total_guaranteed = (
                employment + social_security + pension +
                spouse_employment + spouse_ss + spouse_pension +
                annuity_income
            )

            # Make sure total_guaranteed is broadcastable
            if isinstance(total_guaranteed, (int, float)):
                total_guaranteed = np.full(n_sims, total_guaranteed)

            # Total income including dividends reduces withdrawal needs
            # Roth dividends also reduce withdrawal needs (tax-free)
            total_income_for_spending = total_guaranteed + dividends + roth_dividends

            # Net withdrawal needed from portfolio (after all income including dividends)
            net_need = annual_spending - total_income_for_spending
            net_need = np.maximum(0, net_need)

            # Handle withdrawals and taxes
            if self.tracker:
                # Use tracker to withdraw with proper tax treatment
                withdrawal_result = self.tracker.withdraw(net_need, current_age)

                # Calculate taxes based on account types
                # Traditional withdrawals (including RMD) = ordinary income
                # Taxable withdrawals = capital gains
                # Roth withdrawals = tax-free (not included)
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

                # Traditional withdrawals are ordinary income (add to employment income)
                trad_withdrawals = withdrawal_result["traditional"] + withdrawal_result["traditional_rmd"]
                ordinary_income = employment_total + trad_withdrawals

                # Get prior year AGI for IRMAA (uses income from 2 years prior)
                prior_year_agi = np.zeros(n_sims)
                if year >= 2:
                    prior_year_agi = yearly_agi[:, year - 2]

                tax_results = self.tax_calc.calculate_batch_taxes(
                    capital_gains_array=np.asarray(withdrawal_result["taxable"]).flatten(),
                    social_security_array=np.asarray(ss_income).flatten(),
                    ages=np.full(n_sims, current_age),
                    filing_status=p.filing_status,
                    dividend_income_array=np.asarray(dividends).flatten(),
                    employment_income_array=np.asarray(ordinary_income).flatten(),
                    year=START_YEAR + year,
                    prior_year_agi=prior_year_agi,
                )

                estimated_taxes = np.asarray(tax_results["total_tax"]).flatten()
                estimated_taxes = np.maximum(0, estimated_taxes)

                # Get IRMAA from PolicyEngine (already calculated based on prior year AGI)
                irmaa_cost = np.zeros(n_sims)
                if p.include_irmaa and current_age >= MEDICARE_AGE:
                    irmaa_cost = np.asarray(tax_results.get("irmaa", np.zeros(n_sims))).flatten()

                # Store AGI for future IRMAA calculations
                yearly_agi[:, year] = np.asarray(tax_results.get("adjusted_gross_income", np.zeros(n_sims))).flatten()

                gross_withdrawal = withdrawal_result["total"] + estimated_taxes + irmaa_cost

                # Apply growth and update portfolio value
                self.tracker.apply_growth(year)
                new_value = self.tracker.total_balance

            else:
                # Legacy mode: simplified tax treatment (all withdrawals as capital gains)
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

                # Get prior year AGI for IRMAA (uses income from 2 years prior)
                prior_year_agi = np.zeros(n_sims)
                if year >= 2:
                    prior_year_agi = yearly_agi[:, year - 2]

                tax_results = self.tax_calc.calculate_batch_taxes(
                    capital_gains_array=np.asarray(net_need).flatten(),
                    social_security_array=np.asarray(ss_income).flatten(),
                    ages=np.full(n_sims, current_age),
                    filing_status=p.filing_status,
                    dividend_income_array=np.asarray(dividends).flatten(),
                    employment_income_array=np.asarray(employment_total).flatten(),
                    year=START_YEAR + year,
                    prior_year_agi=prior_year_agi,
                )
                estimated_taxes = np.asarray(tax_results["total_tax"]).flatten()
                estimated_taxes = np.maximum(0, estimated_taxes)

                # Get IRMAA from PolicyEngine (already calculated based on prior year AGI)
                irmaa_cost = np.zeros(n_sims)
                if p.include_irmaa and current_age >= MEDICARE_AGE:
                    irmaa_cost = np.asarray(tax_results.get("irmaa", np.zeros(n_sims))).flatten()

                # Store AGI for future IRMAA calculations
                yearly_agi[:, year] = np.asarray(tax_results.get("adjusted_gross_income", np.zeros(n_sims))).flatten()

                net_need = np.asarray(net_need).flatten()
                dividends = np.asarray(dividends).flatten()
                gross_withdrawal = net_need + estimated_taxes + irmaa_cost

                # Portfolio dynamics - price returns only, dividends are income not growth
                growth = current_value * price_growth[:, year]
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
            yearly_employment[:, year] = np.broadcast_to(employment_total, n_sims) if isinstance(employment_total, np.ndarray) else employment_total
            yearly_ss[:, year] = np.broadcast_to(ss_income, n_sims) if isinstance(ss_income, np.ndarray) else ss_income
            yearly_pension[:, year] = pension + (spouse_pension if isinstance(spouse_pension, (int, float)) else np.median(spouse_pension))
            yearly_dividends[:, year] = dividends
            yearly_annuity[:, year] = np.broadcast_to(annuity_income, n_sims) if isinstance(annuity_income, np.ndarray) else annuity_income
            yearly_withdrawal[:, year] = gross_withdrawal
            yearly_federal_tax[:, year] = np.asarray(tax_results["federal_income_tax"]).flatten()
            yearly_state_tax[:, year] = np.asarray(tax_results["state_income_tax"]).flatten()
            yearly_total_tax[:, year] = estimated_taxes

        # Calculate results
        final_values = paths[:, -1]

        # Success = either alive at end with money, or died before running out
        if p.include_mortality:
            success_mask = (failure_year > n_years) | (~either_alive[:, -1])
        else:
            success_mask = failure_year > n_years

        success_rate = float(np.mean(success_mask))

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
            portfolio_return = (portfolio_end - portfolio_start + withdrawal) / portfolio_start if portfolio_start > 0 else 0

            year_breakdown.append(YearBreakdown(
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
            ))

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

        # Calculate outcome paths for stacked area chart
        # At each year, categorize each simulation into one of 4 states:
        # - died_with_money: died while still having money
        # - died_broke: ran out of money before death (then died)
        # - alive_with_money: still alive with money
        # - alive_broke: still alive but depleted
        outcome_paths = None
        if p.include_mortality:
            died_with_money = np.zeros(n_years + 1)
            died_broke = np.zeros(n_years + 1)
            alive_with_money = np.zeros(n_years + 1)
            alive_broke = np.zeros(n_years + 1)

            for year_idx in range(n_years + 1):
                # Who is alive at this point?
                alive_at_year = either_alive[:, year_idx]

                # Who has money at this point?
                has_money = paths[:, year_idx] > 0

                # Track cumulative deaths with money vs broke
                if year_idx == 0:
                    # At start, everyone alive
                    cum_died_with_money = 0
                    cum_died_broke = 0
                else:
                    # Who died in the past year (was alive, now dead)?
                    died_this_year = either_alive[:, year_idx - 1] & ~alive_at_year
                    # Of those who died, who had money when they died?
                    # Check portfolio value at previous year (when they were last alive)
                    had_money_when_died = paths[:, year_idx - 1] > 0
                    died_rich_this_year = died_this_year & had_money_when_died
                    died_broke_this_year = died_this_year & ~had_money_when_died

                    # Cumulative from previous year
                    if year_idx == 1:
                        cum_died_with_money = float(np.mean(died_rich_this_year)) * 100
                        cum_died_broke = float(np.mean(died_broke_this_year)) * 100
                    else:
                        cum_died_with_money = died_with_money[year_idx - 1] + float(np.mean(died_rich_this_year)) * 100
                        cum_died_broke = died_broke[year_idx - 1] + float(np.mean(died_broke_this_year)) * 100

                # Current alive states
                pct_alive_with_money = float(np.mean(alive_at_year & has_money)) * 100
                pct_alive_broke = float(np.mean(alive_at_year & ~has_money)) * 100

                died_with_money[year_idx] = cum_died_with_money if year_idx > 0 else 0
                died_broke[year_idx] = cum_died_broke if year_idx > 0 else 0
                alive_with_money[year_idx] = pct_alive_with_money
                alive_broke[year_idx] = pct_alive_broke

            outcome_paths = OutcomePaths(
                died_with_money=died_with_money.tolist(),
                died_broke=died_broke.tolist(),
                alive_with_money=alive_with_money.tolist(),
                alive_broke=alive_broke.tolist(),
            )

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
            outcome_paths=outcome_paths,
            year_breakdown=year_breakdown,
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
