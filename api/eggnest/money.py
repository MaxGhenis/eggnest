"""Amounts of money the one-year drawdown calculators take in.

Both pages show each amount typed into a field to two decimal places, and
both calculators report every figure to the cent (or penny). An amount sent
in finer than that would leave the calculator working on money the page never
showed: a balance of 0.125 left an account of 0.12, and a pot of 1.005 drawn
0.505 put 1.00 twice in the sweep. So each amount comes in rounded to the
cent, half a cent up, on the decimal the number prints as: what
Intl.NumberFormat shows with two decimals (1.005 is 1.01, 0.125 is 0.13).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import AfterValidator

_CENT = Decimal("0.01")


def to_the_cent(value: float) -> float:
    """``value`` to the nearest cent, half a cent up, on its printed decimal."""
    # Adding 0.0 turns a rounded -0.0 into 0.0.
    return float(Decimal(repr(value)).quantize(_CENT, rounding=ROUND_HALF_UP)) + 0.0


# An amount of money, in dollars or pounds, rounded to the cent on the way in.
Money = Annotated[float, AfterValidator(to_the_cent)]
