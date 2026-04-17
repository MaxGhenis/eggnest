"""Pydantic models for API requests and responses."""

from typing import Literal

from pydantic import BaseModel, Field

from .rmd import RMD_START_AGE

# Account types for tax treatment
AccountType = Literal[
    "traditional_401k",
    "traditional_ira",
    "roth_401k",
    "roth_ira",
    "taxable",
]

# Supported funds/indexes
FundType = Literal["vt", "sp500", "bnd", "treasury"]
WithdrawalStrategy = Literal[
    "traditional_first", "roth_first", "taxable_first", "pro_rata"
]
RothConversionPolicy = Literal[
    "fixed_amount",
    "fill_standard_deduction",
    "fill_12_percent_bracket",
    "fill_22_percent_bracket",
]


def default_roth_conversion_end_age(start_age: int, max_age: int) -> int:
    """Return the implicit Roth conversion end age for one scenario."""
    if start_age >= RMD_START_AGE:
        return max_age
    return min(RMD_START_AGE - 1, max_age)


class Holding(BaseModel):
    """A single holding in the portfolio."""

    account_type: AccountType = Field(
        ..., description="Type of account (determines tax treatment)"
    )
    fund: FundType = Field(..., description="Fund/index this holding is invested in")
    balance: float = Field(..., ge=0, description="Current balance in this holding")
    cost_basis: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Optional tax basis for taxable holdings. If omitted, EggNest assumes "
            "zero basis and treats the holding as fully appreciated."
        ),
    )

    def model_post_init(self, __context) -> None:
        """Validate cost basis usage."""
        if self.cost_basis is None:
            return
        if self.cost_basis > self.balance:
            raise ValueError("cost_basis cannot exceed holding balance")
        if self.account_type != "taxable":
            raise ValueError("cost_basis is only valid for taxable holdings")


class SpouseInput(BaseModel):
    """Spouse details for joint simulation."""

    age: int = Field(..., ge=18, le=100, description="Spouse's current age")
    gender: Literal["male", "female"] = Field(
        default="female", description="Spouse's gender for mortality"
    )
    social_security_monthly: float = Field(
        default=0, ge=0, description="Spouse's monthly Social Security"
    )
    social_security_start_age: int = Field(
        default=67, ge=62, le=70, description="Age when spouse starts Social Security"
    )
    pension_annual: float = Field(
        default=0, ge=0, description="Spouse's annual pension"
    )
    employment_income: float = Field(
        default=0, ge=0, description="Spouse's annual employment income"
    )
    employment_growth_rate: float = Field(
        default=0.03, ge=0, le=0.1, description="Spouse's wage growth rate"
    )
    retirement_age: int = Field(
        default=65, ge=18, le=100, description="Spouse's retirement age"
    )


class AnnuityInput(BaseModel):
    """Annuity parameters."""

    monthly_payment: float = Field(..., gt=0, description="Monthly annuity payment")
    annuity_type: Literal["life_with_guarantee", "fixed_period", "life_only"] = Field(
        default="life_with_guarantee", description="Type of annuity"
    )
    guarantee_years: int = Field(
        default=15, ge=0, le=30, description="Guarantee period in years"
    )


class EngineResultMetadata(BaseModel):
    """Metadata stamped onto engine-facing result objects."""

    engine_version: str = Field(..., description="Installed EggNest package version")
    method_version: str = Field(
        ..., description="Version tag for the modeled method and output contract"
    )
    random_seed: int | None = Field(
        default=None,
        description="Random seed used for the run, if the engine resolved one",
    )
    assumptions_summary: str = Field(
        ..., description="Short summary of the key assumptions used for the result"
    )


