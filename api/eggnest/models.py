"""Pydantic models for API requests and responses."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from eggnest.citations import Citation
from eggnest.constants import STATE_FIPS

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


class Holding(BaseModel):
    """A single holding in the portfolio."""

    account_type: AccountType = Field(
        ..., description="Type of account (determines tax treatment)"
    )
    fund: FundType = Field(..., description="Fund/index this holding is invested in")
    balance: float = Field(..., ge=0, description="Current balance in this holding")


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

    # Legacy: simple portfolio (for backward compatibility)
    initial_capital: float | None = Field(
        default=None,
        gt=0,
        description="Starting investment amount (legacy, use holdings instead)",
    )
    annual_spending: float = Field(
        ..., gt=0, description="Desired annual spending need (in today's dollars)"
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
        description="Optional seed for reproducible Monte Carlo paths",
    )
    include_mortality: bool = Field(
        default=True, description="Account for probability of death each year"
    )
    inflation_rate: float = Field(
        default=0.025,
        ge=0.0,
        le=0.10,
        description=(
            "Assumed annual inflation rate. Spending and Social Security grow "
            "at this rate; pension and annuity payments stay fixed in nominal "
            "dollars. The simulation runs in nominal terms to match nominal "
            "historical returns and PolicyEngine tax brackets."
        ),
    )
    return_model: Literal["bootstrap", "block_bootstrap", "historical", "normal"] = (
        Field(
            default="bootstrap",
            description="Return generation method: bootstrap (default), block_bootstrap, historical, or normal",
        )
    )

    # Market assumptions (nominal returns; the engine and historical data are nominal)
    # Note: expected_return, return_volatility, and dividend_yield are only used
    # when return_model="normal"; historical models use historical series.
    expected_return: float = Field(
        default=0.07,
        description="Expected nominal annual total return (only for normal model)",
    )
    return_volatility: float = Field(
        default=0.16, description="Annual return volatility (only for normal model)"
    )
    dividend_yield: float = Field(
        default=0.02,
        ge=0.0,
        le=0.10,
        description=(
            "Annual dividend yield (only for normal model; historical models "
            "use historical dividend yields)"
        ),
    )

    # Asset allocation
    stock_allocation: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Fraction of portfolio in stocks (0.0 to 1.0). Remainder is bonds.",
    )

    # Index selection
    stock_index: Literal["sp500", "vt"] = Field(
        default="vt",
        description="Stock index: 'sp500' (S&P 500, 1928-2024) or 'vt' (Total World, 2008-2024)",
    )
    bond_index: Literal["treasury", "bnd"] = Field(
        default="bnd",
        description="Bond index: 'treasury' (10-Year, 1928-2024) or 'bnd' (Total Bond Market, 2007-2024)",
    )

    @field_validator("state")
    @classmethod
    def validate_state(cls, state: str) -> str:
        """Normalize and validate US state codes before tax calculation."""
        normalized = state.upper()
        if normalized not in STATE_FIPS:
            raise ValueError(f"Unsupported state code: {state}")
        return normalized

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "SimulationInput":
        """Validate fields whose correctness depends on other inputs."""
        if self.max_age <= self.current_age:
            raise ValueError("max_age must be greater than current_age")
        if not self.holdings and self.initial_capital is None:
            raise ValueError("Either holdings or initial_capital must be provided")
        if self.has_spouse and self.spouse is None:
            raise ValueError("spouse is required when has_spouse is true")
        if self.has_annuity and self.annuity is None:
            raise ValueError("annuity is required when has_annuity is true")
        return self

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
    """Detailed breakdown for a single year in the simulation (median path)."""

    age: int = Field(..., description="Age during this year")
    year_index: int = Field(..., description="Year index (0 = first year)")

    # Portfolio
    portfolio_start: float = Field(..., description="Portfolio value at start of year")
    portfolio_end: float = Field(..., description="Portfolio value at end of year")
    portfolio_return: float = Field(..., description="Investment return for this year")

    # Income sources
    employment_income: float = Field(default=0, description="Employment income")
    social_security: float = Field(default=0, description="Social Security benefits")
    pension: float = Field(default=0, description="Pension income")
    dividends: float = Field(default=0, description="Dividend income from portfolio")
    annuity: float = Field(default=0, description="Annuity payments")
    total_income: float = Field(..., description="Total income for the year")

    # Withdrawals and taxes
    withdrawal: float = Field(..., description="Amount withdrawn from portfolio")
    federal_tax: float = Field(default=0, description="Federal income tax")
    state_tax: float = Field(default=0, description="State income tax")
    total_tax: float = Field(..., description="Total taxes paid")
    effective_tax_rate: float = Field(default=0, description="Effective tax rate")

    # Net
    net_income: float = Field(..., description="Net income after taxes")


class SimulationResult(BaseModel):
    """Results from a retirement simulation."""

    success_rate: float = Field(
        ..., description="Probability of not running out of money"
    )
    median_final_value: float = Field(..., description="Median portfolio value at end")
    mean_final_value: float = Field(..., description="Mean portfolio value at end")
    percentiles: dict[str, float] = Field(
        ..., description="Portfolio value percentiles (p5, p25, p50, p75, p95)"
    )
    median_depletion_age: int | None = Field(
        None, description="Median age at depletion (if applicable)"
    )
    total_withdrawn_median: float = Field(
        ..., description="Median total withdrawals over simulation"
    )
    total_taxes_median: float = Field(..., description="Median total taxes paid")

    # For charting
    percentile_paths: dict[str, list[float]] = Field(
        ..., description="Time series of percentile values (by age)"
    )

    # Year-by-year breakdown (median path)
    year_breakdown: list[YearBreakdown] = Field(
        default_factory=list,
        description="Detailed year-by-year breakdown for median scenario",
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


SimulationJobState = Literal["queued", "running", "succeeded", "failed"]


class SimulationJobStatus(BaseModel):
    """Status snapshot for a background simulation job."""

    job_id: str = Field(..., description="Opaque simulation job identifier")
    status: SimulationJobState = Field(..., description="Current job state")
    current_year: float = Field(
        default=0,
        ge=0,
        description="Human-readable current simulated year number",
    )
    total_years: int = Field(..., ge=0, description="Total simulated years")
    progress: float = Field(
        default=0,
        ge=0,
        le=1,
        description="Progress fraction from 0 to 1",
    )
    message: str | None = Field(
        default=None, description="Short human-readable progress message"
    )
    year_summary: dict[str, Any] | None = Field(
        default=None,
        description="Latest completed simulated year preview, when available",
    )
    result: SimulationResult | None = Field(
        default=None, description="Simulation result when status is succeeded"
    )
    error: str | None = Field(
        default=None, description="Error message when status is failed"
    )
    created_at: str = Field(..., description="ISO timestamp when the job was created")
    updated_at: str = Field(..., description="ISO timestamp for the latest job update")
    completed_at: str | None = Field(
        default=None, description="ISO timestamp when the job finished"
    )


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

    simulation_result: SimulationResult
    annuity_total_guaranteed: float
    probability_simulation_beats_annuity: float
    simulation_median_total_income: float
    comparison_summary: str


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

    @field_validator("compare_states")
    @classmethod
    def validate_compare_states(cls, states: list[str]) -> list[str]:
        """Normalize and validate comparison state codes."""
        normalized_states = [state.upper() for state in states]
        unsupported = sorted(set(normalized_states) - set(STATE_FIPS))
        if unsupported:
            raise ValueError(f"Unsupported state code(s): {', '.join(unsupported)}")
        return normalized_states


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

    base_state: str
    results: list[StateResult]
    tax_savings_vs_base: dict[str, float] = Field(
        ...,
        description="Modeled tax difference relative to base state (positive = lower modeled taxes)",
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

    birth_year: int
    full_retirement_age: float
    pia_monthly: float
    results: list[SSTimingResult]
    highest_success_claiming_age: int = Field(
        ..., description="Claiming age with the highest modeled success rate"
    )
    highest_lifetime_income_claiming_age: int = Field(
        ...,
        description="Claiming age with the highest modeled lifetime Social Security income",
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
        ..., description="5th percentile final value (worst case)"
    )
    percentile_95_final_value: float = Field(
        ..., description="95th percentile final value (best case)"
    )
    volatility: float = Field(..., description="Standard deviation of annual returns")
    expected_return: float = Field(..., description="Mean annual return")


class AllocationComparisonResult(BaseModel):
    """Results comparing asset allocation strategies."""

    results: list[AllocationResult]
    highest_success_allocation: float = Field(
        ..., description="Stock allocation with the highest modeled success rate"
    )
    lowest_volatility_allocation: float = Field(
        ...,
        description="Stock allocation with lowest volatility among tested options that meet the success threshold",
    )
    comparison_summary: str = Field(
        ..., description="Plain language factual summary of the modeled comparison"
    )


class WithdrawalStrategyComparisonInput(BaseModel):
    """Input for comparing holdings withdrawal-order strategies."""

    base_input: SimulationInput
    strategies: list[WithdrawalStrategy] = Field(
        default=["taxable_first", "traditional_first", "roth_first", "pro_rata"],
        min_length=1,
        max_length=4,
        description="Withdrawal strategies to compare. The base input strategy is always included.",
    )
    random_seed: int | None = Field(
        default=0,
        ge=0,
        description="Shared seed used for all strategy runs so differences reflect withdrawal order rather than different market paths. Set null to use the base input seed.",
    )

    @model_validator(mode="after")
    def require_holdings(self) -> "WithdrawalStrategyComparisonInput":
        """Withdrawal-order comparisons are only meaningful with holdings mode."""
        if not self.base_input.holdings:
            raise ValueError("holdings are required to compare withdrawal strategies")
        return self


class WithdrawalStrategyResult(BaseModel):
    """Summary result for one withdrawal strategy."""

    withdrawal_strategy: WithdrawalStrategy
    success_rate: float
    median_final_value: float
    total_taxes_median: float
    total_withdrawn_median: float
    median_depletion_age: int | None = None
    initial_withdrawal_rate: float
    success_rate_delta_vs_base: float
    median_final_value_delta_vs_base: float
    total_taxes_delta_vs_base: float


class WithdrawalStrategyComparisonResult(BaseModel):
    """Results comparing withdrawal-order strategies under shared assumptions."""

    base_strategy: WithdrawalStrategy
    shared_random_seed: int | None
    results: list[WithdrawalStrategyResult]
    comparison_summary: str = Field(
        ..., description="Plain language factual summary of the modeled comparison"
    )


class HistoricalCohortComparisonInput(BaseModel):
    """Input for comparing contiguous historical market cohorts."""

    base_input: SimulationInput
    start_years: list[int] | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Optional historical cohort start years. If omitted, all valid start years are used.",
    )
    stock_index: Literal["sp500", "vt"] = Field(
        default="sp500",
        description="Stock index for historical cohorts. S&P 500 has the longest built-in history.",
    )
    bond_index: Literal["treasury", "bnd"] = Field(
        default="treasury",
        description="Bond index for historical cohorts. 10-year Treasury has the longest built-in history.",
    )
    include_mortality: bool = Field(
        default=False,
        description="Whether to include stochastic mortality in cohort outcomes. Defaults false to isolate market sequences.",
    )

    @field_validator("start_years")
    @classmethod
    def validate_start_years(cls, start_years: list[int] | None) -> list[int] | None:
        """Reject duplicate start years so each result row is a distinct cohort."""
        if start_years is None:
            return None
        duplicates = sorted(
            year for year in set(start_years) if start_years.count(year) > 1
        )
        if duplicates:
            raise ValueError(
                "Duplicate start year(s): "
                f"{', '.join(str(year) for year in duplicates)}"
            )
        return start_years

    @model_validator(mode="after")
    def require_simple_portfolio(self) -> "HistoricalCohortComparisonInput":
        """Historical cohorts currently use simple stock/bond allocation mode."""
        if self.base_input.holdings:
            raise ValueError(
                "historical cohort comparison currently requires simple stock/bond portfolio mode"
            )
        return self


class HistoricalCohortResult(BaseModel):
    """Summary result for one historical cohort start year."""

    start_year: int
    end_year: int
    success: bool
    final_value: float
    total_taxes: float
    total_withdrawn: float
    depletion_age: int | None = None


class HistoricalCohortComparisonResult(BaseModel):
    """Results comparing contiguous historical market cohorts."""

    stock_index: Literal["sp500", "vt"]
    bond_index: Literal["treasury", "bnd"]
    stock_allocation: float
    n_years: int
    cohort_success_rate: float
    results: list[HistoricalCohortResult]
    worst_start_year: int
    best_start_year: int
    worst_final_value: float
    best_final_value: float
    comparison_summary: str = Field(
        ..., description="Plain language factual summary of the modeled comparison"
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

    @field_validator("state")
    @classmethod
    def validate_household_state(cls, state: str) -> str:
        """Normalize and validate state codes before PolicyEngine calls."""
        normalized = state.upper()
        if normalized not in STATE_FIPS:
            raise ValueError(f"Unsupported state code: {state}")
        return normalized

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

    # Taxes
    federal_income_tax: float = Field(
        ...,
        description=(
            "Federal income tax after non-refundable credits and before refundable "
            "credits; refundable credits are counted in benefits."
        ),
    )
    state_income_tax: float = Field(..., description="State income tax liability")
    payroll_tax: float = Field(default=0, description="FICA/payroll taxes")
    total_taxes: float = Field(..., description="Total tax liability")

    # Benefits
    benefits: dict[str, float] = Field(
        default_factory=dict,
        description="Cash benefits and refundable tax credits by program",
    )
    total_benefits: float = Field(default=0, description="Total benefits received")

    # Income summary
    total_income: float = Field(..., description="Total gross income")
    net_income: float = Field(..., description="Net income after taxes and benefits")

    # Tax details
    tax_breakdown: dict[str, float] = Field(
        default_factory=dict, description="Detailed tax breakdown"
    )
    marginal_tax_rate: float = Field(default=0, description="Marginal tax rate")
    effective_tax_rate: float = Field(default=0, description="Effective tax rate")
    citations: list[Citation] = Field(
        default_factory=list,
        description="Deduplicated source links for the fields in this result",
    )
    output_citations: dict[str, list[Citation]] = Field(
        default_factory=dict,
        description="Source links keyed by result field, e.g. benefits.snap",
    )


class LifeEventComparisonInput(BaseModel):
    """Input for comparing life events."""

    before: HouseholdInput
    after: HouseholdInput
    event_name: str = Field(default="Life Event", description="Name of the life event")


class LifeEventComparison(BaseModel):
    """Results comparing before/after a life event."""

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


class ProgramOutput(BaseModel):
    """A machine-readable output exposed by an EggNest program."""

    name: str
    label: str
    kind: Literal["scalar", "judgment", "object", "series"]
    description: str
    unit: str | None = None


class ProgramSpec(BaseModel):
    """A program or engine an AI agent can safely call."""

    id: str
    display_name: str
    country: str
    jurisdiction: str
    scope: str
    engine: str
    cli: str
    primary_output: str
    outputs: list[ProgramOutput]
    caveats: list[str] = Field(default_factory=list)


class HouseholdValidationResult(BaseModel):
    """Validation response designed for agent intake loops."""

    status: Literal["ready", "needs_input", "invalid"]
    missing_inputs: list[str] = Field(default_factory=list)
    high_impact_questions: list[str] = Field(default_factory=list)
    safe_defaults_used: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class EarningsGridInput(BaseModel):
    """Input for comparing household resources across earned-income levels."""

    base_input: HouseholdInput
    person_index: int = Field(
        default=0,
        ge=0,
        description="Index of the person whose employment income varies.",
    )
    income_min: float = Field(default=0, ge=0, description="Lowest annual earnings.")
    income_max: float = Field(
        default=80_000, ge=0, description="Highest annual earnings."
    )
    step: float = Field(default=1_000, gt=0, description="Annual earnings increment.")

    @model_validator(mode="after")
    def validate_grid(self) -> "EarningsGridInput":
        """Keep grids bounded and aligned with the household shape."""
        if self.person_index >= len(self.base_input.people):
            raise ValueError("person_index must refer to an existing household member")
        if self.income_max < self.income_min:
            raise ValueError("income_max must be greater than or equal to income_min")
        n_rows = int((self.income_max - self.income_min) / self.step) + 1
        if n_rows > 501:
            raise ValueError("earnings grid cannot exceed 501 rows")
        return self


class EarningsGridPoint(BaseModel):
    """Household resources at one annual earnings level."""

    employment_income: float
    total_income: float
    net_income: float
    total_taxes: float
    total_benefits: float
    benefits: dict[str, float] = Field(default_factory=dict)
    delta_net_income: float | None = None
    effective_marginal_rate: float | None = None


class EarningsGridCliff(BaseModel):
    """A grid interval where higher earnings reduce net resources."""

    from_income: float
    to_income: float
    net_income_change: float
    tax_change: float
    benefit_change: float
    effective_marginal_rate: float
    benefit_changes: dict[str, float] = Field(default_factory=dict)


class EarningsGridComparisonResult(BaseModel):
    """Results comparing household resources across earned-income levels."""

    person_index: int
    income_min: float
    income_max: float
    step: float
    rows: list[EarningsGridPoint]
    cliffs: list[EarningsGridCliff] = Field(default_factory=list)
    largest_cliff: EarningsGridCliff | None = None
    comparison_summary: str
    citations: list[Citation] = Field(default_factory=list)
    output_citations: dict[str, list[Citation]] = Field(default_factory=dict)
