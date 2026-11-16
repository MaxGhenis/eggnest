"""One tax year of drawing on US retirement savings.

Answers one question for one household in 2026: if we take this much from
this account, what does it cost in federal and state income tax and in
benefits, and how does it move Medicare premiums two years later?

PolicyEngine-US computes every tax and benefit (``us_year_engine``). This
module decides which draw amounts to evaluate, splits each extra dollar into
what the household keeps, what goes to tax and what benefits take back, and
marks the draw amounts where a benefit or health coverage ends, where the
later Medicare premium steps up and where withdrawals reach the required
minimum distribution.

It evaluates the year two or three times. The first run covers a grid of
round draw amounts. The second cuts into 24 pieces each grid interval that may
hold a jump or a change of coverage, that holds a change of rate, or where a
benefit reaches zero, and evaluates where the first run placed each change of
rate. Band edges then come from all those points, with each located jump cut
out so no line runs through it. An edge that lands more than $1 from every
evaluated draw gets a third run. On the stand-in rules of
``tests/test_drawdown_us.py``, which are piecewise linear, each change of rate
of 5 cents a dollar or more then lands on an edge within $1, and a jump of $30
or more gets a band 1/24 of its grid interval wide, unless it sits within
1/12 of an interval of a change of rate and is no larger than $25 plus that
change times 1/24 of the interval.

It counts each draw as spent through the year and holds savings at their
balances on January 1, 2026, the figures SSI, Medicaid and SNAP test against.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

import numpy as np

from . import drawdown_bands
from .citations import (
    Citation,
    _policyengine_variable,
    _statute,
    citations_for_keys,
)
from .models_us_drawdown import (
    MEDICARE_PREMIUM_LAG_YEARS,
    USDrawdownAssumptions,
    USDrawdownFigure,
    USDrawdownMarker,
    USDrawdownOutcome,
    USDrawdownSlice,
    USDrawdownYearInput,
    USDrawdownYearResult,
    USMedicareSurcharge,
    USRequiredMinimum,
    source_balance,
)
from .rmd import RMD_START_AGE, UNIFORM_LIFETIME_TABLE, calculate_rmd
from .us_year_engine import (
    CENT,
    FEDERAL_TAX_PARTS,
    OTHER_TAX_PARTS,
    USYearArrays,
)

NEXT_DRAW_STEP = 1_000.0
# 26 USC 4974(a): 25% of the amount by which distributions fall short of the
# required minimum; 10% if corrected within the window in 4974(e).
EXCISE_TAX_RATE = 0.25

# The sweep runs from nothing to the larger of this and 125% of the draw,
# within the account, in at most this many intervals of a round size.
_SWEEP_MIN_TOP = 250_000.0
_SWEEP_MAX_INTERVALS = 400
_SWEEP_STEPS = (
    50,
    100,
    250,
    500,
    1_000,
    2_500,
    5_000,
    10_000,
    25_000,
    50_000,
    100_000,
    250_000,
    500_000,
)
# Benefits for older households end at low incomes, so the sweep is finer
# there.
_SWEEP_FINE_TOP = 40_000.0
_SWEEP_FINE_STEP = 250.0

# A straight line describes a series between band edges to within these.
_BAND_TAX_TOLERANCE = 2.0
_BAND_BENEFIT_TOLERANCE = 15.0
_BAND_INCOME_TOLERANCE = 1.0
_BAND_MIN_WIDTH = 1.0
# Adjacent bands whose rates differ by less than this are one band.
_SAME_RATE = 0.0005

# A tax or benefit jumps inside an interval, rather than phasing in or out,
# when it moves faster than $1.05 per dollar of draw plus $25, or when a
# window of intervals moves $25 beyond what the rates on either side of the
# window give (drawdown_bands.JumpRule).
_JUMPS = drawdown_bands.JumpRule(rate=1.05, minimum=25.0)

# Items in a benefit breakdown that are remainders or never end with a draw.
_UNMARKED_PROGRAMS = frozenset(
    {"other_benefits", "other_computed_income", "ak_permanent_fund_dividend"}
)

_FEDERAL_TAX_CITATIONS = (
    _statute("26", "1", "Tax rates, including the rates on long-term gains"),
    _statute("26", "63", "Standard deduction and the addition for age 65"),
    _statute("26", "86", "Social Security benefits in gross income"),
    _statute("26", "151", "Deduction for seniors aged 65 and over"),
)
# Parts of federal income tax cited when the household pays them.
_FEDERAL_PART_CITATIONS = {
    "net_investment_income_tax": _statute("26", "1411", "Net investment income tax"),
    "alternative_minimum_tax": _statute("26", "55", "Alternative minimum tax"),
}
assert set(_FEDERAL_PART_CITATIONS) == set(FEDERAL_TAX_PARTS)
# The state tax on an election path that state_income_tax_before_refundable_credits
# ignores; Wisconsin's retirement income exclusion is the one PolicyEngine-US has.
_STATE_ELECTION_CITATION = _policyengine_variable(
    "state_income_tax", "State income tax, on the path the filer elects"
)
_WISCONSIN_EXCLUSION_CITATION = Citation(
    id="us-wi:statutes/71.05(6)(b)54m.a",
    url="https://docs.legis.wisconsin.gov/statutes/statutes/71/i/05/6/b/54m/a",
    title="Wisconsin retirement income exclusion",
    source="Wis. Stat. 71.05(6)(b)54m.a",
)
MEDICARE_CITATIONS = (
    _statute("42", "1395r", "Part B premium and its income-related adjustment"),
    _statute("42", "1395w-113", "Part D income-related monthly adjustment"),
)
REQUIRED_MINIMUM_CITATIONS = (
    _statute("26", "401", "Required minimum distributions, 401(a)(9)"),
    _statute("26", "4974", "Excise tax on a shortfall"),
)


class USYearEngine(Protocol):
    """Evaluates a household's year at many draw amounts. Tests use stand-ins."""

    name: str

    def label(self) -> str: ...

    def evaluate(
        self, inputs: USDrawdownYearInput, draws: np.ndarray
    ) -> USYearArrays: ...


