"""Where the rate on the next unit of a draw changes.

The one-year drawdown calculators evaluate a year's result on a grid of draw
amounts. These helpers find the draw amounts where a straight line stops
describing each series (tax, benefits) and place each change of rate where
the lines on either side cross, so a coarse grid still gives band edges far
closer than its spacing. On a piecewise-linear series whose changes of rate
sit three or more grid intervals apart, each edge lands within a cent of the
change (tests/test_drawdown_bands.py).
"""

from __future__ import annotations

import numpy as np

Series = list[tuple[np.ndarray, float]]

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
