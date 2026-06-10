"""Tests for the experimental Axiom UK tax and benefits backend.

These run only when the Axiom rules engine and a rulespec-uk checkout are
configured (EGGNEST_AXIOM_ENGINE_BIN / EGGNEST_RULESPEC_UK_ROOT); they are
skipped otherwise, e.g. in CI until the engine is provisioned there.
"""

import numpy as np
import pytest

from eggnest import axiom_uk
from eggnest.tax_uk import UKYearInputs, calculate_uk_tax

pytestmark = pytest.mark.skipif(
    not axiom_uk.available(),
    reason="Axiom rules engine not configured",
)


def _inputs(**overrides) -> UKYearInputs:
    base = {
        "age": 60,
        "year": 2025,
        "state_pension": np.zeros(1),
        "private_pension_income": np.zeros(1),
        "savings_interest": np.zeros(1),
        "dividend_income": np.zeros(1),
        "employment_income": np.zeros(1),
    }
    base.update(overrides)
    return UKYearInputs(**base)


class TestStatutoryExactness:
    """Hand-computed ITA 2007 / SSCBA 1992 results, to the pound."""

    def test_basic_rate_pension_income(self):
        # 31,502 income - 12,570 PA = 18,932 at 20% = 3,786.40
        result = axiom_uk.calculate_uk_tax_axiom(
            _inputs(
                age=70,
                state_pension=np.array([11_502.0]),
                private_pension_income=np.array([20_000.0]),
            )
        )
        assert result.total_tax[0] == pytest.approx(3_786.40, abs=0.01)

    def test_higher_rate_pension_income(self):
        # 71,502 - 12,570 = 58,932: 37,700@20% + 21,232@40% = 16,032.80
        result = axiom_uk.calculate_uk_tax_axiom(
            _inputs(
                age=70,
                state_pension=np.array([11_502.0]),
                private_pension_income=np.array([60_000.0]),
            )
        )
        assert result.total_tax[0] == pytest.approx(16_032.80, abs=0.01)

    def test_personal_allowance_taper(self):
        # 110,000 income: PA = 12,570 - (110,000-100,000)/2 = 7,570.
        # Taxable 102,430: 37,700@20% + 64,730@40% = 33,432.
        result = axiom_uk.calculate_uk_tax_axiom(
            _inputs(age=60, private_pension_income=np.array([110_000.0]))
        )
        assert result.total_tax[0] == pytest.approx(33_432.0, abs=0.01)

    def test_employment_income_with_ni_under_pension_age(self):
        # IT: (40,000-12,570)@20% = 5,486.
        # NI: (40,000/52 - 241.73)@8% * 52 = (769.23-241.73)*0.08*52 = 2,194.40
        result = axiom_uk.calculate_uk_tax_axiom(
            _inputs(age=45, employment_income=np.array([40_000.0]))
        )
        assert result.total_tax[0] == pytest.approx(5_486.0 + 2_194.40, abs=0.5)

    def test_no_employee_ni_over_pension_age(self):
        # SSCBA 1992 s.6(3): no primary contributions over pensionable age.
        result = axiom_uk.calculate_uk_tax_axiom(
            _inputs(age=70, employment_income=np.array([40_000.0]))
        )
        assert result.total_tax[0] == pytest.approx(5_486.0, abs=0.01)

    def test_dividends_stack_above_other_income(self):
        # Non-savings 50,000 - PA = 37,430 (basic band nearly full).
        # Dividends 5,000: 270 within basic @8.75% + 4,730 @33.75%.
        result = axiom_uk.calculate_uk_tax_axiom(
            _inputs(
                age=60,
                private_pension_income=np.array([50_000.0]),
                dividend_income=np.array([5_000.0]),
            )
        )
        expected_it = 37_430 * 0.20
        expected_div = 270 * 0.0875 + 4_730 * 0.3375
        assert result.total_tax[0] == pytest.approx(
            expected_it + expected_div, abs=0.01
        )


