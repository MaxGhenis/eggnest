"""Tests for the experimental Axiom UK tax and benefits backend.

These need the Axiom rules engine and a rulespec-uk checkout
(EGGNEST_AXIOM_ENGINE_BIN / EGGNEST_RULESPEC_UK_ROOT). Locally they skip
when those are absent; CI installs the pinned engine and sets
EGGNEST_REQUIRE_AXIOM=1, which turns a missing engine into a failure
instead of a silent skip. Engine-free wiring tests live in
test_axiom_uk_wiring.py.
"""

import os

import numpy as np
import pytest

from eggnest import axiom_uk
from eggnest.tax_uk import UKYearInputs, calculate_uk_tax

REQUIRED = os.environ.get("EGGNEST_REQUIRE_AXIOM") == "1"

pytestmark = pytest.mark.skipif(
    not REQUIRED and not axiom_uk.available(),
    reason="Axiom rules engine not configured",
)


def test_engine_is_available():
    """Fails (rather than skipping the module) when CI requires the engine
    but it is missing or incompatible."""
    assert axiom_uk.available()


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
        # Dividends 5,000: the first 500 at the s.13A nil rate (270 of it in
        # the basic band, 230 in higher), then 4,500 @33.75%.
        result = axiom_uk.calculate_uk_tax_axiom(
            _inputs(
                age=60,
                private_pension_income=np.array([50_000.0]),
                dividend_income=np.array([5_000.0]),
            )
        )
        expected_it = 37_430 * 0.20
        expected_div = 4_500 * 0.3375
        assert result.total_tax[0] == pytest.approx(
            expected_it + expected_div, abs=0.01
        )

    def test_dividend_only_income_with_pa_spill(self):
        # ITA 2007 s.25(2): unused personal allowance spills onto dividends.
        # 20,000 dividends - 12,570 PA = 7,430 taxable: 500 at the s.13A nil
        # rate, then 6,930 at 8.75% = 606.375.
        result = axiom_uk.calculate_uk_tax_axiom(
            _inputs(age=60, dividend_income=np.array([20_000.0]))
        )
        assert result.total_tax[0] == pytest.approx(606.38, abs=0.01)

    def test_savings_starting_rate_and_allowance(self):
        # ITA 2007 ss.12-12B (encoded in rulespec-uk): taxable savings 7,430
        # = 5,000 at the starting rate (0%) + 1,000 personal savings
        # allowance (0%) + 1,430 at 20% = 286.
        result = axiom_uk.calculate_uk_tax_axiom(
            _inputs(age=60, savings_interest=np.array([20_000.0]))
        )
        assert result.total_tax[0] == pytest.approx(286.0, abs=0.01)


class TestPolicyEngineAgreement:
    """Both engines agree exactly on the gap-free scenario class:
    under pension age, no dividends, no savings interest."""

    @pytest.mark.parametrize(
        "employment,pension,savings,dividends",
        [
            (0.0, 20_000.0, 0.0, 0.0),
            (0.0, 60_000.0, 0.0, 0.0),
            (30_000.0, 0.0, 0.0, 0.0),
            (60_000.0, 0.0, 0.0, 0.0),
            # Savings allowances (ITA ss.12-12B) agree across engines.
            (0.0, 30_000.0, 2_000.0, 0.0),
            (0.0, 60_000.0, 2_000.0, 0.0),
            (0.0, 20_000.0, 20_000.0, 0.0),
            # Dividend nil rate agrees when it does not straddle a band edge.
            (0.0, 15_000.0, 0.0, 5_000.0),
            (0.0, 0.0, 0.0, 20_000.0),
            (0.0, 110_000.0, 0.0, 5_000.0),
        ],
    )
    def test_under_spa_agreement(self, employment, pension, savings, dividends):
        inputs = _inputs(
            age=60,
            employment_income=np.array([employment]),
            private_pension_income=np.array([pension]),
            savings_interest=np.array([savings]),
            dividend_income=np.array([dividends]),
        )
        axiom = axiom_uk.calculate_uk_tax_axiom(inputs).total_tax[0]
        pe = calculate_uk_tax(inputs).total_tax[0]
        assert axiom == pytest.approx(pe, abs=1.0)