class SimulationInput(BaseModel):
    """Input parameters for a retirement simulation."""

    # Holdings-based portfolio (preferred)
    holdings: list[Holding] | None = Field(
        default=None,
        description="List of holdings with account types and funds. If provided, overrides initial_capital and stock_allocation.",
    )
    withdrawal_strategy: WithdrawalStrategy = Field(
        default="taxable_first",
        description="Order to withdraw from accounts: taxable_first (most common), traditional_first, roth_first, or pro_rata",
    )
    roth_conversion_amount: float = Field(
        default=0,
        ge=0,
        description=(
            "Optional annual amount to convert from traditional accounts to Roth "
            "accounts during the simulation. Conversion taxes are modeled, but "
            "the converted assets remain in the portfolio."
        ),
    )
    roth_conversion_policy: RothConversionPolicy = Field(
        default="fixed_amount",
        description=(
            "How to size Roth conversions during the simulation: a fixed annual "
            "amount, filling unused standard deduction space, or filling the "
            "modeled 12% or 22% marginal federal bracket."
        ),
    )
    roth_conversion_start_age: int | None = Field(
        default=None,
        ge=18,
        le=100,
        description=(
            "Age when Roth conversions start. If omitted and roth_conversion_amount "
            "is positive, EggNest starts at current_age."
        ),
    )
    roth_conversion_end_age: int | None = Field(
        default=None,
        ge=18,
        le=100,
        description=(
            "Age when Roth conversions stop. If omitted and roth_conversion_amount "
            "is positive, EggNest stops before RMD age when starting earlier, "
            "or at max_age when already in the RMD years."
        ),
    )

    # Legacy: simple portfolio (for backward compatibility)
    initial_capital: float | None = Field(
        default=None,
        gt=0,
        description="Starting investment amount (legacy, use holdings instead)",
    )
    annual_spending: float = Field(
        ...,
        gt=0,
        description=(
            "Annual spending target. When spending_mode='real' (default), this "
            "is interpreted in today's dollars and inflated each year. When "
            "spending_mode='nominal', it stays flat in nominal dollars."
        ),
    )
    home_value: float = Field(
        default=0,
        ge=0,
        description="Home equity value (not included in portfolio, for net worth display)",
    )
    current_age: int = Field(..., ge=18, le=100, description="Current age")
    max_age: int = Field(
        default=95, ge=50, le=120, description="Planning horizon (max age)"
    )
    gender: Literal["male", "female"] = Field(
        default="male", description="Gender for mortality tables"
    )

    # Income sources
    social_security_monthly: float = Field(
        default=0, ge=0, description="Monthly Social Security benefits"
    )
    social_security_start_age: int = Field(
        default=67, ge=62, le=70, description="Age when Social Security starts"
    )
    pension_annual: float = Field(
        default=0, ge=0, description="Annual pension/other guaranteed income"
    )
    employment_income: float = Field(
        default=0, ge=0, description="Annual employment income (pre-retirement)"
    )
    employment_growth_rate: float = Field(
        default=0.03, ge=0, le=0.1, description="Annual wage growth rate"
    )
    retirement_age: int = Field(
        default=65, ge=18, le=100, description="Age when employment income stops"
    )
    spending_mode: Literal["real", "nominal"] = Field(
        default="real",
        description=(
            "Whether annual_spending is a real spending target in today's "
            "dollars (default) or a flat nominal dollar amount."
        ),
    )
    inflation_model: Literal["historical", "constant"] = Field(
        default="historical",
        description=(
            "Inflation process for real spending and real reporting: "
            "'historical' samples annual CPI from history, 'constant' uses the "
            "fixed inflation_rate each year."
        ),
    )
    inflation_rate: float = Field(
        default=0.025,
        ge=0,
        le=0.1,
        description=(
            "Annual inflation rate used when inflation_model='constant'. "
            "Also serves as the fallback assumption for legacy clients."
        ),
    )
    social_security_inflation_adjusted: bool = Field(
        default=True,
        description=(
            "If true, Social Security benefits receive the simulated inflation "
            "COLA after claiming."
        ),
    )
    pension_cola_rate: float = Field(
        default=0.0,
        ge=0,
        le=0.1,
        description="Annual nominal COLA applied to pension income.",
    )
    annuity_cola_rate: float = Field(
        default=0.0,
        ge=0,
        le=0.1,
        description="Annual nominal COLA applied to annuity payments.",
    )

    # Tax settings
    state: str = Field(default="CA", description="Two-letter state code")
    filing_status: Literal["single", "married_filing_jointly", "head_of_household"] = (
        Field(default="single", description="Tax filing status")
    )

    # Spouse (optional)
    has_spouse: bool = Field(default=False, description="Include spouse in simulation")
    spouse: SpouseInput | None = Field(
        default=None, description="Spouse details if has_spouse is True"
    )

    # Annuity (optional)
    has_annuity: bool = Field(default=False, description="Include annuity income")
    annuity: AnnuityInput | None = Field(
        default=None, description="Annuity details if has_annuity is True"
    )

    # Simulation settings
    n_simulations: int = Field(
        default=10_000, ge=100, le=100_000, description="Number of Monte Carlo paths"
    )
    random_seed: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Optional RNG seed for deterministic simulations. If omitted, EggNest "
            "uses fresh randomness on each run."
        ),
    )
    include_mortality: bool = Field(
        default=True, description="Account for probability of death each year"
    )
    return_model: Literal["bootstrap", "block_bootstrap", "historical", "normal"] = (
        Field(
            default="bootstrap",
            description="Return generation method: bootstrap (default), block_bootstrap, historical, or normal",
        )
    )

    # Market assumptions for the optional normal return model (nominal returns)
    # Note: expected_return and return_volatility are only used when return_model="normal"
    expected_return: float = Field(
        default=0.07,
        description="Expected nominal annual return (only for normal model)",
    )
    return_volatility: float = Field(
        default=0.16,
        description="Annual return volatility (only for normal model)",
    )
    dividend_yield: float = Field(default=0.02, description="Annual dividend yield")

    # Asset allocation
    stock_allocation: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Fraction of portfolio in stocks (0.0 to 1.0). Remainder is bonds.",
    )

    # Index selection
    stock_index: Literal["sp500", "vt"] = Field(
        default="sp500",
        description=(
            "Stock index: 'sp500' (S&P 500, 1928-2024, default long-history "
            "baseline) or 'vt' (Total World, 2008-2024)"
        ),
    )
    bond_index: Literal["treasury", "bnd"] = Field(
        default="treasury",
        description=(
            "Bond index: 'treasury' (10-Year, 1928-2024, default long-history "
            "baseline) or 'bnd' (Total Bond Market, 2007-2024)"
        ),
    )

    def model_post_init(self, __context) -> None:
        """Validate Roth conversion window inputs."""
        if (
            self.roth_conversion_policy == "fixed_amount"
            and self.roth_conversion_amount <= 0
        ):
            return

        start_age = (
            self.roth_conversion_start_age
            if self.roth_conversion_start_age is not None
            else self.current_age
        )
        end_age = (
            self.roth_conversion_end_age
            if self.roth_conversion_end_age is not None
            else default_roth_conversion_end_age(start_age, self.max_age)
        )
        if end_age < start_age:
            raise ValueError("roth_conversion_end_age cannot be earlier than start age")
        if not self.holdings:
            raise ValueError(
                "Roth conversion modeling requires detailed holdings with account types"
            )
        if not self.has_traditional_accounts:
            raise ValueError(
                "Roth conversion modeling requires at least one traditional account"
            )

    @property
    def total_capital(self) -> float:
        """Get total portfolio value from holdings or initial_capital."""
        if self.holdings:
            return sum(h.balance for h in self.holdings)
        return self.initial_capital or 0

    @property
    def has_traditional_accounts(self) -> bool:
        """Check if portfolio has any traditional (tax-deferred) accounts."""
        if not self.holdings:
            return False
        return any(
            h.account_type in ("traditional_401k", "traditional_ira")
            for h in self.holdings
        )

    @property
    def has_roth_accounts(self) -> bool:
        """Check if portfolio has any Roth (tax-free) accounts."""
        if not self.holdings:
            return False
        return any(h.account_type in ("roth_401k", "roth_ira") for h in self.holdings)

    def get_holdings_by_account_type(self, account_type: str) -> list["Holding"]:
        """Get all holdings for a specific account type."""
        if not self.holdings:
            return []
        return [h for h in self.holdings if h.account_type == account_type]

    def get_balance_by_account_type(self, account_type: str) -> float:
        """Get total balance for a specific account type."""
        return sum(h.balance for h in self.get_holdings_by_account_type(account_type))


