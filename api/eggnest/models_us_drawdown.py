"""Pydantic models for the one-year US drawdown calculator."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .citations import Citation
from .constants import STATE_FIPS

USDrawdownSource = Literal["traditional", "roth", "taxable", "cash"]
USDrawdownFilingStatus = Literal["single", "married_filing_jointly"]
USDrawdownOwner = Literal["you", "spouse"]
USDrawdownMarkerKind = Literal[
    "benefit_ends",
    "coverage_ends",
    "medicare_surcharge_step",
    "required_minimum_reached",
]

SUPPORTED_TAX_YEAR = 2026
MEDICARE_AGE = 65  # 42 USC 426(a)
OLDEST_AGE = 120
# Medicare's income-related premiums use income from the second calendar year
# before the premium year (42 USC 1395r(i)(4)(B)).
MEDICARE_PREMIUM_LAG_YEARS = 2

_MAX_DOLLARS = 100_000_000.0


def _dollars(description: str | None = None) -> float:
    return Field(default=0.0, ge=0.0, le=_MAX_DOLLARS, description=description)


class USDrawdownPerson(BaseModel):
    """One adult's own income and retirement accounts for 2026."""

    birth_year: int = Field(
        ge=SUPPORTED_TAX_YEAR - OLDEST_AGE,
        le=SUPPORTED_TAX_YEAR - MEDICARE_AGE,
        description=(
            "Sets age at the end of 2026, which decides the extra standard "
            "deduction and senior deduction at 65, Medicare and required "
            "minimum distributions. Everyone must be 65 or older by then."
        ),
    )
    social_security: float = _dollars(
        "Social Security benefits for 2026, before Medicare premiums come out."
    )
    pension_income: float = _dollars(
        "Taxable private pension and annuity income for 2026."
    )
    government_pension_income: float = _dollars(
        "Taxable federal, state or local government pension income for 2026. "
        "Some states tax it differently from private pensions."
    )
    earnings: float = _dollars("Wages for 2026.")
    traditional_balance: float = _dollars(
        "Traditional IRA and 401(k) balances on December 31, 2025, which also "
        "set the 2026 required minimum distribution."
    )
    roth_balance: float = _dollars("Roth IRA balances at the start of 2026.")
    other_traditional_withdrawals: float = _dollars(
        "Withdrawals from traditional IRAs and 401(k)s in 2026 besides the draw "
        "being tested, such as a required minimum distribution already planned."
    )
    roth_conversion: float = _dollars(
        "Amount converted from traditional accounts to a Roth IRA in 2026. It "
        "is taxable income but not money to spend."
    )

    @property
    def age(self) -> int:
        """Age at the end of the tax year."""
        return SUPPORTED_TAX_YEAR - self.birth_year


