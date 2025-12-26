"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, Field
from typing import Literal


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


class Holding(BaseModel):
    """A single holding in the portfolio."""

    account_type: AccountType = Field(..., description="Type of account (determines tax treatment)")
    fund: FundType = Field(..., description="Fund/index this holding is invested in")
    balance: float = Field(..., ge=0, description="Current balance in this holding")


class SpouseInput(BaseModel):
    """Spouse details for joint simulation."""

    age: int = Field(..., ge=18, le=100, description="Spouse's current age")
    gender: Literal["male", "female"] = Field(default="female", description="Spouse's gender for mortality")
    social_security_monthly: float = Field(default=0, ge=0, description="Spouse's monthly Social Security")
    social_security_start_age: int = Field(default=67, ge=62, le=70, description="Age when spouse starts Social Security")
    pension_annual: float = Field(default=0, ge=0, description="Spouse's annual pension")
    employment_income: float = Field(default=0, ge=0, description="Spouse's annual employment income")
    employment_growth_rate: float = Field(default=0.03, ge=0, le=0.1, description="Spouse's wage growth rate")
    retirement_age: int = Field(default=65, ge=18, le=100, description="Spouse's retirement age")


class AnnuityInput(BaseModel):
    """Annuity parameters."""

    monthly_payment: float = Field(..., gt=0, description="Monthly annuity payment")
    annuity_type: Literal["life_with_guarantee", "fixed_period", "life_only"] = Field(
        default="life_with_guarantee", description="Type of annuity"
    )
    guarantee_years: int = Field(default=15, ge=0, le=30, description="Guarantee period in years")