class YearBreakdown(BaseModel):
    """Detailed breakdown for a single year in one representative simulation path."""

    age: int = Field(..., description="Age during this year")
    year_index: int = Field(..., description="Year index (0 = first year)")

    # Portfolio
    portfolio_start: float = Field(..., description="Portfolio value at start of year")
    portfolio_end: float = Field(..., description="Portfolio value at end of year")
    portfolio_return: float = Field(..., description="Investment return for this year")
    inflation_rate: float = Field(
        default=0, description="Inflation rate applied over this year"
    )
    cumulative_inflation: float = Field(
        default=1,
        description="Inflation multiplier at the start of the year relative to today",
    )
    spending_target: float = Field(
        default=0,
        description="Nominal spending target for the year after any inflation adjustment",
    )
    spending_target_real: float = Field(
        default=0,
        description="Same year's spending target in today's dollars",
    )

    # Income sources
    employment_income: float = Field(default=0, description="Employment income")
    social_security: float = Field(default=0, description="Social Security benefits")
    pension: float = Field(default=0, description="Pension income")
    dividends: float = Field(default=0, description="Dividend income from portfolio")
    annuity: float = Field(default=0, description="Annuity payments")
    total_income: float = Field(..., description="Total income for the year")

    # Withdrawals and taxes
    traditional_rmd: float = Field(
        default=0,
        description="Required minimum distribution withdrawn from traditional accounts",
    )
    traditional_withdrawal: float = Field(
        default=0,
        description="Additional traditional withdrawal beyond the RMD",
    )
    roth_withdrawal: float = Field(
        default=0,
        description="Tax-free withdrawal from Roth accounts",
    )
    taxable_withdrawal: float = Field(
        default=0,
        description="Withdrawal from invested taxable holdings",
    )
    taxable_cash_withdrawal: float = Field(
        default=0,
        description="Withdrawal from taxable cash reserves",
    )
    taxable_capital_gains: float = Field(
        default=0,
        description="Realized capital gains from taxable withdrawals",
    )
    surplus_redeposited_to_taxable_cash: float = Field(
        default=0,
        description=(
            "Excess gross-up cash redeposited to taxable cash after covering spending "
            "and taxes"
        ),
    )
    roth_conversion: float = Field(
        default=0,
        description="Amount converted from traditional accounts to Roth accounts",
    )
    ordinary_income: float = Field(
        default=0,
        description=(
            "Modeled ordinary income before Social Security taxation adjustments"
        ),
    )
    federal_taxable_income: float = Field(
        default=0,
        description="Modeled federal taxable income after any Roth conversion",
    )
    federal_taxable_income_without_roth_conversion: float = Field(
        default=0,
        description=(
            "Counterfactual modeled federal taxable income with the same-year Roth "
            "conversion removed"
        ),
    )
    federal_bracket_headroom_used: float = Field(
        default=0,
        description=(
            "Increase in modeled federal taxable income attributable to the year's "
            "Roth conversion"
        ),
    )
    federal_marginal_rate_on_last_conversion_dollar: float = Field(
        default=0,
        description=(
            "Modeled federal marginal tax rate on the last converted dollar for "
            "this year"
        ),
    )
    withdrawal: float = Field(
        ...,
        description=(
            "Net amount withdrawn from the portfolio after any same-year redeposit "
            "of surplus gross-up cash"
        ),
    )
    federal_tax: float = Field(default=0, description="Federal income tax")
    state_tax: float = Field(default=0, description="State income tax")
    total_tax: float = Field(..., description="Total taxes paid")
    medicare_part_b_premium: float = Field(
        default=0,
        description="Annual Medicare Part B premium, including any IRMAA adjustment",
    )
    medicare_part_b_irmaa_increment: float = Field(
        default=0,
        description="Part B IRMAA amount above the base annual Part B premium",
    )
    medicare_part_b_irmaa_bracket: str = Field(
        default="none",
        description="Modeled Part B IRMAA MAGI band for the year",
    )
    medicare_part_d_premium_surcharge: float = Field(
        default=0,
        description=(
            "Annual Medicare Part D IRMAA surcharge; excludes the underlying plan "
            "premium"
        ),
    )
    medicare_part_d_irmaa_bracket: str = Field(
        default="none",
        description="Modeled Part D IRMAA MAGI band for the year",
    )
    medicare_total_premium: float = Field(
        default=0,
        description=(
            "Annual Medicare Part B premium plus modeled Part D IRMAA surcharge"
        ),
    )
    medicare_premium_delta_vs_no_roth_conversion: float = Field(
        default=0,
        description=(
            "Annual Medicare premium difference versus a same-year no-conversion "
            "counterfactual"
        ),
    )
    medicare_premium_delta_vs_baseline: float = Field(
        default=0,
        description=(
            "Annual Medicare premium difference versus the selected Roth-comparison "
            "baseline scenario; zero outside comparisons"
        ),
    )
    effective_tax_rate: float = Field(default=0, description="Effective tax rate")

    # Account balances
    traditional_balance_end: float = Field(
        default=0,
        description="Traditional-account balance at the end of the year",
    )
    roth_balance_end: float = Field(
        default=0,
        description="Roth-account balance at the end of the year",
    )
    taxable_balance_end: float = Field(
        default=0,
        description="Taxable-account balance at the end of the year, including cash",
    )

    # Net
    net_income: float = Field(..., description="Net income after taxes")


