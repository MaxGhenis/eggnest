"""Pydantic models for the one-year UK drawdown calculator."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .models_uk import UKCitationRef

UKDrawdownSource = Literal["sipp", "isa", "gia", "cash"]
UKDrawdownPattern = Literal["regular", "one_off"]
UKDrawdownRegion = Literal["England", "Wales", "Northern Ireland"]
UKDrawdownPensionCreditStatus = Literal["calculated", "under_qualifying_age"]
UKDrawdownMarkerKind = Literal["pot_income_covered", "guarantee_credit_ends"]

# The Minimum Pension Age for 2026/27, Finance Act 2004 s.279.
MINIMUM_PENSION_AGE = 55
SUPPORTED_TAX_YEAR = 2026
FULL_NEW_STATE_PENSION_2026 = 12547.60  # £241.30 a week x 52
LUMP_SUM_ALLOWANCE = 268_275.0  # gov.uk/tax-on-your-private-pension/lump-sum-allowance
MAX_TAX_FREE_FRACTION = 0.25

_MAX_POUNDS = 100_000_000.0


class UKDrawdownYearInput(BaseModel):
    """One person, one tax year, one amount drawn from one pot."""

    birth_date: date = Field(
        description="Sets age, State Pension age and the Pension Credit qualifying age."
    )
    region: UKDrawdownRegion = Field(
        default="England",
        description=(
            "Where the person pays income tax. Scotland sets its own rates, and "
            "neither engine holds the 2026/27 Scottish bands."
        ),
    )
    tax_year: Literal[2026] = Field(
        default=SUPPORTED_TAX_YEAR,
        description="Calendar year the tax year starts in: 2026 means 2026/27.",
    )

    # Income for the tax year before any draw, £
    state_pension: float = Field(
        default=FULL_NEW_STATE_PENSION_2026,
        ge=0.0,
        le=_MAX_POUNDS,
        description=(
            "Annual State Pension, claimed or not: Pension Credit counts one "
            "not yet claimed from the qualifying age (SI 2002/1792 reg 18(1))."
        ),
    )
    other_pension_income: float = Field(
        default=0.0,
        ge=0.0,
        le=_MAX_POUNDS,
        description="Annual workplace, defined benefit or annuity pension income.",
    )
    employment_income: float = Field(default=0.0, ge=0.0, le=_MAX_POUNDS)
    savings_interest: float = Field(
        default=0.0,
        ge=0.0,
        le=_MAX_POUNDS,
        description="Taxable interest outside ISAs.",
    )
    dividend_income: float = Field(
        default=0.0,
        ge=0.0,
        le=_MAX_POUNDS,
        description="Taxable dividends outside ISAs.",
    )

    # Balances at the start of the tax year, £
    sipp_balance: float = Field(
        default=0.0,
        ge=0.0,
        le=_MAX_POUNDS,
        description="Money purchase pension pot, SIPP or workplace.",
    )
    isa_balance: float = Field(default=0.0, ge=0.0, le=_MAX_POUNDS)
    gia_balance: float = Field(default=0.0, ge=0.0, le=_MAX_POUNDS)
    cash_savings: float = Field(
        default=0.0,
        ge=0.0,
        le=_MAX_POUNDS,
        description="Cash and other capital outside an ISA.",
    )

    # The decision
    draw_source: UKDrawdownSource = "sipp"
    draw_amount: float = Field(default=0.0, ge=0.0, le=_MAX_POUNDS)
    sipp_draw_pattern: UKDrawdownPattern = Field(
        default="regular",
        description=(
            "'regular' withdrawals count as income for Pension Credit; 'one_off' "
            "withdrawals count as capital (DWP DMG 85456-85457)."
        ),
    )
    sipp_tax_free_fraction: float = Field(
        default=MAX_TAX_FREE_FRACTION,
        ge=0.0,
        le=MAX_TAX_FREE_FRACTION,
        description=(
            "Share of each pot withdrawal paid tax free: 0.25 for uncrystallised "
            "funds, 0 when the tax-free cash has already been taken."
        ),
    )
    lump_sum_allowance_remaining: float = Field(
        default=LUMP_SUM_ALLOWANCE,
        ge=0.0,
        le=LUMP_SUM_ALLOWANCE,
        description="Tax-free cash still available under the Lump Sum Allowance.",
    )

    # The assumption behind notional income on an undrawn pot
    gilt_yield_percent: float = Field(
        default=5.25,
        ge=0.0,
        le=20.0,
        description=(
            "15-year gilt yield for the GAD annuity table. The default is the Bank "
            "of England 15-year nominal spot rate of 5.47% on 5 November 2026, "
            "rounded down to the next 0.25% as GAD's instructions require."
        ),
    )
    annuity_income_per_1000: float | None = Field(
        default=None,
        ge=0.0,
        le=1000.0,
        description=(
            "Annual annuity income per £1,000 of pot, from a provider's figure. "
            "When absent, the GAD table sets it from age and gilt yield."
        ),
    )

    @model_validator(mode="after")
    def validate_draw(self) -> UKDrawdownYearInput:
        balance = {
            "sipp": self.sipp_balance,
            "isa": self.isa_balance,
            "gia": self.gia_balance,
            "cash": self.cash_savings,
        }[self.draw_source]
        if self.draw_amount > balance:
            raise ValueError(
                f"draw_amount (£{self.draw_amount:,.2f}) exceeds the "
                f"{self.draw_source} balance (£{balance:,.2f})"
            )
        tax_year_start = date(self.tax_year, 4, 6)
        had_birthday = (tax_year_start.month, tax_year_start.day) >= (
            self.birth_date.month,
            self.birth_date.day,
        )
        age = tax_year_start.year - self.birth_date.year - (not had_birthday)
        if not 18 <= age <= 120:
            raise ValueError("birth_date must give an age from 18 to 120")
        if (
            self.draw_source == "sipp"
            and self.draw_amount > 0
            and age < (MINIMUM_PENSION_AGE)
        ):
            raise ValueError(
                f"A pension pot can't be drawn before age {MINIMUM_PENSION_AGE}"
            )
        return self


class UKDrawdownFigure(BaseModel):
    """An amount, the engine that computed it and the law behind it."""

    amount: float
    engine: str
    citations: list[UKCitationRef] = Field(default_factory=list)


class UKDrawdownOutcome(BaseModel):
    """The whole year's result at one draw amount, £."""

    draw: float
    taxable_draw: float
    income_tax: float
    employee_ni: float
    pension_credit: float
    money_to_spend: float = Field(
        description=(
            "All income and money drawn in the year, plus Pension Credit, less "
            "income tax and employee National Insurance."
        )
    )


