"""Pydantic models for the UK simulator."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

UKAccountType = Literal["isa", "sipp", "gia"]
UKReturnSource = Literal[
    "gaussian",
    "historical_bootstrap",
    "historical_block_bootstrap",
    "historical_sequential",
]
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
    employment_income: float = Field(ge=0.0, default=0.0)
    retirement_age: int = Field(ge=18, le=80, default=67)

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


class UKSimulationResult(BaseModel):
    """Aggregated simulation output."""

    metadata: dict
    success_rate: float
    median_final_value: float
    median_final_value_real: float
    percentiles: dict[str, float]
    percentiles_real: dict[str, float]
    percentile_paths: dict[str, list[float]]
    year_breakdown: list[UKYearBreakdown]
    initial_withdrawal_rate: float
    prob_10_year_failure: float
