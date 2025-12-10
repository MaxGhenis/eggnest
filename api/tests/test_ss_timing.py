"""Tests for Social Security timing calculations."""

import pytest
from eggnest.ss_timing import (
    get_full_retirement_age,
    get_early_reduction_factor,
    get_delayed_retirement_credit,
    calculate_adjusted_benefit,
)


class TestFullRetirementAge:
    """Test FRA calculation by birth year."""

    def test_born_1937_or_earlier(self):
        """Birth year 1937 or earlier has FRA of 65."""
        assert get_full_retirement_age(1937) == 65.0
        assert get_full_retirement_age(1930) == 65.0

    def test_born_1938(self):
        """Birth year 1938 has FRA of 65 and 2 months."""
        assert get_full_retirement_age(1938) == pytest.approx(65 + 2/12, rel=0.01)

    def test_born_1939(self):
        """Birth year 1939 has FRA of 65 and 4 months."""
        assert get_full_retirement_age(1939) == pytest.approx(65 + 4/12, rel=0.01)

    def test_born_1940(self):
        """Birth year 1940 has FRA of 65 and 6 months."""
        assert get_full_retirement_age(1940) == pytest.approx(65 + 6/12, rel=0.01)

    def test_born_1941(self):
        """Birth year 1941 has FRA of 65 and 8 months."""
        assert get_full_retirement_age(1941) == pytest.approx(65 + 8/12, rel=0.01)

    def test_born_1942(self):
        """Birth year 1942 has FRA of 65 and 10 months."""
        assert get_full_retirement_age(1942) == pytest.approx(65 + 10/12, rel=0.01)

    def test_born_1943_to_1954(self):
        """Birth years 1943-1954 have FRA of 66."""
        for year in range(1943, 1955):
            assert get_full_retirement_age(year) == 66.0

    def test_born_1955(self):
        """Birth year 1955 has FRA of 66 and 2 months."""
        assert get_full_retirement_age(1955) == pytest.approx(66 + 2/12, rel=0.01)

    def test_born_1956(self):
        """Birth year 1956 has FRA of 66 and 4 months."""
        assert get_full_retirement_age(1956) == pytest.approx(66 + 4/12, rel=0.01)

    def test_born_1957(self):
        """Birth year 1957 has FRA of 66 and 6 months."""
        assert get_full_retirement_age(1957) == pytest.approx(66 + 6/12, rel=0.01)

    def test_born_1958(self):
        """Birth year 1958 has FRA of 66 and 8 months."""
        assert get_full_retirement_age(1958) == pytest.approx(66 + 8/12, rel=0.01)

    def test_born_1959(self):
        """Birth year 1959 has FRA of 66 and 10 months."""
        assert get_full_retirement_age(1959) == pytest.approx(66 + 10/12, rel=0.01)

    def test_born_1960_or_later(self):
        """Birth year 1960 or later has FRA of 67."""
        assert get_full_retirement_age(1960) == 67.0
        assert get_full_retirement_age(1970) == 67.0
        assert get_full_retirement_age(1990) == 67.0


class TestEarlyReductionFactor:
    """Test early retirement reduction calculations.

    Per SSA: 5/9 of 1% per month for first 36 months early,
    then 5/12 of 1% per month for additional months beyond 36.
    """

    def test_at_fra_no_reduction(self):
        """Claiming at FRA has no reduction."""
        # Person born 1960, FRA=67, claiming at 67
        factor = get_early_reduction_factor(birth_year=1960, claiming_age=67)
        assert factor == pytest.approx(1.0, rel=0.001)

    def test_one_year_early_fra_67(self):
        """Claiming 1 year (12 months) early with FRA 67."""
        # 12 months × 5/9 of 1% = 12 × 0.00556 = 6.67% reduction
        factor = get_early_reduction_factor(birth_year=1960, claiming_age=66)
        expected = 1.0 - (12 * 5/9 * 0.01)  # ~0.9333
        assert factor == pytest.approx(expected, rel=0.001)

    def test_three_years_early_fra_67(self):
        """Claiming 3 years (36 months) early with FRA 67."""
        # 36 months × 5/9 of 1% = 20% reduction
        factor = get_early_reduction_factor(birth_year=1960, claiming_age=64)
        expected = 1.0 - (36 * 5/9 * 0.01)  # 0.80
        assert factor == pytest.approx(expected, rel=0.001)

    def test_five_years_early_fra_67_claiming_62(self):
        """Claiming at 62 with FRA 67 (60 months early)."""
        # First 36 months: 36 × 5/9 of 1% = 20%
        # Additional 24 months: 24 × 5/12 of 1% = 10%
        # Total: 30% reduction
        factor = get_early_reduction_factor(birth_year=1960, claiming_age=62)
        expected = 1.0 - (36 * 5/9 * 0.01) - (24 * 5/12 * 0.01)  # 0.70
        assert factor == pytest.approx(expected, rel=0.001)

    def test_four_years_early_fra_66(self):
        """Claiming at 62 with FRA 66 (48 months early)."""
        # First 36 months: 36 × 5/9 of 1% = 20%
        # Additional 12 months: 12 × 5/12 of 1% = 5%
        # Total: 25% reduction
        factor = get_early_reduction_factor(birth_year=1950, claiming_age=62)
        expected = 1.0 - (36 * 5/9 * 0.01) - (12 * 5/12 * 0.01)  # 0.75
        assert factor == pytest.approx(expected, rel=0.001)

    def test_after_fra_returns_one(self):
        """Claiming after FRA returns factor of 1.0 (no reduction)."""
        factor = get_early_reduction_factor(birth_year=1960, claiming_age=68)
        assert factor == pytest.approx(1.0, rel=0.001)