class SimulationResult(BaseModel):
    """Results from a retirement simulation."""

    metadata: EngineResultMetadata | None = Field(
        default=None,
        description="Engine metadata for reproducibility and integration clients",
    )

    success_rate: float = Field(
        ..., description="Probability of not running out of money"
    )
    median_final_value: float = Field(..., description="Median portfolio value at end")
    mean_final_value: float = Field(..., description="Mean portfolio value at end")
    median_final_value_real: float = Field(
        default=0,
        description="Median end portfolio value in today's dollars",
    )
    mean_final_value_real: float = Field(
        default=0,
        description="Mean end portfolio value in today's dollars",
    )
    percentiles: dict[str, float] = Field(
        ..., description="Portfolio value percentiles (p5, p25, p50, p75, p95)"
    )
    percentiles_real: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "End portfolio value percentiles in today's dollars "
            "(p5, p25, p50, p75, p95)"
        ),
    )
    median_depletion_age: int | None = Field(
        None, description="Median age at depletion (if applicable)"
    )
    total_withdrawn_median: float = Field(
        ..., description="Median total withdrawals over simulation"
    )
    total_taxes_median: float = Field(..., description="Median total taxes paid")
    total_medicare_premiums_median: float = Field(
        default=0,
        description=(
            "Median total Medicare Part B premiums plus Part D IRMAA surcharges "
            "paid over the simulation"
        ),
    )
    total_roth_conversions_median: float = Field(
        default=0,
        description="Median total amount converted from traditional to Roth accounts",
    )

    # For charting
    percentile_paths: dict[str, list[float]] = Field(
        ..., description="Time series of percentile values (by age)"
    )

    # Year-by-year breakdown (representative path)
    year_breakdown: list[YearBreakdown] = Field(
        default_factory=list,
        description="Detailed year-by-year breakdown for a representative scenario path",
    )

    # Withdrawal rate info
    initial_withdrawal_rate: float = Field(
        ..., description="Initial withdrawal rate as percentage"
    )

    # Additional statistics
    prob_10_year_failure: float = Field(
        default=0, description="Probability of failure within 10 years"
    )

    # Backward compatibility
    median_depletion_year: float | None = Field(
        None, description="DEPRECATED: Use median_depletion_age instead"
    )


class HistoricalBacktestInput(BaseModel):
    """Input for deterministic historical cohort backtesting."""

    base_input: SimulationInput = Field(
        ..., description="Base simulation assumptions to replay over historical cohorts"
    )
    start_years: list[int] | None = Field(
        default=None,
        description=(
            "Optional specific retirement start years to run. If omitted, EggNest "
            "runs every valid cohort for the chosen horizon and selected assets."
        ),
    )


class HistoricalCohortResult(BaseModel):
    """Outcome for one historical retirement start year."""

    start_year: int
    success: bool
    final_value: float
    final_value_real: float
    total_withdrawn: float
    total_taxes: float
    total_medicare_premiums: float = 0
    total_roth_conversions: float = 0
    failure_age: int | None = None


class HistoricalBacktestResult(BaseModel):
    """Aggregate result across deterministic historical retirement cohorts."""

    metadata: EngineResultMetadata | None = Field(
        default=None,
        description="Engine metadata for reproducibility and integration clients",
    )

    horizon_years: int
    start_years: list[int]
    results: list[HistoricalCohortResult]
    success_rate: float
    median_final_value: float
    median_final_value_real: float
    total_withdrawn_median: float
    total_taxes_median: float
    total_medicare_premiums_median: float = 0
    total_roth_conversions_median: float = 0
    strongest_start_year: int
    weakest_start_year: int
    median_path: list[float]
    median_path_real: list[float]


class AnnuityComparison(BaseModel):
    """Input for comparing simulation to an annuity."""

    simulation_input: SimulationInput
    annuity_monthly_payment: float = Field(
        ..., gt=0, description="Monthly annuity payment"
    )
    annuity_guarantee_years: int = Field(
        default=20, ge=1, le=40, description="Annuity guarantee period"
    )


class AnnuityComparisonResult(BaseModel):
    """Results comparing simulation to annuity."""

    metadata: EngineResultMetadata | None = Field(
        default=None,
        description="Engine metadata for reproducibility and integration clients",
    )

    simulation_result: SimulationResult
    annuity_total_guaranteed: float
    probability_simulation_beats_annuity: float
    simulation_median_total_income: float
    summary: str


class SavedSimulation(BaseModel):
    """A saved simulation for a user."""

    id: str | None = None
    user_id: str | None = None
    name: str
    input_params: SimulationInput
    created_at: str | None = None
    updated_at: str | None = None


class MortalityRates(BaseModel):
    """Mortality rates by age."""

    ages: list[int]
    rates: list[float]
    survival_curve: list[float]


class StateComparisonInput(BaseModel):
    """Input for comparing outcomes across states."""

    base_input: SimulationInput
    compare_states: list[str] = Field(
        ..., min_length=1, max_length=10, description="List of state codes to compare"
    )


class StateResult(BaseModel):
    """Summary result for a single state."""

    state: str
    success_rate: float
    median_final_value: float
    total_taxes_median: float
    total_withdrawn_median: float
    net_after_tax_median: float


class StateComparisonResult(BaseModel):
    """Results comparing outcomes across states."""

    metadata: EngineResultMetadata | None = Field(
        default=None,
        description="Engine metadata for reproducibility and integration clients",
    )

    base_state: str
    results: list[StateResult]
    tax_savings_vs_base: dict[str, float] = Field(
        ..., description="Tax savings relative to base state (positive = saves money)"
    )


class SSTimingInput(BaseModel):
    """Input for Social Security timing comparison."""

    base_input: SimulationInput
    birth_year: int = Field(
        ..., ge=1900, le=2010, description="Birth year (determines Full Retirement Age)"
    )
    pia_monthly: float = Field(
        ...,
        gt=0,
        le=10000,
        description="Primary Insurance Amount (monthly benefit at FRA)",
    )
    claiming_ages: list[int] = Field(
        default=[62, 63, 64, 65, 66, 67, 68, 69, 70],
        min_length=1,
        max_length=9,
        description="Claiming ages to compare (62-70)",
    )


class SSTimingResult(BaseModel):
    """Result for a single claiming age."""

    claiming_age: int
    monthly_benefit: float = Field(
        ..., description="Adjusted monthly benefit at this claiming age"
    )
    annual_benefit: float = Field(..., description="Annual benefit (monthly * 12)")
    adjustment_factor: float = Field(
        ..., description="Factor applied to PIA (e.g., 0.7 = 30% reduction)"
    )
    success_rate: float
    median_final_value: float
    total_ss_income_median: float = Field(
        ..., description="Total SS income over lifetime (median)"
    )
    total_taxes_median: float
    breakeven_vs_62: int | None = Field(
        None, description="Age at which cumulative benefits exceed claiming at 62"
    )


class SSTimingComparisonResult(BaseModel):
    """Results comparing Social Security claiming strategies."""

    metadata: EngineResultMetadata | None = Field(
        default=None,
        description="Engine metadata for reproducibility and integration clients",
    )

    birth_year: int
    full_retirement_age: float
    pia_monthly: float
    results: list[SSTimingResult]
    highest_success_claiming_age: int = Field(
        ..., description="Claiming age with highest modeled success rate"
    )
    highest_lifetime_income_claiming_age: int = Field(
        ..., description="Claiming age with highest modeled lifetime Social Security income"
    )


