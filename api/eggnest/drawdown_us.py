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

It evaluates the year twice. The first run covers a grid of round draw
amounts. The second runs where the first found the rate on the next dollar
changing, so band edges land on the dollar, and inside any interval where a
benefit or tax jumps, so a cliff is placed to a few dollars.

Money drawn counts as spent through the year and savings balances are those on
January 1, 2026, the figures SSI, Medicaid and SNAP test against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from . import drawdown_bands
from .citations import Citation, _statute, citations_for_keys
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
from .rmd import UNIFORM_LIFETIME_TABLE, calculate_rmd
from .us_year_engine import CENT, USYearArrays

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
# when it moves faster than this rate per dollar of draw plus this many
# dollars, or when a window of intervals moves this many dollars beyond what
# the rates on either side of the window give.
_CLIFF_RATE = 1.05
_CLIFF_MIN = 25.0
_CLIFF_SUBDIVISIONS = 24
# The grid tests windows of one and two intervals, so a jump beside another
# can't hide behind its neighbour's rate. Inside an interval, where two jumps
# rarely sit side by side, windows of one.
_GRID_WINDOWS = (1, 2)
_REFINED_WINDOWS = (1,)
# A neighbour gives a rate only if it is this many dollars wide and this share
# of the window's width, since rounding swamps the rate of a sliver. Up to
# this many intervals out, narrower ones are passed over.
_NEIGHBOUR_MIN_WIDTH = 5.0
_NEIGHBOUR_MIN_SHARE = 0.25
_NEIGHBOUR_REACH = 3

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


