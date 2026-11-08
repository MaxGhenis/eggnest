"""The one-year UK drawdown calculator on the real rules engine.

These need the Axiom rules engine and a rulespec-uk checkout
(EGGNEST_AXIOM_ENGINE_BIN / EGGNEST_RULESPEC_UK_ROOT). Locally they skip when
those are absent; CI installs the pinned engine and sets
EGGNEST_REQUIRE_AXIOM=1, which turns a missing engine into a failure.

The expected figures are calculated by hand from the statutory rates:
- 2026/27 Personal Allowance £12,570; basic rate band £37,700.
- Standard minimum guarantee £238.00 a week (SI 2002/1792 reg 6).
- Ordinary and upper dividend rates of 10.75% and 35.75% from 2026-27
  (Income Tax Act 2007 s.8 as amended by Finance Act 2026 s.4).
"""

from __future__ import annotations

import os
from datetime import date

import numpy as np
import pytest

from eggnest import axiom_uk
from eggnest.core.uk_drawdown_year import (
    build_uk_drawdown_year_scenario,
    extract_uk_drawdown_year_result,
    run_uk_drawdown_year_scenario,
)
from eggnest.drawdown_uk import run_uk_drawdown_year
from eggnest.models_uk_drawdown import UKDrawdownYearInput
from eggnest.tax_uk import UKYearInputs, calculate_uk_tax

REQUIRED = os.environ.get("EGGNEST_REQUIRE_AXIOM") == "1"

pytestmark = pytest.mark.skipif(
    not REQUIRED and not axiom_uk.available(),
    reason="Axiom rules engine not configured",
)

BORN = date(1958, 6, 15)  # 67 on 6 April 2026


def test_engine_is_available():
    assert axiom_uk.available()


def _inputs(**overrides) -> UKYearInputs:
    base = {
        "age": 67,
        "year": 2026,
        "state_pension": np.zeros(1),
        "private_pension_income": np.zeros(1),
        "savings_interest": np.zeros(1),
        "dividend_income": np.zeros(1),
        "employment_income": np.zeros(1),
    }
    return UKYearInputs(**{**base, **overrides})


class TestScenariosByHand:
    def test_small_pot_regular_draw(self):
        # Draw £2,500 from £20,000. £180 + £48.08 = £228.08 counted, so
        # credit of £9.92 a week. Taxable £11,235 sits below the allowance.
        result = run_uk_drawdown_year(
            UKDrawdownYearInput(
                birth_date=BORN,
                state_pension=9_360.0,
                sipp_balance=20_000.0,
                draw_amount=2_500.0,
            )
        )
        assert result.income_tax.amount == 0.0
        assert result.pension_credit.amount == pytest.approx(516.0, abs=0.01)
        assert result.money_to_spend == pytest.approx(12_376.0, abs=0.01)
        # With no draw: £180 + £30.77 notional, so £27.23 a week.
        assert result.with_no_draw.pension_credit == pytest.approx(1_416.0, abs=0.01)
        assert result.pension_credit_working.annuity_income_per_1000 == 80.0

    def test_turning_points_land_on_the_pound(self):
        result = run_uk_drawdown_year(
            UKDrawdownYearInput(
                birth_date=BORN,
                state_pension=9_360.0,
                sipp_balance=20_000.0,
                draw_amount=2_500.0,
            )
        )
        edges = [round(b.draw_to) for b in result.bands]
        # Annuity income, credit gone at £180 + D/52 = £238, then tax once
        # 0.75 D passes the £3,210 of allowance left.
        assert edges == [1_600, 3_016, 4_280, 20_000]
        assert [round(b.kept, 2) for b in result.bands] == [1.0, 0.0, 1.0, 0.85]

    def test_same_draw_taken_as_a_one_off(self):
        # DMG 85457-85458: capital, and the pot is re-valued at £17,500.
        result = run_uk_drawdown_year(
            UKDrawdownYearInput(
                birth_date=BORN,
                state_pension=9_360.0,
                sipp_balance=20_000.0,
                draw_amount=2_500.0,
                sipp_draw_pattern="one_off",
            )
        )
        assert result.pension_credit.amount == pytest.approx(1_616.0, abs=0.01)
        assert result.money_to_spend == pytest.approx(13_476.0, abs=0.01)

    def test_savings_draw_spreads_deemed_income_over_the_year(self):
        result = run_uk_drawdown_year(
            UKDrawdownYearInput(
                birth_date=BORN,
                state_pension=9_360.0,
                isa_balance=30_000.0,
                draw_source="isa",
                draw_amount=15_000.0,
            )
        )
        working = result.pension_credit_working
        assert working.deemed_income_first_week == 40.0
        assert working.deemed_income_last_week == 11.0
        assert result.income_tax.amount == 0.0
        # With no draw: £20,000 over £10,000 deems £40 a week, £18 of credit.
        assert result.with_no_draw.pension_credit == pytest.approx(936.0, abs=0.01)

    def test_large_pot_full_new_state_pension(self):
        result = run_uk_drawdown_year(
            UKDrawdownYearInput(
                birth_date=BORN,
                state_pension=12_547.60,
                sipp_balance=400_000.0,
                draw_amount=30_000.0,
            )
        )
        # (£12,547.60 + £22,500 - £12,570) x 20%
        assert result.income_tax.amount == pytest.approx(4_495.52, abs=0.01)
        assert result.pension_credit.amount == 0.0
        assert result.money_to_spend == pytest.approx(38_052.08, abs=0.01)
        edges = [b.draw_to for b in result.bands]
        # 0.75 D reaches the higher-rate threshold at D = £50,296.53.
        assert any(abs(edge - 50_296.53) <= 3 for edge in edges)
        # And the Personal Allowance taper at D = £116,603.20.
        assert any(abs(edge - 116_603.20) <= 3 for edge in edges)

    def test_employee_ni_stops_at_state_pension_age(self):
        # 66th birthday on 15 June 2026; qualifying date in the same year.
        younger = run_uk_drawdown_year(
            UKDrawdownYearInput(
                birth_date=date(1960, 6, 15),
                state_pension=0.0,
                employment_income=30_000.0,
            )
        )
        past_spa = run_uk_drawdown_year(
            UKDrawdownYearInput(
                birth_date=BORN, state_pension=0.0, employment_income=30_000.0
            )
        )
        assert past_spa.employee_ni.amount == 0.0
        assert younger.employee_ni.amount > 0.0