class TestDelayedRetirementCredit:
    """Test delayed retirement credit calculations.

    For those born 1943 or later, DRC is 8% per year of delay after FRA (up to age 70).
    """

    def test_at_fra_no_credit(self):
        """Claiming at FRA has no delayed credit."""
        credit = get_delayed_retirement_credit(birth_year=1960, claiming_age=67)
        assert credit == pytest.approx(1.0, rel=0.001)

    def test_one_year_delay(self):
        """Claiming 1 year after FRA gives 8% increase."""
        credit = get_delayed_retirement_credit(birth_year=1960, claiming_age=68)
        assert credit == pytest.approx(1.08, rel=0.001)

    def test_two_years_delay(self):
        """Claiming 2 years after FRA gives 16% increase."""
        credit = get_delayed_retirement_credit(birth_year=1960, claiming_age=69)
        assert credit == pytest.approx(1.16, rel=0.001)

    def test_three_years_delay_fra_67(self):
        """Claiming at 70 with FRA 67 gives 24% increase."""
        credit = get_delayed_retirement_credit(birth_year=1960, claiming_age=70)
        assert credit == pytest.approx(1.24, rel=0.001)

    def test_four_years_delay_fra_66(self):
        """Claiming at 70 with FRA 66 gives 32% increase."""
        credit = get_delayed_retirement_credit(birth_year=1950, claiming_age=70)
        assert credit == pytest.approx(1.32, rel=0.001)

    def test_no_credit_beyond_70(self):
        """No additional credit for delaying past age 70."""
        credit_70 = get_delayed_retirement_credit(birth_year=1960, claiming_age=70)
        credit_71 = get_delayed_retirement_credit(birth_year=1960, claiming_age=71)
        assert credit_70 == credit_71

    def test_before_fra_returns_one(self):
        """Claiming before FRA returns factor of 1.0 (no credit)."""
        credit = get_delayed_retirement_credit(birth_year=1960, claiming_age=65)
        assert credit == pytest.approx(1.0, rel=0.001)


class TestCalculateAdjustedBenefit:
    """Test combined benefit adjustment calculation."""

    def test_at_fra_no_change(self):
        """Benefit at FRA equals PIA."""
        pia = 2000  # Monthly benefit at FRA
        adjusted = calculate_adjusted_benefit(
            pia_monthly=pia,
            birth_year=1960,
            claiming_age=67
        )
        assert adjusted == pytest.approx(pia, rel=0.001)

    def test_early_claiming_reduces_benefit(self):
        """Claiming at 62 with FRA 67 reduces benefit by 30%."""
        pia = 2000
        adjusted = calculate_adjusted_benefit(
            pia_monthly=pia,
            birth_year=1960,
            claiming_age=62
        )
        assert adjusted == pytest.approx(1400, rel=0.01)  # 70% of 2000

    def test_delayed_claiming_increases_benefit(self):
        """Claiming at 70 with FRA 67 increases benefit by 24%."""
        pia = 2000
        adjusted = calculate_adjusted_benefit(
            pia_monthly=pia,
            birth_year=1960,
            claiming_age=70
        )
        assert adjusted == pytest.approx(2480, rel=0.01)  # 124% of 2000

    def test_claiming_at_65_with_fra_67(self):
        """Claiming at 65 with FRA 67 (24 months early)."""
        # 24 months × 5/9 of 1% = 13.33% reduction
        pia = 2000
        adjusted = calculate_adjusted_benefit(
            pia_monthly=pia,
            birth_year=1960,
            claiming_age=65
        )
        expected = 2000 * (1.0 - (24 * 5/9 * 0.01))  # ~1733
        assert adjusted == pytest.approx(expected, rel=0.01)

    def test_fractional_claiming_age(self):
        """Handle fractional claiming ages (e.g., 62.5)."""
        pia = 2000
        adjusted = calculate_adjusted_benefit(
            pia_monthly=pia,
            birth_year=1960,
            claiming_age=62.5
        )
        # 54 months early: 36 × 5/9 of 1% + 18 × 5/12 of 1% = 20% + 7.5% = 27.5%
        expected = 2000 * (1.0 - 0.275)  # 1450
        assert adjusted == pytest.approx(expected, rel=0.01)


class TestEdgeCases:
    """Test edge cases and input validation."""

    def test_claiming_before_62_raises_error(self):
        """Cannot claim before age 62."""
        with pytest.raises(ValueError, match="62"):
            calculate_adjusted_benefit(
                pia_monthly=2000,
                birth_year=1960,
                claiming_age=61
            )

    def test_zero_pia(self):
        """Zero PIA returns zero regardless of claiming age."""
        adjusted = calculate_adjusted_benefit(
            pia_monthly=0,
            birth_year=1960,
            claiming_age=62
        )
        assert adjusted == 0

    def test_negative_pia_raises_error(self):
        """Negative PIA raises error."""
        with pytest.raises(ValueError, match="positive"):
            calculate_adjusted_benefit(
                pia_monthly=-100,
                birth_year=1960,
                claiming_age=67
            )