class TestPolicyEngineAgreement:
    """Both engines agree exactly on the gap-free scenario class:
    under pension age, no dividends, no savings interest."""

    @pytest.mark.parametrize(
        "employment,pension",
        [(0.0, 20_000.0), (0.0, 60_000.0), (30_000.0, 0.0), (60_000.0, 0.0)],
    )
    def test_under_spa_no_dividends(self, employment, pension):
        inputs = _inputs(
            age=60,
            employment_income=np.array([employment]),
            private_pension_income=np.array([pension]),
        )
        axiom = axiom_uk.calculate_uk_tax_axiom(inputs).total_tax[0]
        pe = calculate_uk_tax(inputs).total_tax[0]
        assert axiom == pytest.approx(pe, abs=1.0)


class TestPensionCreditScreen:
    def test_guarantee_credit_tops_up_to_minimum(self):
        screen = axiom_uk.pension_credit_screen(
            year=2025, ages=np.array([70]), annual_income=np.array([6_000.0])
        )
        weekly = screen["weekly_minimum_guarantee"]
        assert weekly > 200  # encoded SMG for a single claimant
        assert screen["annual_amount"][0] == pytest.approx(
            weekly * 52 - 6_000.0, abs=0.01
        )

    def test_no_credit_above_minimum_guarantee(self):
        screen = axiom_uk.pension_credit_screen(
            year=2025, ages=np.array([70]), annual_income=np.array([20_000.0])
        )
        assert screen["annual_amount"][0] == 0.0

    def test_not_entitled_under_qualifying_age(self):
        screen = axiom_uk.pension_credit_screen(
            year=2025, ages=np.array([60]), annual_income=np.array([0.0])
        )
        assert screen["annual_amount"][0] == 0.0
        assert screen["citations"] == []

    def test_mixed_ages_masked_by_qualifying_age(self):
        screen = axiom_uk.pension_credit_screen(
            year=2025,
            ages=np.array([60, 66, 75]),
            annual_income=np.array([0.0, 6_000.0, 50_000.0]),
        )
        amounts = screen["annual_amount"]
        assert amounts[0] == 0.0  # under qualifying age
        assert amounts[1] > 0  # low income, qualifying age
        assert amounts[2] == 0.0  # income above the minimum guarantee

    def test_citations_point_at_legislation(self):
        screen = axiom_uk.pension_credit_screen(
            year=2025, ages=np.array([70]), annual_income=np.array([6_000.0])
        )
        urls = {citation.url for citation in screen["citations"]}
        assert any("legislation.gov.uk/ukpga/2002/16" in url for url in urls)
        assert any("legislation.gov.uk/uksi/2002/1792" in url for url in urls)

    def test_simulation_populates_screen_for_modest_retiree(self):
        from eggnest.models_uk import UKSimulationInput
        from eggnest.simulation_uk import run_uk_simulation

        result = run_uk_simulation(
            UKSimulationInput(
                current_age=66,
                max_age=75,
                isa_balance=20_000,
                sipp_balance=30_000,
                gia_balance=0,
                annual_spending=14_000,
                state_pension_annual=6_000,  # partial NI record
                n_simulations=100,
                random_seed=11,
                include_mortality=False,
            )
        )
        screen = result.pension_credit
        assert screen is not None
        assert screen.years_indicated > 0
        assert len(screen.annual_amounts) == len(result.year_breakdown)
        assert any(
            citation.url.startswith("https://www.legislation.gov.uk")
            for citation in screen.citations
        )


class TestEngineSeam:
    def test_default_backend_is_policyengine(self, monkeypatch):
        from eggnest.tax_uk import get_uk_tax_calculator

        monkeypatch.delenv("EGGNEST_UK_TAX_ENGINE", raising=False)
        assert get_uk_tax_calculator() is calculate_uk_tax

    def test_axiom_backend_selected(self, monkeypatch):
        from eggnest.tax_uk import get_uk_tax_calculator

        monkeypatch.setenv("EGGNEST_UK_TAX_ENGINE", "axiom")
        assert get_uk_tax_calculator() is axiom_uk.calculate_uk_tax_axiom

    def test_citations_available_for_tax_rules(self):
        citations = axiom_uk.tax_citations(2025)
        urls = {citation.url for citation in citations}
        assert any("ukpga/2007/3/section/35" in url for url in urls)
        assert len(citations) >= 5