def default_engine() -> USYearEngine:
    from .us_year_engine import PolicyEngineUSYear

    return PolicyEngineUSYear()


def sweep_draws(inputs: USDrawdownYearInput) -> np.ndarray:
    """A grid of round draw amounts from nothing up to the useful top."""
    top = min(source_balance(inputs), max(_SWEEP_MIN_TOP, inputs.draw_amount * 1.25))
    step = next(
        (s for s in _SWEEP_STEPS if top / s <= _SWEEP_MAX_INTERVALS),
        _SWEEP_STEPS[-1],
    )
    coarse = np.arange(0.0, top + step, step, dtype=float)
    fine = np.arange(0.0, _SWEEP_FINE_TOP + _SWEEP_FINE_STEP, _SWEEP_FINE_STEP)
    # The $1 point gives the rate on the very first dollars, so a change of
    # rate inside the first interval can be placed.
    grid = np.concatenate([coarse, fine, [1.0, top]])
    return np.unique(grid[grid <= top])


def taxable_draw(inputs: USDrawdownYearInput, draws: np.ndarray) -> np.ndarray:
    """The part of each draw in adjusted gross income."""
    draws = np.asarray(draws, dtype=float)
    if inputs.draw_source == "traditional":
        return draws
    if inputs.draw_source == "taxable":
        return draws * inputs.taxable_gain_share
    return np.zeros(len(draws))


def cash_income(inputs: USDrawdownYearInput) -> float:
    """Money the household receives in the year before any draw, $."""
    people = sum(
        person.social_security
        + person.pension_income
        + person.government_pension_income
        + person.earnings
        + person.other_traditional_withdrawals
        for _, person in inputs.people
    )
    return (
        people + inputs.taxable_interest + inputs.tax_exempt_interest + inputs.dividends
    )


def _money(value: float) -> float:
    # Adding 0.0 turns a rounded -0.0 into 0.0.
    return round(float(value), 2) + 0.0


