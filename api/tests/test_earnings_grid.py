"""Earnings levels for the earnings grid (no PolicyEngine).

Invariants, for finite inputs the grid model accepts with amounts up to $2
billion, the range the property strategies draw:
1. The levels strictly increase: no row is computed twice.
2. They start at income_min and end at income_max, both rounded to cents.
3. Every level is a whole number of cents.
4. Consecutive levels are at most step + 1 cent apart.
5. An accepted grid lists at most 501 rows. For whole-cent inputs, the model
   rejects a grid exactly when it lists more than 501 rows.
"""

import math
from itertools import pairwise

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from eggnest.earnings_grid import (
    MAX_GRID_ROWS,
    earnings_grid_too_large,
    earnings_grid_values,
)
from eggnest.models import EarningsGridInput, HouseholdInput, PersonInput

# Pure arithmetic: cheap enough for many more examples than the profile's 20.
MANY = settings(max_examples=500)

cents = st.integers(min_value=0, max_value=100_000_000_000).map(lambda c: c / 100)
steps = st.one_of(
    st.integers(min_value=1, max_value=10_000_000_000).map(lambda c: c / 100),
    st.floats(min_value=0.001, max_value=100_000_000),
)
# Spans as the agent surfaces build them: whole cents, or a sum with float
# noise such as wages + 1_000.
spans = st.one_of(cents, st.floats(min_value=0, max_value=1_000_000_000))


def _household() -> HouseholdInput:
    return HouseholdInput(
        state="TX",
        year=2025,
        people=[PersonInput(age=40, employment_income=0, is_tax_unit_head=True)],
    )


def _grid_input(income_min: float, income_max: float, step: float) -> EarningsGridInput:
    return EarningsGridInput(
        base_input=_household(),
        income_min=income_min,
        income_max=income_max,
        step=step,
    )


@MANY
@example(income_min=3096.14, span=1000.0, step=1000.0)  # the duplicate-row case
@example(income_min=0.0, span=1.0, step=0.004)  # steps below a cent
@example(income_min=0.0, span=50_050.0, step=100.0)  # 500 steps + income_max
@given(income_min=cents, span=spans, step=steps)
def test_grid_levels_hold_their_invariants(income_min, span, step):
    income_max = income_min + span
    if earnings_grid_too_large(income_min, income_max, step):
        return
    values = earnings_grid_values(income_min, income_max, step)

    assert all(b > a for a, b in pairwise(values))
    assert values[0] == round(income_min, 2)
    assert values[-1] == round(income_max, 2)
    assert all(round(value, 2) == value for value in values)
    # 1e-6 covers float error in the subtraction at the largest amounts.
    assert all(b - a <= step + 0.01 + 1e-6 for a, b in pairwise(values))
    assert len(values) <= MAX_GRID_ROWS


@MANY
@example(min_cents=0, step_cents=10_000, n_steps=500, tail_cents=0)  # 501 rows
@example(min_cents=0, step_cents=10_000, n_steps=500, tail_cents=5_000)  # 502 rows
@example(min_cents=0, step_cents=10_000, n_steps=501, tail_cents=0)  # 502 rows
@example(min_cents=309_614, step_cents=100_000, n_steps=1, tail_cents=0)
# (8.05 - 3.05) / 0.01 is 500.00000000000006 in floating point: still 501 rows.
@example(min_cents=305, step_cents=1, n_steps=500, tail_cents=0)
@given(
    min_cents=st.integers(min_value=0, max_value=100_000_000_000),
    step_cents=st.integers(min_value=1, max_value=1_000_000_000),
    n_steps=st.integers(min_value=0, max_value=MAX_GRID_ROWS + 1),
    tail_cents=st.integers(min_value=0, max_value=1_000_000_000),
)
def test_whole_cent_grids_match_integer_arithmetic(
    min_cents, step_cents, n_steps, tail_cents
):
    # Differential: integer cents give the levels and the row count without
    # any floating point, in both directions of the model's limit.
    tail_cents %= step_cents
    max_cents = min_cents + n_steps * step_cents + tail_cents
    expected = [min_cents + i * step_cents for i in range(n_steps + 1)]
    if tail_cents:
        expected.append(max_cents)
    income_min, income_max, step = min_cents / 100, max_cents / 100, step_cents / 100

    if len(expected) > MAX_GRID_ROWS:
        with pytest.raises(ValidationError, match="cannot exceed 501 rows"):
            _grid_input(income_min, income_max, step)
    else:
        _grid_input(income_min, income_max, step)
        assert earnings_grid_values(income_min, income_max, step) == [
            cents_value / 100 for cents_value in expected
        ]


