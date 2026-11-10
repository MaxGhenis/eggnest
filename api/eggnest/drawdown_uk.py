"""One tax year of drawing on UK savings.

Answers a single question for a single person in a single tax year: if I take
this much from this pot, what does it cost me in income tax, National Insurance
and Pension Credit?

The tax and benefit rules run in the Axiom rules engine from rulespec-uk
encodings (``axiom_uk``). This module decides what each rule is given: which
money counts as income, which counts as capital, and when. Every such decision
follows a cited provision:

Pension Credit counts, each week (SPC Act 2002 ss.15-16; SI 2002/1792):
- State Pension in full, claimed or not, from the qualifying age (reg 18(1)).
- Other pension income in full (s.16(1)(f)).
- Regular withdrawals from a pot in full, tax-free part included (DMG 85456,
  85476). One-off withdrawals count as capital instead (DMG 85457).
- For a pot past the qualifying age, the rate of annuity it could buy, less
  regular withdrawals already counted (reg 18(2)-(3); DMG 85460). Withdrawing
  less than that rate therefore doesn't raise Pension Credit.
- Earnings less £5 a week (Sch VI para 5(a)).
- Less income tax and NI payable on that income (reg 17(10)).
- Plus income deemed from savings: £1 a week per £500 or part above £10,000
  (reg 15(6)). A pot is not capital (Sch V para 22), and actual interest and
  dividends are disregarded (Sch IV para 18).

Money drawn is taken to be spent evenly through the year, so savings fall week
by week and each of the 52 weeks is assessed separately.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import axiom_uk, drawdown_bands
from .citations import Citation
from .drawdown_bands import band_breaks, crossing_point  # noqa: F401 (re-exported)
from .models_uk import UKCitationRef
from .models_uk_drawdown import (
    UKDrawdownAssumptions,
    UKDrawdownFigure,
    UKDrawdownMarker,
    UKDrawdownOutcome,
    UKDrawdownPensionCreditWorking,
    UKDrawdownSlice,
    UKDrawdownYearInput,
    UKDrawdownYearResult,
)
from .state_pension_age import (
    pension_credit_qualifying_date,
    share_of_period_from,
    state_pension_age_date,
)
from .tax_uk import AXIOM_UK_TAX_ENGINE, UKYearInputs, UKYearResults

WEEKS_IN_YEAR = 52
_EARNINGS_DISREGARD_WEEKLY = 5.0  # SI 2002/1792 Sch VI para 5(a)
_NEXT_DRAW_STEP = 1_000.0

# Sweep range. With a quarter of each draw tax free, drawing £180,000 carries
# someone with a State Pension past the additional-rate threshold (£125,140),
# so larger draws add no new tax band.
_SWEEP_MIN_TOP = 180_000.0
_SWEEP_MAX_INTERVALS = 200
_SWEEP_STEPS = (50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000, 25_000, 50_000)
# Benefit rules bite at small draws, so every pot gets a fine grid there.
_SWEEP_FINE_TOP = 20_000.0
_SWEEP_FINE_STEP = 250.0

# How far a band's straight line may stray from the true figures, £ a year.
# Income tax is exactly piecewise linear, so its bands follow every kink.
# Pension Credit's deemed income moves in £1-a-week steps at each £500 of
# capital, which can shift a year's credit by up to £52 with no change in the
# underlying rate, so its bands ignore movements of that size.
_BAND_TAX_TOLERANCE = 1.0
_BAND_CREDIT_TOLERANCE = 60.0
_BAND_MIN_WIDTH = 1.0

_GAD_FACTORS_PATH = Path(__file__).parent / "data" / "gad_drawdown_factors.json"

_SPC_REGS = "https://www.legislation.gov.uk/uksi/2002/1792"
_DMG_CHAPTER_85 = (
    "https://assets.publishing.service.gov.uk/media/690b7db588a98da87e292365/"
    "dmg-ch-85.pdf"
)
_GAD_TABLES = "https://www.gov.uk/government/publications/drawdown-pension-tables"

# Provisions this module applies by hand before the engine runs, so the
# engine's own traces don't list them.
_PENSION_CREDIT_CITATIONS = (
    Citation(
        id="State Pension Credit Act 2002 s.16(1)(f): income from a personal pension",
        url="https://www.legislation.gov.uk/ukpga/2002/16/section/16",
    ),
    Citation(
        id="SI 2002/1792 reg 17(10): tax and NI disregarded",
        url=f"{_SPC_REGS}/regulation/17",
    ),
    Citation(
        id="SI 2002/1792 reg 18: notional income from an undrawn pot",
        url=f"{_SPC_REGS}/regulation/18",
    ),
    Citation(
        id="SI 2002/1792 Sch IV para 18: actual income from capital disregarded",
        url=f"{_SPC_REGS}/schedule/IV/paragraph/18",
    ),
    Citation(
        id="SI 2002/1792 Sch V para 22: a pension pot is not capital",
        url=f"{_SPC_REGS}/schedule/V/paragraph/22",
    ),
    Citation(
        id="SI 2002/1792 Sch VI para 5(a): £5 weekly earnings disregard",
        url=f"{_SPC_REGS}/schedule/VI/paragraph/5",
    ),
    Citation(
        id="DWP Decision Makers Guide 85456-85460, 85470, 85476",
        url=_DMG_CHAPTER_85,
    ),
    Citation(id="GAD drawdown pension tables", url=_GAD_TABLES),
)

UKTaxCalculator = Callable[[UKYearInputs], UKYearResults]
PensionCreditEvaluator = Callable[..., dict]


class DrawdownEngineUnavailable(RuntimeError):
    """The rules engine this calculator depends on is not configured."""


@dataclass(frozen=True)
class DrawdownEngines:
    """The rules this calculator runs. Tests inject simple stand-ins."""

    tax: UKTaxCalculator
    pension_credit: PensionCreditEvaluator
    tax_citations: Callable[[int], list[Citation]]


def default_engines() -> DrawdownEngines:
    """The Axiom engine, which holds the 2026/27 rates this calculator needs."""
    if not axiom_uk.available():
        raise DrawdownEngineUnavailable(
            "This calculator needs the Axiom rules engine and a rulespec-uk "
            "checkout (EGGNEST_AXIOM_ENGINE_BIN, EGGNEST_RULESPEC_UK_ROOT)."
        )
    return DrawdownEngines(
        tax=axiom_uk.calculate_uk_tax_axiom,
        pension_credit=axiom_uk.pension_credit_screen,
        tax_citations=axiom_uk.tax_citations,
    )


@lru_cache(maxsize=1)
def _gad_factors() -> dict:
    return json.loads(_GAD_FACTORS_PATH.read_text())


def _yield_used(gilt_yield_percent: float) -> float:
    """GAD Step D: round down to the next 0.25%; the table stops at 8%."""
    return min(max(np.floor(gilt_yield_percent * 4.0) / 4.0, 0.0), 8.0)


def gad_annuity_income_per_1000(age: int, gilt_yield_percent: float) -> float:
    """Annual annuity income per £1,000 of pot from GAD Table 1."""
    table = _gad_factors()
    row = table["factors_by_age"][
        str(min(age, table["last_age_means_that_age_or_over"]))
    ]
    return float(
        row[table["gilt_yields_percent"].index(_yield_used(gilt_yield_percent))]
    )


def age_on(birth_date: date, on: date) -> int:
    """Age in complete years on a date."""
    had_birthday = (on.month, on.day) >= (birth_date.month, birth_date.day)
    return on.year - birth_date.year - (not had_birthday)


def _source_balance(inputs: UKDrawdownYearInput) -> float:
    return {
        "sipp": inputs.sipp_balance,
        "isa": inputs.isa_balance,
        "gia": inputs.gia_balance,
        "cash": inputs.cash_savings,
    }[inputs.draw_source]


def _is_regular_pot_draw(inputs: UKDrawdownYearInput) -> bool:
    return inputs.draw_source == "sipp" and inputs.sipp_draw_pattern == "regular"


def _is_one_off_pot_draw(inputs: UKDrawdownYearInput) -> bool:
    return inputs.draw_source == "sipp" and inputs.sipp_draw_pattern == "one_off"


def _sweep_draws(inputs: UKDrawdownYearInput) -> np.ndarray:
    """A grid of round draw amounts from nothing up to the useful top."""
    balance = _source_balance(inputs)
    top = min(balance, max(_SWEEP_MIN_TOP, inputs.draw_amount * 1.25))
    step = next(
        (s for s in _SWEEP_STEPS if top / s <= _SWEEP_MAX_INTERVALS),
        _SWEEP_STEPS[-1],
    )
    coarse = np.arange(0.0, top + step, step, dtype=float)
    fine = np.arange(0.0, _SWEEP_FINE_TOP + _SWEEP_FINE_STEP, _SWEEP_FINE_STEP)
    # The £1 point gives the rate on the very first pounds, so a change of
    # rate inside the first interval can be placed.
    grid = np.concatenate([coarse, fine, [1.0, top]])
    return np.unique(grid[grid <= top])


@dataclass
class _Evaluated:
    """Each array holds one value per draw amount."""

    draws: np.ndarray
    taxable_draw: np.ndarray
    income_tax: np.ndarray
    employee_ni: np.ndarray
    pension_credit: np.ndarray
    money_to_spend: np.ndarray
    regular_pot_income: np.ndarray
    notional_pot_income: np.ndarray
    tax_deducted: np.ndarray
    deemed_first_week: np.ndarray
    deemed_last_week: np.ndarray
    capital_first_week: np.ndarray
    capital_last_week: np.ndarray
    annual_annuity_income: np.ndarray
    weekly_minimum_guarantee: float | None
    pension_credit_citations: list[Citation]

    def index_of(self, draw: float) -> int:
        return int(np.argmin(np.abs(self.draws - draw)))

    def outcome(self, index: int) -> UKDrawdownOutcome:
        return UKDrawdownOutcome(
            draw=_money(self.draws[index]),
            taxable_draw=_money(self.taxable_draw[index]),
            income_tax=_money(self.income_tax[index]),
            employee_ni=_money(self.employee_ni[index]),
            pension_credit=_money(self.pension_credit[index]),
            money_to_spend=_money(self.money_to_spend[index]),
        )


def _money(value: float) -> float:
    # Adding 0.0 turns a rounded -0.0 into 0.0.
    return round(float(value), 2) + 0.0


class _Calculation:
    """One person's year, ready to evaluate at any set of draw amounts."""

    def __init__(self, inputs: UKDrawdownYearInput, engines: DrawdownEngines):
        self.inputs = inputs
        self.engines = engines
        self.tax_year_start = date(inputs.tax_year, 4, 6)
        self.age = age_on(inputs.birth_date, self.tax_year_start)
        self.qualifying_date = pension_credit_qualifying_date(inputs.birth_date)
        self.annuity_income_per_1000 = (
            inputs.annuity_income_per_1000
            if inputs.annuity_income_per_1000 is not None
            else gad_annuity_income_per_1000(self.age, inputs.gilt_yield_percent)
        )
        self.eligible = np.array(
            [
                self.tax_year_start + timedelta(days=7 * week) >= self.qualifying_date
                for week in range(WEEKS_IN_YEAR)
            ]
        )
        # NI stops on earnings paid after State Pension age (SSCBA 1992 s.6(3)).
        self.share_over_spa = share_of_period_from(
            self.tax_year_start,
            date(inputs.tax_year + 1, 4, 6),
            state_pension_age_date(inputs.birth_date, "female"),
        )

    def _tax(
        self, taxable_draw: np.ndarray, *, include_investment_income: bool = True
    ) -> UKYearResults:
        n = len(taxable_draw)
        inputs = self.inputs
        interest = inputs.savings_interest if include_investment_income else 0.0
        dividends = inputs.dividend_income if include_investment_income else 0.0
        return self.engines.tax(
            UKYearInputs(
                age=self.age,
                year=inputs.tax_year,
                state_pension=np.full(n, inputs.state_pension),
                private_pension_income=inputs.other_pension_income + taxable_draw,
                savings_interest=np.full(n, interest),
                dividend_income=np.full(n, dividends),
                employment_income=np.full(n, inputs.employment_income),
                birth_date=inputs.birth_date,
                share_of_year_over_spa=self.share_over_spa,
            )
        )

    def _taxable_part(self, draws: np.ndarray) -> np.ndarray:
        inputs = self.inputs
        if inputs.draw_source != "sipp":
            return np.zeros_like(draws)
        tax_free = np.minimum(
            draws * inputs.sipp_tax_free_fraction, inputs.lump_sum_allowance_remaining
        )
        return draws - tax_free

    def evaluate(self, draws: np.ndarray) -> _Evaluated:
        inputs = self.inputs
        draws = np.asarray(draws, dtype=float)
        n = len(draws)
        taxable = self._taxable_part(draws)
        tax = self._tax(taxable)
        direct_tax = tax.income_tax + tax.employee_ni

        regular = _is_regular_pot_draw(inputs)
        one_off = _is_one_off_pot_draw(inputs)

        # Reg 17(10) deducts tax on income Pension Credit counts. Interest and
        # dividends are not counted, and income tax charges them last, so the
        # tax on counted income is the tax with them removed. A one-off draw
        # is capital, so its tax comes off the capital, not the income.
        counted_taxable = taxable if regular else np.zeros(n)
        if inputs.savings_interest or inputs.dividend_income or not regular:
            counted = self._tax(counted_taxable, include_investment_income=False)
        else:
            counted = tax
        tax_deducted = counted.income_tax + counted.employee_ni

        pot_for_annuity = inputs.sipp_balance - (draws if one_off else np.zeros(n))
        annuity = np.maximum(pot_for_annuity, 0.0) * (
            self.annuity_income_per_1000 / 1_000.0
        )
        regular_pot_income = draws if regular else np.zeros(n)
        notional = np.maximum(annuity - regular_pot_income, 0.0)
        earnings_counted = max(
            inputs.employment_income - _EARNINGS_DISREGARD_WEEKLY * WEEKS_IN_YEAR, 0.0
        )
        counted_annual = (
            inputs.state_pension
            + inputs.other_pension_income
            + regular_pot_income
            + notional
            + earnings_counted
            - tax_deducted
        )
        weekly_income = np.maximum(counted_annual, 0.0) / WEEKS_IN_YEAR

        opening_capital = inputs.isa_balance + inputs.gia_balance + inputs.cash_savings
        spent = (np.arange(WEEKS_IN_YEAR) + 0.5) / WEEKS_IN_YEAR
        if inputs.draw_source != "sipp":
            capital = opening_capital - np.outer(draws, spent)
        elif one_off:
            no_draw_tax = self._tax(np.zeros(1))
            tax_on_draw = direct_tax - float(
                no_draw_tax.income_tax[0] + no_draw_tax.employee_ni[0]
            )
            capital = opening_capital + np.outer(draws - tax_on_draw, 1.0 - spent)
        else:
            capital = np.full((n, WEEKS_IN_YEAR), opening_capital)
        capital = np.maximum(capital, 0.0)

        pension_credit, deemed, guarantee, citations = self._pension_credit(
            weekly_income, capital
        )
        money_to_spend = (
            inputs.state_pension
            + inputs.other_pension_income
            + inputs.employment_income
            + inputs.savings_interest
            + inputs.dividend_income
            + draws
            + pension_credit
            - direct_tax
        )
        first, last = self._first_and_last_eligible_week()
        return _Evaluated(
            draws=draws,
            taxable_draw=taxable,
            income_tax=tax.income_tax,
            employee_ni=tax.employee_ni,
            pension_credit=pension_credit,
            money_to_spend=money_to_spend,
            regular_pot_income=regular_pot_income,
            notional_pot_income=notional,
            tax_deducted=tax_deducted,
            deemed_first_week=deemed[:, first],
            deemed_last_week=deemed[:, last],
            capital_first_week=capital[:, first],
            capital_last_week=capital[:, last],
            annual_annuity_income=annuity,
            weekly_minimum_guarantee=guarantee,
            pension_credit_citations=citations,
        )

    def _first_and_last_eligible_week(self) -> tuple[int, int]:
        weeks = np.flatnonzero(self.eligible)
        return (int(weeks[0]), int(weeks[-1])) if weeks.size else (0, 0)

    def _pension_credit(
        self, weekly_income: np.ndarray, capital: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, float | None, list[Citation]]:
        """Guarantee credit for the year: each eligible week assessed alone."""
        n, weeks = capital.shape
        if not self.eligible.any():
            return np.zeros(n), np.zeros((n, weeks)), None, []

        repeated_income = np.repeat(weekly_income, weeks)
        flat_capital = capital.ravel()
        # Weeks and draw amounts often share an assessment; run each one once.
        rows, inverse = np.unique(
            np.round(np.column_stack([repeated_income, flat_capital]), 6),
            axis=0,
            return_inverse=True,
        )
        screen = self.engines.pension_credit(
            year=self.inputs.tax_year, weekly_income=rows[:, 0], capital=rows[:, 1]
        )
        inverse = np.asarray(inverse).reshape(-1)
        weekly_credit = (
            np.asarray(screen["annual_amount"], dtype=float)[inverse] / WEEKS_IN_YEAR
        ).reshape(n, weeks)
        deemed = np.asarray(screen["weekly_deemed_income"], dtype=float)[
            inverse
        ].reshape(n, weeks)
        annual = (weekly_credit * self.eligible).sum(axis=1)
        return annual, deemed, screen["weekly_minimum_guarantee"], screen["citations"]