class AllocationInput(BaseModel):
    """Input for asset allocation comparison."""

    base_input: SimulationInput
    allocations: list[float] = Field(
        default=[0.2, 0.4, 0.6, 0.8, 1.0],
        min_length=1,
        max_length=10,
        description="Stock allocations to compare (0.0 to 1.0)",
    )

    def model_post_init(self, __context) -> None:
        """Validate allocations are between 0 and 1."""
        for alloc in self.allocations:
            if not 0.0 <= alloc <= 1.0:
                raise ValueError(f"Allocation {alloc} must be between 0.0 and 1.0")


class AllocationResult(BaseModel):
    """Result for a single asset allocation."""

    stock_allocation: float = Field(..., description="Fraction in stocks (0.0 to 1.0)")
    bond_allocation: float = Field(..., description="Fraction in bonds (0.0 to 1.0)")
    success_rate: float
    median_final_value: float
    percentile_5_final_value: float = Field(
        ..., description="5th percentile final value (lower-tail case)"
    )
    percentile_95_final_value: float = Field(
        ..., description="95th percentile final value (upper-tail case)"
    )
    volatility: float = Field(..., description="Standard deviation of annual returns")
    expected_return: float = Field(..., description="Mean annual return")


class AllocationComparisonResult(BaseModel):
    """Results comparing asset allocation strategies."""

    metadata: EngineResultMetadata | None = Field(
        default=None,
        description="Engine metadata for reproducibility and integration clients",
    )

    results: list[AllocationResult]
    highest_success_allocation: float = Field(
        ..., description="Stock allocation with highest modeled success rate"
    )
    highest_safety_allocation: float = Field(
        ...,
        description="Stock allocation with the lowest volatility among high-success options",
    )
    summary: str = Field(
        ..., description="Plain-language summary based on the comparison results"
    )


class StrategyComparisonInput(BaseModel):
    """Input for withdrawal strategy comparison."""

    base_input: SimulationInput
    strategies: list[WithdrawalStrategy] = Field(
        default=["taxable_first", "traditional_first", "roth_first", "pro_rata"],
        min_length=1,
        max_length=4,
        description="Withdrawal strategies to compare",
    )


class StrategyScenarioSummary(BaseModel):
    """Summary metrics for one strategy under one evaluation lens."""

    success_rate: float
    median_final_value: float
    median_final_value_real: float
    total_taxes_median: float
    total_medicare_premiums_median: float = 0
    total_withdrawn_median: float


class HistoricalStrategySummary(StrategyScenarioSummary):
    """Historical cohort summary for one withdrawal strategy."""

    cohort_count: int = Field(..., description="Number of historical start years tested")
    strongest_start_year: int
    weakest_start_year: int
    worst_final_value_real: float = Field(
        ..., description="Lowest real final value among historical cohorts"
    )


class StrategyComparisonItem(BaseModel):
    """One withdrawal strategy with Monte Carlo and historical summaries."""

    strategy: WithdrawalStrategy
    monte_carlo: StrategyScenarioSummary
    historical: HistoricalStrategySummary
    blended_score: float = Field(
        ..., description="0-100 blended score across success, resilience, and taxes"
    )


class StrategyComparisonResult(BaseModel):
    """Results comparing withdrawal strategies for one household."""

    metadata: EngineResultMetadata | None = Field(
        default=None,
        description="Engine metadata for reproducibility and integration clients",
    )

    results: list[StrategyComparisonItem]
    top_scoring_strategy: WithdrawalStrategy = Field(
        ..., description="Highest-scoring strategy based on the blended score"
    )
    lowest_modeled_tax_strategy: WithdrawalStrategy = Field(
        ..., description="Strategy with the lowest Monte Carlo median taxes"
    )
    strongest_historical_strategy: WithdrawalStrategy = Field(
        ..., description="Strategy with the strongest historical cohort resilience"
    )
    summary: str = Field(
        ..., description="Plain-language summary of the comparison"
    )


class RothConversionInput(BaseModel):
    """Input for fixed-amount Roth conversion analysis."""

    base_input: SimulationInput
    annual_conversion_amounts: list[float] = Field(
        default=[0, 25_000, 50_000, 100_000],
        min_length=1,
        max_length=10,
        description="Annual Roth conversion amounts to compare",
    )
    conversion_policies: list[RothConversionPolicy] = Field(
        default=[
            "fill_standard_deduction",
            "fill_12_percent_bracket",
            "fill_22_percent_bracket",
        ],
        min_length=0,
        max_length=4,
        description=(
            "Dynamic Roth conversion policies to compare alongside any fixed annual amounts"
        ),
    )
    conversion_start_age: int | None = Field(
        default=None,
        ge=18,
        le=100,
        description="Age when conversions start. Defaults to current_age.",
    )
    conversion_end_age: int | None = Field(
        default=None,
        ge=18,
        le=100,
        description=(
            "Age when conversions stop. Defaults to the year before RMDs begin "
            "when starting earlier, or max_age when already in the RMD years."
        ),
    )

    def model_post_init(self, __context) -> None:
        """Validate Roth conversion analysis inputs."""
        if any(amount < 0 for amount in self.annual_conversion_amounts):
            raise ValueError("annual_conversion_amounts must all be non-negative")
        start_age = (
            self.conversion_start_age
            if self.conversion_start_age is not None
            else self.base_input.current_age
        )
        end_age = (
            self.conversion_end_age
            if self.conversion_end_age is not None
            else default_roth_conversion_end_age(start_age, self.base_input.max_age)
        )
        if end_age < start_age:
            raise ValueError("conversion_end_age cannot be earlier than start age")
        if not self.base_input.holdings:
            raise ValueError(
                "Roth conversion analysis requires detailed holdings with account types"
            )
        if not self.base_input.has_traditional_accounts:
            raise ValueError(
                "Roth conversion analysis requires at least one traditional account"
            )


