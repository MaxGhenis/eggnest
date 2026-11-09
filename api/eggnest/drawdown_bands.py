"""Where the rate on the next unit of a draw changes.

The one-year drawdown calculators evaluate a year's result on a grid of draw
amounts. These helpers find the draw amounts where a straight line stops
describing each series (tax, benefits) and place each change of rate on the
pound or dollar, so a coarse grid still gives exact band edges for rules that
are piecewise linear.
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


def band_edges(draws: np.ndarray, series: Series, min_width: float = 1.0) -> np.ndarray:
    """Draw amounts, to the cent, where the rate on the next unit changes.

    A rate changes between grid points, and the interval holding the change
    mixes both rates. So the edge comes from where the clean lines on either
    side cross, which puts it on the pound or dollar while the grid stays
    coarse. Edges closer together than ``min_width`` merge.
    """
    breaks = band_breaks(draws, series)

    def crossing(left: tuple[int, int], right: tuple[int, int]) -> float | None:
        for values, _ in series:
            point = crossing_point(draws, values, left, right)
            if point is not None:
                return point
        return None

    edges = [float(draws[breaks[0]]), float(draws[breaks[-1]])]
    index = 1
    while index < len(breaks) - 1:
        before, at, after = breaks[index - 1 : index + 2]
        # Two neighbouring breaks bracket one interval that holds the change.
        if after == at + 1 and index + 2 < len(breaks):
            point = crossing((before, at), (after, breaks[index + 2]))
            if point is not None:
                edges.append(point)
                index += 2
                continue
        # A lone break sits just next to the change, on either side.
        point = crossing((before, at - 1), (at + 1, after))
        edges.append(float(draws[at]) if point is None else point)
        index += 1

    ordered = np.unique(np.round(edges, 2))
    separated = [ordered[0]]
    for edge in ordered[1:-1]:
        if edge - separated[-1] >= min_width:
            separated.append(edge)
    separated.append(ordered[-1])
    return np.unique(separated)
