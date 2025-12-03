"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, Field


class SimulationInput(BaseModel):
    """Input parameters for a retirement simulation."""

    initial_capital: float = Field(..., gt=0, description="Starting investment amount")
    target_monthly_income: float = Field(
        ..., gt=0, description="Desired monthly after-tax income"
    )
    social_security_monthly: float = Field(
        default=0, ge=0, description="Monthly Social Security benefits"
    )
    current_age: int = Field(..., ge=18, le=100, description="Current age")
    retirement_age: int = Field(default=65, ge=18, le=100, description="Retirement age")
    state: str = Field(default="CA", description="Two-letter state code")
    filing_status: str = Field(default="single", description="Tax filing status")
    n_simulations: int = Field(
        default=10_000, ge=100, le=100_000, description="Number of Monte Carlo paths"
    )
    n_years: int = Field(default=30, ge=1, le=60, description="Simulation horizon")

    # Market assumptions
    expected_return: float = Field(
        default=0.07, description="Expected annual return (0.07 = 7%)"
    )
    return_volatility: float = Field(
        default=0.16, description="Annual return volatility"
    )
    dividend_yield: float = Field(default=0.02, description="Annual dividend yield")
    inflation_rate: float = Field(default=0.03, description="Expected inflation rate")


class SimulationResult(BaseModel):
    """Results from a retirement simulation."""

    success_rate: float = Field(
        ..., description="Probability of not running out of money"
    )
    median_final_value: float = Field(
        ..., description="Median portfolio value at end"
    )
    mean_final_value: float = Field(..., description="Mean portfolio value at end")
    percentiles: dict[str, float] = Field(
        ..., description="Portfolio value percentiles (p5, p25, p50, p75, p95)"
    )
    median_depletion_year: float | None = Field(
        None, description="Median year of depletion (if applicable)"
    )
    total_withdrawn_median: float = Field(
        ..., description="Median total withdrawals over simulation"
    )
    total_taxes_median: float = Field(..., description="Median total taxes paid")

    # For charting
    percentile_paths: dict[str, list[float]] = Field(
        ..., description="Time series of percentile values"
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
    recommendation: str


class SavedSimulation(BaseModel):
    """A saved simulation for a user."""

    id: str | None = None
    user_id: str | None = None
    name: str
    input_params: SimulationInput
    created_at: str | None = None
    updated_at: str | None = None
