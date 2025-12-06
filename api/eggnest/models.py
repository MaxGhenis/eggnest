"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, Field
from typing import Literal


class SpouseInput(BaseModel):
    """Spouse details for joint simulation."""

    age: int = Field(..., ge=18, le=100, description="Spouse's current age")
    gender: Literal["male", "female"] = Field(default="female", description="Spouse's gender for mortality")
    social_security_monthly: float = Field(default=0, ge=0, description="Spouse's monthly Social Security")
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

    # Core parameters
    initial_capital: float = Field(..., gt=0, description="Starting investment amount")
    annual_spending: float = Field(..., gt=0, description="Desired annual spending need (in today's dollars)")
    current_age: int = Field(..., ge=18, le=100, description="Current age")
    max_age: int = Field(default=95, ge=50, le=120, description="Planning horizon (max age)")
    gender: Literal["male", "female"] = Field(default="male", description="Gender for mortality tables")

    # Backward compatibility
    target_monthly_income: float | None = Field(
        default=None, description="DEPRECATED: Use annual_spending instead"
    )

    # Income sources
    social_security_monthly: float = Field(default=0, ge=0, description="Monthly Social Security benefits")
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

    # Market assumptions (real returns, after inflation)
    expected_return: float = Field(default=0.05, description="Expected real annual return (0.05 = 5%)")
    return_volatility: float = Field(default=0.16, description="Annual return volatility")
    dividend_yield: float = Field(default=0.02, description="Annual dividend yield")

    def model_post_init(self, __context) -> None:
        """Handle backward compatibility."""
        # Convert target_monthly_income to annual_spending if provided
        if self.target_monthly_income is not None and self.annual_spending is None:
            object.__setattr__(self, 'annual_spending', self.target_monthly_income * 12)


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
