"""Where the rate on the next unit of a draw changes, and where a tax or
benefit jumps.

The one-year drawdown calculators evaluate a year's result on a grid of draw
amounts. These helpers find the draw amounts where a straight line stops
describing each series (tax, benefits) and place each change of rate where
the lines on either side cross, so a coarse grid still gives band edges far
closer than its spacing. On a piecewise-linear series whose changes of rate
sit three or more grid intervals apart, each edge lands within a cent of the
change (tests/test_drawdown_bands.py).

A tax or benefit can also change all at once. The grid flags intervals that
may hold such a jump (``cliff_intervals``), a second run cuts them and the
intervals around each change of rate into pieces (``refined_intervals``), and
``locate_jumps`` picks the pieces that hold one. Band edges then come from
each stretch between jumps on its own (``edges_between_jumps``), and
``band_pieces`` gives each located jump a band of its own. Both calculators
use these; ``JumpRule`` holds the thresholds each one sets.

A change of rate a piece or two from a jump leaves too few pieces between
them to tell a rate from a jump, so the pieces between can pass for jumps
too. ``crowded_jumps`` finds each located jump with a band beside it too
short to judge, ``closer_look`` cuts the pieces around it finer for one more
run, and ``relocated_jumps`` locates the jumps there again. The UK
calculator does this before ``pin_changes``; the US one does not.

``pin_changes`` goes further, to the cent: it runs a few more evaluations to
find where the straight line on each side of a change stops describing a
series, which tells a kink from a jump beside it and puts an edge on the cent
where a series that moves in small steps (rounding to whole pounds, say)
meets a straight line.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

Series = list[tuple[np.ndarray, float]]
CENT = 0.01

# A change of rate smaller than this is no change.
KINK_MIN_RATE_CHANGE = 0.005


def band_breaks(draws: np.ndarray, series: Series) -> list[int]:
    """Grid indices where a straight line stops describing a series.

    Splits each span at the point furthest from the chord across it
    (Ramer-Douglas-Peucker) until every series stays within its tolerance.
    """
    breaks = {0, len(draws) - 1}
    spans = [(0, len(draws) - 1)]
    while spans:
        low, high = spans.pop()
        if high - low < 2:
            continue
        share = (draws[low + 1 : high] - draws[low]) / (draws[high] - draws[low])
        split, worst = None, 1.0
        for values, tolerance in series:
            chord = values[low] + share * (values[high] - values[low])
            excess = np.abs(values[low + 1 : high] - chord) / tolerance
            at = int(np.argmax(excess))
            if excess[at] > worst:
                split, worst = low + 1 + at, float(excess[at])
        if split is not None:
            breaks.add(split)
            spans += [(low, split), (split, high)]
    return sorted(breaks)


def crossing_point(
    draws: np.ndarray,
    values: np.ndarray,
    left: tuple[int, int],
    right: tuple[int, int],
    min_rate_change: float = KINK_MIN_RATE_CHANGE,
) -> float | None:
    """Where the line through grid span ``left`` crosses the one through ``right``.

    Returns None when the two lines carry the same rate or cross outside the
    gap between them.
    """
    left_from, left_to = left
    right_from, right_to = right
    if left_to <= left_from or right_to <= right_from:
        return None
    left_rate = (values[left_to] - values[left_from]) / (
        draws[left_to] - draws[left_from]
    )
    right_rate = (values[right_to] - values[right_from]) / (
        draws[right_to] - draws[right_from]
    )
    if abs(left_rate - right_rate) < min_rate_change:
        return None
    crossing = (
        values[right_from]
        - values[left_from]
        + left_rate * draws[left_from]
        - right_rate * draws[right_from]
    ) / (left_rate - right_rate)
    return float(crossing) if draws[left_to] <= crossing <= draws[right_from] else None


def _fits(
    draws: np.ndarray, values: np.ndarray, span: tuple[int, int], tolerance: float
) -> bool:
    """Whether the line through a span's ends passes within ``tolerance`` of
    every point between them."""
    low, high = span
    if high - low < 2:
        return True
    share = (draws[low + 1 : high] - draws[low]) / (draws[high] - draws[low])
    chord = values[low] + share * (values[high] - values[low])
    return bool(np.all(np.abs(values[low + 1 : high] - chord) <= tolerance))


def _line_span(
    draws: np.ndarray,
    values: np.ndarray,
    tolerance: float,
    span: tuple[int, int],
    gap_above: bool,
) -> tuple[int, int]:
    """The part of a span next to the gap that a straight line describes.

    The span's far end is itself a break, which can sit just past the next
    change of rate, so it stays out of the line while the span has room. Then
    the span gives up points at its far end until its line fits every point
    within the series' tolerance; one interval always fits.
    """
    low, high = span

    def shorter(low: int, high: int) -> tuple[int, int]:
        return (low + 1, high) if gap_above else (low, high - 1)

    if high - low >= 2:
        low, high = shorter(low, high)
    while high - low >= 2 and not _fits(draws, values, (low, high), tolerance):
        low, high = shorter(low, high)
    return low, high


def _changes(draws: np.ndarray, series: Series) -> list[tuple[int, int, float]]:
    """Each change of rate: the grid indices either side of the interval or
    two that hold it, and where it lies.

    A rate changes between grid points, and the interval holding the change
    mixes both rates. So the change lies where the lines on either side
    cross, each through points it fits within the series' tolerance; where no
    series' lines cross in the gap, it stays on the break.
    """
    breaks = band_breaks(draws, series)

    def crossing(left: tuple[int, int], right: tuple[int, int]) -> float | None:
        for values, tolerance in series:
            point = crossing_point(
                draws,
                values,
                _line_span(draws, values, tolerance, left, gap_above=True),
                _line_span(draws, values, tolerance, right, gap_above=False),
            )
            if point is not None:
                return point
        return None

    changes = []
    index = 1
    while index < len(breaks) - 1:
        before, at, after = breaks[index - 1 : index + 2]
        # Two neighbouring breaks bracket one interval that holds the change.
        if after == at + 1 and index + 2 < len(breaks):
            point = crossing((before, at), (after, breaks[index + 2]))
            if point is not None:
                changes.append((at, after, point))
                index += 2
                continue
        # A lone break sits just next to the change, on either side.
        point = crossing((before, at - 1), (at + 1, after))
        changes.append((at - 1, at + 1, float(draws[at]) if point is None else point))
        index += 1
    return changes


def change_intervals(draws: np.ndarray, series: Series) -> list[tuple[float, float]]:
    """The stretch of grid, one interval or two, that holds each change of rate."""
    return [
        (float(draws[low]), float(draws[high]))
        for low, high, _ in _changes(draws, series)
    ]


def band_edges(draws: np.ndarray, series: Series, min_width: float = 1.0) -> np.ndarray:
    """Draw amounts where the rate on the next unit changes.

    Each lies where the lines either side of its change cross (``_changes``),
    which places it far closer than the grid's spacing. Edges closer together
    than ``min_width`` merge.
    """
    edges = [
        float(draws[0]),
        float(draws[-1]),
        *(point for _, _, point in _changes(draws, series)),
    ]
    ordered = np.unique(np.round(edges, 2))
    separated = [ordered[0]]
    for edge in ordered[1:-1]:
        if edge - separated[-1] >= min_width:
            separated.append(edge)
    separated.append(ordered[-1])
    return np.unique(separated)


def _index_of(draws: np.ndarray, draw: float) -> int:
    return int(np.argmin(np.abs(draws - draw)))


# Jumps ----------------------------------------------------------------------


@dataclass(frozen=True)
class JumpRule:
    """When a move inside an interval of draws counts as a jump.

    A tax or benefit jumps inside an interval, rather than phasing in or out,
    when it moves faster than ``rate`` per unit of draw plus ``minimum``, or
    when a window of intervals moves ``minimum`` beyond what the rates on
    either side of the window give. The grid tests windows of
    ``grid_windows`` intervals, so a jump beside another can't hide behind its
    neighbour's rate. A closer look cuts an interval into ``subdivisions``
    pieces and tests windows of ``refined_windows``, since two jumps rarely
    sit side by side inside one. A neighbour gives a rate only if it is
    ``neighbour_min_width`` wide and ``neighbour_min_share`` of the window's
    width, since rounding swamps the rate of a sliver; up to
    ``neighbour_reach`` intervals out, narrower ones are passed over.
    """

    rate: float
    minimum: float
    subdivisions: int = 24
    grid_windows: tuple[int, ...] = (1, 2)
    refined_windows: tuple[int, ...] = (1,)
    neighbour_min_width: float = 5.0
    neighbour_min_share: float = 0.25
    neighbour_reach: int = 3


def _neighbours(
    width: np.ndarray,
    size: int,
    rule: JumpRule,
    passed_over: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For the window of ``size`` intervals starting at each interval: its
    width, and the nearest interval on each side wide enough to give a rate
    and not ``passed_over`` (-1 where none is)."""
    count = len(width) - size + 1
    if count <= 0:
        none = np.zeros(0, dtype=int)
        return np.zeros(0), none, none
    window = np.convolve(width, np.ones(size), mode="valid")
    need = np.maximum(rule.neighbour_min_width, rule.neighbour_min_share * window)
    usable = width if passed_over is None else np.where(passed_over, -1.0, width)
    left = np.full(count, -1)
    right = np.full(count, -1)
    for start in range(count):
        for j in range(start - 1, max(start - 1 - rule.neighbour_reach, -1), -1):
            if usable[j] >= need[start]:
                left[start] = j
                break
        for j in range(
            start + size, min(start + size + rule.neighbour_reach, len(width))
        ):
            if usable[j] >= need[start]:
                right[start] = j
                break
    return window, left, right


