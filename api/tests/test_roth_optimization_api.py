"""Tests for Roth conversion optimization API endpoint."""

from fastapi.testclient import TestClient

import main
from eggnest.models import (
    HistoricalRothConversionSummary,
    Holding,
    RothConversionComparisonItem,
    RothConversionScenarioDelta,
    RothConversionScenarioSummary,
    RothOptimizationInput,
    RothOptimizationResult,
    SimulationInput,
)
from main import app

client = TestClient(app)


def make_base_params() -> SimulationInput:
    """Base holdings-driven scenario for Roth optimization."""
    return SimulationInput(
        annual_spending=48_000,
        social_security_monthly=2_000,
        current_age=60,
        max_age=72,
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,
        holdings=[
            Holding(
                account_type="taxable",
                fund="sp500",
                balance=250_000,
                cost_basis=180_000,
            ),
            Holding(account_type="traditional_ira", fund="sp500", balance=400_000),
            Holding(account_type="roth_ira", fund="treasury", balance=150_000),
        ],
        withdrawal_strategy="taxable_first",
    )


def make_result() -> RothOptimizationResult:
    """Sample Roth optimization result for API contract tests."""
    return RothOptimizationResult(
        results=[
            RothConversionComparisonItem(
                conversion_policy="fill_12_percent_bracket",
                scenario_label="Fill 12% bracket (ages 60-64)",
                annual_conversion_amount=None,
                conversion_start_age=60,
                conversion_end_age=64,
                monte_carlo=RothConversionScenarioSummary(
                    success_rate=0.93,
                    median_final_value=990_000,
                    median_final_value_real=435_000,
                    total_taxes_median=205_000,
                    total_medicare_premiums_median=15_500,
                    total_withdrawn_median=1_500_000,
                    total_roth_conversions_median=210_000,
                    year_breakdown=[],
                ),
                historical=HistoricalRothConversionSummary(
                    success_rate=0.8,
                    median_final_value=700_000,
                    median_final_value_real=280_000,
                    total_taxes_median=201_000,
                    total_medicare_premiums_median=14_800,
                    total_withdrawn_median=1_485_000,
                    total_roth_conversions_median=210_000,
                    cohort_count=42,
                    strongest_start_year=1982,
                    weakest_start_year=1966,
                    worst_final_value_real=95_000,
                ),
                blended_score=84.6,
                delta_vs_baseline=RothConversionScenarioDelta(
                    blended_score_delta=5.1,
                    monte_carlo_success_rate_delta=0.02,
                    historical_success_rate_delta=0.03,
                    monte_carlo_median_final_value_real_delta=40_000,
                    historical_median_final_value_real_delta=32_000,
                    monte_carlo_total_taxes_median_delta=18_000,
                    monte_carlo_total_medicare_premiums_median_delta=2_100,
                    monte_carlo_total_roth_conversions_median_delta=210_000,
                    historical_total_medicare_premiums_median_delta=1_800,
                    historical_worst_final_value_real_delta=20_000,
                ),
            )
        ],
        baseline_scenario_label="No annual conversion",
        baseline_conversion_amount=0,
        top_scoring_scenario_label="Fill 12% bracket (ages 60-64)",
        top_scoring_conversion_amount=None,
        lowest_modeled_tax_scenario_label="No annual conversion",
        lowest_modeled_tax_amount=0,
        strongest_historical_scenario_label="Fill 12% bracket (ages 60-64)",
        strongest_historical_conversion_amount=None,
        candidate_count=7,
        candidate_start_ages=[60, 65],
        window_lengths=[5, 10],
        lowest_medicare_premium_scenario_label="No annual conversion",
        lowest_medicare_premium_conversion_amount=0,
        highest_real_ending_wealth_scenario_label="Fill 12% bracket (ages 60-64)",
        highest_real_ending_wealth_conversion_amount=None,
        summary="Fill 12% bracket (ages 60-64) is the current score leader.",
    )


class TestRothOptimizationModels:
    """Test Roth optimization Pydantic models."""

    def test_roth_optimization_input_valid(self):
        optimization = RothOptimizationInput(
            base_input=make_base_params(),
            annual_conversion_amounts=[0, 25_000],
            candidate_start_ages=[60, 65],
            window_lengths=[5, 10],
        )
        assert optimization.base_input.holdings
        assert optimization.candidate_start_ages == [60, 65]

    def test_roth_optimization_result_model(self):
        result = make_result()
        assert result.candidate_count == 7
        assert result.top_scoring_scenario_label == "Fill 12% bracket (ages 60-64)"


class TestRothOptimizationEndpoint:
    """Test /optimize-roth-conversions API endpoint."""

    def test_optimize_roth_conversions_returns_results(self, monkeypatch):
        sample_result = make_result()
        monkeypatch.setattr(
            main,
            "_run_roth_optimization",
            lambda payload: sample_result.model_dump(mode="json"),
        )

        response = client.post(
            "/optimize-roth-conversions",
            json={
                "base_input": make_base_params().model_dump(),
                "candidate_start_ages": [60, 65],
                "window_lengths": [5, 10],
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["candidate_count"] == 7
        assert data["top_scoring_scenario_label"] == "Fill 12% bracket (ages 60-64)"
        assert data["lowest_medicare_premium_scenario_label"] == "No annual conversion"

    def test_optimize_roth_conversions_requires_holdings(self):
        no_holdings = SimulationInput(
            initial_capital=500_000,
            annual_spending=40_000,
            current_age=65,
            max_age=75,
            gender="male",
            state="CA",
            filing_status="single",
            n_simulations=100,
        )

        response = client.post(
            "/optimize-roth-conversions",
            json={"base_input": no_holdings.model_dump()},
        )
        assert response.status_code == 422
        assert "detailed holdings" in str(response.json()["detail"])

    def test_optimize_roth_conversions_requires_traditional_accounts(self):
        no_traditional = make_base_params().model_copy(
            update={
                "holdings": [
                    Holding(
                        account_type="taxable",
                        fund="sp500",
                        balance=250_000,
                        cost_basis=180_000,
                    ),
                    Holding(account_type="roth_ira", fund="treasury", balance=150_000),
                ]
            }
        )

        response = client.post(
            "/optimize-roth-conversions",
            json={"base_input": no_traditional.model_dump()},
        )
        assert response.status_code == 422
        assert "traditional account" in str(response.json()["detail"]).lower()

    def test_optimize_roth_conversions_honors_max_simulations(self, monkeypatch):
        monkeypatch.setattr(main.settings, "max_n_simulations", 50)

        response = client.post(
            "/optimize-roth-conversions",
            json={"base_input": make_base_params().model_dump()},
        )

        assert response.status_code == 400
        assert "n_simulations cannot exceed 50" in response.json()["detail"]

    def test_optimize_roth_conversions_returns_validation_error_for_invalid_search(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            main,
            "_run_roth_optimization",
            lambda payload: (_ for _ in ()).throw(ValueError("too many candidates")),
        )

        response = client.post(
            "/optimize-roth-conversions",
            json={"base_input": make_base_params().model_dump()},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "too many candidates"
