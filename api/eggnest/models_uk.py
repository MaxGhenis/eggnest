"""Pydantic models for the UK simulator."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

UKAccountType = Literal["isa", "sipp", "gia"]
UKReturnSource = Literal[
    "gaussian",
    "historical_bootstrap",
    "historical_block_bootstrap",
    "historical_sequential",
]
UKEarningsModel = Literal["flat", "deterministic", "stochastic"]
UKRegion = Literal[
    "London",
    "South East",
    "South West",
    "East Midlands",
    "West Midlands",
    "Yorkshire and the Humber",
    "North East",
    "North West",
    "East of England",
    "Scotland",
    "Wales",
    "Northern Ireland",
]


class UKSimulationInput(BaseModel):
    """Input parameters for a UK retirement simulation."""

    # Demographics
    current_age: int = Field(ge=18, le=100)
    max_age: int = Field(ge=25, le=120)
    gender: Literal["male", "female"] = "male"
    region: UKRegion = "London"

    # Accounts (GBP)
    isa_balance: float = Field(ge=0.0, default=0.0)
    sipp_balance: float = Field(ge=0.0, default=0.0)
    gia_balance: float = Field(ge=0.0, default=0.0)

    # Spending
    annual_spending: float = Field(ge=0.0)
    spending_mode: Literal["real", "nominal"] = "real"

    # Income sources (annual, GBP)
    state_pension_annual: float = Field(
        ge=0.0,
        default=11502.0,
        description="Full new State Pension 2024/25 = £221.20/wk × 52 ≈ £11,502.",
    )
    state_pension_start_age: int = Field(ge=55, le=75, default=67)
    employment_income: float = Field(
        ge=0.0,
        default=0.0,
        description=(
            "Gross employment earnings. If earnings_model='stochastic', this "
            "is the year-0 starting level, not a flat value for all years."
        ),
    )
    retirement_age: int = Field(ge=18, le=80, default=67)
    earnings_model: UKEarningsModel = Field(
        default="flat",
        description=(
            "How employment income evolves over pre-retirement years: 'flat' "
            "holds employment_income constant (original behaviour), "
            "'deterministic' applies a UK age-wage hump profile, 'stochastic' "
            "adds AR(1) permanent + iid transitory shocks calibrated from the "
            "UK earnings-dynamics literature (Blundell-Pistaferri-Preston-style)."
        ),
    )
    earnings_persistent_sigma: float = Field(
        ge=0.0,
        le=0.5,
        default=0.10,
        description=(
            "Stdev of annual innovation to the persistent log-earnings "
            "component (σ_η). UK calibration ≈ 0.10; multiply by ~1.4 for US."
        ),
    )
    earnings_transitory_sigma: float = Field(
        ge=0.0,
        le=0.5,
        default=0.20,
        description=(
            "Stdev of the transitory log-earnings shock (σ_ε). "
            "UK calibration ≈ 0.20; multiply by ~1.3 for US."
        ),
    )
    earnings_persistence: float = Field(
        ge=0.0,
        le=1.0,
        default=0.97,
        description="AR(1) coefficient on the persistent earnings component (ρ).",
    )
    earnings_profile_peak_growth: float = Field(
        ge=0.0,
        le=1.5,
        default=0.40,
        description=(
            "Entry-to-peak log-earnings growth in the deterministic age profile. "
            "UK ≈ 0.40 (compressed); US ≈ 0.55."
        ),
    )
    savings_rate: float = Field(
        ge=0.0,
        le=1.0,
        default=0.08,
        description=(
            "Fraction of gross pre-retirement earnings saved each year "
            "(auto-enrolment floor = 0.08)."
        ),
    )
    sipp_contribution_share: float = Field(
        ge=0.0,
        le=1.0,
        default=1.0,
        description=(
            "Share of annual savings routed to SIPP (rest → ISA). "
            "1.0 = all pension (matches workplace auto-enrolment)."
        ),
    )

    # Return model
    return_source: UKReturnSource = Field(
        default="historical_block_bootstrap",
        description=(
            "How to generate annual returns: 'gaussian' uses expected_return/"
            "return_volatility; the historical_* variants sample from 150 years "
            "of UK equity + gilt + CPI history (JST Macrohistory)."
        ),
    )

    # Market assumptions (decimal fractions; only used when return_source='gaussian')
    expected_return: float = Field(ge=-0.1, le=0.2, default=0.055)
    return_volatility: float = Field(ge=0.0, le=0.5, default=0.15)
    dividend_yield: float = Field(ge=0.0, le=0.15, default=0.025)
    # Equity/gilt allocation split (only used for historical sampling).
    equity_weight: float = Field(
        ge=0.0,
        le=1.0,
        default=0.6,
        description="Portfolio weight on UK equities (balance: UK gilts).",
    )

    # Inflation (only used when return_source='gaussian')
    inflation_rate: float = Field(ge=0.0, le=0.15, default=0.025)

    # Monte Carlo controls
    n_simulations: int = Field(ge=100, le=50000, default=5000)
    random_seed: int = Field(default=42)
    include_mortality: bool = True

    @model_validator(mode="after")
    def validate_cross_fields(self) -> UKSimulationInput:
        """Validate fields whose correctness depends on other inputs.

        The UK simulator runs max_age - current_age + 1 years inclusively, so
        max_age == current_age is a valid single-year simulation.
        """
        if self.max_age < self.current_age:
            raise ValueError("max_age must be at least current_age")
        return self


class UKYearBreakdown(BaseModel):
    """Per-year median results from the UK simulation."""

    year_index: int
    age: int
    portfolio_start: float
    portfolio_end: float
    spending_target: float
    total_income: float
    withdrawal: float
    total_tax: float
    inflation_rate: float
    portfolio_return: float
    effective_tax_rate: float
    state_pension: float
    employment_income: float
    sipp_withdrawal: float
    isa_withdrawal: float
    gia_withdrawal: float


class UKCitationRef(BaseModel):
    """Statute or regulation citation backing a computed number."""

    id: str
    url: str


class UKPensionCreditScreen(BaseModel):
    """Modeled guarantee credit screening along the median path.

    Computed with the Axiom rules engine from statute encodings (State
    Pension Credit Act 2002 s.2; SI 2002/1792 reg 6). A screening estimate,
    not a benefits decision: the modeled income stands in for the full
    SPC Act s.15 income assessment.
    """

    weekly_minimum_guarantee: float
    ages: list[int]
    annual_amounts: list[float]
    years_indicated: int
    citations: list[UKCitationRef] = []


class UKSimulationResult(BaseModel):
    """Aggregated simulation output."""

    metadata: dict
    success_rate: float
    strict_horizon_success_rate: float
    median_final_value: float
    median_final_value_real: float
    percentiles: dict[str, float]
    percentiles_real: dict[str, float]
    percentile_paths: dict[str, list[float]]
    tax_percentile_paths: dict[str, list[float]] = {}
    earnings_percentile_paths: dict[str, list[float]] = {}
    year_breakdown: list[UKYearBreakdown]
    initial_withdrawal_rate: float
    prob_10_year_failure: float
    percentile_path_start_years: dict[str, int] | None = Field(
        default=None,
        description=(
            "Per-percentile start year of the representative cohort: for each "
            "p ∈ {5,25,50,75,95}, the start year of the sim whose final "
            "portfolio value is closest to that percentile. Only populated for "
            "sequential sampling."
        ),
    )
    pension_credit: UKPensionCreditScreen | None = Field(
        default=None,
        description=(
            "Guarantee credit screening along the median path, computed from "
            "statute encodings via the Axiom rules engine when available."
        ),
    )