class RothOptimizationInput(BaseModel):
    """Input for bounded Roth conversion search across windows and sizing rules."""

    base_input: SimulationInput
    annual_conversion_amounts: list[float] = Field(
        default=[0, 25_000, 50_000, 100_000],
        min_length=1,
        max_length=10,
        description="Fixed annual Roth conversion amounts to include in the search",
    )
    conversion_policies: list[RothConversionPolicy] = Field(
        default=[
            "fill_standard_deduction",
            "fill_12_percent_bracket",
            "fill_22_percent_bracket",
        ],
        min_length=0,
        max_length=4,
        description="Dynamic Roth conversion sizing policies to include in the search",
    )
    candidate_start_ages: list[int] | None = Field(
        default=None,
        description=(
            "Candidate ages when Roth conversions can begin. Defaults to a bounded "
            "set of ages spanning the current age through pre-RMD years."
        ),
    )
    window_lengths: list[int] = Field(
        default=[5, 10],
        min_length=1,
        max_length=6,
        description="Candidate conversion-window lengths in years",
    )
    max_candidates: int = Field(
        default=96,
        ge=1,
        le=200,
        description="Maximum number of scenario candidates the search will evaluate",
    )

    def model_post_init(self, __context) -> None:
        """Validate bounded Roth optimization inputs."""
        if any(amount < 0 for amount in self.annual_conversion_amounts):
            raise ValueError("annual_conversion_amounts must all be non-negative")
        if any(length <= 0 for length in self.window_lengths):
            raise ValueError("window_lengths must all be positive")
        if self.candidate_start_ages is not None and any(
            age < self.base_input.current_age or age > self.base_input.max_age
            for age in self.candidate_start_ages
        ):
            raise ValueError(
                "candidate_start_ages must all fall within the modeled retirement horizon"
            )
        if not self.base_input.holdings:
            raise ValueError(
                "Roth conversion optimization requires detailed holdings with account types"
            )
        if not self.base_input.has_traditional_accounts:
            raise ValueError(
                "Roth conversion optimization requires at least one traditional account"
            )


class RothConversionScenarioSummary(StrategyScenarioSummary):
    """Summary metrics for one Roth conversion amount."""

    total_roth_conversions_median: float = Field(
        default=0,
        description="Median lifetime amount converted from traditional to Roth",
    )
    year_breakdown: list[YearBreakdown] = Field(
        default_factory=list,
        description="Representative-path year-by-year Roth conversion and tax ledger",
    )


class HistoricalRothConversionSummary(HistoricalStrategySummary):
    """Historical cohort summary for one Roth conversion amount."""

    total_roth_conversions_median: float = Field(
        default=0,
        description="Median lifetime amount converted from traditional to Roth",
    )


class RothConversionScenarioDelta(BaseModel):
    """Delta metrics for one Roth scenario relative to a comparison baseline."""

    blended_score_delta: float = Field(
        default=0,
        description="Blended-score difference versus the baseline scenario",
    )
    monte_carlo_success_rate_delta: float = Field(
        default=0,
        description="Monte Carlo success-rate difference versus the baseline scenario",
    )
    historical_success_rate_delta: float = Field(
        default=0,
        description="Historical success-rate difference versus the baseline scenario",
    )
    monte_carlo_median_final_value_real_delta: float = Field(
        default=0,
        description="Monte Carlo median real ending-wealth difference versus baseline",
    )
    historical_median_final_value_real_delta: float = Field(
        default=0,
        description="Historical median real ending-wealth difference versus baseline",
    )
    monte_carlo_total_taxes_median_delta: float = Field(
        default=0,
        description="Monte Carlo median lifetime-tax difference versus baseline",
    )
    monte_carlo_total_medicare_premiums_median_delta: float = Field(
        default=0,
        description="Monte Carlo median Medicare Part B premium difference versus baseline",
    )
    monte_carlo_total_roth_conversions_median_delta: float = Field(
        default=0,
        description="Monte Carlo median lifetime-conversion difference versus baseline",
    )
    historical_total_medicare_premiums_median_delta: float = Field(
        default=0,
        description="Historical median Medicare Part B premium difference versus baseline",
    )
    historical_worst_final_value_real_delta: float = Field(
        default=0,
        description="Historical weakest-cohort real ending-wealth difference versus baseline",
    )


class RothConversionComparisonItem(BaseModel):
    """One fixed Roth conversion amount with Monte Carlo and historical summaries."""

    conversion_policy: RothConversionPolicy
    scenario_label: str
    annual_conversion_amount: float | None = None
    conversion_start_age: int
    conversion_end_age: int
    monte_carlo: RothConversionScenarioSummary
    historical: HistoricalRothConversionSummary
    blended_score: float = Field(
        ..., description="0-100 blended score across success, resilience, and taxes"
    )
    delta_vs_baseline: RothConversionScenarioDelta = Field(
        default_factory=RothConversionScenarioDelta,
        description="Differences versus the comparison baseline scenario",
    )


class RothConversionComparisonResult(BaseModel):
    """Results comparing fixed-amount Roth conversion plans."""

    metadata: EngineResultMetadata | None = Field(
        default=None,
        description="Engine metadata for reproducibility and integration clients",
    )

    results: list[RothConversionComparisonItem]
    baseline_scenario_label: str | None = Field(
        default=None,
        description="Scenario used as the delta baseline, usually no annual conversion",
    )
    baseline_conversion_amount: float | None = Field(
        default=None,
        description="Fixed annual conversion amount used as baseline, if applicable",
    )
    top_scoring_scenario_label: str = Field(
        ..., description="Scenario label with the highest blended score"
    )
    top_scoring_conversion_amount: float | None = Field(
        default=None,
        description="Fixed annual conversion amount with the highest blended score, if applicable",
    )
    lowest_modeled_tax_scenario_label: str = Field(
        ..., description="Scenario label with the lowest Monte Carlo median taxes"
    )
    lowest_modeled_tax_amount: float | None = Field(
        default=None,
        description="Fixed annual conversion amount with the lowest Monte Carlo median taxes, if applicable",
    )
    strongest_historical_scenario_label: str = Field(
        ..., description="Scenario label with the strongest historical cohort resilience"
    )
    strongest_historical_conversion_amount: float | None = Field(
        default=None,
        description="Fixed annual conversion amount with the strongest historical cohort resilience, if applicable",
    )
    summary: str = Field(
        ..., description="Plain-language summary of the comparison"
    )


