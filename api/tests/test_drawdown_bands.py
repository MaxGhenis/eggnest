"""Where the rate on the next unit of a draw changes (drawdown_bands).

Both one-year drawdown calculators place band edges with these helpers.

Invariants, on continuous piecewise-linear series:

- band_edges places an edge within a cent of each change of rate when changes
  sit at least three grid intervals apart, on an even grid or on the
  calculators' fine-then-coarse grids. (It can also leave an edge on a break
  where nothing changes; the calculators join the bands either side.)
- Each crossing comes from lines that fit their points within the series'
  tolerance and stop short of the break at their far end, so two changes of
  rate less than three intervals apart (one inside the other's span) still
  each get their own edge.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from eggnest.drawdown_bands import band_edges


def _line(draws: np.ndarray, kinks: list[float], rates: list[float]) -> np.ndarray:
    """A continuous series through 0 whose rate is rates[i] after kinks[i - 1]."""
    edges = np.concatenate([[0.0], kinks, [draws[-1]]])
    pieces = np.clip(draws[:, None] - edges[:-1], 0.0, np.diff(edges))
    return pieces @ np.asarray(rates)


def _grid(fine_top: float, fine_step: float, top: float, step: float) -> np.ndarray:
    return np.unique(
        np.concatenate(
            [
                [0.0, 1.0],
                np.arange(0.0, fine_top + 1, fine_step),
                np.arange(0.0, top + 1, step),
            ]
        )
    )


def test_two_kinks_in_neighbouring_spans_are_both_placed():
    """uk-law-3: credit flat to 3,100, falls a unit per unit to 3,376, then
    tax from 4,760, on a grid of 100. The second kink sits in the span the
    first kink's crossing read, which put the first at 3,086.36."""
    draws = _grid(20_000.0, 100.0, 20_000.0, 250.0)
    credit = np.clip(276.0 - np.maximum(draws - 3_100.0, 0.0), 0.0, None)
    tax = 0.15 * np.maximum(draws - 4_760.0, 0.0)
    edges = band_edges(draws, [(tax, 1.0), (credit, 60.0)])
    assert edges == pytest.approx([0.0, 3_100.0, 3_376.0, 4_760.0, 20_000.0], abs=0.01)


def _assert_each_kink_has_an_edge(edges: np.ndarray, kinks: list[float]) -> None:
    for kink in kinks:
        assert np.min(np.abs(edges - kink)) <= 0.01, (kink, edges)


_RATES = st.sampled_from([-1.0, -0.5, -0.3, 0.0, 0.1, 0.22, 0.35, 0.5, 1.0])


@st.composite
def kinked(draw, rates_from=_RATES):
    """A grid, and a series on it whose kinks sit three or more intervals apart."""
    shape = draw(
        st.sampled_from(
            [
                (0.0, 250.0, 30_000.0, 100.0),  # even, fine
                (40_000.0, 250.0, 250_000.0, 1_000.0),  # the US sweep's grid
                (20_000.0, 250.0, 180_000.0, 1_000.0),  # the UK sweep's grid
                (0.0, 250.0, 12_000_000.0, 50_000.0),  # coarse
            ]
        )
    )
    draws = _grid(*shape)
    count = draw(st.integers(1, 4))
    kinks: list[float] = []
    index = draw(st.integers(3, 20))
    while len(kinks) < count and index < len(draws) - 4:
        low, high = draws[index], draws[index + 1]
        kinks.append(round(draw(st.floats(low, high, exclude_max=True)), 2))
        index += draw(st.integers(3, 30))
    rates = [draw(rates_from) for _ in range(len(kinks) + 1)]
    return draws, kinks, rates


@given(kinked())
def test_each_change_of_rate_gets_an_edge_within_a_cent(case):
    draws, kinks, rates = case
    real = [
        kink
        for kink, before, after in zip(kinks, rates, rates[1:], strict=False)
        if before != after
    ]
    edges = band_edges(draws, [(_line(draws, kinks, rates), 2.0)])
    assert edges[0] == 0.0 and edges[-1] == draws[-1]
    _assert_each_kink_has_an_edge(edges, real)


@given(
    kinked(st.sampled_from([-1.0, -0.5, 0.0, 0.5, 1.0])),
    st.sampled_from([1.0, 15.0, 60.0]),
)
def test_kinks_of_a_second_series_are_placed_too(case, tolerance):
    """Kinks of the series consulted second, with the first running straight.
    Each change of rate is half a unit per unit or more, so even across three
    intervals of 100 it strays from a straight line by more than 60."""
    draws, kinks, rates = case
    real = [
        kink
        for kink, before, after in zip(kinks, rates, rates[1:], strict=False)
        if before != after
    ]
    edges = band_edges(
        draws, [(0.2 * draws, 2.0), (_line(draws, kinks, rates), tolerance)]
    )
    _assert_each_kink_has_an_edge(edges, real)