class SimulationInput(BaseModel):
    """Input parameters for a retirement simulation."""

    # Holdings-based portfolio (preferred)
    holdings: list[Holding] | None = Field(
        default=None,
        description="List of holdings with account types and funds. If provided, overrides initial_capital and stock_allocation."
    )
    withdrawal_strategy: Literal["traditional_first", "roth_first", "taxable_first", "pro_rata"] = Field(
        default="taxable_first",
        description="Order to withdraw from accounts: taxable_first (most common), traditional_first, roth_first, or pro_rata"
    )

    # Legacy: simple portfolio (for backward compatibility)
    initial_capital: float | None = Field(default=None, gt=0, description="Starting investment amount (legacy, use holdings instead)")
    annual_spending: float = Field(..., gt=0, description="Desired annual spending need (in today's dollars)")
    home_value: float = Field(default=0, ge=0, description="Home equity value (not included in portfolio, for net worth display)")
    current_age: int = Field(..., ge=18, le=100, description="Current age")
    max_age: int = Field(default=95, ge=50, le=120, description="Planning horizon (max age)")
    gender: Literal["male", "female"] = Field(default="male", description="Gender for mortality tables")

    # Backward compatibility
    target_monthly_income: float | None = Field(
        default=None, description="DEPRECATED: Use annual_spending instead"
    )

    # Income sources
    social_security_monthly: float = Field(default=0, ge=0, description="Monthly Social Security benefits")
    social_security_start_age: int = Field(default=67, ge=62, le=70, description="Age when Social Security starts")
    pension_annual: float = Field(default=0, ge=0, description="Annual pension/other guaranteed income")
    employment_income: float = Field(default=0, ge=0, description="Annual employment income (pre-retirement)")
    employment_growth_rate: float = Field(default=0.03, ge=0, le=0.1, description="Annual wage growth rate")
    retirement_age: int = Field(default=65, ge=18, le=100, description="Age when employment income stops")

    # Tax settings
    state: str = Field(default="CA", description="Two-letter state code")
    filing_status: Literal["single", "married_filing_jointly", "head_of_household"] = Field(
        default="single", description="Tax filing status"
    )

    # Spouse (optional)
    has_spouse: bool = Field(default=False, description="Include spouse in simulation")
    spouse: SpouseInput | None = Field(default=None, description="Spouse details if has_spouse is True")

    # Annuity (optional)
    has_annuity: bool = Field(default=False, description="Include annuity income")
    annuity: AnnuityInput | None = Field(default=None, description="Annuity details if has_annuity is True")

    # Simulation settings
    n_simulations: int = Field(default=10_000, ge=100, le=100_000, description="Number of Monte Carlo paths")
    include_mortality: bool = Field(default=True, description="Account for probability of death each year")
    include_irmaa: bool = Field(default=True, description="Include Medicare IRMAA surcharges (ages 65+)")
    return_model: Literal["bootstrap", "block_bootstrap", "historical", "normal"] = Field(
        default="bootstrap",
        description="Return generation method: bootstrap (default), block_bootstrap, historical, or normal"
    )

    # Market assumptions (real returns, after inflation)
    # Note: expected_return and return_volatility are only used when return_model="normal"
    expected_return: float = Field(default=0.07, description="Expected real annual return (only for normal model)")
    return_volatility: float = Field(default=0.16, description="Annual return volatility (only for normal model)")
    dividend_yield: float = Field(default=0.02, description="Annual dividend yield")

    # Asset allocation
    stock_allocation: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Fraction of portfolio in stocks (0.0 to 1.0). Remainder is bonds."
    )

    # Index selection
    stock_index: Literal["sp500", "vt"] = Field(
        default="vt",
        description="Stock index: 'sp500' (S&P 500, 1928-2024) or 'vt' (Total World, 2008-2024)"
    )
    bond_index: Literal["treasury", "bnd"] = Field(
        default="bnd",
        description="Bond index: 'treasury' (10-Year, 1928-2024) or 'bnd' (Total Bond Market, 2007-2024)"
    )

    def model_post_init(self, __context) -> None:
        """Handle backward compatibility."""
        # Convert target_monthly_income to annual_spending if provided
        if self.target_monthly_income is not None and self.annual_spending is None:
            object.__setattr__(self, 'annual_spending', self.target_monthly_income * 12)

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
        return any(h.account_type in ("traditional_401k", "traditional_ira") for h in self.holdings)

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

    success_rate: float = Field(..., description="Probability of not running out of money")
    median_final_value: float = Field(..., description="Median portfolio value at end")
    mean_final_value: float = Field(..., description="Mean portfolio value at end")
    percentiles: dict[str, float] = Field(
        ..., description="Portfolio value percentiles (p5, p25, p50, p75, p95)"
    )
    median_depletion_age: int | None = Field(None, description="Median age at depletion (if applicable)")
    total_withdrawn_median: float = Field(..., description="Median total withdrawals over simulation")
    total_taxes_median: float = Field(..., description="Median total taxes paid")

    # For charting
    percentile_paths: dict[str, list[float]] = Field(
        ..., description="Time series of percentile values (by age)"
    )

    # Year-by-year breakdown (median path)
    year_breakdown: list[YearBreakdown] = Field(
        default_factory=list, description="Detailed year-by-year breakdown for median scenario"
    )

    # Withdrawal rate info
    initial_withdrawal_rate: float = Field(..., description="Initial withdrawal rate as percentage")

    # Additional statistics
    prob_10_year_failure: float = Field(default=0, description="Probability of failure within 10 years")

    # Backward compatibility
    median_depletion_year: float | None = Field(
        None, description="DEPRECATED: Use median_depletion_age instead"
    )


class AnnuityComparison(BaseModel):
    """Input for comparing simulation to an annuity."""

    simulation_input: SimulationInput
    annuity_monthly_payment: float = Field(..., gt=0, description="Monthly annuity payment")
    annuity_guarantee_years: int = Field(default=20, ge=1, le=40, description="Annuity guarantee period")


class AnnuityComparisonResult(BaseModel):
    """Results comparing simulation to annuity."""

    simulation_result: SimulationResult
    annuity_total_guaranteed: float
    probability_simulation_beats_annuity: float
    simulation_median_total_income: float
    recommendation: str


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
        ..., gt=0, le=10000, description="Primary Insurance Amount (monthly benefit at FRA)"
    )
    claiming_ages: list[int] = Field(
        default=[62, 63, 64, 65, 66, 67, 68, 69, 70],
        min_length=1,
        max_length=9,
        description="Claiming ages to compare (62-70)"
    )


class SSTimingResult(BaseModel):
    """Result for a single claiming age."""

    claiming_age: int
    monthly_benefit: float = Field(..., description="Adjusted monthly benefit at this claiming age")
    annual_benefit: float = Field(..., description="Annual benefit (monthly * 12)")
    adjustment_factor: float = Field(..., description="Factor applied to PIA (e.g., 0.7 = 30% reduction)")
    success_rate: float
    median_final_value: float
    total_ss_income_median: float = Field(..., description="Total SS income over lifetime (median)")
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
    optimal_claiming_age: int = Field(
        ..., description="Claiming age with highest success rate"
    )
    optimal_for_longevity: int = Field(
        ..., description="Claiming age optimal if living to max_age"
    )


