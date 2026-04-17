"""Tests for annuity comparison API endpoint."""

from fastapi.testclient import TestClient

import main
from eggnest.models import (
    AnnuityComparison,
    AnnuityComparisonResult,
    SimulationInput,
    SimulationResult,
)
from main import app

client = TestClient(app)


def _make_simulation_result() -> SimulationResult:
    return SimulationResult(
        success_rate=0.9,
        median_final_value=900_000,
        mean_final_value=940_000,
        median_final_value_real=420_000,
        mean_final_value_real=450_000,
        percentiles={"p5": 120_000, "p25": 450_000, "p50": 900_000, "p75": 1_300_000, "p95": 1_900_000},
        percentiles_real={"p5": 60_000, "p25": 220_000, "p50": 420_000, "p75": 610_000, "p95": 860_000},
        median_depletion_age=None,
        median_depletion_year=None,
        total_withdrawn_median=1_500_000,
        total_taxes_median=205_000,
        percentile_paths={"p5": [500_000], "p25": [500_000], "p50": [500_000], "p75": [500_000], "p95": [500_000]},
        year_breakdown=[],
        initial_withdrawal_rate=4.0,
        prob_10_year_failure=0.08,
    )


def _make_base_input() -> SimulationInput:
    return SimulationInput(
        initial_capital=500_000,
        annual_spending=40_000,
        current_age=65,
        max_age=80,
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,
    )


class FakeSimulator:
    def __init__(self, _params):
        self._total_withdrawn = None
        self._total_taxes = None

    def run(self):
        return _make_simulation_result()


class TestAnnuityComparisonModels:
    """Test annuity comparison Pydantic models."""

    def test_annuity_comparison_result_model(self):
        result = AnnuityComparisonResult(
            simulation_result=_make_simulation_result(),
            annuity_total_guaranteed=360_000,
            probability_simulation_beats_annuity=0.64,
            simulation_median_total_income=410_000,
            summary="The portfolio path exceeds the annuity in a high share of modeled outcomes while keeping depletion risk relatively low.",
        )
        assert result.annuity_total_guaranteed == 360_000
        assert "portfolio path exceeds the annuity" in result.summary.lower()


class TestAnnuityComparisonEndpoint:
    """Test /compare-annuity API endpoint."""

    def test_compare_annuity_returns_summary(self, monkeypatch):
        monkeypatch.setattr(main, "MonteCarloSimulator", FakeSimulator)
        monkeypatch.setattr(
            main,
            "compare_to_annuity",
            lambda **_: {
                "annuity_total_guaranteed": 360_000,
                "probability_simulation_beats_annuity": 0.64,
                "simulation_median_total_income": 410_000,
                "summary": "The portfolio path exceeds the annuity in a high share of modeled outcomes while keeping depletion risk relatively low.",
            },
        )

        comparison = AnnuityComparison(
            simulation_input=_make_base_input(),
            annuity_monthly_payment=1_500,
            annuity_guarantee_years=20,
        )

        response = client.post("/compare-annuity", json=comparison.model_dump(mode="json"))
        assert response.status_code == 200

        data = response.json()
        assert data["annuity_total_guaranteed"] == 360_000
        assert data["probability_simulation_beats_annuity"] == 0.64
        assert "summary" in data
        assert "portfolio path exceeds the annuity" in data["summary"].lower()