def _slice(evaluated: _Evaluated, low: int, high: int) -> UKDrawdownSlice:
    """Where the pounds between two draw amounts go."""
    width = float(evaluated.draws[high] - evaluated.draws[low])
    kept = float(evaluated.money_to_spend[high] - evaluated.money_to_spend[low]) / width
    direct_tax = evaluated.income_tax + evaluated.employee_ni
    return UKDrawdownSlice(
        draw_from=_money(evaluated.draws[low]),
        draw_to=_money(evaluated.draws[high]),
        kept=kept,
        to_tax=float(direct_tax[high] - direct_tax[low]) / width,
        to_pension_credit=(
            float(evaluated.pension_credit[low] - evaluated.pension_credit[high])
            / width
        ),
    )


def band_edges(draws: np.ndarray, tax: np.ndarray, credit: np.ndarray) -> np.ndarray:
    """Draw amounts, to the penny, where the rate on the next pound changes."""
    return drawdown_bands.band_edges(
        draws,
        [(tax, _BAND_TAX_TOLERANCE), (credit, _BAND_CREDIT_TOLERANCE)],
        min_width=_BAND_MIN_WIDTH,
    )


def _markers(
    inputs: UKDrawdownYearInput, evaluated: _Evaluated
) -> list[UKDrawdownMarker]:
    markers: list[UKDrawdownMarker] = []
    credit = evaluated.pension_credit
    draws = evaluated.draws

    if _is_regular_pot_draw(inputs) and evaluated.weekly_minimum_guarantee is not None:
        covered = float(evaluated.annual_annuity_income[0])
        # With no credit at that draw, there's no credit to start losing.
        if (
            0.0 < covered <= float(draws[-1])
            and np.interp(covered, draws, credit) > 0.005
        ):
            markers.append(
                UKDrawdownMarker(kind="pot_income_covered", draw=_money(covered))
            )

    gone = np.flatnonzero((credit[:-1] > 0.005) & (credit[1:] <= 0.005))
    if gone.size:
        low = int(gone[0])
        slope = (
            (credit[low - 1] - credit[low]) / (draws[low] - draws[low - 1])
            if low > 0
            else 0.0
        )
        width = float(draws[low + 1] - draws[low])
        # Run the last rate down to zero; if no earlier rate exists, or the
        # credit fell faster than that, take the grid point.
        reach = float(credit[low]) / slope if slope > 1e-9 else width
        markers.append(
            UKDrawdownMarker(
                kind="guarantee_credit_ends",
                draw=_money(float(draws[low]) + min(reach, width)),
            )
        )
    return markers


