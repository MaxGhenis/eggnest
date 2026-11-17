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
- A change of rate with no jump gets no jump, and its one edge lies within a
  cent plus the half cent of rounding over the change of rate (3p at 15p a
  pound), even where a second edge's band, too short to judge, takes in the
  change: of edges placed under £1 apart, the one nearest the edge its change
  replaces stays.
- A series that rises in 40p steps (tax as the tapered allowance rounds up
  to the pound, ITA 2007 s.35(3)) between two straight lines gets its edges
  on the last cent before the first step and on the last step, and no edge
  or jump between them.
- On a series that jumps and then gives the jump back, as the Personal
  Savings Allowance's fall at the higher rate does (ITA 2007 s.12B), on
  grids where the bands beside the change past the jump can be too short to
  judge, every band but a jump's is £1 wide or more, to the cent, and no
  edge lands within £1 of either end of a jump. (A gap between two jumps,
  and a sweep under £1 in all, would be exempt; these series have one jump
  and run to £20,000 or more.)

Before pin_changes, the UK calculator looks again around crowded jumps:

- crowded_jumps gives a stretch for each located jump with a band beside it
  holding fewer than five evaluated draws, from the interval just past that
  band's far edge through the jump's own piece; closer_look cuts no piece
  narrower than asked.
- With a jump a 24th of a grid interval from a change of rate, relocating
  on the finer pieces leaves only the jump, which pin_changes puts on its
  penny, and each change gets an edge within a cent plus half a cent over
  its change of rate.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from eggnest.drawdown_bands import (
    JumpRule,
    band_edges,
    closer_look,
    crowded_jumps,
    edges_between_jumps,
    locate_jumps,
    pin_changes,
    relocated_jumps,
)


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


def test_a_pound_moved_in_a_penny_is_a_jump_however_the_line_rounds():
    """us-edge, from test_a_jump_at_a_change_of_rate_is_pinned_to_the_cent
    under the thorough profile (seed 41): tax at 15p a pound jumps £1.01 at
    3,106.50 and stays flat after, at 466.985, a half penny, so its figures
    round to 466.98 or 466.99. The 15p line comes back to the flat series at
    3,113.20, so the flat line alone finds the jump's penny, and fitted to
    those figures it sits at 466.9776 there: 99.76p above the 465.98 before
    the jump. The series itself moves £1.00 in that penny, which is a jump."""
    at = 3_106.5

    def series(points):
        # As the property writes it, so the flat part carries its float noise.
        points = np.asarray(points, dtype=float)
        beyond = np.maximum(points - at, 0.0)
        return _cents(0.15 * points + np.where(points > at, 1.01 - 0.15 * beyond, 0.0))

    edges, jumps, calls = _pin(series, _FINE)
    assert jumps == [(at, 3_106.51)]
    assert all(abs(edge - at) >= 1.0 for edge in edges if edge not in (at, 3_106.51))
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


def test_a_change_two_edges_find_keeps_one_edge():
    """us-edge, from test_a_change_of_rate_alone_keeps_its_edge under the
    thorough profile (seed 31): tax at 45p a pound, then 60p from 5,715.50.
    On a 24th of £1,000 the grid point before the change sits 7.17 short of
    it, so band_edges also leaves an edge on the break at 5,833.33, where
    nothing changes. That edge's band below holds two draws, so it takes in
    the band beyond, across the change, and is uneven; its 60p line runs back
    to where it stops holding within 5p, 5,715.14. The change's own lines
    cross at 5,715.49. Two edges 35p apart mark one change: the one placed
    nearer the edge it replaces stays, and no two edges lie under £1 apart."""
    at, before, after = 5_715.5, 0.45, 0.6

    def series(points):
        points = np.asarray(points, dtype=float)
        return _cents(before * points + (after - before) * np.maximum(points - at, 0.0))

    edges, jumps, calls = _pin(series, _FINE)
    assert jumps == []
    assert edges == pytest.approx([0.0, at, 20_000.0], abs=0.01 + 0.005 / 0.15)
    assert calls <= 3


def _given_back(at, size, stretch, before, after, extra=0.0):
    """Tax at ``before`` a pound that jumps ``size`` past ``at``, charges
    ``after`` for ``stretch``, then ``before`` again until it has given the
    jump back, and ``extra`` more of draw, then ``after``: the Personal
    Savings Allowance's fall at the higher rate (ITA 2007 s.12B), in cents.
    The line past the give-back meets the line before the jump ``extra``
    short of ``at``."""
    kink = at + stretch
    back = kink + size / (after - before) + extra

    def series(points):
        points = np.asarray(points, dtype=float)
        return _cents(
            before * points
            + np.where(points > at, size, 0.0)
            + (after - before) * np.maximum(points - at, 0.0)
            - (after - before) * np.maximum(points - kink, 0.0)
            + (after - before) * np.maximum(points - back, 0.0)
        )

    return series