class RothOptimizationResult(RothConversionComparisonResult):
    """Results from a bounded Roth conversion search across windows and policies."""

    candidate_count: int = Field(
        ..., description="Number of Roth conversion candidates evaluated"
    )
    candidate_start_ages: list[int] = Field(
        ..., description="Start ages explored by the Roth optimization search"
    )
    window_lengths: list[int] = Field(
        ..., description="Window lengths explored by the Roth optimization search"
    )
    lowest_medicare_premium_scenario_label: str = Field(
        ..., description="Scenario label with the lowest Monte Carlo Medicare premiums"
    )
    lowest_medicare_premium_conversion_amount: float | None = Field(
        default=None,
        description=(
            "Fixed annual conversion amount with the lowest Monte Carlo Medicare "
            "premiums, if applicable"
        ),
    )
    highest_real_ending_wealth_scenario_label: str = Field(
        ..., description="Scenario label with the highest Monte Carlo real ending wealth"
    )
    highest_real_ending_wealth_conversion_amount: float | None = Field(
        default=None,
        description=(
            "Fixed annual conversion amount with the highest Monte Carlo real "
            "ending wealth, if applicable"
        ),
    )


class RothOptimizationSearchSpace(BaseModel):
    """Candidate search ranges used for a Roth optimization run."""

    candidate_count: int = Field(
        ..., description="Number of Roth conversion candidates evaluated"
    )
    candidate_start_ages: list[int] = Field(
        ..., description="Start ages explored by the Roth optimization search"
    )
    window_lengths: list[int] = Field(
        ..., description="Window lengths explored by the Roth optimization search"
    )


class RothOptimizationLeaders(BaseModel):
    """Scenario labels for the main Roth optimization leaders."""

    score_leader: str = Field(..., description="Scenario label with the top blended score")
    lowest_modeled_tax: str = Field(
        ..., description="Scenario label with the lowest modeled median taxes"
    )
    lowest_medicare_premium: str = Field(
        ..., description="Scenario label with the lowest modeled Medicare premiums"
    )
    highest_real_ending_wealth: str = Field(
        ..., description="Scenario label with the highest modeled real ending wealth"
    )
    strongest_historical: str = Field(
        ..., description="Scenario label with the strongest historical resilience"
    )


class RothOptimizationReportArtifact(BaseModel):
    """Export-friendly report artifact for Roth optimization results."""

    artifact_type: Literal["eggnest_roth_optimization_report"] = Field(
        default="eggnest_roth_optimization_report",
        description="Stable type tag for the Roth optimization report artifact",
    )
    generated_at: str = Field(
        ..., description="UTC timestamp when the report artifact was generated"
    )
    baseline_scenario_label: str | None = Field(
        default=None,
        description="Scenario used as the baseline for delta columns",
    )
    summary: str = Field(..., description="Plain-language summary of the Roth search")
    metadata: EngineResultMetadata | None = Field(
        default=None,
        description="Engine metadata for reproducibility and integration clients",
    )
    search_space: RothOptimizationSearchSpace = Field(
        ..., description="Candidate ages and window lengths explored"
    )
    leaders: RothOptimizationLeaders = Field(
        ..., description="Primary score, tax, Medicare, wealth, and historical leaders"
    )
    results: list[RothConversionComparisonItem] = Field(
        ..., description="Full per-scenario Roth optimization results"
    )
    representative_cliff_ledger: list[YearBreakdown] = Field(
        default_factory=list,
        description="Representative year-by-year ledger for the score-leading scenario",
    )


# === Household Tax Calculator Models ===


class PersonInput(BaseModel):
    """Input for a single person in a household."""

    age: int = Field(..., ge=0, le=120, description="Person's age")
    employment_income: float = Field(
        default=0, ge=0, description="Annual employment income"
    )
    self_employment_income: float = Field(
        default=0, ge=0, description="Annual self-employment income"
    )
    social_security: float = Field(
        default=0, ge=0, description="Annual Social Security benefits"
    )
    pension_income: float = Field(default=0, ge=0, description="Annual pension income")
    investment_income: float = Field(
        default=0, ge=0, description="Annual investment income (dividends, interest)"
    )
    capital_gains: float = Field(default=0, ge=0, description="Annual capital gains")
    roth_conversion_amount: float = Field(
        default=0,
        ge=0,
        description=(
            "Annual traditional-to-Roth conversion amount. This is modeled as "
            "tax-relevant Roth conversion income and is never treated as "
            "spendable cash income. Older PolicyEngine-US builds may fall back "
            "to taxable IRA distributions until the dedicated Roth input is "
            "available."
        ),
    )

    # Tax unit roles
    is_tax_unit_head: bool = Field(
        default=False, description="Is this person the tax unit head?"
    )
    is_tax_unit_spouse: bool = Field(
        default=False, description="Is this person the spouse?"
    )
    is_tax_unit_dependent: bool = Field(
        default=False, description="Is this person a dependent?"
    )

    def model_post_init(self, __context) -> None:
        """Auto-set dependent status for children under 19."""
        if self.age < 19 and not self.is_tax_unit_head and not self.is_tax_unit_spouse:
            object.__setattr__(self, "is_tax_unit_dependent", True)


class HouseholdInput(BaseModel):
    """Input for a household tax calculation."""

    state: str = Field(..., description="Two-letter state code")
    year: int = Field(default=2025, ge=2020, le=2035, description="Tax year")
    filing_status: Literal[
        "single",
        "married_filing_jointly",
        "married_filing_separately",
        "head_of_household",
    ] = Field(default="single", description="Tax filing status")
    people: list[PersonInput] = Field(
        ..., min_length=1, description="People in the household"
    )
    countable_cash_assets: float = Field(
        default=0,
        ge=0,
        description=(
            "Countable liquid assets used by means-tested benefit programs. "
            "Mapped to bank-account-style cash assets for the SPM unit."
        ),
    )

    def model_post_init(self, __context) -> None:
        """Auto-infer filing status from household composition."""
        spouses = sum(1 for p in self.people if p.is_tax_unit_spouse)
        dependents = sum(1 for p in self.people if p.is_tax_unit_dependent)

        # Auto-set filing status if not explicitly set (still "single")
        if self.filing_status == "single":
            if spouses > 0:
                object.__setattr__(self, "filing_status", "married_filing_jointly")
            elif dependents > 0:
                object.__setattr__(self, "filing_status", "head_of_household")