class TestEnvelope:
    def test_citations_come_from_the_engine_traces(self):
        inputs = UKDrawdownYearInput(
            birth_date=BORN,
            state_pension=9_360.0,
            sipp_balance=20_000.0,
            draw_amount=2_500.0,
        )
        envelope = run_uk_drawdown_year_scenario(
            build_uk_drawdown_year_scenario(inputs)
        )
        result = extract_uk_drawdown_year_result(envelope)
        assert any("legislation.gov.uk" in c.url for c in envelope.citations)
        assert any(
            "regulation/6" in ref.url or "reg 6" in ref.id
            for ref in result.pension_credit.citations
        )
        versions = envelope.reproducibility.tax_engine_versions
        assert versions["axiom-rules-engine"]
        assert versions["rulespec-uk"]


class TestDividendRates:
    """Finance Act 2026 s.4 raised two of the three rates from 2026-27."""

    def test_ordinary_rate_2026_27(self):
        # £20,000 dividends: £12,570 allowance, £500 nil rate, £6,930 at 10.75%.
        tax = axiom_uk.calculate_uk_tax_axiom(
            _inputs(dividend_income=np.array([20_000.0]))
        ).income_tax[0]
        assert tax == pytest.approx(744.98, abs=0.01)

    def test_upper_rate_2026_27(self):
        # £80,000: £37,200 at 10.75% after the nil rate, £29,730 at 35.75%.
        tax = axiom_uk.calculate_uk_tax_axiom(
            _inputs(dividend_income=np.array([80_000.0]))
        ).income_tax[0]
        assert tax == pytest.approx(3_999.0 + 10_628.48, abs=0.01)

    def test_earlier_years_keep_the_old_rates(self):
        tax = axiom_uk.calculate_uk_tax_axiom(
            _inputs(year=2025, dividend_income=np.array([20_000.0]))
        ).income_tax[0]
        assert tax == pytest.approx(606.38, abs=0.01)


class TestShareOfYearOverStatePensionAge:
    def test_the_caller_can_set_the_share(self):
        earnings = np.array([30_000.0])
        full = axiom_uk.calculate_uk_tax_axiom(
            _inputs(age=60, employment_income=earnings, share_of_year_over_spa=0.0)
        ).employee_ni[0]
        half = axiom_uk.calculate_uk_tax_axiom(
            _inputs(age=60, employment_income=earnings, share_of_year_over_spa=0.5)
        ).employee_ni[0]
        none = axiom_uk.calculate_uk_tax_axiom(
            _inputs(age=60, employment_income=earnings, share_of_year_over_spa=1.0)
        ).employee_ni[0]
        assert full > 0.0
        assert half == pytest.approx(full * 0.5, abs=0.01)
        assert none == 0.0


class TestAgainstCompiledEngine:
    """Two implementations of the same income tax must agree for 2026/27.

    Dividends are left out: policyengine-uk-compiled still applies the
    2025/26 dividend rates to 2026/27.
    """

    @staticmethod
    def tax_both_ways(draws, interest):
        n = len(draws)
        inputs = _inputs(
            state_pension=np.full(n, 12_547.60),
            private_pension_income=draws,
            savings_interest=np.full(n, interest),
            dividend_income=np.zeros(n),
            employment_income=np.full(n, 8_000.0),
        )
        return (
            axiom_uk.calculate_uk_tax_axiom(inputs).income_tax,
            calculate_uk_tax(inputs).income_tax,
        )

    def test_income_tax_matches_across_draws(self):
        axiom, compiled = self.tax_both_ways(np.arange(0.0, 200_001.0, 500.0), 0.0)
        assert np.max(np.abs(axiom - compiled)) <= 1.0

    def test_income_tax_matches_with_interest_clear_of_the_thresholds(self):
        # Total income stays clear of £50,270 and £125,140 by more than the
        # interest, where the engines part ways (see the next test).
        draws = np.concatenate(
            [np.arange(0.0, 27_001.0, 500.0), np.arange(32_000.0, 100_001.0, 500.0)]
        )
        axiom, compiled = self.tax_both_ways(draws, 1_500.0)
        assert np.max(np.abs(axiom - compiled)) <= 1.0

    def test_savings_allowance_where_interest_straddles_the_threshold(self):
        # An intended difference from the compiled engine. ITA 2007 s.12B(8)
        # counts income that would be higher-rate but for the savings nil
        # rate, so £49,000 pension and £1,500 interest get the £500 allowance.
        # Pension: £36,430 x 20%. Interest: £500 nil, £770 at 20%, £230 at 40%.
        tax = axiom_uk.calculate_uk_tax_axiom(
            _inputs(
                private_pension_income=np.array([49_000.0]),
                savings_interest=np.array([1_500.0]),
            )
        ).income_tax[0]
        assert tax == pytest.approx(7_286.0 + 154.0 + 92.0, abs=0.01)
