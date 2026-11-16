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

pin_changes, on a series rounded to the cent (the UK income tax's shape),
with three more evaluations at most:

- A jump that moves the series £1 or more in its penny, at a change of rate
  of 5p a pound or more, or a jump of £5 or more with none, gets a jump band
  from its last cent to its first, and no other edge lands within £1 of it.
- A change of rate with no jump gets no jump, and its edge lies within a cent
  plus the half cent of rounding over the change of rate (3p at 15p a pound).
- A series that rises in 40p steps (tax as the tapered allowance rounds up
  to the pound, ITA 2007 s.35(3)) between two straight lines gets its edges
  on the last cent before the first step and on the last step, and no edge
  or jump between them.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from eggnest.drawdown_bands import band_edges, edges_between_jumps, pin_changes


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


def _cents(values: np.ndarray) -> np.ndarray:
    return np.round(values, 2)


def _pin(series, draws: np.ndarray):
    """Edges and jumps a run would report for ``series``, and the number of
    times pin_changes asked for more values."""
    calls = []

    def evaluate(points):
        calls.append(points)
        return series(points)

    values = series(draws)
    edges = edges_between_jumps(draws, [(values, 1.0)], [], 1.0)
    edges, jumps, _ = pin_changes(
        draws,
        values,
        edges,
        [],
        evaluate,
        tolerance=0.05,
        step_min=1.0,
        min_width=1.0,
        also=draws[:0],
    )
    return edges, jumps, len(calls)


_FINE = _cents(np.linspace(0.0, 20_000.0, 481))  # a 24th of £1,000
_PER_POUND = st.sampled_from([0.0, 0.15, 0.2, 0.3, 0.4, 0.45, 0.6])


@given(
    st.floats(3_000.0, 17_000.0).map(lambda value: round(value, 2)),
    # From £1.01, so the series moves £1 or more in the jump's penny however
    # its rate changes there (by 60p a pound at most).
    st.floats(1.01, 300.0),
    st.sampled_from([-1.0, 1.0]),
    _PER_POUND,
    _PER_POUND,
)
def test_a_jump_at_a_change_of_rate_is_pinned_to_the_cent(
    at, size, sign, before, after
):
    """R3: the savings allowance falls as income reaches the higher rate, so
    tax jumps where its rate changes."""
    assume(abs(after - before) >= 0.05 or size >= 5.0)
    jump = sign * size

    def series(points):
        points = np.asarray(points, dtype=float)
        beyond = np.maximum(points - at, 0.0)
        return _cents(
            before * points
            + np.where(points > at, jump + (after - before) * beyond, 0.0)
        )

    edges, jumps, calls = _pin(series, _FINE)
    upper = round(at + 0.01, 2)
    assert jumps == [(at, upper)]
    assert all(abs(edge - at) >= 1.0 for edge in edges if edge not in (at, upper))
    assert calls <= 3


@given(
    st.floats(3_000.0, 17_000.0).map(lambda value: round(value, 2)),
    _PER_POUND,
    _PER_POUND,
)
def test_a_change_of_rate_alone_keeps_its_edge(at, before, after):
    assume(abs(after - before) >= 0.05)

    def series(points):
        points = np.asarray(points, dtype=float)
        return _cents(before * points + (after - before) * np.maximum(points - at, 0.0))

    edges, jumps, calls = _pin(series, _FINE)
    assert jumps == []
    assert len(edges) == 3
    # Rounding each figure to the cent leaves the change itself uncertain by
    # half a cent over the change of rate.
    assert edges[1] == pytest.approx(at, abs=0.01 + 0.005 / abs(after - before))
    assert calls <= 3


def _whole_pound_taper(points):
    """Tax at 40p a pound on income, plus 40p for each pound of a £12,570
    allowance lost at £1 per £2 over £100,000 and rounded up to the pound,
    then 45p a pound from £125,140, where none is left."""
    points = np.asarray(points, dtype=float)
    allowance = np.ceil(
        np.maximum(12_570.0 - np.maximum(points - 100_000.0, 0.0) / 2, 0.0)
    )
    return _cents(
        0.4 * points
        + 0.4 * (12_570.0 - allowance)
        + 0.05 * np.maximum(points - 125_140.0, 0.0)
    )


@pytest.mark.parametrize("step", [1_000.0, 2_500.0, 10_000.0])
def test_whole_pound_steps_put_each_edge_on_the_end_steps(step):
    """R7: s.35(3) moves tax 40p at a time through the taper. The first step
    is at £100,002, where half the excess first reaches £1; the last at
    £125,140, where the allowance runs out."""
    grid = np.arange(60_000.0, 200_001.0, step)
    draws = _cents(
        np.unique(
            np.concatenate(
                [
                    grid,
                    np.linspace(97_000.0, 104_000.0, 169),
                    np.linspace(122_000.0, 128_000.0, 145),
                ]
            )
        )
    )
    edges, jumps, calls = _pin(_whole_pound_taper, draws)
    assert jumps == []
    assert edges[1:-1] == [100_001.99, 125_140.0]
    assert calls <= 3
