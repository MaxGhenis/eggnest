"""Monte Carlo simulation engine for retirement planning."""

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from .holdings import create_holdings_tracker
from .models import (
    RothConversionPolicy,
    SimulationInput,
    SimulationResult,
    YearBreakdown,
    default_roth_conversion_end_age,
)
from .mortality import generate_alive_mask, generate_joint_alive_mask
from .returns import generate_blended_returns, generate_inflation_paths
from .rmd import RMD_START_AGE
from .tax import TaxCalculator
from .withdrawal_policies import WithdrawalPolicy, resolve_withdrawal_policy

# Base year for calendar year calculations
START_YEAR = datetime.now().year
TAX_GROSS_UP_MAX_ITERATIONS = 8
TAX_GROSS_UP_TOLERANCE = 0.01
ROTH_CONVERSION_POLICY_SEARCH_STEPS = 12
ROTH_CONVERSION_MARGINAL_TOLERANCE = 1e-4
ROTH_CONVERSION_PROBE_STEP = 0.01

ROTH_CONVERSION_MARGINAL_RATE_TARGETS: dict[RothConversionPolicy, float | None] = {
    "fixed_amount": None,
    "fill_standard_deduction": 0.0,
    "fill_12_percent_bracket": 0.12,
    "fill_22_percent_bracket": 0.22,
}


@dataclass(frozen=True)
class SimulationPathOverrides:
    """Optional externally supplied market/inflation paths for the simulator."""

    price_growth: np.ndarray | None = None
    div_yields: np.ndarray | None = None
    sampled_years: np.ndarray | None = None
    inflation_rates: np.ndarray | None = None
    fund_returns: dict[str, tuple[np.ndarray, np.ndarray]] | None = None


def _combine_primary_and_spouse(
    n_sims: int,
    primary_value: float,
    spouse_value: float | np.ndarray,
) -> np.ndarray:
    """Combine a primary scalar and a spouse value (scalar or array) into a simulation array."""
    result = np.full(n_sims, primary_value)
    if isinstance(spouse_value, np.ndarray):
        result = result + spouse_value
    elif isinstance(spouse_value, (int, float)) and spouse_value > 0:
        result = result + spouse_value
    return result


def _as_sim_array(n_sims: int, value: float | np.ndarray) -> np.ndarray:
    """Convert a scalar or simulation array into a flat simulation array."""
    if isinstance(value, np.ndarray):
        return np.asarray(value, dtype=float).flatten()
    return np.full(n_sims, float(value), dtype=float)


def _tax_result_array(
    tax_results: dict[str, np.ndarray], key: str, n_sims: int
) -> np.ndarray:
    """Fetch one numeric tax result as a flat simulation array."""
    return np.asarray(tax_results.get(key, np.zeros(n_sims)), dtype=float).flatten()


def _tax_result_label_array(
    tax_results: dict[str, np.ndarray], key: str, n_sims: int
) -> np.ndarray:
    """Fetch one string tax result as an object simulation array."""
    return np.asarray(
        tax_results.get(key, np.full(n_sims, "none", dtype=object)), dtype=object
    ).flatten()


def _empty_withdrawal_result(n_sims: int) -> dict[str, np.ndarray]:
    """Create an empty withdrawal result matching HoldingsTracker output."""
    return {
        "traditional_rmd": np.zeros(n_sims),
        "traditional": np.zeros(n_sims),
        "roth": np.zeros(n_sims),
        "taxable": np.zeros(n_sims),
        "taxable_cash": np.zeros(n_sims),
        "taxable_capital_gains": np.zeros(n_sims),
        "total": np.zeros(n_sims),
    }


def _merge_withdrawal_results(
    base: dict[str, np.ndarray], extra: dict[str, np.ndarray]
) -> dict[str, np.ndarray]:
    """Sum two withdrawal result dictionaries."""
    return {key: base[key] + extra[key] for key in base}


def _build_inflation_factors(inflation_rates: np.ndarray) -> np.ndarray:
    """Convert annual inflation rates into cumulative start-of-year multipliers."""
    n_sims, n_years = inflation_rates.shape
    factors = np.ones((n_sims, n_years + 1), dtype=float)
    if n_years > 0:
        factors[:, 1:] = np.cumprod(1 + inflation_rates, axis=1)
    return factors