def _window_scores(
    change: np.ndarray,
    width: np.ndarray,
    size: int,
    neighbours: tuple[np.ndarray, np.ndarray, np.ndarray],
    minimum: float,
) -> np.ndarray:
    """How far each interval's window moves beyond what the rates on either
    side of it give; -inf where no neighbour gives a rate."""
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
    beyond = np.fmax(moved - high, low - moved) - minimum
    beyond = np.where(np.isnan(beyond), -np.inf, beyond)
    for offset in range(size):
        stop = offset + len(beyond)
        scores[offset:stop] = np.maximum(scores[offset:stop], beyond)
    return scores


def jump_scores(
    draws: np.ndarray,
    moving: Sequence[np.ndarray],
    rule: JumpRule,
    windows: tuple[int, ...],
    changes_of_state: Sequence[np.ndarray] = (),
    passed_over: np.ndarray | None = None,
) -> np.ndarray:
    """How far each interval's largest move exceeds what a phase-out could do.

    A score of zero or more marks a jump in one of the ``moving`` series,
    found two ways. A series can move faster than any phase-out. Or a window
    of intervals can move beyond what the rates on either side of it give: a
    change of rate inside the window leaves its move between those rates, so
    only a jump takes it more than ``rule.minimum`` beyond them, however small
    the jump is beside the window's width. Where one of the
    ``changes_of_state`` (true or false at each draw) changes, the score is at
    least zero. Intervals ``passed_over`` give no window its rates.
    """
    width = np.diff(draws)
    scores = np.full(len(width), -np.inf)
    if not len(width):
        return scores
    allowed = rule.rate * width + rule.minimum
    neighbours = {size: _neighbours(width, size, rule, passed_over) for size in windows}
    for values in moving:
        change = np.diff(values)
        scores = np.maximum(scores, np.abs(change) - allowed)
        for size, around in neighbours.items():
            scores = np.maximum(
                scores, _window_scores(change, width, size, around, rule.minimum)
            )
    for state in changes_of_state:
        changed = state[:-1] != state[1:]
        scores = np.where(changed, np.maximum(scores, 0.0), scores)
    return scores