@dataclass
class _Evaluated:
    """Each array holds one value per draw amount, in draw order."""

    draws: np.ndarray
    taxable_draw: np.ndarray
    federal_income_tax: np.ndarray
    state_income_tax: np.ndarray
    other_taxes: np.ndarray
    benefits: np.ndarray
    taxable_social_security: np.ndarray
    medicare_income: np.ndarray
    later_medicare_surcharge: np.ndarray
    money_to_spend: np.ndarray
    programs: dict[str, np.ndarray] = field(default_factory=dict)
    coverage: dict[str, np.ndarray] = field(default_factory=dict)
    tax_parts: dict[str, np.ndarray] = field(default_factory=dict)
    federal_parts: dict[str, np.ndarray] = field(default_factory=dict)
    state_election: np.ndarray | None = None

    _ARRAYS = (
        "draws",
        "taxable_draw",
        "federal_income_tax",
        "state_income_tax",
        "other_taxes",
        "benefits",
        "taxable_social_security",
        "medicare_income",
        "later_medicare_surcharge",
        "money_to_spend",
    )

    @property
    def taxes(self) -> np.ndarray:
        return self.federal_income_tax + self.state_income_tax + self.other_taxes

    def index_of(self, draw: float) -> int:
        return int(np.argmin(np.abs(self.draws - draw)))

    def outcome(self, index: int) -> USDrawdownOutcome:
        return USDrawdownOutcome(
            draw=_money(self.draws[index]),
            taxable_draw=_money(self.taxable_draw[index]),
            federal_income_tax=_money(self.federal_income_tax[index]),
            state_income_tax=_money(self.state_income_tax[index]),
            other_taxes=_money(self.other_taxes[index]),
            benefits=_money(self.benefits[index]),
            benefits_by_program={
                name: _money(values[index]) for name, values in self.programs.items()
            },
            taxable_social_security=_money(self.taxable_social_security[index]),
            medicare_income=_money(self.medicare_income[index]),
            later_medicare_surcharge=_money(self.later_medicare_surcharge[index]),
            money_to_spend=_money(self.money_to_spend[index]),
        )

    def programs_at(self, index: int) -> dict[str, float]:
        return {
            name: _money(values[index])
            for name, values in self.programs.items()
            if abs(values[index]) > CENT
        }

    def tax_parts_at(self, index: int) -> list[str]:
        """The parts of other taxes the household pays at this draw."""
        return [
            name for name, values in self.tax_parts.items() if abs(values[index]) > CENT
        ]

    def federal_parts_at(self, index: int) -> list[str]:
        """The parts of federal income tax with law of their own paid at this draw."""
        return [
            name
            for name, values in self.federal_parts.items()
            if abs(values[index]) > CENT
        ]

    def coverage_at(self, index: int) -> dict[str, bool]:
        return {name: bool(values[index]) for name, values in self.coverage.items()}

    def merge(self, other: _Evaluated) -> _Evaluated:
        """Both evaluations' draw amounts, in order."""
        draws = np.concatenate([self.draws, other.draws])
        order = np.argsort(draws, kind="stable")
        keep = order[np.concatenate([[True], np.diff(draws[order]) > 0])]

        def combined(first: np.ndarray, second: np.ndarray) -> np.ndarray:
            return np.concatenate([first, second])[keep]

        def by_name(first: dict, second: dict, empty) -> dict:
            names = list(dict.fromkeys([*first, *second]))
            return {
                name: combined(
                    first.get(name, np.full(len(self.draws), empty)),
                    second.get(name, np.full(len(other.draws), empty)),
                )
                for name in names
            }

        return _Evaluated(
            **{
                name: combined(getattr(self, name), getattr(other, name))
                for name in self._ARRAYS
            },
            programs=by_name(self.programs, other.programs, 0.0),
            coverage=by_name(self.coverage, other.coverage, False),
            tax_parts=by_name(self.tax_parts, other.tax_parts, 0.0),
            federal_parts=by_name(self.federal_parts, other.federal_parts, 0.0),
            state_election=(
                combined(self.state_election, other.state_election)
                if self.state_election is not None and other.state_election is not None
                else None
            ),
        )


@dataclass
class _Run:
    """Everything one evaluation of the engine returns."""

    evaluated: _Evaluated
    people_on_medicare: int
    medicare_lines: list[float]
    medicare_rates_year: int