class UKDrawdownSlice(BaseModel):
    """Where each extra pound of draw goes across a range of draw amounts.

    kept + to_tax + to_pension_credit == 1. Each can fall outside 0-1: drawing
    down savings can raise Pension Credit, so kept can exceed 1.
    """

    draw_from: float
    draw_to: float
    kept: float
    to_tax: float
    to_pension_credit: float


class UKDrawdownMarker(BaseModel):
    """A draw amount where the result changes character."""

    kind: UKDrawdownMarkerKind
    draw: float


class UKDrawdownPensionCreditWorking(BaseModel):
    """How the chosen draw enters the guarantee credit test, £ a week."""

    status: UKDrawdownPensionCreditStatus
    qualifying_date: date
    eligible_weeks: int
    weekly_minimum_guarantee: float | None = None
    annual_annuity_income: float = Field(
        description="What the pot could pay as an annuity, a year."
    )
    annuity_income_per_1000: float
    annuity_age: int
    state_pension: float
    other_pension_income: float
    earnings_counted: float
    regular_pot_income: float = Field(description="Regular withdrawals from the pot.")
    notional_pot_income: float = Field(
        description="Top-up to the annuity rate when withdrawals fall short of it."
    )
    tax_deducted: float = Field(
        description="Income tax and NI payable on the income counted (reg 17(10))."
    )
    deemed_income_first_week: float = Field(
        description="Income deemed from savings in the first eligible week (reg 15(6))."
    )
    deemed_income_last_week: float
    capital_first_week: float
    capital_last_week: float


class UKDrawdownAssumptions(BaseModel):
    """The modeling choices behind this result."""

    tax_free_fraction_applied: float
    money_spent_evenly_through_year: bool = True
    gilt_yield_percent_used: float | None = Field(
        default=None,
        description="Yield read from the GAD table; null with a provider's figure.",
    )


class UKDrawdownYearResult(BaseModel):
    """What one year's draw costs in tax and Pension Credit."""

    tax_year_label: str
    draw_source: UKDrawdownSource
    sipp_draw_pattern: UKDrawdownPattern
    pot_left: float = Field(
        description="Balance of the source pot after the draw, before any growth."
    )
    income_tax: UKDrawdownFigure
    employee_ni: UKDrawdownFigure
    pension_credit: UKDrawdownFigure
    money_to_spend: float
    at_chosen_draw: UKDrawdownOutcome
    with_no_draw: UKDrawdownOutcome
    next_1000: UKDrawdownSlice | None = Field(
        description=(
            "Where the next £1,000 of draw goes; a smaller step near the end of "
            "the pot; null once the pot is empty."
        )
    )
    pension_credit_working: UKDrawdownPensionCreditWorking
    sweep: list[UKDrawdownOutcome]
    bands: list[UKDrawdownSlice]
    markers: list[UKDrawdownMarker]
    assumptions: UKDrawdownAssumptions
