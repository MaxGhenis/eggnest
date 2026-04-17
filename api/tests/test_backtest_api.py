"""Tests for the historical backtest API endpoint."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_historical_backtest_endpoint_returns_requested_cohorts():
    """The API should return one result row per requested historical start year."""
    response = client.post(
        "/backtest/historical",
        json={
            "base_input": {
                "initial_capital": 750000,
                "annual_spending": 42000,
                "social_security_monthly": 1800,
                "social_security_start_age": 67,
                "current_age": 65,
                "max_age": 68,
                "gender": "male",
                "state": "CA",
                "filing_status": "single",
                "stock_allocation": 0.6,
                "spending_mode": "real",
                "inflation_model": "historical",
                "include_mortality": True,
                "n_simulations": 100,
            },
            "start_years": [1973, 2008],
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["horizon_years"] == 3
    assert data["start_years"] == [1973, 2008]
    assert len(data["results"]) == 2
    assert data["strongest_start_year"] in [1973, 2008]
    assert data["weakest_start_year"] in [1973, 2008]
    assert len(data["median_path"]) == 4
    assert len(data["median_path_real"]) == 4