def _evaluate(
    engine: USYearEngine, inputs: USDrawdownYearInput, draws: np.ndarray
) -> _Run:
    # Whole cents, so no two points round to the same reported amount.
    draws = np.unique(np.round(np.asarray(draws, dtype=float), 2))
    arrays = engine.evaluate(inputs, draws)
    money = cash_income(inputs) + draws - arrays.taxes + arrays.benefits
    return _Run(
        evaluated=_Evaluated(
            draws=draws,
            taxable_draw=taxable_draw(inputs, draws),
            federal_income_tax=arrays.federal_income_tax,
            state_income_tax=arrays.state_income_tax,
            other_taxes=arrays.other_taxes,
            benefits=arrays.benefits,
            taxable_social_security=arrays.taxable_social_security,
            medicare_income=arrays.medicare_income,
            later_medicare_surcharge=arrays.later_medicare_surcharge,
            money_to_spend=money,
            programs=dict(arrays.programs),
            coverage={
                name: np.asarray(v, dtype=bool) for name, v in arrays.coverage.items()
            },
            tax_parts=dict(arrays.other_tax_parts),
            federal_parts=dict(arrays.federal_tax_parts),
            state_election=(
                None
                if arrays.state_tax_election is None
                else np.asarray(arrays.state_tax_election, dtype=bool)
            ),
        ),
        people_on_medicare=arrays.people_on_medicare,
        medicare_lines=list(arrays.medicare_lines),
        medicare_rates_year=arrays.medicare_rates_year,
    )


def _band_series(evaluated: _Evaluated) -> drawdown_bands.Series:
    return [
        (evaluated.taxes, _BAND_TAX_TOLERANCE),
        (evaluated.benefits, _BAND_BENEFIT_TOLERANCE),
        (evaluated.taxable_social_security, _BAND_INCOME_TOLERANCE),
        (evaluated.medicare_income, _BAND_INCOME_TOLERANCE),
    ]


def _moving(evaluated: _Evaluated) -> list[np.ndarray]:
    """The series a jump can show in: taxes and each benefit."""
    return [evaluated.taxes, *evaluated.programs.values()]


def cliff_intervals(evaluated: _Evaluated) -> list[tuple[float, float]]:
    """Grid intervals that may hold a jump in a tax or benefit, or a change of
    coverage; a closer look inside each settles which do."""
    return drawdown_bands.cliff_intervals(
        evaluated.draws,
        _moving(evaluated),
        _JUMPS,
        changes_of_state=list(evaluated.coverage.values()),
    )


def refined_intervals(first: _Evaluated) -> list[tuple[float, float]]:
    """Grid intervals the second run cuts into pieces for a closer look
    (drawdown_bands.refined_intervals), with each benefit but the remainders
    checked for reaching zero."""
    return drawdown_bands.refined_intervals(
        first.draws,
        _band_series(first),
        _moving(first),
        _JUMPS,
        changes_of_state=list(first.coverage.values()),
        reaching_zero=[
            values
            for program, values in first.programs.items()
            if program not in _UNMARKED_PROGRAMS
        ],
        zero=CENT,
    )


def _slice(evaluated: _Evaluated, low: int, high: int) -> USDrawdownSlice:
    """Where the dollars between two draw amounts go."""
    width = float(evaluated.draws[high] - evaluated.draws[low])

    def rate(values: np.ndarray) -> float:
        return float(values[high] - values[low]) / width

    return USDrawdownSlice(
        draw_from=_money(evaluated.draws[low]),
        draw_to=_money(evaluated.draws[high]),
        kept=rate(evaluated.money_to_spend),
        to_tax=rate(evaluated.taxes),
        to_benefits=-rate(evaluated.benefits),
        social_security_taxed=rate(evaluated.taxable_social_security),
    )


def _same_rates(left: USDrawdownSlice, right: USDrawdownSlice) -> bool:
    return all(
        abs(getattr(left, name) - getattr(right, name)) < _SAME_RATE
        for name in ("kept", "to_tax", "to_benefits", "social_security_taxed")
    )


def _bands(
    merged: _Evaluated, edges: list[float], jumps: list[tuple[float, float]]
) -> list[USDrawdownSlice]:
    """Slices between edges, each located jump on its own, with neighbours
    that share their rates joined (drawdown_bands.band_pieces)."""
    pieces = drawdown_bands.band_pieces(
        merged.draws,
        edges,
        jumps,
        lambda left, right: _same_rates(_slice(merged, *left), _slice(merged, *right)),
    )
    return [
        _slice(merged, low, high).model_copy(update={"jump": jump})
        for low, high, jump in pieces
    ]


def band_edges(first: _Evaluated) -> np.ndarray:
    """Draw amounts where the rate on the next dollar changes, where the lines
    on either side cross (drawdown_bands.band_edges)."""
    return drawdown_bands.band_edges(
        first.draws, _band_series(first), min_width=_BAND_MIN_WIDTH
    )