# Grids a 24th of £25,000 and of £50,000 apart, to £25,000, and £1,000 apart,
# to £20,000.
_COARSE = {
    "24th of 25k": _cents(np.linspace(0.0, 25_000.0, 25)),
    "24th of 50k": _cents(np.linspace(0.0, 25_000.0, 13)),
    "1k": _cents(np.arange(0.0, 20_001.0, 1_000.0)),
}


def _pin_after_a_grid(series, grid: np.ndarray):
    """Edges and jumps a UK run would report for ``series`` on ``grid``: the
    grid's own edges evaluated too, as the calculators' second run does, the
    jumps located, then pin_changes as drawdown_uk calls it."""
    first = band_edges(grid, [(series(grid), 1.0)], min_width=1.0)
    draws = np.unique(_cents(np.concatenate([grid, first])))
    values = series(draws)
    jumps = locate_jumps(draws, [values], draws[0], draws[-1], _JUMP_RULE)
    edges = edges_between_jumps(draws, [(values, 1.0)], jumps, 1.0)
    have = set(draws.tolist())
    edges, jumps, _ = pin_changes(
        draws,
        values,
        edges,
        jumps,
        series,
        tolerance=0.05,
        step_min=1.0,
        min_width=1.0,
        also=np.array([edge for edge in _cents(np.array(edges)) if edge not in have]),
        straight_within=1.0,
    )
    return edges, jumps


def _assert_no_band_but_a_jumps_is_narrow(edges, jumps, min_width=1.0):
    """Every band but a jump's, and a gap between two jumps, is at least
    ``min_width`` wide, to the cent."""
    jump_bands = {(round(low, 2), round(high, 2)) for low, high in jumps}
    ends = {round(end, 2) for jump in jumps for end in jump}
    for low, high in zip(edges, edges[1:], strict=False):
        low, high = round(low, 2), round(high, 2)
        if (low, high) in jump_bands or (low in ends and high in ends):
            continue
        assert round((high - low) * 100) >= round(min_width * 100), (low, high)


@pytest.mark.parametrize(
    ("grid", "at", "size", "stretch", "extra", "jump"),
    [
        ("24th of 25k", 9_406.94, 1.01, 1_371.66, 0.0, (9_406.94, 9_406.95)),
        ("1k", 12_000.0, 1.01, 5.0, 1.01, (12_000.0, 12_000.01)),
    ],
)
def test_no_edge_lands_under_a_pound_past_a_jump(grid, at, size, stretch, extra, jump):
    """P2-c, as the stepped stand-in's run at £58,243.05 (test_drawdown_uk.py,
    TestStepsInIncomeTax): the change at the grid point past the jump has
    bands too short to judge on both sides, so its lines come from the bands
    beyond: the line before the jump and the line past the give-back, which
    cross at the jump. pin_changes put that edge 6p and 99p past the jump's
    end, so a band under £1 wide followed it. Now no edge lands within £1 of
    a jump's ends."""
    edges, jumps = _pin_after_a_grid(
        _given_back(at, size, stretch, 0.4, 0.45, extra), _COARSE[grid]
    )
    assert jump in jumps
    _assert_no_band_but_a_jumps_is_narrow(edges, jumps)


@given(
    st.sampled_from([*_COARSE.values(), _FINE]),
    st.floats(2_000.0, 12_000.0).map(lambda value: round(value, 2)),
    st.floats(1.01, 300.0).map(lambda value: round(value, 2)),
    st.floats(5.0, 3_000.0).map(lambda value: round(value, 2)),
    st.sampled_from([(0.2, 0.4), (0.168, 0.336), (0.4, 0.45), (0.15, 0.6)]),
    st.floats(-1.0, 1.0),
)
def test_no_band_but_a_jumps_is_narrower_than_the_minimum_width(
    grid, at, size, stretch, rates, extra
):
    """A jump whose rates give it back, as the Personal Savings Allowance's
    fall does, short of it or past it by up to £1 of draw, on grids where the
    bands beside the change past the jump can be too short to judge."""
    before, after = rates
    series = _given_back(at, size, stretch, before, after, extra)
    edges, jumps = _pin_after_a_grid(series, grid)
    _assert_no_band_but_a_jumps_is_narrow(edges, jumps)


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


_JUMP_RULE = JumpRule(rate=1.05, minimum=5.0)  # the UK calculator's


def _crowded_series(jump_at: float, size: float, stretch: float):
    """Tax at 20p a pound that jumps ``size`` past ``jump_at``, then charges
    40p for ``stretch``, 20p for £500 and 40p after: the Personal Savings
    Allowance's fall at the higher rate (ITA 2007 s.12B), in cents."""
    kink = jump_at + stretch

    def series(points):
        points = np.asarray(points, dtype=float)
        return _cents(
            0.2 * points
            + np.where(points > jump_at, size, 0.0)
            + 0.2 * np.maximum(points - jump_at, 0.0)
            - 0.2 * np.maximum(points - kink, 0.0)
            + 0.2 * np.maximum(points - kink - 500.0, 0.0)
        )

    return series, (kink, kink + 500.0)


