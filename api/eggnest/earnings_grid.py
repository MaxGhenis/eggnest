"""Earnings levels for the earnings-grid comparison.

Pure arithmetic with no PolicyEngine import, so the input model's validator
and ``compare_earnings_grid`` share it, and the row limit counts the grid's
own levels.
"""

from __future__ import annotations

import math

# A grid lists at most this many earnings levels.
MAX_GRID_ROWS = 501


def earnings_grid_values(
    income_min: float, income_max: float, step: float
) -> list[float]:
    """Earnings levels from ``income_min`` to ``income_max``, rounded to cents.

    The levels are ``income_min + i * step`` for each whole step (computed,
    not accumulated), then ``income_max`` if the steps miss it. Rounding to
    cents can merge levels less than a cent apart, so a level is kept only if
    it exceeds the one before. The list therefore strictly increases, starts
    at ``income_min`` and ends at ``income_max``, both rounded to cents.
    """
    if not all(math.isfinite(value) for value in (income_min, income_max, step)):
        raise ValueError("income_min, income_max and step must be finite")
    if not step > 0:
        raise ValueError("step must be positive")
    if not income_min <= income_max:
        raise ValueError("income_max must be greater than or equal to income_min")
    whole_steps = _whole_steps(income_min, income_max, step)
    if whole_steps is None or whole_steps + 1 > MAX_GRID_ROWS:
        raise ValueError(f"earnings grid cannot exceed {MAX_GRID_ROWS} rows")
    high = round(income_max, 2)
    values: list[float] = []
    for i in range(whole_steps + 1):
        value = round(income_min + i * step, 2)
        # On a half-cent tie, float noise can round a step's level a cent
        # above income_max.
        if value > high:
            break
        if not values or value > values[-1]:
            values.append(value)
    if values[-1] < high:
        values.append(high)
    return values


def earnings_grid_too_large(income_min: float, income_max: float, step: float) -> bool:
    """Whether the grid would list more than ``MAX_GRID_ROWS`` levels.

    Counts whole steps arithmetically first, so a huge range never builds a
    huge list, then counts the levels ``earnings_grid_values`` returns,
    including an ``income_max`` the steps miss. The arithmetic count includes
    levels that rounding would merge, so a grid with steps below a cent can
    be rejected although it would list fewer rows.
    """
    whole_steps = _whole_steps(income_min, income_max, step)
    if whole_steps is None or whole_steps + 1 > MAX_GRID_ROWS:
        return True
    return len(earnings_grid_values(income_min, income_max, step)) > MAX_GRID_ROWS


def _whole_steps(income_min: float, income_max: float, step: float) -> int | None:
    """Whole steps from ``income_min`` that stay within ``income_max``.

    None when the count is not finite (an infinite range, or a step so small
    the division overflows).
    """
    quotient = (income_max - income_min) / step
    if not math.isfinite(quotient):
        return None
    return math.floor(quotient)