def _neighbours(
    width: np.ndarray, size: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For the window of ``size`` intervals starting at each interval: its
    width, and the nearest interval on each side wide enough to give a rate
    (-1 where none is)."""
    count = len(width) - size + 1
    if count <= 0:
        none = np.zeros(0, dtype=int)
        return np.zeros(0), none, none
    window = np.convolve(width, np.ones(size), mode="valid")
    need = np.maximum(_NEIGHBOUR_MIN_WIDTH, _NEIGHBOUR_MIN_SHARE * window)
    left = np.full(count, -1)
    right = np.full(count, -1)
    for start in range(count):
        for j in range(start - 1, max(start - 1 - _NEIGHBOUR_REACH, -1), -1):
            if width[j] >= need[start]:
                left[start] = j
                break
        for j in range(start + size, min(start + size + _NEIGHBOUR_REACH, len(width))):
            if width[j] >= need[start]:
                right[start] = j
                break
    return window, left, right


def _window_scores(
    change: np.ndarray,
    width: np.ndarray,
    size: int,
    neighbours: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> np.ndarray:
    """How far each interval's window moves beyond what the rates on either
    side of it give, $; -inf where no neighbour gives a rate."""
    window, left, right = neighbours
    scores = np.full(len(change), -np.inf)
    if not len(window):
        return scores
    rate = change / width
    moved = np.convolve(change, np.ones(size), mode="valid")
    left_rate = np.where(left >= 0, rate[left], np.nan)
    right_rate = np.where(right >= 0, rate[right], np.nan)
    low = np.fmin(left_rate, right_rate) * window
    high = np.fmax(left_rate, right_rate) * window
    beyond = np.fmax(moved - high, low - moved) - _CLIFF_MIN
    beyond = np.where(np.isnan(beyond), -np.inf, beyond)
    for offset in range(size):
        stop = offset + len(beyond)
        scores[offset:stop] = np.maximum(scores[offset:stop], beyond)
    return scores


def _jump_scores(evaluated: _Evaluated, windows: tuple[int, ...]) -> np.ndarray:
    """How far each interval's largest move exceeds what a phase-out could do, $.

    A score of zero or more marks a jump, found two ways. A tax or benefit can
    move faster than any phase-out. Or a window of intervals can move beyond
    what the rates on either side of it give: a change of rate inside the
    window leaves its move between those rates, so only a jump takes it more
    than ``_CLIFF_MIN`` beyond them, however small the jump is beside the
    window's width. A change of coverage scores zero.
    """
    width = np.diff(evaluated.draws)
    scores = np.full(len(width), -np.inf)
    if not len(width):
        return scores
    allowed = _CLIFF_RATE * width + _CLIFF_MIN
    neighbours = {size: _neighbours(width, size) for size in windows}
    for values in [evaluated.taxes, *evaluated.programs.values()]:
        change = np.diff(values)
        scores = np.maximum(scores, np.abs(change) - allowed)
        for size, around in neighbours.items():
            scores = np.maximum(scores, _window_scores(change, width, size, around))
    for covered in evaluated.coverage.values():
        changed = covered[:-1] != covered[1:]
        scores = np.where(changed, np.maximum(scores, 0.0), scores)
    return scores


def cliff_intervals(evaluated: _Evaluated) -> list[tuple[float, float]]:
    """Grid intervals that may hold a jump in a tax or benefit, or a change of
    coverage; a closer look inside each settles which do."""
    draws = evaluated.draws
    return [
        (float(draws[i]), float(draws[i + 1]))
        for i in np.flatnonzero(_jump_scores(evaluated, _GRID_WINDOWS) >= 0.0)
    ]


def _refinement(intervals: list[tuple[float, float]]) -> np.ndarray:
    steps = np.arange(1, _CLIFF_SUBDIVISIONS) / _CLIFF_SUBDIVISIONS
    points = [low + steps * (high - low) for low, high in intervals]
    return np.concatenate(points) if points else np.zeros(0)


def _locate_jumps(
    merged: _Evaluated, low: float, high: float
) -> list[tuple[float, float]]:
    """The neighbouring draw amounts between which each jump inside an interval
    falls; none if a closer look finds only changes of rate."""
    inside = np.flatnonzero((merged.draws >= low) & (merged.draws <= high))
    # One more point on each side gives the outermost pieces a neighbour.
    span = np.arange(max(inside[0] - 1, 0), min(inside[-1] + 2, len(merged.draws)))
    part = _Evaluated(
        **{name: getattr(merged, name)[span] for name in _Evaluated._ARRAYS},
        programs={k: v[span] for k, v in merged.programs.items()},
        coverage={k: v[span] for k, v in merged.coverage.items()},
    )
    draws = part.draws
    return [
        (float(draws[i]), float(draws[i + 1]))
        for i in np.flatnonzero(_jump_scores(part, _REFINED_WINDOWS) >= 0.0)
        if low <= draws[i] and draws[i + 1] <= high
    ]


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


def _bands(merged: _Evaluated, edges: list[float]) -> list[USDrawdownSlice]:
    """Slices between edges, with neighbours that share their rates joined."""
    indices = [merged.index_of(edge) for edge in edges]
    if len(indices) < 2:
        return []  # An empty account has nothing to draw.
    joined = [indices[0], indices[1]]
    for index in indices[2:]:
        if _same_rates(
            _slice(merged, joined[-2], joined[-1]), _slice(merged, joined[-1], index)
        ):
            joined[-1] = index
        else:
            joined.append(index)
    return [
        _slice(merged, low, high) for low, high in zip(joined, joined[1:], strict=False)
    ]


def band_edges(first: _Evaluated) -> np.ndarray:
    """Draw amounts, to the cent, where the rate on the next dollar changes."""
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
    return USRequiredMinimum(
        person=minimum.person,
        age=minimum.age,
        balance=_money(minimum.balance),
        divisor=minimum.divisor,
        amount=_money(minimum.amount),
        other_withdrawals=_money(minimum.other_withdrawals),
        withdrawn=_money(withdrawn),
        shortfall=_money(shortfall),
        excise_tax_rate=EXCISE_TAX_RATE,
        excise_tax_on_shortfall=_money(EXCISE_TAX_RATE * shortfall),
    )


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
    cliffs = cliff_intervals(first)
    second = _evaluate(
        engine, inputs, np.concatenate([edges, _refinement(cliffs)])
    ).evaluated
    merged = first.merge(second)

    final_edges = {float(edge) for edge in edges}
    for low, high in cliffs:
        jumps = _locate_jumps(merged, low, high)
        if not jumps:
            continue  # Only changes of rate, which the band edges place.
        # Edges the first run put near a jump are artefacts of it.
        final_edges = {edge for edge in final_edges if not low < edge < high}
        for jump in jumps:
            final_edges.update(jump)
    bands = _bands(merged, sorted(final_edges))

    chosen = merged.index_of(inputs.draw_amount)
    upcoming = merged.index_of(next_draw)
    no_draw = merged.index_of(0.0)
    minimums = required_minimums(inputs)
    engine_label = engine.label()

    program_keys = list(
        dict.fromkeys([*merged.programs_at(chosen), *merged.programs_at(no_draw)])
    )
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
            citations=[
                *citations_for_keys(["federal_income_tax"]),
                *_FEDERAL_TAX_CITATIONS,
            ],
        ),
        state_income_tax=USDrawdownFigure(
            amount=_money(merged.state_income_tax[chosen]),
            engine=engine_label,
            citations=citations_for_keys(["state_income_tax"]),
        ),
        other_taxes=USDrawdownFigure(
            amount=_money(merged.other_taxes[chosen]),
            engine=engine_label,
            citations=citations_for_keys(["payroll_tax", "other_taxes"]),
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
        next_1000=_slice(merged, chosen, upcoming) if upcoming != chosen else None,
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