class USDrawdownYearInput(BaseModel):
    """One household, one tax year, one amount drawn from one account."""

    tax_year: Literal[2026] = Field(default=SUPPORTED_TAX_YEAR)
    state: str = Field(
        description="Two-letter code of the state, or DC, the household lives in."
    )
    filing_status: USDrawdownFilingStatus = "single"
    you: USDrawdownPerson
    spouse: USDrawdownPerson | None = Field(
        default=None,
        description="Required when filing jointly, absent otherwise.",
    )

    # Household income for 2026 before any draw, $
    taxable_interest: float = _dollars("Taxable interest.")
    tax_exempt_interest: float = _dollars(
        "Tax-exempt interest, such as from municipal bonds. It adds to the income "
        "that decides how much Social Security is taxed and Medicare premiums."
    )
    dividends: float = _dollars("Dividends, all treated as qualified dividends.")

    # Balances at the start of 2026, $
    taxable_balance: float = _dollars(
        "Value of investments in taxable brokerage accounts."
    )
    taxable_gain_share: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Share of each dollar of investments sold that is gain, held more "
            "than a year. The rest returns what was paid."
        ),
    )
    cash_savings: float = _dollars("Checking, savings and money market balances.")

    # The decision
    draw_source: USDrawdownSource = "traditional"
    draw_owner: USDrawdownOwner = Field(
        default="you",
        description="Whose IRA or 401(k) a traditional or Roth draw comes from.",
    )
    draw_amount: float = _dollars("Amount to take from the source in 2026.")

    @field_validator("state")
    @classmethod
    def known_state(cls, value: str) -> str:
        code = value.strip().upper()
        if code not in STATE_FIPS:
            raise ValueError(f"Unknown state code: {value}")
        return code

    @model_validator(mode="after")
    def validate_household(self) -> USDrawdownYearInput:
        joint = self.filing_status == "married_filing_jointly"
        if joint and self.spouse is None:
            raise ValueError("A joint return needs the spouse's details")
        if not joint and self.spouse is not None:
            raise ValueError("Only a joint return can include a spouse")
        if self.draw_owner == "spouse" and self.spouse is None:
            raise ValueError("A draw from the spouse's account needs a spouse")
        balance = source_balance(self)
        if self.draw_amount > balance:
            raise ValueError(
                f"draw_amount (${self.draw_amount:,.2f}) exceeds the "
                f"{self.draw_source} balance (${balance:,.2f})"
            )
        return self

    def person(self, who: USDrawdownOwner) -> USDrawdownPerson:
        if who == "spouse":
            if self.spouse is None:
                raise ValueError("No spouse in this household")
            return self.spouse
        return self.you

    @property
    def people(self) -> list[tuple[USDrawdownOwner, USDrawdownPerson]]:
        members: list[tuple[USDrawdownOwner, USDrawdownPerson]] = [("you", self.you)]
        if self.spouse is not None:
            members.append(("spouse", self.spouse))
        return members


def source_balance(inputs: USDrawdownYearInput) -> float:
    """What the chosen source holds at the start of the year."""
    if inputs.draw_source == "taxable":
        return inputs.taxable_balance
    if inputs.draw_source == "cash":
        return inputs.cash_savings
    owner = inputs.spouse if inputs.draw_owner == "spouse" else inputs.you
    if owner is None:
        return 0.0
    if inputs.draw_source == "traditional":
        return owner.traditional_balance
    return owner.roth_balance


class USDrawdownFigure(BaseModel):
    """An amount, the engine that computed it and the law behind it."""

    amount: float
    engine: str
    citations: list[Citation] = Field(default_factory=list)


class USDrawdownOutcome(BaseModel):
    """The whole year's result at one draw amount, $."""

    draw: float
    taxable_draw: float = Field(
        description=(
            "Part of the draw counted in adjusted gross income: all of a "
            "traditional draw, the gain on investments sold, none of a Roth or "
            "cash draw."
        )
    )
    federal_income_tax: float = Field(
        description="Federal income tax before refundable credits."
    )
    state_income_tax: float
    other_taxes: float = Field(
        description="Payroll, local and other taxes before refundable credits."
    )
    benefits: float = Field(
        description=(
            "Cash and food benefits plus refundable tax credits, Social Security "
            "and health coverage aside."
        )
    )
    benefits_by_program: dict[str, float] = Field(
        description=(
            "The benefits above by program, keyed by PolicyEngine-US variable. "
            "Every outcome in a result lists the same programs: those that pay "
            "something at some draw."
        )
    )
    taxable_social_security: float
    medicare_income: float = Field(
        description=(
            "Adjusted gross income plus tax-exempt interest: the income that sets "
            "Medicare's income-related premiums two years later."
        )
    )
    later_medicare_surcharge: float = Field(
        description=(
            "Part B and Part D income-related premiums this year's income sets "
            "for the household two years later, at this year's rates and lines."
        )
    )
    money_to_spend: float = Field(
        description=(
            "All income and money drawn in the year, plus benefits and refundable "
            "credits, less taxes. Roth conversions add tax but no money."
        )
    )