def _ends(draws: np.ndarray, values: np.ndarray, first_zero: int) -> float:
    """Where a benefit last above zero at ``first_zero - 1`` reaches zero."""
    last = first_zero - 1
    width = float(draws[first_zero] - draws[last])
    slope = (
        (values[last - 1] - values[last]) / (draws[last] - draws[last - 1])
        if last > 0
        else 0.0
    )
    # Run the last rate down to zero; if no earlier rate exists, or the
    # benefit fell faster than that, take the next point.
    reach = float(values[last]) / slope if slope > 1e-9 else width
    return float(draws[last]) + min(reach, width)


@dataclass(frozen=True)
class _RequiredMinimum:
    person: str
    age: int
    balance: float
    divisor: float
    amount: float
    other_withdrawals: float

    @property
    def first_year(self) -> bool:
        """Whether this is the person's first distribution calendar year: the
        year they reach the applicable age, 73 for anyone it reaches in 2026
        (26 USC 401(a)(9)(C)(v)). Anyone older reached it in an earlier year."""
        return self.age == RMD_START_AGE


def _due_by(minimum: _RequiredMinimum, tax_year: int) -> date:
    """The first minimum can wait until the required beginning date, April 1
    of the next year (26 USC 401(a)(9)(C)(i)); later ones are due by the end of
    the year."""
    return date(tax_year + 1, 4, 1) if minimum.first_year else date(tax_year, 12, 31)


def required_minimums(inputs: USDrawdownYearInput) -> list[_RequiredMinimum]:
    """2026 required minimum distributions from the Uniform Lifetime Table."""
    found = []
    for who, person in inputs.people:
        amount = calculate_rmd(person.traditional_balance, person.age)
        if amount <= 0:
            continue
        found.append(
            _RequiredMinimum(
                person=who,
                age=person.age,
                balance=person.traditional_balance,
                divisor=UNIFORM_LIFETIME_TABLE.get(
                    person.age, UNIFORM_LIFETIME_TABLE[120]
                ),
                amount=amount,
                other_withdrawals=person.other_traditional_withdrawals,
            )
        )
    return found


def _required_minimum(
    inputs: USDrawdownYearInput, minimum: _RequiredMinimum
) -> USRequiredMinimum:
    draws_here = (
        inputs.draw_source == "traditional" and inputs.draw_owner == minimum.person
    )
    withdrawn = minimum.other_withdrawals + (inputs.draw_amount if draws_here else 0.0)
    shortfall = max(minimum.amount - withdrawn, 0.0)
    # A first-year shortfall can still be taken by April 1 of the next year;
    # the excise tax on it falls in that year (26 CFR 54.4974-1(f)).
    excise = 0.0 if minimum.first_year else EXCISE_TAX_RATE * shortfall
    return USRequiredMinimum(
        person=minimum.person,
        age=minimum.age,
        balance=_money(minimum.balance),
        divisor=minimum.divisor,
        amount=_money(minimum.amount),
        other_withdrawals=_money(minimum.other_withdrawals),
        withdrawn=_money(withdrawn),
        shortfall=_money(shortfall),
        first_year=minimum.first_year,
        due_by=_due_by(minimum, inputs.tax_year),
        excise_tax_rate=EXCISE_TAX_RATE,
        excise_tax_on_shortfall=_money(excise),
    )


def _medicare_points(first: _Evaluated, lines: list[float]) -> np.ndarray:
    """Draws at which the first run's Medicare income reaches each line, and
    halfway between neighbouring lines, as straight lines between its points
    place them.

    The second run samples them, so no interval of the sweep spans two lines
    and each marker carries its own line's step. Without them two lines can
    share a grid interval, between steps on either side that make the
    surcharge rise like a ramp, which the jump test rightly passes over.
    """
    income = first.medicare_income
    draws = first.draws
    targets = [*lines, *((low + high) / 2 for low, high in itertools.pairwise(lines))]
    points = []
    for target in targets:
        crossed = np.flatnonzero((income[:-1] < target) & (income[1:] >= target))
        if crossed.size:
            i = int(crossed[0])
            share = (target - income[i]) / (income[i + 1] - income[i])
            points.append(draws[i] + share * (draws[i + 1] - draws[i]))
    return np.array(points, dtype=float)