class HouseholdResult(BaseModel):
    """Results from a household tax calculation."""

    metadata: EngineResultMetadata | None = Field(
        default=None,
        description="Engine metadata for reproducibility and integration clients",
    )

    # Taxes
    federal_income_tax: float = Field(..., description="Federal income tax liability")
    state_income_tax: float = Field(..., description="State income tax liability")
    payroll_tax: float = Field(default=0, description="FICA/payroll taxes")
    total_taxes: float = Field(..., description="Total tax liability")

    # Benefits
    benefits: dict[str, float] = Field(
        default_factory=dict, description="Benefits by program"
    )
    total_benefits: float = Field(default=0, description="Total benefits received")

    # Income summary
    total_income: float = Field(..., description="Total spendable gross income")
    modeled_non_cash_income: float = Field(
        default=0,
        description=(
            "Non-cash taxable income included in the tax/benefit model, such as "
            "Roth conversions."
        ),
    )
    total_modeled_income: float = Field(
        ...,
        description="Total income seen by the tax/benefit model",
    )
    net_income: float = Field(..., description="Net income after taxes and benefits")

    # Tax details
    tax_breakdown: dict[str, float] = Field(
        default_factory=dict, description="Detailed tax breakdown"
    )
    marginal_tax_rate: float = Field(default=0, description="Marginal tax rate")
    effective_tax_rate: float = Field(default=0, description="Effective tax rate")


class LifeEventComparisonInput(BaseModel):
    """Input for comparing life events."""

    before: HouseholdInput
    after: HouseholdInput
    event_name: str = Field(default="Life Event", description="Name of the life event")


class LifeEventComparison(BaseModel):
    """Results comparing before/after a life event."""

    metadata: EngineResultMetadata | None = Field(
        default=None,
        description="Engine metadata for reproducibility and integration clients",
    )

    event_name: str
    before_result: HouseholdResult
    after_result: HouseholdResult
    tax_change: float = Field(
        ..., description="Change in total taxes (positive = more taxes)"
    )
    benefit_change: float = Field(
        ..., description="Change in total benefits (positive = more benefits)"
    )
    net_income_change: float = Field(
        ..., description="Change in net income (positive = better off)"
    )


# === Employer Compensation Models ===


class CompensationBenchmark(BaseModel):
    """A market benchmark row available for employer-side package analysis."""

    id: str
    role: str
    tier: str
    label: str
    source: str
    market_p25_total: float
    market_p50_total: float
    market_p75_total: float


class CompensationEmployeeProfile(BaseModel):
    """Simplified household profile used to estimate employee after-tax value."""

    state: str = Field(default="CA", description="Two-letter state code")
    year: int = Field(default=2025, ge=2020, le=2035)
    filing_status: Literal[
        "single",
        "married_filing_jointly",
        "head_of_household",
    ] = Field(default="single")
    age: int = Field(default=35, ge=18, le=100)
    spouse_age: int = Field(default=35, ge=18, le=100)
    spouse_employment_income: float = Field(default=0, ge=0)
    children: int = Field(default=0, ge=0, le=10)
    child_age: int = Field(default=6, ge=0, le=18)


class CompensationPackageInput(BaseModel):
    """Employer-side package input for one role or offer."""

    name: str = Field(..., description="Human-readable label for the package")
    benchmark_id: str = Field(..., description="Benchmark row identifier")
    salary: float = Field(..., ge=0)
    annual_bonus: float = Field(default=0, ge=0)
    annual_equity: float = Field(default=0, ge=0)
    taxable_equity_treatment: Literal["w2", "capital_gains"] = Field(default="w2")
    employer_retirement_rate: float = Field(default=0.05, ge=0, le=1)
    employer_retirement_cap: float | None = Field(default=None, ge=0)
    employer_retirement_amount: float | None = Field(default=None, ge=0)
    employer_health_premiums: float = Field(default=0, ge=0)
    other_employer_costs: float = Field(default=0, ge=0)


class CompensationAnalysisInput(BaseModel):
    """Request body for employer-side package analysis."""

    employee_profile: CompensationEmployeeProfile = Field(
        default_factory=CompensationEmployeeProfile
    )
    packages: list[CompensationPackageInput] = Field(..., min_length=1, max_length=10)


class CompensationPackageTotals(BaseModel):
    guaranteed_total: float
    upside_total: float
    employer_retirement: float
    taxable_wages: float


class CompensationMarketPosition(BaseModel):
    guaranteed_percentile: float
    upside_percentile: float
    guaranteed_percentile_label: str
    upside_percentile_label: str
    market_p25_total: float
    market_p50_total: float
    market_p75_total: float


class CompensationEmployerCost(BaseModel):
    salary: float
    annual_bonus: float
    annual_equity: float
    employer_retirement: float
    employer_health_premiums: float
    other_employer_costs: float
    employer_social_security_tax: float
    employer_medicare_tax: float
    employer_additional_payroll_taxes: float = 0
    employer_payroll_tax_components: dict[str, float] = Field(default_factory=dict)
    employer_payroll_tax_variables_used: list[str] = Field(default_factory=list)
    employer_payroll_taxes: float
    total_cost: float


class CompensationEmployeeValue(BaseModel):
    gross_income: float
    federal_income_tax: float
    state_income_tax: float
    payroll_tax: float
    total_taxes: float
    modeled_public_benefits: float
    cash_after_tax: float
    employer_retirement: float
    employer_health_premiums: float
    other_benefits_value: float
    net_resources_total: float
    effective_tax_rate: float
    marginal_tax_rate: float


class CompensationAnalysisResult(BaseModel):
    """Full employer-side analysis for one package."""

    metadata: EngineResultMetadata | None = Field(
        default=None,
        description="Engine metadata for reproducibility and integration clients",
    )

    package: CompensationPackageInput
    benchmark: CompensationBenchmark
    totals: CompensationPackageTotals
    market_position: CompensationMarketPosition
    employer_cost: CompensationEmployerCost
    employee_value: CompensationEmployeeValue