class USDrawdownSlice(BaseModel):
    """Where each extra dollar of draw goes across a range of draw amounts.

    kept + to_tax + to_benefits == 1. Each can fall outside 0-1.
    """

    draw_from: float
    draw_to: float
    kept: float
    to_tax: float
    to_benefits: float
    social_security_taxed: float = Field(
        description="Extra Social Security made taxable by each dollar of draw."
    )


class USDrawdownMarker(BaseModel):
    """A draw amount where the result changes character."""

    kind: USDrawdownMarkerKind
    draw: float
    program: str | None = Field(
        default=None,
        description=(
            "PolicyEngine-US variable of the benefit that ends, or medicaid or "
            "msp for health coverage."
        ),
    )
    amount: float | None = Field(
        default=None,
        description=(
            "Rise in the household's yearly Medicare surcharge at a step, or the "
            "required minimum distribution."
        ),
    )


class USRequiredMinimum(BaseModel):
    """One person's 2026 required minimum distribution."""

    person: USDrawdownOwner
    age: int
    balance: float
    divisor: float
    amount: float
    other_withdrawals: float = Field(
        description="Traditional withdrawals entered besides the draw."
    )
    withdrawn: float = Field(
        description="Traditional withdrawals at the chosen draw, conversions aside."
    )
    shortfall: float
    excise_tax_rate: float = Field(
        description="Share of a shortfall due as excise tax (26 USC 4974(a))."
    )
    excise_tax_on_shortfall: float = Field(
        description="25% of the shortfall (26 USC 4974(a)); 10% if corrected in time."
    )


class USMedicareSurcharge(BaseModel):
    """How this year's income moves Medicare premiums two years later."""

    premium_year: int
    rates_year: int = Field(
        description=(
            "Year whose income lines and surcharges stand in for the premium "
            "year's, which CMS has not yet set."
        )
    )
    people_on_medicare: int
    lines: list[float] = Field(
        description="Income lines where the surcharge steps up, for this filing status."
    )
    at_chosen_draw: float
    with_no_draw: float


class USDrawdownAssumptions(BaseModel):
    """The modeling choices behind this result."""

    taxable_gain_share_applied: float | None
    savings_tested_on: str = "2026-01-01"
    retirement_accounts_count_for_ssi_tests: bool = True
    dividends_qualified: bool = True
    money_spent_evenly_through_year: bool = True


class USDrawdownYearResult(BaseModel):
    """What one year's draw costs in tax, benefits and later Medicare premiums."""

    tax_year: int
    state: str
    filing_status: USDrawdownFilingStatus
    draw_source: USDrawdownSource
    draw_owner: USDrawdownOwner
    account_left: float = Field(
        description="Balance of the source after the draw, before any growth."
    )
    federal_income_tax: USDrawdownFigure
    state_income_tax: USDrawdownFigure
    other_taxes: USDrawdownFigure
    benefits: USDrawdownFigure
    coverage_at_chosen_draw: dict[str, bool] = Field(
        description=(
            "Health coverage PolicyEngine-US finds the household eligible for "
            "(medicaid, msp). Its value isn't counted in money to spend."
        )
    )
    coverage_with_no_draw: dict[str, bool]
    money_to_spend: float
    at_chosen_draw: USDrawdownOutcome
    with_no_draw: USDrawdownOutcome
    next_1000: USDrawdownSlice | None = Field(
        description=(
            "Where the next $1,000 of draw goes; a smaller step near the end of "
            "the account; null once it is empty."
        )
    )
    medicare_surcharge: USMedicareSurcharge
    required_minimums: list[USRequiredMinimum]
    sweep: list[USDrawdownOutcome]
    bands: list[USDrawdownSlice]
    markers: list[USDrawdownMarker]
    assumptions: USDrawdownAssumptions