def _refs(citations: list[Citation]) -> list[UKCitationRef]:
    return [UKCitationRef(id=item.id, url=item.url) for item in citations]


def run_uk_drawdown_year(
    inputs: UKDrawdownYearInput, engines: DrawdownEngines | None = None
) -> UKDrawdownYearResult:
    """Cost out one year's draw and every other draw this pot allows."""
    engines = engines or default_engines()
    calculation = _Calculation(inputs, engines)
    balance = _source_balance(inputs)
    next_draw = min(inputs.draw_amount + _NEXT_DRAW_STEP, balance)

    grid = np.unique(
        np.concatenate([_sweep_draws(inputs), [0.0, inputs.draw_amount, next_draw]])
    )
    evaluated = calculation.evaluate(grid)

    chosen = evaluated.index_of(inputs.draw_amount)
    upcoming = evaluated.index_of(next_draw)
    no_draw = evaluated.index_of(0.0)

    edges = calculation.evaluate(
        band_edges(
            evaluated.draws,
            evaluated.income_tax + evaluated.employee_ni,
            evaluated.pension_credit,
        )
    )
    tax_citations = _refs(engines.tax_citations(inputs.tax_year))
    has_credit_weeks = bool(calculation.eligible.any())
    credit_citations = _refs(
        evaluated.pension_credit_citations + list(_PENSION_CREDIT_CITATIONS)
    )
    return UKDrawdownYearResult(
        tax_year_label=f"{inputs.tax_year}/{(inputs.tax_year + 1) % 100:02d}",
        draw_source=inputs.draw_source,
        sipp_draw_pattern=inputs.sipp_draw_pattern,
        pot_left=_money(balance - inputs.draw_amount),
        income_tax=UKDrawdownFigure(
            amount=_money(evaluated.income_tax[chosen]),
            engine=AXIOM_UK_TAX_ENGINE,
            citations=tax_citations,
        ),
        employee_ni=UKDrawdownFigure(
            amount=_money(evaluated.employee_ni[chosen]),
            engine=AXIOM_UK_TAX_ENGINE,
            citations=tax_citations,
        ),
        pension_credit=UKDrawdownFigure(
            amount=_money(evaluated.pension_credit[chosen]),
            engine=AXIOM_UK_TAX_ENGINE,
            citations=credit_citations,
        ),
        money_to_spend=_money(evaluated.money_to_spend[chosen]),
        at_chosen_draw=evaluated.outcome(chosen),
        with_no_draw=evaluated.outcome(no_draw),
        next_1000=_slice(evaluated, chosen, upcoming) if upcoming != chosen else None,
        pension_credit_working=UKDrawdownPensionCreditWorking(
            status="calculated" if has_credit_weeks else "under_qualifying_age",
            qualifying_date=calculation.qualifying_date,
            eligible_weeks=int(calculation.eligible.sum()),
            weekly_minimum_guarantee=evaluated.weekly_minimum_guarantee,
            annual_annuity_income=_money(evaluated.annual_annuity_income[chosen]),
            annuity_income_per_1000=calculation.annuity_income_per_1000,
            annuity_age=calculation.age,
            state_pension=_money(inputs.state_pension / WEEKS_IN_YEAR),
            other_pension_income=_money(inputs.other_pension_income / WEEKS_IN_YEAR),
            earnings_counted=_money(
                max(
                    inputs.employment_income / WEEKS_IN_YEAR
                    - _EARNINGS_DISREGARD_WEEKLY,
                    0.0,
                )
            ),
            regular_pot_income=_money(
                evaluated.regular_pot_income[chosen] / WEEKS_IN_YEAR
            ),
            notional_pot_income=_money(
                evaluated.notional_pot_income[chosen] / WEEKS_IN_YEAR
            ),
            tax_deducted=_money(evaluated.tax_deducted[chosen] / WEEKS_IN_YEAR),
            deemed_income_first_week=_money(evaluated.deemed_first_week[chosen]),
            deemed_income_last_week=_money(evaluated.deemed_last_week[chosen]),
            capital_first_week=_money(evaluated.capital_first_week[chosen]),
            capital_last_week=_money(evaluated.capital_last_week[chosen]),
        ),
        sweep=[evaluated.outcome(i) for i in range(len(grid))],
        bands=[_slice(edges, i, i + 1) for i in range(len(edges.draws) - 1)],
        markers=_markers(inputs, evaluated),
        assumptions=UKDrawdownAssumptions(
            tax_free_fraction_applied=(
                inputs.sipp_tax_free_fraction if inputs.draw_source == "sipp" else 0.0
            ),
            gilt_yield_percent_used=(
                None
                if inputs.annuity_income_per_1000 is not None
                else _yield_used(inputs.gilt_yield_percent)
            ),
        ),
    )
