"""Tests for withdrawal strategy comparison API endpoint."""

import pytest
from fastapi.testclient import TestClient

import main
from eggnest.models import (
    HistoricalStrategySummary,
    Holding,
    SimulationInput,
    StrategyComparisonInput,
    StrategyComparisonItem,
    StrategyComparisonResult,
    StrategyScenarioSummary,
)
from main import app

client = TestClient(app)


@pytest.fixture
def base_params():
    """Base holdings-driven scenario for strategy comparison."""
    return SimulationInput(
        annual_spending=48_000,
        social_security_monthly=2_000,
        current_age=65,
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


@pytest.fixture
def stub_strategy_batches(monkeypatch):
    """Stub Monte Carlo and historical summaries for contract tests."""
    monte_carlo_profiles = {
        "taxable_first": {
            "success_rate": 0.93,
            "median_final_value": 990_000,
            "median_final_value_real": 435_000,
            "total_taxes_median": 205_000,
            "total_withdrawn_median": 1_500_000,
        },
        "traditional_first": {
            "success_rate": 0.88,
            "median_final_value": 930_000,
            "median_final_value_real": 400_000,
            "total_taxes_median": 240_000,
            "total_withdrawn_median": 1_500_000,
        },
        "roth_first": {
            "success_rate": 0.84,
            "median_final_value": 910_000,
            "median_final_value_real": 385_000,
            "total_taxes_median": 198_000,
            "total_withdrawn_median": 1_500_000,
        },
        "pro_rata": {
            "success_rate": 0.9,
            "median_final_value": 955_000,
            "median_final_value_real": 415_000,
            "total_taxes_median": 220_000,
            "total_withdrawn_median": 1_500_000,
        },
    }
    historical_profiles = {
        "taxable_first": {
            "success_rate": 0.8,
            "median_final_value": 700_000,
            "median_final_value_real": 280_000,
            "total_taxes_median": 201_000,
            "total_withdrawn_median": 1_485_000,
            "cohort_count": 42,
            "strongest_start_year": 1982,
            "weakest_start_year": 1966,
            "worst_final_value_real": 95_000,
        },
        "traditional_first": {
            "success_rate": 0.7,
            "median_final_value": 610_000,
            "median_final_value_real": 220_000,
            "total_taxes_median": 235_000,
            "total_withdrawn_median": 1_480_000,
            "cohort_count": 42,
            "strongest_start_year": 1982,
            "weakest_start_year": 1973,
            "worst_final_value_real": 40_000,
        },
        "roth_first": {
            "success_rate": 0.68,
            "median_final_value": 590_000,
            "median_final_value_real": 205_000,
            "total_taxes_median": 196_000,
            "total_withdrawn_median": 1_478_000,
            "cohort_count": 42,
            "strongest_start_year": 1982,
            "weakest_start_year": 1973,
            "worst_final_value_real": 35_000,
        },
        "pro_rata": {
            "success_rate": 0.75,
            "median_final_value": 650_000,
            "median_final_value_real": 245_000,
            "total_taxes_median": 214_000,
            "total_withdrawn_median": 1_482_000,
            "cohort_count": 42,
            "strongest_start_year": 1982,
            "weakest_start_year": 1969,
            "worst_final_value_real": 62_000,
        },
    }

    async def fake_simulation_batch(inputs):
        return [
            monte_carlo_profiles[params.withdrawal_strategy]
            for params in inputs
        ]

    async def fake_historical_batch(inputs):
        return [
            historical_profiles[params.withdrawal_strategy]
            for params in inputs
        ]

    monkeypatch.setattr(main, "_run_simulation_batch", fake_simulation_batch)
    monkeypatch.setattr(main, "_run_historical_backtest_batch", fake_historical_batch)


class TestStrategyComparisonModels:
    """Test strategy comparison Pydantic models."""

    def test_strategy_comparison_input_valid(self, base_params):
        comparison = StrategyComparisonInput(
            base_input=base_params,
            strategies=["taxable_first", "pro_rata"],
        )
        assert comparison.base_input.holdings
        assert comparison.strategies == ["taxable_first", "pro_rata"]

    def test_strategy_comparison_result_model(self):
        result = StrategyComparisonResult(
            results=[
                StrategyComparisonItem(
                    strategy="taxable_first",
                    monte_carlo=StrategyScenarioSummary(
                        success_rate=0.92,
                        median_final_value=980_000,
                        median_final_value_real=430_000,
                        total_taxes_median=205_000,
                        total_withdrawn_median=1_500_000,
                    ),
                    historical=HistoricalStrategySummary(
                        success_rate=0.8,
                        median_final_value=700_000,
                        median_final_value_real=280_000,
                        total_taxes_median=201_000,
                        total_withdrawn_median=1_485_000,
                        cohort_count=42,
                        strongest_start_year=1982,
                        weakest_start_year=1966,
                        worst_final_value_real=95_000,
                    ),
                    blended_score=84.6,
                )
            ],
            top_scoring_strategy="taxable_first",
            lowest_modeled_tax_strategy="taxable_first",
            strongest_historical_strategy="taxable_first",
            summary="Taxable first leads this scorecard after weighting Monte Carlo success at 35%, historical success at 35%, weakest historical cohort at 15%, median real ending wealth at 10%, and lower modeled taxes at 5%.",
        )
        assert result.results[0].strategy == "taxable_first"
        assert result.top_scoring_strategy == "taxable_first"


class TestStrategyComparisonEndpoint:
    """Test /compare-withdrawal-strategies API endpoint."""

    @pytest.mark.montecarlo_smoke
    def test_compare_withdrawal_strategies_returns_results(self, base_params):
        response = client.post(
            "/compare-withdrawal-strategies",
            json={"base_input": base_params.model_dump()},
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data["results"]) == 4
        assert "top_scoring_strategy" in data

    def test_compare_withdrawal_strategies_requires_holdings(self):
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
            "/compare-withdrawal-strategies",
            json={"base_input": no_holdings.model_dump()},
        )
        assert response.status_code == 400
        assert "detailed holdings" in response.json()["detail"]

    def test_compare_withdrawal_strategies_result_fields(
        self, base_params, stub_strategy_batches
    ):
        response = client.post(
            "/compare-withdrawal-strategies",
            json={"base_input": base_params.model_dump()},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["top_scoring_strategy"] == "taxable_first"
        assert data["strongest_historical_strategy"] == "taxable_first"
        assert data["lowest_modeled_tax_strategy"] == "roth_first"
        assert data["summary"]

        first = data["results"][0]
        assert "monte_carlo" in first
        assert "historical" in first
        assert "blended_score" in first
        assert first["historical"]["cohort_count"] == 42

    def test_compare_withdrawal_strategies_deduplicates_requested_strategies(
        self, base_params, stub_strategy_batches
    ):
        response = client.post(
            "/compare-withdrawal-strategies",
            json={
                "base_input": base_params.model_dump(),
                "strategies": ["taxable_first", "taxable_first", "pro_rata"],
            },
        )
        assert response.status_code == 200

        data = response.json()
        strategies = [result["strategy"] for result in data["results"]]
        assert strategies == ["taxable_first", "pro_rata"]
