"""State Pension age and Pension Credit qualifying age (UK).

State Pension age ("pensionable age") is set by the rules in Pensions Act
1995 Schedule 4 Part I paragraph 1, as amended by the Pensions Acts 2007,
2011 and 2014; SSCBA 1992 s.122(1) and State Pension Credit Act 2002 s.17(1)
both define pensionable age by those rules. The schedule lives in
data/state_pension_age.json: one row per birth-date cohort, either an age
(years and months) or, for the transitional cohorts, a date that steps by a
fixed number of months per monthly cohort, plus the three dates rule (7A)
fixes. It was checked against the legislation.gov.uk revised text of
2026-09-29 (tests/data/spa_schedule_explicit.json holds every table row as
enacted; the tests compare the two).

rulespec-uk has no encoding of Schedule 4 (SPC Act s.1 takes pensionable age
as an input), so eggnest computes it here.
"""

from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

Sex = Literal["male", "female"]

_SCHEDULE_PATH = Path(__file__).parent / "data" / "state_pension_age.json"
SCHEDULE_URL = "https://www.legislation.gov.uk/ukpga/1995/26/schedule/4/part/I"
PENSION_CREDIT_QUALIFYING_AGE_URL = (
    "https://www.legislation.gov.uk/ukpga/2002/16/section/1"
)


@dataclass(frozen=True)
class _Row:
    born_on_or_after: date | None
    born_on_or_before: date | None
    sex: str  # "male", "female" or "any"
    para: str
    spa_years: int | None = None
    spa_months: int | None = None
    first_spa_date: date | None = None
    step_months: int | None = None

    def covers(self, birth: date, sex: Sex) -> bool:
        return (
            (self.sex == "any" or self.sex == sex)
            and (self.born_on_or_after is None or birth >= self.born_on_or_after)
            and (self.born_on_or_before is None or birth <= self.born_on_or_before)
        )


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


@lru_cache(maxsize=1)
def _schedule() -> tuple[tuple[_Row, ...], dict[date, date]]:
    raw = json.loads(_SCHEDULE_PATH.read_text())
    rows = tuple(
        _Row(
            born_on_or_after=_parse_date(row["born_on_or_after"]),
            born_on_or_before=_parse_date(row["born_on_or_before"]),
            sex=row["sex"],
            para=row["para"],
            spa_years=row.get("spa_years"),
            spa_months=row.get("spa_months"),
            first_spa_date=_parse_date(row.get("first_spa_date")),
            step_months=row.get("step_months"),
        )
        for row in raw["schedule"]
    )
    overrides = {
        date.fromisoformat(born): date.fromisoformat(reached)
        for born, reached in raw["overrides"].items()
    }
    return rows, overrides


def add_months(start: date, months: int) -> date:
    """``start`` plus ``months`` calendar months, clamped to the month's end."""
    index = start.year * 12 + (start.month - 1) + months
    year, month = divmod(index, 12)
    day = min(start.day, calendar.monthrange(year, month + 1)[1])
    return date(year, month + 1, day)


def whole_months_between(start: date, end: date) -> int:
    """Complete calendar months from ``start`` to ``end`` (month-end clamped)."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if add_months(start, months) > end:
        months -= 1
    return months


def anniversary(birth: date, years: int, months: int = 0) -> date:
    """The day a person born on ``birth`` attains an age.

    Ages are attained at the start of the relevant anniversary (Family Law
    Reform Act 1969 s.9; Age of Legal Capacity (Scotland) Act 1991 s.6). A
    29 February birthday falls on 1 March in years without one (1991 Act
    s.6(2); English law is silent), and month arithmetic otherwise clamps
    to the month's end, which reproduces the Pensions Act 1995 Sch 4 para
    1(7A) dates.
    """
    reached = add_months(birth, years * 12 + months)
    if birth.month == 2 and birth.day == 29 and reached.day == 28 and months == 0:
        return date(reached.year, 3, 1)
    return reached


def _row_for(birth: date, sex: Sex) -> _Row:
    rows, _ = _schedule()
    matches = [row for row in rows if row.covers(birth, sex)]
    if len(matches) != 1:
        raise ValueError(
            f"State Pension age schedule has {len(matches)} rows for a "
            f"{sex} born {birth.isoformat()}"
        )
    return matches[0]


def state_pension_age_date(birth: date, sex: Sex) -> date:
    """The day a person reaches State Pension age (Pensions Act 1995 Sch 4)."""
    _, overrides = _schedule()
    if birth in overrides:
        return overrides[birth]
    row = _row_for(birth, sex)
    if row.spa_years is not None:
        return anniversary(birth, row.spa_years, row.spa_months or 0)
    # Date cohorts run from the 6th of one month to the 5th of the next.
    assert row.born_on_or_after is not None and row.first_spa_date is not None
    cohort = (birth.year - row.born_on_or_after.year) * 12 + (
        birth.month - row.born_on_or_after.month
    )
    if birth.day < row.born_on_or_after.day:
        cohort -= 1
    return add_months(row.first_spa_date, cohort * (row.step_months or 0))


def state_pension_age_citation(birth: date, sex: Sex) -> str:
    """The Schedule 4 paragraph that sets this person's State Pension age."""
    return f"Pensions Act 1995 Sch 4 para {_row_for(birth, sex).para}"


def pension_credit_qualifying_date(birth: date) -> date:
    """The day a person reaches the qualifying age for State Pension Credit.

    State Pension Credit Act 2002 s.1(6): a woman's pensionable age, or for
    a man the pensionable age of a woman born on the same day. The schedule
    treats both sexes alike for births from 6 December 1953, so this equals
    State Pension age for anyone born since then.
    """
    return state_pension_age_date(birth, "female")


def assumed_birth_date(current_age: int, today: date) -> date:
    """Birth date for someone aged ``current_age`` today, taking the birthday
    to be today (the simulator only knows a whole-year age)."""
    year = today.year - current_age
    day = min(today.day, calendar.monthrange(year, today.month)[1])
    return date(year, today.month, day)


def share_of_period_from(start: date, end: date, reached: date) -> float:
    """Share of the period [start, end) falling on or after ``reached``."""
    if reached <= start:
        return 1.0
    if reached >= end:
        return 0.0
    return (end - reached).days / (end - start).days