def cliff_intervals(
    draws: np.ndarray,
    moving: Sequence[np.ndarray],
    rule: JumpRule,
    changes_of_state: Sequence[np.ndarray] = (),
) -> list[tuple[float, float]]:
    """Grid intervals that may hold a jump or a change of state; a closer look
    inside each settles which do."""
    scores = jump_scores(draws, moving, rule, rule.grid_windows, changes_of_state)
    return [
        (float(draws[i]), float(draws[i + 1])) for i in np.flatnonzero(scores >= 0.0)
    ]


def subdivide(intervals: Sequence[tuple[float, float]], pieces: int) -> np.ndarray:
    """The points that cut each interval into ``pieces`` equal pieces."""
    steps = np.arange(1, pieces) / pieces
    points = [low + steps * (high - low) for low, high in intervals]
    return np.concatenate(points) if points else np.zeros(0)


def refined_intervals(
    draws: np.ndarray,
    series: Series,
    moving: Sequence[np.ndarray],
    rule: JumpRule,
    changes_of_state: Sequence[np.ndarray] = (),
    reaching_zero: Sequence[np.ndarray] = (),
    zero: float = 0.005,
    beside: int = 0,
) -> list[tuple[float, float]]:
    """Grid intervals a second run cuts into pieces for a closer look.

    Those that may hold a jump or a change of state (``cliff_intervals``); the
    one or two that hold each change of rate, since a jump beside one can move
    its interval no further than a change of rate could, with ``beside`` more
    on each side; and those where one of the ``reaching_zero`` series falls to
    zero, since a phase-out that ends in a small cliff looks from the grid
    like one that runs on to zero.

    A series that rises in small steps, such as tax on an allowance rounded
    to the pound, can sit on a straight line at every grid draw when the grid's
    spacing is a whole number of steps; the pieces of the intervals beside a
    change, a 24th of the spacing, show its steps.
    """
    chosen = set(cliff_intervals(draws, moving, rule, changes_of_state))
    for low, high in change_intervals(draws, series):
        first = max(int(np.searchsorted(draws, low)) - beside, 0)
        last = min(int(np.searchsorted(draws, high)) + beside, len(draws) - 1)
        for i in range(first, last):
            chosen.add((float(draws[i]), float(draws[i + 1])))
    for values in reaching_zero:
        for i in np.flatnonzero((values[:-1] > zero) & (values[1:] <= zero)):
            chosen.add((float(draws[i]), float(draws[i + 1])))
    return sorted(chosen)