def _empty_tax_results(n_sims: int) -> dict[str, np.ndarray]:
    """Create a zeroed tax-results payload for helper flows."""
    return {
        "federal_income_tax": np.zeros(n_sims, dtype=float),
        "state_income_tax": np.zeros(n_sims, dtype=float),
        "taxable_income": np.zeros(n_sims, dtype=float),
        "total_tax": np.zeros(n_sims, dtype=float),
        "effective_tax_rate": np.zeros(n_sims, dtype=float),
    }


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
        path_overrides: SimulationPathOverrides | None = None,
    ):
        """Initialize simulator with input parameters."""
        self.params = params
        self.path_overrides = path_overrides
        self._rng = np.random.default_rng(params.random_seed)
        self.tax_calc = TaxCalculator(state=params.state)
        self.withdrawal_policy: WithdrawalPolicy = resolve_withdrawal_policy(
            params.withdrawal_strategy
        )

        # Create holdings tracker if holdings are provided
        n_years = params.max_age - params.current_age
        self.tracker = create_holdings_tracker(
            params=params,
            n_simulations=params.n_simulations,
            n_years=n_years,
            withdrawal_policy=self.withdrawal_policy,
            fund_returns=(
                path_overrides.fund_returns if path_overrides is not None else None
            ),
            sampled_return_years=(
                path_overrides.sampled_years if path_overrides is not None else None
            ),
            rng=self._rng,
        )

    def _calculate_holdings_taxes(
        self,
        *,
        n_sims: int,
        year_index: int,
        current_age: int,
        filing_status: str,
        dividends: np.ndarray,
        ss_income: np.ndarray,
        ordinary_income_base: np.ndarray,
        roth_conversions: np.ndarray,
        withdrawal_result: dict[str, np.ndarray],
        agi_two_years_prior: np.ndarray,
    ) -> tuple[dict[str, np.ndarray], np.ndarray]:
        """Calculate taxes for a holdings-based withdrawal mix."""
        trad_withdrawals = (
            withdrawal_result["traditional"] + withdrawal_result["traditional_rmd"]
        )
        ordinary_income = ordinary_income_base + trad_withdrawals + roth_conversions

        tax_results = self.tax_calc.calculate_batch_taxes(
            capital_gains_array=np.asarray(
                withdrawal_result["taxable_capital_gains"]
            ).flatten(),
            social_security_array=np.asarray(ss_income).flatten(),
            ages=np.full(n_sims, current_age),
            filing_status=filing_status,
            dividend_income_array=np.asarray(dividends).flatten(),
            employment_income_array=np.asarray(ordinary_income).flatten(),
            agi_two_years_prior_array=np.asarray(agi_two_years_prior).flatten(),
            year=START_YEAR + year_index,
        )

        estimated_outflows = np.asarray(tax_results["total_tax"]).flatten() + np.asarray(
            tax_results["total_medicare_premium"]
        ).flatten()
        return tax_results, np.maximum(0, estimated_outflows)

    def _calculate_legacy_taxes(
        self,
        *,
        year_index: int,
        current_age: int,
        filing_status: str,
        dividends: np.ndarray,
        ss_income: np.ndarray,
        ordinary_income_base: np.ndarray,
        withdrawal_amount: np.ndarray,
        agi_two_years_prior: np.ndarray,
    ) -> tuple[dict[str, np.ndarray], np.ndarray]:
        """Calculate taxes when all portfolio withdrawals are treated as capital gains."""
        tax_results = self.tax_calc.calculate_batch_taxes(
            capital_gains_array=np.asarray(withdrawal_amount).flatten(),
            social_security_array=np.asarray(ss_income).flatten(),
            ages=np.full(len(withdrawal_amount), current_age),
            filing_status=filing_status,
            dividend_income_array=np.asarray(dividends).flatten(),
            employment_income_array=np.asarray(ordinary_income_base).flatten(),
            agi_two_years_prior_array=np.asarray(agi_two_years_prior).flatten(),
            year=START_YEAR + year_index,
        )

        estimated_outflows = np.asarray(tax_results["total_tax"]).flatten() + np.asarray(
            tax_results["total_medicare_premium"]
        ).flatten()
        return tax_results, np.maximum(0, estimated_outflows)

    def _calculate_roth_explainability(
        self,
        *,
        n_sims: int,
        year_index: int,
        current_age: int,
        filing_status: str,
        dividends: np.ndarray,
        ss_income: np.ndarray,
        ordinary_income_base: np.ndarray,
        roth_conversions: np.ndarray,
        withdrawal_result: dict[str, np.ndarray],
        agi_two_years_prior: np.ndarray,
        active: np.ndarray,
        tax_results: dict[str, np.ndarray],
    ) -> dict[str, np.ndarray]:
        """Build year-level explainability metrics for Roth conversion and IRMAA."""
        taxable_income = _tax_result_array(tax_results, "taxable_income", n_sims)
        federal_tax = _tax_result_array(tax_results, "federal_income_tax", n_sims)
        medicare_total = _tax_result_array(tax_results, "total_medicare_premium", n_sims)
        baseline_taxable_income = taxable_income.copy()
        baseline_medicare_total = medicare_total.copy()
        marginal_rate = np.zeros(n_sims, dtype=float)

        converted_mask = active & (roth_conversions > TAX_GROSS_UP_TOLERANCE)
        if np.any(converted_mask):
            baseline_tax_results, _ = self._calculate_holdings_taxes(
                n_sims=n_sims,
                year_index=year_index,
                current_age=current_age,
                filing_status=filing_status,
                dividends=dividends,
                ss_income=ss_income,
                ordinary_income_base=ordinary_income_base,
                roth_conversions=np.zeros(n_sims, dtype=float),
                withdrawal_result=withdrawal_result,
                agi_two_years_prior=agi_two_years_prior,
            )
            baseline_taxable_income = _tax_result_array(
                baseline_tax_results, "taxable_income", n_sims
            )
            baseline_medicare_total = _tax_result_array(
                baseline_tax_results, "total_medicare_premium", n_sims
            )

            lower_conversion = np.where(
                converted_mask,
                np.maximum(0.0, roth_conversions - ROTH_CONVERSION_PROBE_STEP),
                roth_conversions,
            )
            delta_conversion = roth_conversions - lower_conversion
            marginal_mask = converted_mask & (
                delta_conversion > ROTH_CONVERSION_MARGINAL_TOLERANCE
            )
            if np.any(marginal_mask):
                lower_tax_results, _ = self._calculate_holdings_taxes(
                    n_sims=n_sims,
                    year_index=year_index,
                    current_age=current_age,
                    filing_status=filing_status,
                    dividends=dividends,
                    ss_income=ss_income,
                    ordinary_income_base=ordinary_income_base,
                    roth_conversions=lower_conversion,
                    withdrawal_result=withdrawal_result,
                    agi_two_years_prior=agi_two_years_prior,
                )
                lower_federal_tax = _tax_result_array(
                    lower_tax_results, "federal_income_tax", n_sims
                )
                marginal_rate = np.divide(
                    federal_tax - lower_federal_tax,
                    delta_conversion,
                    out=np.zeros_like(federal_tax),
                    where=marginal_mask,
                )

        return {
            "federal_taxable_income": taxable_income,
            "federal_taxable_income_without_roth_conversion": baseline_taxable_income,
            "federal_bracket_headroom_used": np.where(
                active,
                np.maximum(0.0, taxable_income - baseline_taxable_income),
                0.0,
            ),
            "federal_marginal_rate_on_last_conversion_dollar": np.where(
                active, marginal_rate, 0.0
            ),
            "medicare_part_b_irmaa_increment": _tax_result_array(
                tax_results, "medicare_part_b_irmaa_increment", n_sims
            ),
            "medicare_part_b_irmaa_bracket": _tax_result_label_array(
                tax_results, "medicare_part_b_irmaa_bracket", n_sims
            ),
            "medicare_part_d_irmaa_bracket": _tax_result_label_array(
                tax_results, "medicare_part_d_irmaa_bracket", n_sims
            ),
            "medicare_total_premium": medicare_total,
            "medicare_premium_delta_vs_no_roth_conversion": np.where(
                active, medicare_total - baseline_medicare_total, 0.0
            ),
        }

    def _resolve_roth_conversion_amounts(
        self,
        *,
        policy: RothConversionPolicy,
        current_age: int,
        year_index: int,
        filing_status: str,
        dividends: np.ndarray,
        ss_income: np.ndarray,
        ordinary_income_base: np.ndarray,
        active: np.ndarray,
        fixed_amount: float,
        traditional_rmd: np.ndarray,
    ) -> np.ndarray:
        """Determine Roth conversion amounts for the current year."""
        n_sims = len(active)
        if not np.any(active):
            return np.zeros(n_sims, dtype=float)

        available = np.where(active, self.tracker.traditional_balance, 0.0)
        if not np.any(available > TAX_GROSS_UP_TOLERANCE):
            return np.zeros(n_sims, dtype=float)

        if policy == "fixed_amount":
            return np.minimum(
                available, np.where(active, np.full(n_sims, fixed_amount), 0.0)
            )

        preview_withdrawal = _empty_withdrawal_result(n_sims)
        preview_withdrawal["traditional_rmd"] = traditional_rmd

        baseline_tax_results, _ = self._calculate_holdings_taxes(
            n_sims=n_sims,
            year_index=year_index,
            current_age=current_age,
            filing_status=filing_status,
            dividends=dividends,
            ss_income=ss_income,
            ordinary_income_base=ordinary_income_base,
            roth_conversions=np.zeros(n_sims, dtype=float),
            withdrawal_result=preview_withdrawal,
            agi_two_years_prior=np.zeros(n_sims, dtype=float),
        )
        baseline_federal_tax = np.asarray(
            baseline_tax_results["federal_income_tax"]
        ).flatten()

        low = np.zeros(n_sims, dtype=float)
        high = available.copy()
        best = np.zeros(n_sims, dtype=float)
        target_rate = ROTH_CONVERSION_MARGINAL_RATE_TARGETS[policy]
        probe_step = np.minimum(
            ROTH_CONVERSION_PROBE_STEP,
            np.maximum(1.0, available),
        )

        for _ in range(ROTH_CONVERSION_POLICY_SEARCH_STEPS):
            mid = (low + high) / 2
            tax_results, _ = self._calculate_holdings_taxes(
                n_sims=n_sims,
                year_index=year_index,
                current_age=current_age,
                filing_status=filing_status,
                dividends=dividends,
                ss_income=ss_income,
                ordinary_income_base=ordinary_income_base,
                roth_conversions=mid,
                withdrawal_result=preview_withdrawal,
                agi_two_years_prior=np.zeros(n_sims, dtype=float),
            )
            federal_tax = np.asarray(tax_results["federal_income_tax"]).flatten()

            if policy == "fill_standard_deduction":
                fits = federal_tax <= (
                    baseline_federal_tax + ROTH_CONVERSION_MARGINAL_TOLERANCE
                )
            else:
                probe = np.minimum(mid + probe_step, available)
                probe_tax_results, _ = self._calculate_holdings_taxes(
                    n_sims=n_sims,
                    year_index=year_index,
                    current_age=current_age,
                    filing_status=filing_status,
                    dividends=dividends,
                    ss_income=ss_income,
                    ordinary_income_base=ordinary_income_base,
                    roth_conversions=probe,
                    withdrawal_result=preview_withdrawal,
                    agi_two_years_prior=np.zeros(n_sims, dtype=float),
                )
                probe_federal_tax = np.asarray(
                    probe_tax_results["federal_income_tax"]
                ).flatten()
                delta_conversion = probe - mid
                marginal_rate = np.divide(
                    probe_federal_tax - federal_tax,
                    delta_conversion,
                    out=np.zeros_like(probe_federal_tax),
                    where=delta_conversion > 0,
                )
                fits = marginal_rate <= (
                    target_rate + ROTH_CONVERSION_MARGINAL_TOLERANCE
                )

            fits = fits & active
            best = np.where(fits, mid, best)
            low = np.where(fits, mid, low)
            high = np.where(fits, high, mid)

        return np.where(active, best, 0.0)

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
        sampled_return_years: np.ndarray | None = None

        # Initialize paths
        paths = np.zeros((n_sims, n_years + 1))
        if self.tracker:
            # Use tracker for holdings-based portfolio
            paths[:, 0] = self.tracker.total_balance
            sampled_return_years = getattr(self.tracker, "sampled_return_years", None)
        else:
            # Legacy mode: single total_capital
            paths[:, 0] = p.total_capital

        # Track withdrawals and taxes
        total_withdrawn = np.zeros(n_sims)
        total_taxes = np.zeros(n_sims)
        total_medicare_premiums = np.zeros(n_sims)
        total_roth_conversions = np.zeros(n_sims)
        failure_year = np.full(n_sims, n_years + 1, dtype=float)

        # Generate market returns using selected model and allocation
        # Only needed if NOT using tracker (tracker has its own returns)
        if not self.tracker:
            if (
                self.path_overrides is not None
                and self.path_overrides.price_growth is not None
                and self.path_overrides.div_yields is not None
            ):
                price_growth = self.path_overrides.price_growth
                div_yields = self.path_overrides.div_yields
                sampled_return_years = self.path_overrides.sampled_years
            else:
                try:
                    price_growth, div_yields, sampled_return_years = (
                        generate_blended_returns(
                            n_simulations=n_sims,
                            n_years=n_years,
                            stock_allocation=p.stock_allocation,
                            method=p.return_model,
                            expected_stock_return=p.expected_return,
                            stock_volatility=p.return_volatility,
                            stock_index=p.stock_index,
                            bond_index=p.bond_index,
                            rng=self._rng,
                            return_sampled_years=True,
                        )
                    )
                except TypeError:
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
                    sampled_return_years = None

        if self.path_overrides is not None and self.path_overrides.inflation_rates is not None:
            inflation_rates = self.path_overrides.inflation_rates
        else:
            inflation_rates = generate_inflation_paths(
                n_simulations=n_sims,
                n_years=n_years,
                model=p.inflation_model,
                inflation_rate=p.inflation_rate,
                method=p.return_model,
                sampled_years=sampled_return_years,
                rng=self._rng,
            )
        inflation_factors = _build_inflation_factors(inflation_rates)
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
            spouse_alive = None

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
        yield ("progress", 0, n_years)

        # Track year-by-year data for detailed breakdown
        yearly_employment = np.zeros((n_sims, n_years))
        yearly_ss = np.zeros((n_sims, n_years))
        yearly_pension = np.zeros((n_sims, n_years))
        yearly_dividends = np.zeros((n_sims, n_years))
        yearly_annuity = np.zeros((n_sims, n_years))
        yearly_traditional_rmd = np.zeros((n_sims, n_years))
        yearly_traditional_withdrawal = np.zeros((n_sims, n_years))
        yearly_roth_withdrawal = np.zeros((n_sims, n_years))
        yearly_taxable_withdrawal = np.zeros((n_sims, n_years))
        yearly_taxable_cash_withdrawal = np.zeros((n_sims, n_years))
        yearly_taxable_capital_gains = np.zeros((n_sims, n_years))
        yearly_surplus_redeposited = np.zeros((n_sims, n_years))
        yearly_roth_conversion = np.zeros((n_sims, n_years))
        yearly_ordinary_income = np.zeros((n_sims, n_years))
        yearly_withdrawal = np.zeros((n_sims, n_years))
        yearly_federal_tax = np.zeros((n_sims, n_years))
        yearly_state_tax = np.zeros((n_sims, n_years))
        yearly_total_tax = np.zeros((n_sims, n_years))
        yearly_federal_taxable_income = np.zeros((n_sims, n_years))
        yearly_federal_taxable_income_without_roth_conversion = np.zeros(
            (n_sims, n_years)
        )
        yearly_federal_bracket_headroom_used = np.zeros((n_sims, n_years))
        yearly_federal_marginal_rate_on_last_conversion_dollar = np.zeros(
            (n_sims, n_years)
        )
        yearly_medicare_part_b_premium = np.zeros((n_sims, n_years))
        yearly_medicare_part_b_irmaa_increment = np.zeros((n_sims, n_years))
        yearly_medicare_part_d_premium_surcharge = np.zeros((n_sims, n_years))
        yearly_medicare_total_premium = np.zeros((n_sims, n_years))
        yearly_medicare_premium_delta_vs_no_roth_conversion = np.zeros(
            (n_sims, n_years)
        )
        yearly_medicare_part_b_irmaa_bracket = np.full(
            (n_sims, n_years), "none", dtype=object
        )
        yearly_medicare_part_d_irmaa_bracket = np.full(
            (n_sims, n_years), "none", dtype=object
        )
        yearly_adjusted_gross_income = np.zeros((n_sims, n_years))
        yearly_spending = np.zeros((n_sims, n_years))
        yearly_inflation_rate = np.zeros((n_sims, n_years))
        yearly_cumulative_inflation = np.zeros((n_sims, n_years))
        yearly_traditional_balance_end = np.zeros((n_sims, n_years))
        yearly_roth_balance_end = np.zeros((n_sims, n_years))
        yearly_taxable_balance_end = np.zeros((n_sims, n_years))

        # Process year by year
        for year in range(n_years):
            current_age = p.current_age + year
            current_value = paths[:, year]
            inflation_factor = inflation_factors[:, year]
            current_inflation_rate = inflation_rates[:, year]

            if p.spending_mode == "real":
                spending_need = annual_spending * inflation_factor
            else:
                spending_need = np.full(n_sims, annual_spending, dtype=float)

            # Skip dead or depleted paths
            active = (current_value > 0) & either_alive[:, year]
            if not np.any(active):
                paths[:, year + 1] = current_value
                yield ("progress", year + 1, n_years)
                continue

            # Calculate income for this year
            # Primary person
            employment = 0.0
            if p.employment_income > 0 and current_age < p.retirement_age:
                years_worked = min(year, p.retirement_age - p.current_age)
                employment = p.employment_income * (
                    (1 + p.employment_growth_rate) ** years_worked
                )

            ss_start_age = getattr(p, "social_security_start_age", 67)
            ss_multiplier = inflation_factor if p.social_security_inflation_adjusted else 1.0
            social_security = (
                p.social_security_monthly * 12 * ss_multiplier
                if current_age >= ss_start_age
                else 0
            )
            pension = p.pension_annual * ((1 + p.pension_cola_rate) ** year)

            # Spouse income
            spouse_employment = 0.0
            spouse_ss = 0.0
            spouse_pension = 0.0
            if p.has_spouse and p.spouse and spouse_alive is not None:
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
                    spouse_ss = p.spouse.social_security_monthly * 12 * ss_multiplier
                spouse_pension = p.spouse.pension_annual * (
                    (1 + p.pension_cola_rate) ** year
                )

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
                annuity_payment = p.annuity.monthly_payment * 12 * (
                    (1 + p.annuity_cola_rate) ** year
                )
                if p.annuity.annuity_type == "fixed_period":
                    if year < p.annuity.guarantee_years:
                        annuity_income = annuity_payment
                elif p.annuity.annuity_type == "life_with_guarantee":
                    # Pay if within guarantee period OR primary is alive
                    annuity_income = annuity_payment
                    if year >= p.annuity.guarantee_years:
                        # Only pay if primary alive after guarantee
                        annuity_income = np.where(
                            primary_alive[:, year], annuity_income, 0
                        )
                else:  # life_only
                    annuity_income = np.where(
                        primary_alive[:, year], annuity_payment, 0
                    )

            # Portfolio dividend income
            if self.tracker:
                # Dividends are only available while the household is active.
                div_by_account = self.tracker.get_dividends(year, mask=active)
                dividends = div_by_account["taxable"] + div_by_account["traditional"]
                roth_dividends = div_by_account["roth"]
            else:
                dividends = np.where(active, current_value * div_yields[:, year], 0.0)
                roth_dividends = np.zeros(n_sims)

            # Build combined income arrays and zero out inactive paths.
            ss_income = np.where(
                active,
                _combine_primary_and_spouse(n_sims, social_security, spouse_ss),
                0.0,
            )
            employment_total = np.where(
                active,
                _combine_primary_and_spouse(n_sims, employment, spouse_employment),
                0.0,
            )
            pension_total = np.where(
                active, _combine_primary_and_spouse(n_sims, pension, spouse_pension), 0.0
            )
            annuity_array = np.where(active, _as_sim_array(n_sims, annuity_income), 0.0)
            dividends = np.where(active, np.asarray(dividends).flatten(), 0.0)
            roth_dividends = np.where(
                active, np.asarray(roth_dividends).flatten(), 0.0
            )

            # Total guaranteed income (not including dividends).
            total_guaranteed = (
                employment_total + ss_income + pension_total + annuity_array
            )

            # Total pre-tax cash available before portfolio withdrawals.
            total_income_for_spending = total_guaranteed + dividends + roth_dividends
            ordinary_income_base = employment_total + pension_total + annuity_array

            # Start with the pre-tax spending gap, then iterate taxes on top.
            net_need = np.where(
                active, np.maximum(0, spending_need - total_income_for_spending), 0.0
            )
            roth_conversions = np.zeros(n_sims, dtype=float)
            traditional_rmd = np.zeros(n_sims, dtype=float)
            traditional_withdrawal = np.zeros(n_sims, dtype=float)
            roth_withdrawal = np.zeros(n_sims, dtype=float)
            taxable_withdrawal = np.zeros(n_sims, dtype=float)
            taxable_cash_withdrawal = np.zeros(n_sims, dtype=float)
            taxable_capital_gains = np.zeros(n_sims, dtype=float)
            surplus_redeposited = np.zeros(n_sims, dtype=float)
            ordinary_income = np.asarray(ordinary_income_base, dtype=float).copy()
            medicare_part_b_premium = np.zeros(n_sims, dtype=float)
            medicare_part_b_irmaa_increment = np.zeros(n_sims, dtype=float)
            medicare_part_b_irmaa_bracket = np.full(n_sims, "none", dtype=object)
            medicare_part_d_premium_surcharge = np.zeros(n_sims, dtype=float)
            medicare_part_d_irmaa_bracket = np.full(n_sims, "none", dtype=object)
            medicare_total_premium = np.zeros(n_sims, dtype=float)
            medicare_premium_delta_vs_no_roth_conversion = np.zeros(
                n_sims, dtype=float
            )
            federal_taxable_income = np.zeros(n_sims, dtype=float)
            federal_taxable_income_without_roth_conversion = np.zeros(
                n_sims, dtype=float
            )
            federal_bracket_headroom_used = np.zeros(n_sims, dtype=float)
            federal_marginal_rate_on_last_conversion_dollar = np.zeros(
                n_sims, dtype=float
            )
            traditional_balance_end = np.zeros(n_sims, dtype=float)
            roth_balance_end = np.zeros(n_sims, dtype=float)
            taxable_balance_end = np.zeros(n_sims, dtype=float)
            agi_two_years_prior = (
                yearly_adjusted_gross_income[:, year - 2].copy()
                if year >= 2
                else np.zeros(n_sims, dtype=float)
            )

            # Handle withdrawals and taxes
            if self.tracker:
                roth_conversion_policy = p.roth_conversion_policy
                conversion_start_age = (
                    p.roth_conversion_start_age
                    if p.roth_conversion_start_age is not None
                    else p.current_age
                )
                conversion_end_age = (
                    p.roth_conversion_end_age
                    if p.roth_conversion_end_age is not None
                    else default_roth_conversion_end_age(conversion_start_age, p.max_age)
                )
                withdrawal_result = _empty_withdrawal_result(n_sims)
                remaining_net_need = net_need

                # RMDs must come out before any same-year Roth conversion.
                if (
                    (
                        roth_conversion_policy != "fixed_amount"
                        or p.roth_conversion_amount > 0
                    )
                    and current_age >= RMD_START_AGE
                ):
                    rmd_only_result = self.tracker.withdraw(
                        np.zeros(n_sims, dtype=float),
                        current_age,
                        include_rmd=True,
                        mask=active,
                    )
                    withdrawal_result = _merge_withdrawal_results(
                        withdrawal_result, rmd_only_result
                    )
                    remaining_net_need = np.where(
                        active,
                        np.maximum(0, remaining_net_need - rmd_only_result["total"]),
                        0.0,
                    )

                if (
                    (
                        roth_conversion_policy != "fixed_amount"
                        or p.roth_conversion_amount > 0
                    )
                    and conversion_start_age <= current_age <= conversion_end_age
                ):
                    desired_roth_conversions = self._resolve_roth_conversion_amounts(
                        policy=roth_conversion_policy,
                        current_age=current_age,
                        year_index=year,
                        filing_status=p.filing_status,
                        dividends=dividends,
                        ss_income=ss_income,
                        ordinary_income_base=ordinary_income_base,
                        active=active,
                        fixed_amount=p.roth_conversion_amount,
                        traditional_rmd=withdrawal_result["traditional_rmd"],
                    )
                    roth_conversions = self.tracker.convert_traditional_to_roth(
                        desired_roth_conversions,
                        mask=active,
                    )

                spending_withdrawal = self.tracker.withdraw(
                    remaining_net_need,
                    current_age,
                    include_rmd=not (
                        (
                            roth_conversion_policy != "fixed_amount"
                            or p.roth_conversion_amount > 0
                        )
                        and current_age >= RMD_START_AGE
                    ),
                    mask=active,
                )
                withdrawal_result = _merge_withdrawal_results(
                    withdrawal_result, spending_withdrawal
                )
                traditional_rmd = withdrawal_result["traditional_rmd"]
                traditional_withdrawal = withdrawal_result["traditional"]
                roth_withdrawal = withdrawal_result["roth"]
                taxable_withdrawal = withdrawal_result["taxable"]
                taxable_cash_withdrawal = withdrawal_result["taxable_cash"]
                taxable_capital_gains = withdrawal_result["taxable_capital_gains"]
                ordinary_income = (
                    np.asarray(ordinary_income_base, dtype=float)
                    + traditional_rmd
                    + traditional_withdrawal
                    + roth_conversions
                )
                tax_results, estimated_taxes = self._calculate_holdings_taxes(
                    n_sims=n_sims,
                    year_index=year,
                    current_age=current_age,
                    filing_status=p.filing_status,
                    dividends=dividends,
                    ss_income=ss_income,
                    ordinary_income_base=ordinary_income_base,
                    roth_conversions=roth_conversions,
                    withdrawal_result=withdrawal_result,
                    agi_two_years_prior=agi_two_years_prior,
                )

                for _ in range(TAX_GROSS_UP_MAX_ITERATIONS):
                    required_portfolio_cash = np.where(
                        active,
                        np.maximum(
                            0,
                            spending_need
                            + estimated_taxes
                            - total_income_for_spending,
                        ),
                        0.0,
                    )
                    shortfall = np.where(
                        active,
                        np.maximum(
                            0, required_portfolio_cash - withdrawal_result["total"]
                        ),
                        0.0,
                    )
                    if not np.any(shortfall > TAX_GROSS_UP_TOLERANCE):
                        break

                    extra_withdrawal = self.tracker.withdraw(
                        shortfall,
                        current_age,
                        include_rmd=False,
                        mask=active,
                    )
                    if not np.any(extra_withdrawal["total"] > TAX_GROSS_UP_TOLERANCE):
                        break

                    withdrawal_result = _merge_withdrawal_results(
                        withdrawal_result, extra_withdrawal
                    )
                    tax_results, estimated_taxes = self._calculate_holdings_taxes(
                        n_sims=n_sims,
                        year_index=year,
                        current_age=current_age,
                        filing_status=p.filing_status,
                        dividends=dividends,
                        ss_income=ss_income,
                        ordinary_income_base=ordinary_income_base,
                        roth_conversions=roth_conversions,
                        withdrawal_result=withdrawal_result,
                        agi_two_years_prior=agi_two_years_prior,
                    )

                required_portfolio_cash = np.where(
                    active,
                    np.maximum(
                        0, spending_need + estimated_taxes - total_income_for_spending
                    ),
                    0.0,
                )
                surplus_cash = np.where(
                    active,
                    np.maximum(0, withdrawal_result["total"] - required_portfolio_cash),
                    0.0,
                )
                surplus_redeposited = surplus_cash
                if np.any(surplus_cash > TAX_GROSS_UP_TOLERANCE):
                    self.tracker.deposit_to_taxable(surplus_cash, mask=active)

                traditional_rmd = withdrawal_result["traditional_rmd"]
                traditional_withdrawal = withdrawal_result["traditional"]
                roth_withdrawal = withdrawal_result["roth"]
                taxable_withdrawal = withdrawal_result["taxable"]
                taxable_cash_withdrawal = withdrawal_result["taxable_cash"]
                taxable_capital_gains = withdrawal_result["taxable_capital_gains"]
                ordinary_income = (
                    np.asarray(ordinary_income_base, dtype=float)
                    + traditional_rmd
                    + traditional_withdrawal
                    + roth_conversions
                )
                gross_withdrawal = withdrawal_result["total"] - surplus_cash
                medicare_part_b_premium = np.asarray(
                    tax_results["medicare_part_b_premium"]
                ).flatten()
                roth_explainability = self._calculate_roth_explainability(
                    n_sims=n_sims,
                    year_index=year,
                    current_age=current_age,
                    filing_status=p.filing_status,
                    dividends=dividends,
                    ss_income=ss_income,
                    ordinary_income_base=ordinary_income_base,
                    roth_conversions=roth_conversions,
                    withdrawal_result=withdrawal_result,
                    agi_two_years_prior=agi_two_years_prior,
                    active=active,
                    tax_results=tax_results,
                )
                medicare_part_b_irmaa_increment = roth_explainability[
                    "medicare_part_b_irmaa_increment"
                ]
                medicare_part_b_irmaa_bracket = roth_explainability[
                    "medicare_part_b_irmaa_bracket"
                ]
                medicare_part_d_premium_surcharge = np.asarray(
                    tax_results["medicare_part_d_premium_surcharge"]
                ).flatten()
                medicare_part_d_irmaa_bracket = roth_explainability[
                    "medicare_part_d_irmaa_bracket"
                ]
                medicare_total_premium = roth_explainability["medicare_total_premium"]
                medicare_premium_delta_vs_no_roth_conversion = roth_explainability[
                    "medicare_premium_delta_vs_no_roth_conversion"
                ]
                federal_taxable_income = roth_explainability["federal_taxable_income"]
                federal_taxable_income_without_roth_conversion = roth_explainability[
                    "federal_taxable_income_without_roth_conversion"
                ]
                federal_bracket_headroom_used = roth_explainability[
                    "federal_bracket_headroom_used"
                ]
                federal_marginal_rate_on_last_conversion_dollar = roth_explainability[
                    "federal_marginal_rate_on_last_conversion_dollar"
                ]

                # Apply growth only to active paths and freeze balances after death/depletion.
                self.tracker.apply_growth(year, mask=active)
                new_value = np.where(active, self.tracker.total_balance, current_value)
                traditional_balance_end = self.tracker.traditional_balance.copy()
                roth_balance_end = self.tracker.roth_balance.copy()
                taxable_balance_end = self.tracker.taxable_balance.copy()

            else:
                gross_withdrawal = net_need.copy()
                taxable_withdrawal = gross_withdrawal.copy()
                taxable_capital_gains = gross_withdrawal.copy()
                ordinary_income = np.asarray(ordinary_income_base, dtype=float)
                tax_results, estimated_taxes = self._calculate_legacy_taxes(
                    year_index=year,
                    current_age=current_age,
                    filing_status=p.filing_status,
                    dividends=dividends,
                    ss_income=ss_income,
                    ordinary_income_base=ordinary_income_base,
                    withdrawal_amount=gross_withdrawal,
                    agi_two_years_prior=agi_two_years_prior,
                )

                for _ in range(TAX_GROSS_UP_MAX_ITERATIONS):
                    required_portfolio_cash = np.where(
                        active,
                        np.maximum(
                            0,
                            spending_need
                            + estimated_taxes
                            - total_income_for_spending,
                        ),
                        0.0,
                    )
                    if np.allclose(
                        required_portfolio_cash,
                        gross_withdrawal,
                        atol=TAX_GROSS_UP_TOLERANCE,
                        rtol=0,
                    ):
                        gross_withdrawal = required_portfolio_cash
                        break

                    gross_withdrawal = required_portfolio_cash
                    tax_results, estimated_taxes = self._calculate_legacy_taxes(
                        year_index=year,
                        current_age=current_age,
                        filing_status=p.filing_status,
                        dividends=dividends,
                        ss_income=ss_income,
                        ordinary_income_base=ordinary_income_base,
                        withdrawal_amount=gross_withdrawal,
                        agi_two_years_prior=agi_two_years_prior,
                    )

                # Portfolio dynamics - price returns only, dividends are income not growth.
                growth = np.where(active, current_value * price_growth[:, year], 0.0)
                new_value = np.where(
                    active, current_value + growth - gross_withdrawal, current_value
                )
                taxable_withdrawal = gross_withdrawal.copy()
                taxable_capital_gains = gross_withdrawal.copy()
                taxable_balance_end = new_value.copy()
                medicare_part_b_premium = np.asarray(
                    tax_results["medicare_part_b_premium"]
                ).flatten()
                medicare_part_d_premium_surcharge = np.asarray(
                    tax_results["medicare_part_d_premium_surcharge"]
                ).flatten()
                medicare_total_premium = _tax_result_array(
                    tax_results, "total_medicare_premium", n_sims
                )
                medicare_part_b_irmaa_increment = _tax_result_array(
                    tax_results, "medicare_part_b_irmaa_increment", n_sims
                )
                medicare_part_b_irmaa_bracket = _tax_result_label_array(
                    tax_results, "medicare_part_b_irmaa_bracket", n_sims
                )
                medicare_part_d_irmaa_bracket = _tax_result_label_array(
                    tax_results, "medicare_part_d_irmaa_bracket", n_sims
                )
                federal_taxable_income = _tax_result_array(
                    tax_results, "taxable_income", n_sims
                )
                federal_taxable_income_without_roth_conversion = (
                    federal_taxable_income.copy()
                )

            # Track depletion
            depleted = (current_value > 0) & (new_value <= 0)
            depleted_mask = depleted & (failure_year > year)
            failure_year[depleted_mask] = year + 1

            # Update paths
            paths[:, year + 1] = np.maximum(0, new_value)
            total_withdrawn[active] += gross_withdrawal[active]
            total_taxes[active] += np.asarray(tax_results["total_tax"]).flatten()[active]
            total_medicare_premiums[active] += np.asarray(
                tax_results["total_medicare_premium"]
            ).flatten()[active]
            total_roth_conversions[active] += roth_conversions[active]

            # Store yearly breakdown data
            yearly_employment[:, year] = (
                np.broadcast_to(employment_total, n_sims)
                if isinstance(employment_total, np.ndarray)
                else employment_total
            )
            yearly_ss[:, year] = (
                np.broadcast_to(ss_income, n_sims)
                if isinstance(ss_income, np.ndarray)
                else ss_income
            )
            yearly_pension[:, year] = pension_total
            yearly_dividends[:, year] = dividends
            yearly_annuity[:, year] = annuity_array
            yearly_traditional_rmd[:, year] = traditional_rmd
            yearly_traditional_withdrawal[:, year] = traditional_withdrawal
            yearly_roth_withdrawal[:, year] = roth_withdrawal
            yearly_taxable_withdrawal[:, year] = taxable_withdrawal
            yearly_taxable_cash_withdrawal[:, year] = taxable_cash_withdrawal
            yearly_taxable_capital_gains[:, year] = taxable_capital_gains
            yearly_surplus_redeposited[:, year] = surplus_redeposited
            yearly_roth_conversion[:, year] = roth_conversions
            yearly_ordinary_income[:, year] = ordinary_income
            yearly_withdrawal[:, year] = gross_withdrawal
            yearly_federal_tax[:, year] = np.asarray(
                tax_results["federal_income_tax"]
            ).flatten()
            yearly_state_tax[:, year] = np.asarray(
                tax_results["state_income_tax"]
            ).flatten()
            yearly_total_tax[:, year] = np.asarray(tax_results["total_tax"]).flatten()
            yearly_federal_taxable_income[:, year] = federal_taxable_income
            yearly_federal_taxable_income_without_roth_conversion[:, year] = (
                federal_taxable_income_without_roth_conversion
            )
            yearly_federal_bracket_headroom_used[:, year] = (
                federal_bracket_headroom_used
            )
            yearly_federal_marginal_rate_on_last_conversion_dollar[:, year] = (
                federal_marginal_rate_on_last_conversion_dollar
            )
            yearly_medicare_part_b_premium[:, year] = medicare_part_b_premium
            yearly_medicare_part_b_irmaa_increment[:, year] = (
                medicare_part_b_irmaa_increment
            )
            yearly_medicare_part_d_premium_surcharge[:, year] = (
                medicare_part_d_premium_surcharge
            )
            yearly_medicare_total_premium[:, year] = medicare_total_premium
            yearly_medicare_premium_delta_vs_no_roth_conversion[:, year] = (
                medicare_premium_delta_vs_no_roth_conversion
            )
            yearly_medicare_part_b_irmaa_bracket[:, year] = (
                medicare_part_b_irmaa_bracket
            )
            yearly_medicare_part_d_irmaa_bracket[:, year] = (
                medicare_part_d_irmaa_bracket
            )
            yearly_adjusted_gross_income[:, year] = np.asarray(
                tax_results["adjusted_gross_income"]
            ).flatten()
            yearly_spending[:, year] = spending_need
            yearly_inflation_rate[:, year] = current_inflation_rate
            yearly_cumulative_inflation[:, year] = inflation_factor
            yearly_traditional_balance_end[:, year] = traditional_balance_end
            yearly_roth_balance_end[:, year] = roth_balance_end
            yearly_taxable_balance_end[:, year] = taxable_balance_end

            # Yield progress after each year
            yield ("progress", year + 1, n_years)

        # Calculate results
        final_values = paths[:, -1]
        real_paths = np.divide(
            paths,
            inflation_factors,
            out=np.zeros_like(paths),
            where=inflation_factors > 0,
        )
        real_final_values = real_paths[:, -1]

        # Store per-path arrays for downstream use (e.g., annuity comparison)
        self._paths = paths
        self._real_paths = real_paths
        self._failure_year = failure_year
        self._total_withdrawn = total_withdrawn
        self._total_taxes = total_taxes
        self._total_medicare_premiums = total_medicare_premiums
        self._total_roth_conversions = total_roth_conversions

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
            int(p.current_age + np.median(depleted_sims))
            if len(depleted_sims) > 0
            else None
        )

        # 10-year failure probability
        prob_10_year_failure = float(np.mean(failure_year <= 10))

        # Build year-by-year breakdown for one coherent representative path.
        representative_index = int(
            np.argmin(
                np.abs(real_final_values - float(np.median(real_final_values)))
            )
        )
        year_breakdown = []
        for year in range(n_years):
            current_age = p.current_age + year
            portfolio_start = float(paths[representative_index, year])
            portfolio_end = float(paths[representative_index, year + 1])

            employment = float(yearly_employment[representative_index, year])
            ss = float(yearly_ss[representative_index, year])
            pension_val = float(yearly_pension[representative_index, year])
            divs = float(yearly_dividends[representative_index, year])
            annuity_val = float(yearly_annuity[representative_index, year])
            traditional_rmd_val = float(
                yearly_traditional_rmd[representative_index, year]
            )
            traditional_withdrawal_val = float(
                yearly_traditional_withdrawal[representative_index, year]
            )
            roth_withdrawal_val = float(yearly_roth_withdrawal[representative_index, year])
            taxable_withdrawal_val = float(
                yearly_taxable_withdrawal[representative_index, year]
            )
            taxable_cash_withdrawal_val = float(
                yearly_taxable_cash_withdrawal[representative_index, year]
            )
            taxable_capital_gains_val = float(
                yearly_taxable_capital_gains[representative_index, year]
            )
            surplus_redeposited_val = float(
                yearly_surplus_redeposited[representative_index, year]
            )
            roth_conversion = float(yearly_roth_conversion[representative_index, year])
            ordinary_income = float(yearly_ordinary_income[representative_index, year])
            withdrawal = float(yearly_withdrawal[representative_index, year])
            fed_tax = float(yearly_federal_tax[representative_index, year])
            state_tax = float(yearly_state_tax[representative_index, year])
            total_tax = float(yearly_total_tax[representative_index, year])
            federal_taxable_income = float(
                yearly_federal_taxable_income[representative_index, year]
            )
            federal_taxable_income_without_roth_conversion = float(
                yearly_federal_taxable_income_without_roth_conversion[
                    representative_index, year
                ]
            )
            federal_bracket_headroom_used = float(
                yearly_federal_bracket_headroom_used[representative_index, year]
            )
            federal_marginal_rate_on_last_conversion_dollar = float(
                yearly_federal_marginal_rate_on_last_conversion_dollar[
                    representative_index, year
                ]
            )
            medicare_part_b = float(
                yearly_medicare_part_b_premium[representative_index, year]
            )
            medicare_part_b_irmaa_increment = float(
                yearly_medicare_part_b_irmaa_increment[representative_index, year]
            )
            medicare_part_b_irmaa_bracket = str(
                yearly_medicare_part_b_irmaa_bracket[representative_index, year]
            )
            medicare_part_d = float(
                yearly_medicare_part_d_premium_surcharge[representative_index, year]
            )
            medicare_part_d_irmaa_bracket = str(
                yearly_medicare_part_d_irmaa_bracket[representative_index, year]
            )
            medicare_total_premium = float(
                yearly_medicare_total_premium[representative_index, year]
            )
            medicare_premium_delta_vs_no_roth_conversion = float(
                yearly_medicare_premium_delta_vs_no_roth_conversion[
                    representative_index, year
                ]
            )
            spending_target = float(yearly_spending[representative_index, year])
            inflation_rate = float(yearly_inflation_rate[representative_index, year])
            cumulative_inflation = float(
                yearly_cumulative_inflation[representative_index, year]
            )
            traditional_balance_end = float(
                yearly_traditional_balance_end[representative_index, year]
            )
            roth_balance_end = float(
                yearly_roth_balance_end[representative_index, year]
            )
            taxable_balance_end = float(
                yearly_taxable_balance_end[representative_index, year]
            )

            total_income = employment + ss + pension_val + divs + annuity_val
            net_income = (
                total_income + withdrawal - total_tax - medicare_part_b - medicare_part_d
            )
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
                    inflation_rate=inflation_rate,
                    cumulative_inflation=cumulative_inflation,
                    spending_target=spending_target,
                    spending_target_real=(
                        spending_target / cumulative_inflation
                        if cumulative_inflation > 0
                        else spending_target
                    ),
                    employment_income=employment,
                    social_security=ss,
                    pension=pension_val,
                    dividends=divs,
                    annuity=annuity_val,
                    total_income=total_income,
                    traditional_rmd=traditional_rmd_val,
                    traditional_withdrawal=traditional_withdrawal_val,
                    roth_withdrawal=roth_withdrawal_val,
                    taxable_withdrawal=taxable_withdrawal_val,
                    taxable_cash_withdrawal=taxable_cash_withdrawal_val,
                    taxable_capital_gains=taxable_capital_gains_val,
                    surplus_redeposited_to_taxable_cash=surplus_redeposited_val,
                    roth_conversion=roth_conversion,
                    ordinary_income=ordinary_income,
                    federal_taxable_income=federal_taxable_income,
                    federal_taxable_income_without_roth_conversion=(
                        federal_taxable_income_without_roth_conversion
                    ),
                    federal_bracket_headroom_used=federal_bracket_headroom_used,
                    federal_marginal_rate_on_last_conversion_dollar=(
                        federal_marginal_rate_on_last_conversion_dollar
                    ),
                    withdrawal=withdrawal,
                    federal_tax=fed_tax,
                    state_tax=state_tax,
                    total_tax=total_tax,
                    medicare_part_b_premium=medicare_part_b,
                    medicare_part_b_irmaa_increment=medicare_part_b_irmaa_increment,
                    medicare_part_b_irmaa_bracket=medicare_part_b_irmaa_bracket,
                    medicare_part_d_premium_surcharge=medicare_part_d,
                    medicare_part_d_irmaa_bracket=medicare_part_d_irmaa_bracket,
                    medicare_total_premium=medicare_total_premium,
                    medicare_premium_delta_vs_no_roth_conversion=(
                        medicare_premium_delta_vs_no_roth_conversion
                    ),
                    effective_tax_rate=effective_rate,
                    traditional_balance_end=traditional_balance_end,
                    roth_balance_end=roth_balance_end,
                    taxable_balance_end=taxable_balance_end,
                    net_income=net_income,
                )
            )

        result = SimulationResult(
            success_rate=success_rate,
            median_final_value=float(np.median(final_values)),
            mean_final_value=float(np.mean(final_values)),
            median_final_value_real=float(np.median(real_final_values)),
            mean_final_value_real=float(np.mean(real_final_values)),
            percentiles={
                "p5": float(np.percentile(final_values, 5)),
                "p25": float(np.percentile(final_values, 25)),
                "p50": float(np.percentile(final_values, 50)),
                "p75": float(np.percentile(final_values, 75)),
                "p95": float(np.percentile(final_values, 95)),
            },
            percentiles_real={
                "p5": float(np.percentile(real_final_values, 5)),
                "p25": float(np.percentile(real_final_values, 25)),
                "p50": float(np.percentile(real_final_values, 50)),
                "p75": float(np.percentile(real_final_values, 75)),
                "p95": float(np.percentile(real_final_values, 95)),
            },
            median_depletion_age=median_depletion_age,
            median_depletion_year=(
                float(np.median(depleted_sims)) if len(depleted_sims) > 0 else None
            ),
            total_withdrawn_median=float(np.median(total_withdrawn)),
            total_taxes_median=float(np.median(total_taxes)),
            total_medicare_premiums_median=float(
                np.median(total_medicare_premiums)
            ),
            total_roth_conversions_median=float(np.median(total_roth_conversions)),
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
        Each progress event: {"type": "progress", "year": int, "total_years": int}
        Final complete event: {"type": "complete", "result": SimulationResult}
        """
        for event in self._simulate_core():
            if event[0] == "progress":
                yield {"type": "progress", "year": event[1], "total_years": event[2]}
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
    total_medicare_premiums: np.ndarray | None = None,
) -> dict:
    """Compare simulation results to an annuity option.

    Args:
        total_withdrawn: Per-path total withdrawal amounts from the simulator.
        total_taxes: Per-path total tax amounts from the simulator.
        total_medicare_premiums: Per-path Medicare Part B premium amounts from the
            simulator, plus any modeled Part D IRMAA surcharge.
            When provided, the actual fraction of paths beating the annuity
            is computed instead of a heuristic estimate.
    """
    annuity_total = annuity_monthly_payment * 12 * annuity_guarantee_years

    # Simulation total income (withdrawals minus taxes)
    sim_total = (
        simulation_result.total_withdrawn_median
        - simulation_result.total_taxes_median
        - simulation_result.total_medicare_premiums_median
    )

    # Compute real probability from path-level data
    if (
        total_withdrawn is not None
        and total_taxes is not None
        and total_medicare_premiums is not None
    ):
        net_income_per_path = total_withdrawn - total_taxes - total_medicare_premiums
        prob_beats = float(np.mean(net_income_per_path > annuity_total))
    else:
        # Fallback: simple estimate from median
        prob_beats = float(sim_total > annuity_total) * 0.5 + 0.25

    # Generate neutral summary
    if simulation_result.success_rate > 0.9 and prob_beats > 0.6:
        summary = "The portfolio path exceeds the annuity in a high share of modeled outcomes while keeping depletion risk relatively low."
    elif simulation_result.success_rate < 0.7:
        summary = (
            "The annuity compares favorably in this model because the portfolio path shows meaningful depletion risk."
        )
    else:
        summary = (
            "Results are mixed in this model: the annuity offers certainty while the portfolio keeps more upside."
        )

    return {
        "annuity_total_guaranteed": annuity_total,
        "probability_simulation_beats_annuity": prob_beats,
        "simulation_median_total_income": sim_total,
        "summary": summary,
    }