def _markers(
    inputs: USDrawdownYearInput,
    merged: _Evaluated,
    lines: list[float],
    minimums: list[_RequiredMinimum],
) -> list[USDrawdownMarker]:
    draws = merged.draws
    markers: list[USDrawdownMarker] = []

    for program, values in merged.programs.items():
        if program in _UNMARKED_PROGRAMS:
            continue
        gone = np.flatnonzero((values[:-1] > CENT) & (values[1:] <= CENT))
        if gone.size:
            markers.append(
                USDrawdownMarker(
                    kind="benefit_ends",
                    draw=_money(_ends(draws, values, int(gone[0]) + 1)),
                    program=program,
                )
            )

    for name, covered in merged.coverage.items():
        lost = np.flatnonzero(covered[:-1] & ~covered[1:])
        if lost.size:
            markers.append(
                USDrawdownMarker(
                    kind="coverage_ends",
                    draw=_money(draws[int(lost[0]) + 1]),
                    program=name,
                )
            )

    income = merged.medicare_income
    surcharge = merged.later_medicare_surcharge
    for line in lines:
        crossed = np.flatnonzero((income[:-1] < line) & (income[1:] >= line))
        if not crossed.size:
            continue
        below = int(crossed[0])
        step = float(surcharge[below + 1] - surcharge[below])
        if step <= CENT:
            continue
        share = (line - income[below]) / (income[below + 1] - income[below])
        markers.append(
            USDrawdownMarker(
                kind="medicare_surcharge_step",
                draw=_money(draws[below] + share * (draws[below + 1] - draws[below])),
                amount=_money(step),
            )
        )

    if inputs.draw_source == "traditional":
        for minimum in minimums:
            reached = minimum.amount - minimum.other_withdrawals
            if minimum.person == inputs.draw_owner and 0.0 < reached <= draws[-1]:
                markers.append(
                    USDrawdownMarker(
                        kind="required_minimum_reached",
                        draw=_money(reached),
                        amount=_money(minimum.amount),
                    )
                )
    return sorted(markers, key=lambda marker: (marker.draw, marker.kind))


def _federal_tax_citations(
    merged: _Evaluated, chosen: int, no_draw: int
) -> list[Citation]:
    """The federal tax's law, with the parts paid at the chosen draw or at none."""
    paid = {*merged.federal_parts_at(chosen), *merged.federal_parts_at(no_draw)}
    return [
        *citations_for_keys(["federal_income_tax"]),
        *_FEDERAL_TAX_CITATIONS,
        *(c for name, c in _FEDERAL_PART_CITATIONS.items() if name in paid),
    ]


def _state_tax_citations(
    inputs: USDrawdownYearInput, merged: _Evaluated, chosen: int
) -> list[Citation]:
    """The variable the chosen draw's state tax comes from."""
    if merged.state_election is None or not merged.state_election[chosen]:
        return citations_for_keys(["state_income_tax"])
    if inputs.state == "WI":
        return [_STATE_ELECTION_CITATION, _WISCONSIN_EXCLUSION_CITATION]
    return [_STATE_ELECTION_CITATION]


def _other_tax_keys(merged: _Evaluated, chosen: int, no_draw: int) -> list[str]:
    """The other taxes to cite: those paid at the chosen draw or at none."""
    if not merged.tax_parts:
        # An engine that doesn't itemize: cite the payroll tax and the total.
        return ["payroll_tax", "other_taxes"]
    paid = {*merged.tax_parts_at(chosen), *merged.tax_parts_at(no_draw)}
    return [name for name in OTHER_TAX_PARTS if name in paid]