def stretches(intervals: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Intervals that touch, joined, so a jump in one can't pass for a
    neighbour's rate in the other."""
    joined: list[tuple[float, float]] = []
    for low, high in intervals:
        if joined and joined[-1][1] == low:
            joined[-1] = (joined[-1][0], high)
        else:
            joined.append((low, high))
    return joined


def locate_jumps(
    draws: np.ndarray,
    moving: Sequence[np.ndarray],
    low: float,
    high: float,
    rule: JumpRule,
) -> list[tuple[float, float]]:
    """The neighbouring draw amounts between which each jump of a ``moving``
    series inside ``low``-``high`` falls; none if a closer look finds only
    changes of rate."""
    inside = np.flatnonzero((draws >= low) & (draws <= high))
    # One more point on each side gives the outermost pieces a neighbour.
    span = np.arange(max(inside[0] - 1, 0), min(inside[-1] + 2, len(draws)))
    part = draws[span]
    part_moving = [values[span] for values in moving]
    # A piece holding a jump gives its neighbours a rate no phase-out has, so
    # a piece beside it, holding only a change of rate, can look like a jump
    # too. So the piece that moves furthest beyond its neighbours is taken
    # first, and the rest are scored again without it as a neighbour, until
    # none is left that moves beyond its neighbours.
    jumps = np.zeros(len(part) - 1, dtype=bool)
    while True:
        scores = jump_scores(
            part, part_moving, rule, rule.refined_windows, passed_over=jumps
        )
        scores[jumps] = -np.inf
        strongest = int(np.argmax(scores))
        if scores[strongest] < 0.0:
            break
        jumps[strongest] = True
    return [
        (float(part[i]), float(part[i + 1]))
        for i in np.flatnonzero(jumps)
        if low <= part[i] and part[i + 1] <= high
    ]


def crowded_jumps(
    draws: np.ndarray,
    edges: Sequence[float],
    jumps: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Stretches of ``draws`` to look at more closely: around each located
    jump whose band on either side holds fewer evaluated draws than
    pin_changes needs to judge the line a series follows there.

    A change of rate a piece or two from a jump leaves the pieces between
    them with a rate that neither neighbour giving a rate has, so
    locate_jumps can take them for jumps too, and pin_changes then finds no
    line beside the jump or them. Each stretch runs through the jump's own
    piece and, on each such side, to the interval just past the band's far
    edge, since the change there can lie on either side of that edge.
    Stretches that touch or overlap are joined.
    """
    edges = sorted(float(edge) for edge in edges)
    last = len(draws) - 1
    found: list[tuple[float, float]] = []
    for low, high in sorted(jumps):
        far_left = max((edge for edge in edges if edge < low), default=draws[0])
        far_right = min((edge for edge in edges if edge > high), default=draws[-1])
        start, stop = low, high
        if np.count_nonzero((draws > far_left) & (draws < low)) < _JUDGED:
            start = float(draws[max(int(np.searchsorted(draws, far_left)) - 1, 0)])
        if np.count_nonzero((draws > high) & (draws < far_right)) < _JUDGED:
            after = int(np.searchsorted(draws, far_right, side="right"))
            stop = float(draws[min(after, last)])
        if (start, stop) != (low, high):
            found.append((start, stop))
    joined: list[tuple[float, float]] = []
    for start, stop in sorted(found):
        if joined and start <= joined[-1][1]:
            joined[-1] = (joined[-1][0], max(joined[-1][1], stop))
        else:
            joined.append((start, stop))
    return joined


def closer_look(
    draws: np.ndarray,
    stretches: Sequence[tuple[float, float]],
    min_width: float,
    most: int,
) -> np.ndarray:
    """The points, to the cent, that cut every interval of ``draws`` inside
    ``stretches`` into up to ``most`` equal pieces. Rounding a point moves it
    half a cent at most, so pieces a cent wider than ``min_width`` leave
    none narrower than it once rounded (locate_jumps takes rates only from
    pieces that wide)."""
    points = []
    for start, stop in stretches:
        inside = draws[(draws >= start) & (draws <= stop)]
        for low, high in zip(inside, inside[1:], strict=False):
            pieces = int(min(most, (high - low) // (min_width + CENT)))
            if pieces > 1:
                points.append(low + np.arange(1, pieces) / pieces * (high - low))
    return np.round(np.concatenate(points), 2) if points else np.zeros(0)


def relocated_jumps(
    draws: np.ndarray,
    moving: Sequence[np.ndarray],
    jumps: Sequence[tuple[float, float]],
    stretches: Sequence[tuple[float, float]],
    rule: JumpRule,
) -> list[tuple[float, float]]:
    """``jumps`` outside ``stretches``, and the ones locate_jumps finds inside
    each stretch on ``draws``, which now cut it more finely."""
    kept = [
        (low, high)
        for low, high in jumps
        if not any(start <= low and high <= stop for start, stop in stretches)
    ]
    found = [
        jump
        for start, stop in stretches
        for jump in locate_jumps(draws, moving, start, stop, rule)
    ]
    return sorted({*kept, *found})


def edges_between_jumps(
    draws: np.ndarray,
    series: Series,
    jumps: Sequence[tuple[float, float]],
    min_width: float,
) -> list[float]:
    """Band edges: each located jump's ends, and where the rate changes in
    each stretch between jumps, from that stretch alone, so no line through a
    jump moves the edge of a change of rate beside it."""
    edges = {float(draws[0]), float(draws[-1])}
    start = 0
    for low, high in [*sorted(jumps), (None, None)]:
        stop = len(draws) - 1 if low is None else _index_of(draws, low)
        if stop > start:
            part = slice(start, stop + 1)
            edges.update(
                float(edge)
                for edge in band_edges(
                    draws[part],
                    [(values[part], tolerance) for values, tolerance in series],
                    min_width=min_width,
                )
            )
        if low is not None:
            edges.update((low, high))
            start = _index_of(draws, high)
    return sorted(edges)


def unevaluated(
    draws: np.ndarray, edges: Sequence[float], distance: float
) -> np.ndarray:
    """Edges more than ``distance`` from every evaluated draw."""
    points = np.asarray(edges, dtype=float)
    at = np.clip(np.searchsorted(draws, points), 1, len(draws) - 1)
    nearest = np.minimum(np.abs(draws[at] - points), np.abs(draws[at - 1] - points))
    return points[nearest > distance]


def band_pieces(
    draws: np.ndarray,
    edges: Sequence[float],
    jumps: Sequence[tuple[float, float]],
    same_rates: Callable[[tuple[int, int], tuple[int, int]], bool],
) -> list[tuple[int, int, bool]]:
    """Each band as the indices of its ends on ``draws`` and whether it holds
    a located jump: each jump on its own, and neighbours that share their
    rates joined."""
    indices = sorted({_index_of(draws, edge) for edge in edges})
    if len(indices) < 2:
        return []
    jump_starts = {_index_of(draws, low) for low, _ in jumps}
    pieces = [
        (low, high, low in jump_starts)
        for low, high in zip(indices, indices[1:], strict=False)
    ]
    joined = [pieces[0]]
    for low, high, jump in pieces[1:]:
        start, end, last_jump = joined[-1]
        if not jump and not last_jump and same_rates((start, end), (low, high)):
            joined[-1] = (start, high, False)
        else:
            joined.append((low, high, jump))
    return joined


# To the cent ----------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    """A straight line through one point of a series at a given rate."""

    at: float
    value: float
    rate: float

    def __call__(self, draws: np.ndarray | float) -> np.ndarray:
        return self.value + self.rate * (np.asarray(draws, dtype=float) - self.at)


def side_line(
    draws: np.ndarray, values: np.ndarray, inside: np.ndarray, tolerance: float
) -> tuple[Line | None, str]:
    """The straight line a series follows across one band, if one does.

    ``inside`` holds the indices of the band's evaluated draws, the one nearest
    the change first. The point nearest each end of the band is left out,
    since an edge placed where lines cross can sit a little way from its
    change, on the far side of a point. The line fits the rest by least
    squares, which averages out rounding to the cent, and it is "straight"
    when all of them lie within ``tolerance`` of it; with fewer than three
    the band is "short", and otherwise "uneven".
    """
    points = np.asarray(inside, dtype=int)[1:-1]
    if len(points) < _JUDGED - 2:
        return None, "short"
    at = draws[points]
    middle = float(at.mean())
    rate, value = np.polyfit(at - middle, values[points], 1)
    line = Line(middle, float(value), float(rate))
    if np.all(np.abs(values[points] - line(at)) <= tolerance):
        return line, "straight"
    return None, "uneven"


# A band needs this many evaluated draws for its line to be judged: the
# nearest each end left out, and three to show a straight line.
_JUDGED = 5


def _cents(draw: float) -> int:
    return int(round(draw * 100))


@dataclass
class _Search:
    """A draw on each side of where a test of a series' value first holds."""

    low: float
    high: float
    holds: Callable[[np.ndarray, np.ndarray], np.ndarray]


def _first_of(indices: np.ndarray, flags: np.ndarray) -> int | None:
    """The first of ``indices`` whose flag is set, if any."""
    found = np.flatnonzero(flags)
    return int(indices[found[0]]) if len(found) else None


def _first_bracket(
    draws: np.ndarray, values: np.ndarray, order: np.ndarray, holds: Callable
) -> tuple[int, int] | None:
    """Along ``order``, the index before the first where ``holds``, and that one."""
    if len(order) < 2:
        return None
    flags = holds(draws[order], values[order])
    if flags[0] or not flags.any():
        return None
    k = int(np.argmax(flags))
    return int(order[k - 1]), int(order[k])


def _narrow(
    searches: list[_Search],
    evaluate: Callable[[np.ndarray], np.ndarray],
    rounds: int,
    first: np.ndarray,
    after_first: Callable[[dict[int, float]], list[_Search]] | None = None,
) -> dict[int, float]:
    """Narrow every search to one cent in ``rounds`` calls of ``evaluate``,
    all searches at once, with ``first`` evaluated in the first call.
    ``after_first`` may then replace the searches, given every value so far.

    Each call cuts a search's bracket of n cents into n ** (1 / rounds left)
    pieces, rounded up, so the last call leaves one cent. Returns each value
    evaluated, by draw in cents.
    """
    known: dict[int, float] = {}
    for left in range(rounds, 0, -1):
        asks = []
        for search in searches:
            low, high = _cents(search.low), _cents(search.high)
            count = high - low
            if count > 1:
                pieces = min(count, math.ceil(count ** (1.0 / left) - 1e-9))
                cuts = np.unique(
                    np.round(np.linspace(0, count, pieces + 1)[1:-1]).astype(int)
                )
                asks.append((low + cuts) / 100.0)
        extra = first if left == rounds else np.zeros(0)
        if not asks and not len(extra):
            break
        points = np.unique(np.round(np.concatenate([*asks, extra]), 2))
        values = np.asarray(evaluate(points), dtype=float)
        known.update(zip((_cents(d) for d in points), values.tolist(), strict=True))
        for search in searches:
            inside = (points > search.low) & (points < search.high)
            if not inside.any():
                continue
            held = search.holds(points[inside], values[inside])
            if held.any():
                search.high = float(points[inside][int(np.argmax(held))])
            before = points[inside][~held & (points[inside] < search.high)]
            if len(before):
                search.low = float(before.max())
        if left == rounds and after_first is not None:
            searches = after_first(known)
    return known


@dataclass
class _Change:
    """A change in a series between two bands, to place to the cent."""

    own: list[float]  # the edges it replaces: one, or a located jump's two
    low: float
    high: float
    left: Line | None
    right: Line | None
    located: tuple[float, float] | None
    # Each side's band's draws, as indices, the one nearest the change first.
    left_near: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    right_near: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    from_left: _Search | None = None
    from_right: _Search | None = None
    crossing: float | None = None


def pin_changes(
    draws: np.ndarray,
    values: np.ndarray,
    edges: Sequence[float],
    jumps: Sequence[tuple[float, float]],
    evaluate: Callable[[np.ndarray], np.ndarray],
    *,
    tolerance: float,
    step_min: float,
    min_width: float,
    rounds: int = 3,
    also: np.ndarray | None = None,
    others_moving: Sequence[np.ndarray] = (),
    straight_within: float | None = None,
) -> tuple[list[float], list[tuple[float, float]], np.ndarray]:
    """Band edges and jumps of one series, each placed to the cent.

    ``edges`` and ``jumps`` come from edges_between_jumps and locate_jumps on
    ``draws``, where the series takes ``values``. At each located jump, and at
    each edge where the series changes rate, it takes the straight line the
    series follows across the band on each side (``side_line``) and finds the
    last cent the left one holds to within ``tolerance`` and the first cent
    the right one does, at most ``rounds`` calls of ``evaluate`` in all, each
    for every change at once (``also`` goes with the first). Then:

    - Where a line ends and the series moves ``step_min`` or more in the next
      cent, it jumps there: that cent becomes a jump band.
    - Where both lines are straight and neither ends in a jump, the change is a
      kink and keeps its edge where the lines cross.
    - Where only one side is straight and the other moves in small steps (the
      tax a whole-pound rounding gives, say), the edge goes on the straight
      line's last cent, so neither band takes in the other's pounds. A side
      judged straight on the grid stays straight only if its line also holds
      at every draw the first round evaluates on that side, since a grid can
      sample such steps at the same point of each.

    A located jump with no straight line on either side keeps its piece. An
    edge left within ``min_width`` of a placed one goes, and so does one with
    no straight line on either side where the series' rate across it changes
    by less than KINK_MIN_RATE_CHANGE and none of ``others_moving`` (the other
    series, on ``draws``) moves: in a stretch the series crosses unevenly, a
    grid point can pass for a change.

    With ``straight_within``, any band other than a jump's whose evaluated
    draws (``draws`` and every one the searches ran) stray further than that
    from the line between its ends takes the edges band_edges finds in it,
    evaluated in one more call: a piece the grid took for a jump can hold a
    change of rate beside the jump, which its own edges no longer mark once
    the jump is placed. So ``evaluate`` runs ``rounds`` + 1 times at most.

    Returns the edges, the jumps and the draws the result rests on that
    ``draws`` lacks.
    """
    edges = sorted(float(edge) for edge in edges)
    jump_ends = {end for jump in jumps for end in jump}

    def bands_beside(low: float, high: float) -> tuple:
        """The line on each side of a change, its state, and the indices of
        each band's draws, nearest the change first. A band too short to
        judge takes in the one beyond it, up to two, since an edge placed
        on a grid point can split a stretch the series crosses unevenly."""
        lower = [edge for edge in edges if edge < low][::-1] or [float(draws[0])]
        upper = [edge for edge in edges if edge > high] or [float(draws[-1])]
        for reach in range(min(3, len(lower))):
            left_inside = np.flatnonzero((draws > lower[reach]) & (draws < low))[::-1]
            if len(left_inside) >= _JUDGED:
                break
        for reach in range(min(3, len(upper))):
            right_inside = np.flatnonzero((draws > high) & (draws < upper[reach]))
            if len(right_inside) >= _JUDGED:
                break
        left, left_state = side_line(draws, values, left_inside, tolerance)
        right, right_state = side_line(draws, values, right_inside, tolerance)
        return left, right, left_state, right_state, left_inside, right_inside

    changes: list[_Change] = []
    for low, high in sorted(jumps):
        left, right, _, _, left_inside, right_inside = bands_beside(low, high)
        if left is not None or right is not None:
            changes.append(
                _Change(
                    [low, high],
                    low,
                    high,
                    left,
                    right,
                    (low, high),
                    left_inside,
                    right_inside,
                )
            )
    for edge in edges[1:-1]:
        if edge in jump_ends:
            continue
        left, right, left_state, right_state, left_inside, right_inside = bands_beside(
            edge, edge
        )
        if left is not None and right is not None:
            moves = (
                abs(left.rate - right.rate) >= KINK_MIN_RATE_CHANGE
                or abs(float(left(edge)) - float(right(edge))) > tolerance
            )
            if not moves:
                continue
        elif not (
            (left is not None and right_state == "uneven")
            or (right is not None and left_state == "uneven")
        ):
            continue
        changes.append(
            _Change(
                [edge],
                edge,
                edge,
                left,
                right,
                None,
                left_inside,
                right_inside,
            )
        )

    def on(line: Line, at: np.ndarray, value: np.ndarray) -> np.ndarray:
        return np.abs(value - line(at)) <= tolerance

    searches: list[_Search] = []
    for change in changes:
        left, right = change.left, change.right
        if left is not None:
            # Holds once the series has left the left line (and, with a line on
            # the right too, has stopped sitting on both).
            def off_left(at, value, left=left, right=right):
                held = ~on(left, at, value)
                return held | on(right, at, value) if right is not None else held

            # The search starts from the band's draw nearest the change that
            # sits on the left line alone; nearer, both lines can hold.
            start = _first_of(
                change.left_near,
                ~off_left(draws[change.left_near], values[change.left_near]),
            )
            order = np.arange(start, len(draws)) if start is not None else []
            bracket = _first_bracket(draws, values, np.asarray(order), off_left)
            if bracket is not None:
                change.from_left = _Search(
                    float(draws[bracket[0]]), float(draws[bracket[1]]), off_left
                )
                searches.append(change.from_left)
        if right is not None:

            def on_right(at, value, left=left, right=right):
                held = on(right, at, value)
                return held & ~on(left, at, value) if left is not None else held

            start = _first_of(
                change.right_near,
                on_right(draws[change.right_near], values[change.right_near]),
            )
            order = np.arange(start, -1, -1) if start is not None else []
            bracket = _first_bracket(
                draws, values, np.asarray(order), lambda a, v, f=on_right: ~f(a, v)
            )
            if bracket is not None:
                change.from_right = _Search(
                    float(draws[bracket[1]]), float(draws[bracket[0]]), on_right
                )
                searches.append(change.from_right)

    # Where both lines are straight, the change may be a kink, whose edge
    # goes where they cross; the first round evaluates that draw.
    crossings = []
    for change in changes:
        left, right = change.left, change.right
        if left is not None and right is not None and abs(left.rate - right.rate) > 0:
            at = (
                right.value - left.value + left.rate * left.at - right.rate * right.at
            ) / (left.rate - right.rate)
            if change.low - 1.0 <= at <= change.high + 1.0 or (
                change.from_left is not None
                and change.from_right is not None
                and change.from_left.low <= at <= change.from_right.high
            ):
                change.crossing = round(float(at), 2)
                crossings.append(change.crossing)
    first = np.concatenate(
        [np.zeros(0) if also is None else np.asarray(also, dtype=float), crossings]
    )
    base = {_cents(d): float(v) for d, v in zip(draws, values, strict=True)}

    def rejudged(known: dict[int, float]) -> list[_Search]:
        """The searches once each side's line is judged again at the first
        round's draws too. A grid can sample a series that moves in small
        steps at the same point of each step, so that it looks straight
        there; between those draws it strays from the line and comes back.
        A line the series leaves and then comes back to, within half the
        tolerance, becomes no line, and the other side's search then looks
        for where its own line alone stops holding. (Where a jump comes
        before the lines cross, the left line fails so; the right one alone
        still finds the jump.)"""
        every = {**base, **known}
        cents = np.array(sorted(every))
        at_all = cents / 100.0
        value_all = np.array([every[cent] for cent in cents])

        def comes_back(line: Line, points: np.ndarray, at: np.ndarray) -> bool:
            gap = np.abs(at - line(points))
            off = gap > tolerance
            if not off.any():
                return False
            return bool(np.any(gap[int(np.argmax(off)) :] <= tolerance / 2))

        for change in changes:
            if change.from_left is None and change.from_right is None:
                continue
            # From the draw furthest from the change that each line was
            # fitted to, so the series starts on it.
            low = (
                float(draws[change.left_near[-2]])
                if len(change.left_near) > 1
                else float(draws[0])
            )
            high = (
                float(draws[change.right_near[-2]])
                if len(change.right_near) > 1
                else float(draws[-1])
            )
            span = (at_all >= low) & (at_all <= high)
            points, at = at_all[span], value_all[span]
            left_fails = change.left is not None and comes_back(change.left, points, at)
            right_fails = change.right is not None and comes_back(
                change.right, points[::-1], at[::-1]
            )
            if not (left_fails or right_fails):
                continue
            if left_fails:
                change.left = None
            if right_fails:
                change.right = None
            change.from_left = change.from_right = None
            change.crossing = None
            if change.left is not None and change.right is None:
                line = change.left
                start = float(draws[change.left_near[0]])
                order = np.flatnonzero(at_all >= start)
                flags = ~on(line, at_all[order], value_all[order])
                if flags.any() and not flags[0]:
                    k = int(np.argmax(flags))
                    change.from_left = _Search(
                        float(at_all[order[k - 1]]),
                        float(at_all[order[k]]),
                        lambda a, v, line=line: ~on(line, a, v),
                    )
            elif change.right is not None and change.left is None:
                line = change.right
                start = float(draws[change.right_near[0]])
                order = np.flatnonzero(at_all <= start)[::-1]
                flags = ~on(line, at_all[order], value_all[order])
                if flags.any() and not flags[0]:
                    k = int(np.argmax(flags))
                    change.from_right = _Search(
                        float(at_all[order[k]]),
                        float(at_all[order[k - 1]]),
                        lambda a, v, line=line: on(line, a, v),
                    )
        return [
            search
            for change in changes
            for search in (change.from_left, change.from_right)
            if search is not None
        ]

    known = _narrow(searches, evaluate, rounds, first, after_first=rejudged)

    def value_at(draw: float) -> float:
        cents = _cents(draw)
        return known[cents] if cents in known else base[cents]

    placed_edges: set[float] = set()
    placed_jumps: set[tuple[float, float]] = set()
    replaced: set[float] = set()
    kept_jumps = list(jumps)
    for change in changes:
        left, right = change.left, change.right
        from_left, from_right = change.from_left, change.from_right
        if from_left is None and from_right is None:
            continue
        found_edges: list[float] = []
        found_jumps: list[tuple[float, float]] = []
        step_left = step_right = 0.0
        if from_left is not None:
            step_left = value_at(from_left.high) - float(left(from_left.high))
        if from_right is not None:
            step_right = float(right(from_right.low)) - value_at(from_right.low)
        jumps_left = from_left is not None and abs(step_left) >= step_min
        jumps_right = from_right is not None and abs(step_right) >= step_min
        if from_left is not None and from_right is not None:
            if jumps_left:
                found_jumps.append((from_left.low, from_left.high))
                if not on(
                    right, np.array(from_left.high), np.array(value_at(from_left.high))
                ):
                    found_edges.append(from_right.high)
            if jumps_right:
                found_jumps.append((from_right.low, from_right.high))
                if not on(
                    left, np.array(from_right.low), np.array(value_at(from_right.low))
                ):
                    found_edges.append(from_left.low)
            if not (jumps_left or jumps_right):
                # A kink: the lines cross between the two ends.
                own = change.own[0] if change.located is None else None
                for edge in (change.crossing, own, from_left.low):
                    if edge is not None and from_left.low <= edge <= from_right.high:
                        found_edges.append(edge)
                        break
        elif from_left is not None:
            if jumps_left:
                found_jumps.append((from_left.low, from_left.high))
            else:
                found_edges.append(from_left.low)
        else:
            if jumps_right:
                found_jumps.append((from_right.low, from_right.high))
            else:
                found_edges.append(from_right.high)
        replaced.update(change.own)
        if change.located is not None:
            kept_jumps.remove(change.located)
        placed_edges.update(found_edges)
        placed_jumps.update(found_jumps)

    fixed = placed_edges | {end for jump in placed_jumps for end in jump}
    fixed |= {end for jump in kept_jumps for end in jump}
    fixed |= {float(draws[0]), float(draws[-1])}
    others = [
        edge
        for edge in edges
        if edge not in replaced
        and edge not in fixed
        and all(abs(edge - placed) >= min_width for placed in fixed)
    ]
    final_edges = _without_uneven_edges(
        sorted({*fixed, *others}),
        fixed,
        draws,
        values,
        value_at,
        others_moving,
        tolerance,
    )
    final_jumps = sorted({*kept_jumps, *placed_jumps})
    if straight_within is not None:
        every = {**base, **known}
        cents = np.array(sorted(every))
        bent = _edges_in_bent_bands(
            final_edges,
            final_jumps,
            cents / 100.0,
            np.array([every[cent] for cent in cents]),
            straight_within,
            min_width,
        )
        asks = np.array(sorted({edge for edge in bent if _cents(edge) not in every}))
        if len(asks):
            values_asked = np.asarray(evaluate(asks), dtype=float)
            known.update(zip(map(_cents, asks), values_asked.tolist(), strict=True))
        final_edges = sorted({*final_edges, *bent})
    rests_on = {*final_edges}
    for search in searches:
        rests_on.update((search.low, search.high))
    have = {_cents(d) for d in draws}
    missing = sorted(d for d in rests_on if _cents(d) not in have)
    return final_edges, final_jumps, np.array(missing, dtype=float)


def _edges_in_bent_bands(
    edges: list[float],
    jumps: list[tuple[float, float]],
    points: np.ndarray,
    values: np.ndarray,
    tolerance: float,
    min_width: float,
) -> list[float]:
    """Changes of rate inside each band other than a jump's that the series,
    at ``points``, shows is not straight to within ``tolerance``
    (pin_changes)."""
    jump_bands = {(_cents(low), _cents(high)) for low, high in jumps}
    found: list[float] = []
    for low, high in zip(edges, edges[1:], strict=False):
        if (_cents(low), _cents(high)) in jump_bands:
            continue
        inside = np.flatnonzero(
            (points >= low - CENT / 2) & (points <= high + CENT / 2)
        )
        if len(inside) < 3 or _fits(
            points[inside], values[inside], (0, len(inside) - 1), tolerance
        ):
            continue
        part = points[inside]
        found.extend(
            float(edge)
            for edge in band_edges(
                part, [(values[inside], tolerance)], min_width=min_width
            )[1:-1]
            if edge - low >= min_width and high - edge >= min_width
        )
    return found


def _without_uneven_edges(
    edges: list[float],
    fixed: set[float],
    draws: np.ndarray,
    values: np.ndarray,
    value_at: Callable[[float], float],
    others_moving: Sequence[np.ndarray],
    tolerance: float,
) -> list[float]:
    """Edges less those inside a stretch the series crosses unevenly that
    mark no change (pin_changes)."""
    edges = list(edges)
    dropped = True
    while dropped:
        dropped = False
        for k in range(1, len(edges) - 1):
            before, edge, after = edges[k - 1 : k + 2]
            if edge in fixed:
                continue
            left_inside = np.flatnonzero((draws > before) & (draws < edge))[::-1]
            right_inside = np.flatnonzero((draws > edge) & (draws < after))
            if (
                side_line(draws, values, left_inside, tolerance)[1] == "straight"
                or side_line(draws, values, right_inside, tolerance)[1] == "straight"
            ):
                continue
            rate_left = (value_at(edge) - value_at(before)) / (edge - before)
            rate_right = (value_at(after) - value_at(edge)) / (after - edge)
            if abs(rate_left - rate_right) >= KINK_MIN_RATE_CHANGE:
                continue
            around = (draws >= before) & (draws <= after)
            if any(np.ptp(other[around]) > tolerance for other in others_moving):
                continue
            del edges[k]
            dropped = True
            break
    return edges