def test_a_closer_look_frees_a_change_of_rate_a_piece_past_a_jump():
    """Case 1 of the 150-example run (test_drawdown_uk.py,
    TestStepsInIncomeTax): pieces £208.33 apart (a 24th of a £5,000 grid),
    an evaluated edge at £49,533.84, a £43.80 jump at £49,583 and the 40p
    stretch past it only £219 wide. locate_jumps takes the stretch's piece
    for a jump too, which leaves no band beside either; once those pieces
    are cut finer, only the jump is one, and the changes of rate get their
    edges, which pin_changes keeps."""
    series, kinks = _crowded_series(49_583.0, 43.80, 219.0)
    pieces = np.unique(
        _cents(np.concatenate([np.linspace(45_000.0, 55_000.0, 49), [49_533.84]]))
    )
    values = series(pieces)
    found = locate_jumps(pieces, [values], pieces[0], pieces[-1], _JUMP_RULE)
    assert found == [(49_533.84, 49_583.33), (49_583.33, 49_791.67)]
    edges = edges_between_jumps(pieces, [(values, 1.0)], found, 1.0)
    crowded = crowded_jumps(pieces, edges, found)
    assert len(crowded) == 1
    assert crowded[0][0] <= 49_375.0 and crowded[0][1] >= 50_000.0
    added = closer_look(pieces, crowded, 5.0, 24)
    assert np.min(np.diff(np.unique(np.concatenate([pieces, added])))) >= 5.0
    draws = np.unique(_cents(np.concatenate([pieces, added])))
    values = series(draws)
    jumps = relocated_jumps(draws, [values], found, crowded, _JUMP_RULE)
    assert len(jumps) == 1 and jumps[0][0] < 49_583.0 < jumps[0][1]
    edges = edges_between_jumps(draws, [(values, 1.0)], jumps, 1.0)
    calls = []

    def evaluate(points):
        calls.append(points)
        return series(points)

    edges, jumps, _ = pin_changes(
        draws,
        values,
        edges,
        jumps,
        evaluate,
        tolerance=0.05,
        step_min=1.0,
        min_width=1.0,
        also=draws[:0],
    )
    assert jumps == [(49_583.0, 49_583.01)]
    for kink in kinks:
        assert min(abs(edge - kink) for edge in edges) <= 0.01 + 0.005 / 0.2
    assert len(calls) <= 3


def test_crowded_jumps_reach_past_each_short_band():
    draws = np.arange(0.0, 41.0)
    # Nine draws on the left, two on the right of a £1 jump: the right band
    # is short, and its far edge, at 23.50, sits in the interval to 24.
    assert crowded_jumps(
        draws, [0.0, 10.0, 20.0, 21.0, 23.5, 40.0], [(20.0, 21.0)]
    ) == [(20.0, 24.0)]
    assert (
        crowded_jumps(draws, [0.0, 10.0, 20.0, 21.0, 30.0, 40.0], [(20.0, 21.0)]) == []
    )
    # Neighbouring jumps leave each an empty band beside the other: one
    # stretch from the interval before the first to the one past the second.
    jumps = [(20.0, 21.0), (21.0, 22.0)]
    edges = [0.0, 10.0, 20.0, 21.0, 22.0, 30.0, 40.0]
    assert crowded_jumps(draws, edges, jumps) == [(19.0, 23.0)]


def test_a_closer_look_cuts_pieces_no_narrower_than_asked():
    # £100 takes 19 pieces of £5.26, since 20 of £5 could round to £4.99;
    # £10.03 takes two; £2 none.
    draws = np.array([0.0, 100.0, 110.03, 112.03])
    points = closer_look(draws, [(0.0, 112.03)], 5.0, 24)
    assert len(points) == 18 + 1
    assert points == pytest.approx(np.round(points, 2))
    cut = np.unique(np.concatenate([draws, points]))
    assert np.min(np.diff(cut)[:-1]) >= 5.0  # all but the £2 left whole
    assert len(closer_look(draws, [(0.0, 100.0)], 1.0, 24)) == 23
    assert len(closer_look(draws, [], 1.0, 24)) == 0


@given(
    st.lists(
        st.floats(0.0, 500.0).map(lambda value: round(value, 2)),
        min_size=2,
        max_size=12,
        unique=True,
    ),
    st.sampled_from([1.0, 5.0]),
)
def test_no_piece_of_a_closer_look_is_narrower_than_asked(draws, min_width):
    draws = np.array(sorted(draws))
    points = closer_look(draws, [(draws[0], draws[-1])], min_width, 24)
    cut = np.unique(np.concatenate([draws, points]))
    new = np.diff(cut)[~np.isin(cut[1:], draws) | ~np.isin(cut[:-1], draws)]
    assert np.all(new >= min_width - 1e-9)
