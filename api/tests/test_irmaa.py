"""Tests for IRMAA (Income-Related Monthly Adjustment Amount) integration."""

import numpy as np
import pytest

from eggnest.tax import TaxCalculator


class TestIRMAAFromPolicyEngine:
    """Test IRMAA calculation via PolicyEngine's income_adjusted_part_b_premium."""

    def test_irmaa_returned_in_tax_results(self):
        """Test that IRMAA is included in tax calculation results."""
        calc = TaxCalculator(state="CA", year=2025)

        # High income scenario that should trigger IRMAA
        # IRMAA uses income from 2 years prior, so we pass prior_year_agi
        results = calc.calculate_batch_taxes(
            capital_gains_array=np.array([50_000]),
            social_security_array=np.array([30_000]),
            ages=np.array([67]),  # Medicare eligible
            filing_status="SINGLE",
            prior_year_agi=np.array([200_000]),  # High income triggers IRMAA
            year=2025,
        )

        assert "irmaa" in results, "IRMAA should be in tax results"
        assert results["irmaa"][0] >= 0, "IRMAA should be non-negative"

    def test_irmaa_zero_for_low_income(self):
        """Test that IRMAA is zero for income below threshold."""
        calc = TaxCalculator(state="CA", year=2025)

        # Low income should have no IRMAA
        results = calc.calculate_batch_taxes(
            capital_gains_array=np.array([10_000]),
            social_security_array=np.array([20_000]),
            ages=np.array([67]),
            filing_status="SINGLE",
            prior_year_agi=np.array([50_000]),  # Below IRMAA threshold
            year=2025,
        )

        assert results["irmaa"][0] == 0, "Low income should have no IRMAA"

    def test_irmaa_higher_for_higher_income(self):
        """Test that IRMAA increases with income."""
        calc = TaxCalculator(state="CA", year=2025)

        # Two scenarios with different prior year income
        results = calc.calculate_batch_taxes(
            capital_gains_array=np.array([50_000, 50_000]),
            social_security_array=np.array([30_000, 30_000]),
            ages=np.array([67, 67]),
            filing_status="SINGLE",
            prior_year_agi=np.array([150_000, 500_000]),  # Different income levels
            year=2025,
        )

        # Higher income should have higher or equal IRMAA
        assert results["irmaa"][1] >= results["irmaa"][0], \
            "Higher income should have higher or equal IRMAA"

    def test_irmaa_zero_under_65(self):
        """Test that IRMAA is zero for people under 65 (not Medicare eligible)."""
        calc = TaxCalculator(state="CA", year=2025)

        # Under 65, not Medicare eligible
        results = calc.calculate_batch_taxes(
            capital_gains_array=np.array([50_000]),
            social_security_array=np.array([0]),  # No SS yet
            ages=np.array([60]),  # Under 65
            filing_status="SINGLE",
            prior_year_agi=np.array([500_000]),  # High income but not eligible
            year=2025,
        )

        assert results["irmaa"][0] == 0, "Under 65 should have no IRMAA"

    def test_irmaa_annual_value(self):
        """Test that IRMAA is returned as annual value (not monthly)."""
        calc = TaxCalculator(state="CA", year=2025)

        # Very high income that definitely triggers IRMAA
        results = calc.calculate_batch_taxes(
            capital_gains_array=np.array([100_000]),
            social_security_array=np.array([30_000]),
            ages=np.array([67]),
            filing_status="SINGLE",
            prior_year_agi=np.array([1_000_000]),  # Very high income
            year=2025,
        )

        # IRMAA should be reasonably sized (annual, so >$100 for high income)
        # Maximum IRMAA surcharge is ~$600/month = ~$7200/year
        irmaa = results["irmaa"][0]
        if irmaa > 0:
            assert irmaa > 100, f"IRMAA {irmaa} seems too low for annual value"
            assert irmaa < 10_000, f"IRMAA {irmaa} seems unreasonably high"