def run_us_drawdown_year(
    inputs: USDrawdownYearInput, engine: USYearEngine | None = None
) -> USDrawdownYearResult:
    """Cost out one year's draw and every other draw this account allows."""
    engine = engine or default_engine()
    balance = source_balance(inputs)
    next_draw = min(inputs.draw_amount + NEXT_DRAW_STEP, balance)

    grid = np.unique(
        np.concatenate([sweep_draws(inputs), [0.0, inputs.draw_amount, next_draw]])
    )
    first_run = _evaluate(engine, inputs, grid)
    first = first_run.evaluated
    edges = band_edges(first)
    refined = refined_intervals(first)
    medicare_points = _medicare_points(first, first_run.medicare_lines)
    second = _evaluate(
        engine,
        inputs,
        np.concatenate(
            [
                edges,
                drawdown_bands.subdivide(refined, _JUMPS.subdivisions),
                medicare_points,
            ]
        ),
    ).evaluated
    merged = first.merge(second)

    # Refined intervals that touch are looked at together, so a jump in one
    # can't pass for a neighbour's rate in the other.
    moving = _moving(merged)
    jumps = sorted(
        jump
        for low, high in drawdown_bands.stretches(refined)
        for jump in drawdown_bands.locate_jumps(merged.draws, moving, low, high, _JUMPS)
    )
    final_edges = drawdown_bands.edges_between_jumps(
        merged.draws, _band_series(merged), jumps, _BAND_MIN_WIDTH
    )
    # An edge the merged grid moves away from every evaluated draw (beside a
    # jump, or between changes of rate the grid alone couldn't separate) gets
    # a run of its own, so its band's rates come from the engine.
    missing = drawdown_bands.unevaluated(merged.draws, final_edges, _BAND_MIN_WIDTH)
    if missing.size:
        merged = merged.merge(_evaluate(engine, inputs, missing).evaluated)
    bands = _bands(merged, final_edges, jumps)

    chosen = merged.index_of(inputs.draw_amount)
    upcoming = merged.index_of(next_draw)
    no_draw = merged.index_of(0.0)
    minimums = required_minimums(inputs)
    engine_label = engine.label()

    program_keys = list(
        dict.fromkeys([*merged.programs_at(chosen), *merged.programs_at(no_draw)])
    )
    other_tax_keys = _other_tax_keys(merged, chosen, no_draw)
    return USDrawdownYearResult(
        tax_year=inputs.tax_year,
        state=inputs.state,
        filing_status=inputs.filing_status,
        draw_source=inputs.draw_source,
        draw_owner=inputs.draw_owner,
        account_left=_money(balance - inputs.draw_amount),
        federal_income_tax=USDrawdownFigure(
            amount=_money(merged.federal_income_tax[chosen]),
            engine=engine_label,
            citations=_federal_tax_citations(merged, chosen, no_draw),
        ),
        state_income_tax=USDrawdownFigure(
            amount=_money(merged.state_income_tax[chosen]),
            engine=engine_label,
            citations=_state_tax_citations(inputs, merged, chosen),
        ),
        other_taxes=USDrawdownFigure(
            amount=_money(merged.other_taxes[chosen]),
            engine=engine_label,
            citations=citations_for_keys(other_tax_keys),
        ),
        benefits=USDrawdownFigure(
            amount=_money(merged.benefits[chosen]),
            engine=engine_label,
            citations=citations_for_keys(program_keys),
        ),
        coverage_at_chosen_draw=merged.coverage_at(chosen),
        coverage_with_no_draw=merged.coverage_at(no_draw),
        money_to_spend=_money(merged.money_to_spend[chosen]),
        at_chosen_draw=merged.outcome(chosen),
        with_no_draw=merged.outcome(no_draw),
        # Under $1 left, rounding swamps the rate, as it does a band's.
        next_1000=(
            _slice(merged, chosen, upcoming)
            if merged.draws[upcoming] - merged.draws[chosen] >= _BAND_MIN_WIDTH
            else None
        ),
        medicare_surcharge=USMedicareSurcharge(
            premium_year=inputs.tax_year + MEDICARE_PREMIUM_LAG_YEARS,
            rates_year=first_run.medicare_rates_year,
            people_on_medicare=first_run.people_on_medicare,
            lines=[_money(line) for line in first_run.medicare_lines],
            at_chosen_draw=_money(merged.later_medicare_surcharge[chosen]),
            with_no_draw=_money(merged.later_medicare_surcharge[no_draw]),
        ),
        required_minimums=[_required_minimum(inputs, m) for m in minimums],
        sweep=[merged.outcome(i) for i in range(len(merged.draws))],
        bands=bands,
        markers=_markers(inputs, merged, first_run.medicare_lines, minimums),
        assumptions=USDrawdownAssumptions(
            taxable_gain_share_applied=(
                inputs.taxable_gain_share if inputs.draw_source == "taxable" else None
            ),
        ),
    )


def citations(result: USDrawdownYearResult) -> list[Citation]:
    """Every source behind a result, each once."""
    seen: dict[str, Citation] = {}
    for figure in (
        result.federal_income_tax,
        result.state_income_tax,
        result.other_taxes,
        result.benefits,
    ):
        for citation in figure.citations:
            seen.setdefault(citation.id, citation)
    for citation in MEDICARE_CITATIONS:
        seen.setdefault(citation.id, citation)
    if result.required_minimums:
        for citation in REQUIRED_MINIMUM_CITATIONS:
            seen.setdefault(citation.id, citation)
    return list(seen.values())