class AllocationInput(BaseModel):
    """Input for asset allocation comparison."""

    base_input: SimulationInput
    allocations: list[float] = Field(
        default=[0.2, 0.4, 0.6, 0.8, 1.0],
        min_length=1,
        max_length=10,
        description="Stock allocations to compare (0.0 to 1.0)"
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
    percentile_5_final_value: float = Field(..., description="5th percentile final value (worst case)")
    percentile_95_final_value: float = Field(..., description="95th percentile final value (best case)")
    volatility: float = Field(..., description="Standard deviation of annual returns")
    expected_return: float = Field(..., description="Mean annual return")


class AllocationComparisonResult(BaseModel):
    """Results comparing asset allocation strategies."""

    results: list[AllocationResult]
    optimal_for_success: float = Field(
        ..., description="Stock allocation with highest success rate"
    )
    optimal_for_safety: float = Field(
        ..., description="Stock allocation with lowest volatility among high-success options"
    )
    recommendation: str = Field(
        ..., description="Plain language recommendation based on results"
    )


# === Household Tax Calculator Models ===


class PersonInput(BaseModel):
    """Input for a single person in a household."""

    age: int = Field(..., ge=0, le=120, description="Person's age")
    employment_income: float = Field(default=0, ge=0, description="Annual employment income")
    self_employment_income: float = Field(default=0, ge=0, description="Annual self-employment income")
    social_security: float = Field(default=0, ge=0, description="Annual Social Security benefits")
    pension_income: float = Field(default=0, ge=0, description="Annual pension income")
    investment_income: float = Field(default=0, ge=0, description="Annual investment income (dividends, interest)")
    capital_gains: float = Field(default=0, ge=0, description="Annual capital gains")

    # Tax unit roles
    is_tax_unit_head: bool = Field(default=False, description="Is this person the tax unit head?")
    is_tax_unit_spouse: bool = Field(default=False, description="Is this person the spouse?")
    is_tax_unit_dependent: bool = Field(default=False, description="Is this person a dependent?")

    def model_post_init(self, __context) -> None:
        """Auto-set dependent status for children under 19."""
        if self.age < 19 and not self.is_tax_unit_head and not self.is_tax_unit_spouse:
            object.__setattr__(self, "is_tax_unit_dependent", True)


class HouseholdInput(BaseModel):
    """Input for a household tax calculation."""

    state: str = Field(..., description="Two-letter state code")
    year: int = Field(default=2025, ge=2020, le=2035, description="Tax year")
    filing_status: Literal["single", "married_filing_jointly", "married_filing_separately", "head_of_household"] = Field(
        default="single", description="Tax filing status"
    )
    people: list[PersonInput] = Field(..., min_length=1, description="People in the household")

    def model_post_init(self, __context) -> None:
        """Auto-infer filing status from household composition."""
        heads = sum(1 for p in self.people if p.is_tax_unit_head)
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
    federal_income_tax: float = Field(..., description="Federal income tax liability")
    state_income_tax: float = Field(..., description="State income tax liability")
    payroll_tax: float = Field(default=0, description="FICA/payroll taxes")
    total_taxes: float = Field(..., description="Total tax liability")

    # Benefits
    benefits: dict[str, float] = Field(default_factory=dict, description="Benefits by program")
    total_benefits: float = Field(default=0, description="Total benefits received")

    # Income summary
    total_income: float = Field(..., description="Total gross income")
    net_income: float = Field(..., description="Net income after taxes and benefits")

    # Tax details
    tax_breakdown: dict[str, float] = Field(default_factory=dict, description="Detailed tax breakdown")
    marginal_tax_rate: float = Field(default=0, description="Marginal tax rate")
    effective_tax_rate: float = Field(default=0, description="Effective tax rate")


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
    tax_change: float = Field(..., description="Change in total taxes (positive = more taxes)")
    benefit_change: float = Field(..., description="Change in total benefits (positive = more benefits)")
    net_income_change: float = Field(..., description="Change in net income (positive = better off)")