class TestPensionCreditScreen:
    """SPC Act 2002 s.2 with SI 2002/1792 regs 6 and 15(6), via the engine."""

    def _screen(self, weekly_income, capital):
        return axiom_uk.pension_credit_screen(
            year=2026,
            weekly_income=np.array(weekly_income, dtype=float),
            capital=np.array(capital, dtype=float),
        )

    def test_guarantee_credit_tops_up_to_minimum(self):
        screen = self._screen([100.0], [0.0])
        weekly = screen["weekly_minimum_guarantee"]
        assert weekly == pytest.approx(238.0)  # reg 6, single claimant
        assert screen["annual_amount"][0] == pytest.approx(
            (weekly - 100.0) * 52, abs=0.01
        )

    def test_no_credit_above_minimum_guarantee(self):
        assert self._screen([300.0], [0.0])["annual_amount"][0] == 0.0

    def test_capital_is_deemed_to_yield_income(self):
        """reg 15(6): £1 a week for each £500, or part, above £10,000."""
        screen = self._screen([0.0] * 6, [0, 10_000, 10_000.01, 10_501, 25_000, 1e6])
        assert list(screen["weekly_deemed_income"]) == [0, 0, 1, 2, 30, 1_980]
        weekly = screen["weekly_minimum_guarantee"]
        expected = [max(weekly - tariff, 0) * 52 for tariff in [0, 0, 1, 2, 30, 1_980]]
        assert screen["annual_amount"] == pytest.approx(expected, abs=0.01)

    def test_large_savings_rule_out_credit(self):
        """A retiree on a small State Pension but with £200,000 in an ISA is
        deemed to have £380 a week, above the minimum guarantee."""
        screen = self._screen([150.0, 150.0], [0.0, 200_000.0])
        assert screen["annual_amount"][0] > 0
        assert screen["annual_amount"][1] == 0.0

    def test_citations_point_at_legislation(self):
        urls = {citation.url for citation in self._screen([0.0], [20_000])["citations"]}
        assert any("legislation.gov.uk/ukpga/2002/16" in url for url in urls)
        assert any(
            "legislation.gov.uk/uksi/2002/1792/regulation/6" in url for url in urls
        )
        assert any(
            "legislation.gov.uk/uksi/2002/1792/regulation/15" in url for url in urls
        )

    def test_simulation_screens_a_modest_retiree(self):
        from eggnest.models_uk import UKSimulationInput
        from eggnest.simulation_uk import run_uk_simulation

        result = run_uk_simulation(
            UKSimulationInput(
                current_age=67,
                max_age=75,
                isa_balance=5_000,
                sipp_balance=0,
                gia_balance=0,
                annual_spending=9_000,
                state_pension_annual=6_000,  # partial NI record
                n_simulations=100,
                random_seed=11,
                include_mortality=False,
            )
        )
        screen = result.pension_credit
        assert screen is not None
        assert screen.status == "screened"
        assert screen.weekly_minimum_guarantee == pytest.approx(238.0)
        # £6,000 of State Pension is £115 a week, well under £238, and £5,000
        # of savings is under the £10,000 threshold: every year is indicated.
        assert screen.share_of_paths_indicated == 1.0
        assert all(share == 1.0 for share in screen.share_indicated_by_age)
        assert screen.ages == list(range(67, 76))
        assert screen.median_annual_amount_by_age[-1] == pytest.approx(
            (238.0 - 6_000 / 52) * 52, abs=1.0
        )
        assert any(
            citation.url.startswith("https://www.legislation.gov.uk")
            for citation in screen.citations
        )

    def test_simulation_reports_under_qualifying_age(self):
        from eggnest.models_uk import UKSimulationInput
        from eggnest.simulation_uk import run_uk_simulation

        result = run_uk_simulation(
            UKSimulationInput(
                current_age=40,
                max_age=60,
                isa_balance=0,
                sipp_balance=0,
                annual_spending=0,
                state_pension_annual=0,
                n_simulations=100,
                random_seed=1,
                include_mortality=False,
            )
        )
        screen = result.pension_credit
        assert screen is not None
        assert screen.status == "under_qualifying_age"
        assert (screen.qualifying_age_years, screen.qualifying_age_months) == (68, 0)
        assert screen.weekly_minimum_guarantee is None
        assert screen.ages == []


class TestEngineCitations:
    def test_citations_available_for_tax_rules(self):
        citations = axiom_uk.tax_citations(2025)
        urls = {citation.url for citation in citations}
        assert any("ukpga/2007/3/section/35" in url for url in urls)
        assert len(citations) >= 5