@MANY
@example(income_min=0.0, span=50_050.0, step=100.0)
@example(income_min=0.0, span=50_000.0, step=100.0)
@example(income_min=0.0, span=4.0, step=0.005)  # rejected, conservatively
@given(income_min=cents, span=spans, step=steps)
def test_accepted_grids_list_at_most_the_limit(income_min, span, step):
    income_max = income_min + span
    try:
        _grid_input(income_min, income_max, step)
    except ValidationError:
        return
    assert len(earnings_grid_values(income_min, income_max, step)) <= MAX_GRID_ROWS


def test_wages_plus_a_thousand_is_two_rows():
    # 3096.14 + 1000 is 4096.139999999999 in floating point. The grid used
    # to compare its rounded last level, 4096.14, with that unrounded maximum
    # and computed the $4,096.14 row twice.
    assert 3096.14 + 1000 != 4096.14
    assert earnings_grid_values(3096.14, 3096.14 + 1000, 1000) == [3096.14, 4096.14]


def test_steps_below_a_cent_do_not_repeat_levels():
    values = earnings_grid_values(0, 0.05, 0.004)
    assert values == [0.0, 0.01, 0.02, 0.03, 0.04, 0.05]


def test_income_max_the_steps_miss_is_the_last_row():
    assert earnings_grid_values(0, 2_500, 1_000) == [0.0, 1_000.0, 2_000.0, 2_500.0]


def test_a_step_rounded_past_income_max_is_dropped():
    # 152193.555 + 357 * 5168.89 lands on a half-cent tie that rounds to
    # 1997487.29, a cent above income_max rounded. The grid must end at
    # income_max.
    assert round(152193.555 + 357 * 5168.89, 2) == 1997487.29
    assert round(1997487.285, 2) == 1997487.28
    values = earnings_grid_values(152193.555, 1997487.285, 5168.89)
    assert values[-1] == 1997487.28
    assert all(b > a for a, b in pairwise(values))


def test_limit_includes_the_income_max_row():
    # 500 whole steps reach $50,000, and income_max adds a 502nd row.
    assert len(earnings_grid_values(0, 50_000, 100)) == MAX_GRID_ROWS
    with pytest.raises(ValidationError, match="cannot exceed 501 rows"):
        _grid_input(0, 50_050, 100)


@pytest.mark.parametrize(
    ("income_max", "step"),
    [(1.0, 5e-324), (1e300, 1e-10)],
)
def test_unbounded_grids_fail_validation(income_max, step):
    # A non-finite step count used to raise OverflowError (a 500), not a 422.
    with pytest.raises(ValidationError, match="cannot exceed 501 rows"):
        _grid_input(0, income_max, step)


@pytest.mark.parametrize(
    ("income_min", "income_max", "step"),
    [
        (0.0, 1_000.0, math.inf),  # 0 * inf made the first level nan
        (0.0, math.inf, 1_000.0),
        (math.inf, math.inf, 1_000.0),
        (0.0, 1_000.0, math.nan),
        (0.0, math.nan, 1_000.0),
        (math.nan, 1_000.0, 1_000.0),
    ],
)
def test_non_finite_inputs_fail_validation(income_min, income_max, step):
    with pytest.raises(ValidationError, match="finite"):
        _grid_input(income_min, income_max, step)


def test_invalid_arguments_raise():
    with pytest.raises(ValueError, match="step must be positive"):
        earnings_grid_values(0, 1_000, 0)
    with pytest.raises(ValueError, match="greater than or equal"):
        earnings_grid_values(2_000, 1_000, 100)
    with pytest.raises(ValueError, match="must be finite"):
        earnings_grid_values(0, 1_000, math.inf)
