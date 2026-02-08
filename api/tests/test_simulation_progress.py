"""Tests for simulation progress streaming functionality."""

import pytest

from eggnest.models import SimulationInput
from eggnest.simulation import MonteCarloSimulator


@pytest.fixture
def basic_params():
    """Basic simulation parameters for testing."""
    return SimulationInput(
        current_age=65,
        max_age=70,  # Short simulation for faster tests
        gender="male",
        initial_capital=500000,
        annual_spending=40000,
        n_simulations=100,  # Small number for speed
        state="CA",
        filing_status="single",
    )


class TestRunWithProgress:
    """Tests for the run_with_progress generator method."""

    def test_yields_progress_events(self, basic_params):
        """Should yield progress events during simulation."""
        simulator = MonteCarloSimulator(basic_params)
        events = list(simulator.run_with_progress())

        # Should have at least one progress event
        progress_events = [e for e in events if e.get("type") == "progress"]
        assert len(progress_events) > 0

    def test_yields_complete_event_at_end(self, basic_params):
        """Should yield a complete event with results at the end."""
        simulator = MonteCarloSimulator(basic_params)
        events = list(simulator.run_with_progress())

        # Last event should be complete
        assert events[-1]["type"] == "complete"
        assert "result" in events[-1]

    def test_progress_events_have_year_info(self, basic_params):
        """Progress events should include current year and total years."""
        simulator = MonteCarloSimulator(basic_params)
        events = list(simulator.run_with_progress())

        progress_events = [e for e in events if e.get("type") == "progress"]
        for event in progress_events:
            assert "year" in event
            assert "total_years" in event
            assert event["year"] >= 0
            assert event["year"] <= event["total_years"]

    def test_progress_increases_over_time(self, basic_params):
        """Year should increase (or stay same) with each progress event."""
        simulator = MonteCarloSimulator(basic_params)
        events = list(simulator.run_with_progress())

        progress_events = [e for e in events if e.get("type") == "progress"]
        years = [e["year"] for e in progress_events]

        # Years should be non-decreasing
        for i in range(1, len(years)):
            assert years[i] >= years[i - 1]

    def test_complete_event_has_valid_result(self, basic_params):
        """Complete event should contain valid simulation result data."""
        simulator = MonteCarloSimulator(basic_params)
        events = list(simulator.run_with_progress())

        complete_event = events[-1]
        result = complete_event["result"]

        # Check required fields
        assert "success_rate" in result
        assert "median_final_value" in result
        assert "percentile_paths" in result
        assert 0 <= result["success_rate"] <= 1

    def test_total_years_matches_simulation_params(self, basic_params):
        """Total years in progress should match max_age - current_age."""
        simulator = MonteCarloSimulator(basic_params)
        events = list(simulator.run_with_progress())

        expected_years = basic_params.max_age - basic_params.current_age
        progress_events = [e for e in events if e.get("type") == "progress"]

        if progress_events:
            assert progress_events[0]["total_years"] == expected_years
