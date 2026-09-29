"""State Pension age schedule (Pensions Act 1995 Sch 4 Pt I para 1)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from eggnest.state_pension_age import (
    add_months,
    anniversary,
    assumed_birth_date,
    pension_credit_qualifying_date,
    share_of_period_from,
    state_pension_age_citation,
    state_pension_age_date,
    whole_months_between,
)

EXPLICIT = json.loads(
    (Path(__file__).parent / "data" / "spa_schedule_explicit.json").read_text()
)


def _explicit_spa(birth: date, sex: str) -> date:
    """The enacted table, row by row: an independent oracle."""
    overrides = EXPLICIT["overrides_para_1_7A"]
    if birth.isoformat() in overrides:
        return date.fromisoformat(overrides[birth.isoformat()])
    matches = [
        row
        for row in EXPLICIT["rows"]
        if row["sex"] in ("any", sex)
        and (
            row["born_on_or_after"] is None
            or birth >= date.fromisoformat(row["born_on_or_after"])
        )
        and (
            row["born_on_or_before"] is None
            or birth <= date.fromisoformat(row["born_on_or_before"])
        )
    ]
    assert len(matches) == 1, (birth, sex, matches)
    row = matches[0]
    if row["kind"] == "date":
        return date.fromisoformat(row["spa_date"])
    return anniversary(birth, row["spa_years"], row["spa_months"])


@pytest.mark.parametrize(
    ("birth", "expected", "para"),
    [
        (date(1960, 4, 5), date(2026, 4, 5), "1(6)"),  # last 66 cohort
        (date(1960, 4, 6), date(2026, 5, 6), "1(7) table 3"),  # 66y1m
        (date(1960, 7, 31), date(2026, 11, 30), "1(7) table 3; 1(7A)(a)"),
        (date(1960, 12, 31), date(2027, 9, 30), "1(7) table 3; 1(7A)(b)"),
        (date(1961, 1, 31), date(2027, 11, 30), "1(7) table 3; 1(7A)(c)"),
        (date(1961, 3, 5), date(2028, 2, 5), "1(7) table 3"),  # 66y11m
        (date(1961, 3, 6), date(2028, 3, 6), "1(8)"),  # 67
        (date(1977, 4, 5), date(2044, 4, 5), "1(8)"),
        (date(1977, 4, 6), date(2044, 5, 6), "1(9) table 4"),
        (date(1978, 4, 5), date(2046, 3, 6), "1(9) table 4"),
        (date(1978, 4, 6), date(2046, 4, 6), "1(10)"),  # 68
        (date(1954, 1, 10), date(2019, 5, 6), "1(5) table 2"),
    ],
)
def test_spot_values(birth, expected, para):
    for sex in ("male", "female"):
        assert state_pension_age_date(birth, sex) == expected
    assert state_pension_age_citation(birth, "female").endswith(f"para {para}")


def test_matches_the_enacted_table_for_every_birth_date():
    """Differential: the compact encoding against every enacted row, for
    every birth date 1935-2005 and both sexes."""
    day = date(1935, 1, 1)
    while day <= date(2005, 12, 31):
        for sex in ("male", "female"):
            assert state_pension_age_date(day, sex) == _explicit_spa(day, sex), (
                day,
                sex,
            )
        day += timedelta(days=1)


def test_women_before_april_1950_and_men_before_december_1953():
    assert state_pension_age_date(date(1949, 6, 1), "female") == date(2009, 6, 1)
    assert state_pension_age_date(date(1953, 12, 5), "male") == date(2018, 12, 5)
    assert state_pension_age_date(date(1953, 12, 5), "female") == date(2018, 11, 6)


def test_leap_day_birthday_on_a_whole_year_age():
    # 66 on 29 Feb 2024 exists; 67 falls on 1 March 2031 (no 29 Feb).
    assert anniversary(date(1964, 2, 29), 67) == date(2031, 3, 1)
    assert state_pension_age_date(date(1964, 2, 29), "male") == date(2031, 3, 1)


births = st.dates(min_value=date(1900, 1, 1), max_value=date(2060, 12, 31))


@given(a=births, b=births, sex=st.sampled_from(["male", "female"]))
def test_later_births_never_reach_state_pension_age_earlier(a, b, sex):
    first, second = sorted((a, b))
    assert state_pension_age_date(first, sex) <= state_pension_age_date(second, sex)


@given(birth=st.dates(min_value=date(1953, 12, 6), max_value=date(2060, 12, 31)))
def test_same_age_for_both_sexes_from_december_1953(birth):
    assert state_pension_age_date(birth, "male") == state_pension_age_date(
        birth, "female"
    )
    assert pension_credit_qualifying_date(birth) == state_pension_age_date(
        birth, "male"
    )


@given(birth=births, sex=st.sampled_from(["male", "female"]))
def test_state_pension_age_is_between_60_and_68(birth, sex):
    reached = state_pension_age_date(birth, sex)
    assert anniversary(birth, 60) <= reached <= anniversary(birth, 68)


@given(birth=births)
def test_qualifying_age_never_after_state_pension_age(birth):
    """SPC Act 2002 s.1(6): a man qualifies at a woman's pensionable age,
    which is never later than his own."""
    assert pension_credit_qualifying_date(birth) <= state_pension_age_date(
        birth, "male"
    )


@given(start=st.dates(), months=st.integers(min_value=-1200, max_value=1200))
def test_add_months_lands_in_the_right_month(start, months):
    try:
        moved = add_months(start, months)
    except ValueError:  # outside the representable date range
        return
    assert (moved.year * 12 + moved.month) - (start.year * 12 + start.month) == (months)
    assert moved.day <= start.day


@given(
    age=st.integers(min_value=18, max_value=100),
    today=st.dates(min_value=date(2020, 1, 1), max_value=date(2040, 12, 31)),
)
def test_assumed_birth_date_gives_the_current_age(age, today):
    birth = assumed_birth_date(age, today)
    assert anniversary(birth, age) <= today < anniversary(birth, age + 1)


@given(
    start=st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 1, 1)),
    length=st.integers(min_value=1, max_value=400),
    offset=st.integers(min_value=-500, max_value=900),
)
def test_share_of_period_is_a_fraction_and_monotone(start, length, offset):
    end = start + timedelta(days=length)
    reached = start + timedelta(days=offset)
    share = share_of_period_from(start, end, reached)
    assert 0.0 <= share <= 1.0
    later = share_of_period_from(start, end, reached + timedelta(days=1))
    assert later <= share


@given(
    start=st.dates(min_value=date(1900, 1, 1), max_value=date(2100, 1, 1)),
    months=st.integers(min_value=0, max_value=1200),
)
def test_whole_months_between_inverts_add_months(start, months):
    assert whole_months_between(start, add_months(start, months)) == months


def test_qualifying_age_in_years_and_months():
    birth = date(1960, 10, 20)  # 66y7m cohort
    assert divmod(
        whole_months_between(birth, pension_credit_qualifying_date(birth)), 12
    ) == (66, 7)
