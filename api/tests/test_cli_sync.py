"""Tests for CLI sync module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from eggnest.sync import (
    EggNestSync,
    scenario_to_yaml,
    yaml_to_scenario,
    get_sync_client,
    DEFAULT_SCENARIOS_DIR,
)


@pytest.fixture
def temp_scenarios_dir(tmp_path):
    """Temporary scenarios directory."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    return scenarios_dir


@pytest.fixture
def sample_scenario():
    """Sample scenario dict as stored in database."""
    return {
        "id": "test-id-123",
        "name": "My Retirement Plan",
        "input_params": {
            "initial_capital": 1000000,
            "annual_spending": 60000,
            "current_age": 60,
            "max_age": 95,
            "gender": "male",
            "social_security_monthly": 2500,
            "social_security_start_age": 67,
            "pension_annual": 0,
            "employment_income": 0,
            "employment_growth_rate": 0.03,
            "retirement_age": 65,
            "state": "CA",
            "filing_status": "single",
            "expected_return": 0.05,
            "return_volatility": 0.16,
            "dividend_yield": 0.02,
            "n_simulations": 10000,
            "include_mortality": True,
            "has_spouse": False,
            "has_annuity": False,
        },
    }


@pytest.fixture
def sample_scenario_with_spouse():
    """Sample scenario with spouse."""
    return {
        "id": "spouse-scenario-123",
        "name": "Joint Retirement",
        "input_params": {
            "initial_capital": 2000000,
            "annual_spending": 80000,
            "current_age": 62,
            "max_age": 95,
            "gender": "male",
            "social_security_monthly": 3000,
            "social_security_start_age": 67,
            "pension_annual": 12000,
            "employment_income": 0,
            "retirement_age": 62,
            "state": "NY",
            "filing_status": "married_filing_jointly",
            "expected_return": 0.05,
            "return_volatility": 0.16,
            "dividend_yield": 0.02,
            "n_simulations": 10000,
            "include_mortality": True,
            "has_spouse": True,
            "spouse": {
                "age": 58,
                "gender": "female",
                "social_security_monthly": 2000,
                "social_security_start_age": 67,
                "pension_annual": 0,
                "employment_income": 50000,
                "retirement_age": 60,
            },
            "has_annuity": False,
        },
    }


class TestScenarioToYaml:
    """Tests for scenario_to_yaml function."""

    def test_basic_scenario(self, sample_scenario):
        """Test converting a basic scenario to YAML."""
        yaml_content = scenario_to_yaml(sample_scenario)

        assert "My Retirement Plan" in yaml_content
        assert "initial_capital: 1000000" in yaml_content
        assert "annual_spending: 60000" in yaml_content
        assert "current_age: 60" in yaml_content
        assert "state: CA" in yaml_content
        assert "has_spouse: false" in yaml_content.lower()

    def test_scenario_with_spouse(self, sample_scenario_with_spouse):
        """Test converting a scenario with spouse to YAML."""
        yaml_content = scenario_to_yaml(sample_scenario_with_spouse)

        assert "has_spouse: true" in yaml_content.lower() or "has_spouse: True" in yaml_content
        assert "spouse:" in yaml_content
        assert "age: 58" in yaml_content

    def test_yaml_is_parseable(self, sample_scenario):
        """Test that generated YAML is valid and parseable."""
        yaml_content = scenario_to_yaml(sample_scenario)

        # Should parse without error
        parsed = yaml.safe_load(yaml_content)
        assert parsed["name"] == "My Retirement Plan"
        assert parsed["initial_capital"] == 1000000


class TestYamlToScenario:
    """Tests for yaml_to_scenario function."""

    def test_parse_basic_scenario(self, temp_scenarios_dir):
        """Test parsing a basic YAML scenario."""
        yaml_content = """
name: Test Scenario
initial_capital: 500000
annual_spending: 40000
current_age: 55
max_age: 90
gender: female
social_security_monthly: 2000
social_security_start_age: 67
pension_annual: 0
employment_income: 100000
employment_growth_rate: 0.03
retirement_age: 60
state: TX
filing_status: single
expected_return: 0.05
return_volatility: 0.16
dividend_yield: 0.02
n_simulations: 5000
include_mortality: true
has_spouse: false
has_annuity: false
"""
        filepath = temp_scenarios_dir / "test.yaml"
        filepath.write_text(yaml_content)

        scenario = yaml_to_scenario(filepath)

        assert scenario["name"] == "Test Scenario"
        assert scenario["input_params"]["initial_capital"] == 500000
        assert scenario["input_params"]["current_age"] == 55
        assert scenario["input_params"]["state"] == "TX"

    def test_parse_scenario_with_spouse(self, temp_scenarios_dir):
        """Test parsing a scenario with spouse."""
        yaml_content = """
name: Joint Plan
initial_capital: 1000000
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
social_security_monthly: 2500
social_security_start_age: 67
pension_annual: 0
employment_income: 0
retirement_age: 65
state: CA
filing_status: married_filing_jointly
expected_return: 0.05
return_volatility: 0.16
dividend_yield: 0.02
n_simulations: 10000
include_mortality: true
has_spouse: true
spouse:
  age: 58
  gender: female
  social_security_monthly: 2000
  social_security_start_age: 67
  pension_annual: 0
  employment_income: 0
  retirement_age: 60
  employment_growth_rate: 0.03
has_annuity: false
"""
        filepath = temp_scenarios_dir / "joint.yaml"
        filepath.write_text(yaml_content)

        scenario = yaml_to_scenario(filepath)

        assert scenario["name"] == "Joint Plan"
        assert scenario["input_params"]["has_spouse"] is True
        assert scenario["input_params"]["spouse"]["age"] == 58
        assert scenario["input_params"]["spouse"]["gender"] == "female"

    def test_name_defaults_to_filename(self, temp_scenarios_dir):
        """Test that name defaults to filename if not specified."""
        yaml_content = """
initial_capital: 500000
annual_spending: 40000
current_age: 55
max_age: 90
gender: male
has_spouse: false
has_annuity: false
"""
        filepath = temp_scenarios_dir / "my-retirement.yaml"
        filepath.write_text(yaml_content)

        scenario = yaml_to_scenario(filepath)
        assert scenario["name"] == "my-retirement"


class TestEggNestSync:
    """Tests for EggNestSync class."""

    def test_init_creates_directory(self, tmp_path):
        """Test that init creates scenarios directory."""
        scenarios_dir = tmp_path / "new_scenarios"
        assert not scenarios_dir.exists()

        sync = EggNestSync(scenarios_dir)
        assert scenarios_dir.exists()

    def test_list_local_empty(self, temp_scenarios_dir):
        """Test listing when no local scenarios exist."""
        sync = EggNestSync(temp_scenarios_dir)
        assert sync.list_local() == []

    def test_list_local_with_scenarios(self, temp_scenarios_dir):
        """Test listing local scenarios."""
        # Create some test scenarios
        (temp_scenarios_dir / "scenario1.yaml").write_text("name: First Scenario")
        (temp_scenarios_dir / "scenario2.yaml").write_text("name: Second Scenario")

        sync = EggNestSync(temp_scenarios_dir)
        scenarios = sync.list_local()

        assert len(scenarios) == 2
        names = {s["name"] for s in scenarios}
        assert "First Scenario" in names
        assert "Second Scenario" in names

    def test_list_local_ignores_non_yaml(self, temp_scenarios_dir):
        """Test that list_local ignores non-YAML files."""
        (temp_scenarios_dir / "scenario.yaml").write_text("name: Real Scenario")
        (temp_scenarios_dir / "notes.txt").write_text("Not a scenario")
        (temp_scenarios_dir / "backup.json").write_text('{"not": "yaml"}')

        sync = EggNestSync(temp_scenarios_dir)
        scenarios = sync.list_local()

        assert len(scenarios) == 1
        assert scenarios[0]["name"] == "Real Scenario"


class TestGetSyncClient:
    """Tests for get_sync_client function."""

    def test_returns_eggnest_sync_instance(self, temp_scenarios_dir):
        """Test that get_sync_client returns EggNestSync instance."""
        sync = get_sync_client(temp_scenarios_dir)
        assert isinstance(sync, EggNestSync)
        assert sync.scenarios_dir == temp_scenarios_dir

    def test_uses_default_directory(self):
        """Test that get_sync_client uses default directory."""
        sync = get_sync_client()
        assert sync.scenarios_dir == DEFAULT_SCENARIOS_DIR


class TestRoundTrip:
    """Tests for round-trip scenario conversion."""

    def test_scenario_round_trip(self, temp_scenarios_dir, sample_scenario):
        """Test that a scenario survives round-trip conversion."""
        # Convert to YAML
        yaml_content = scenario_to_yaml(sample_scenario)

        # Write to file
        filepath = temp_scenarios_dir / "roundtrip.yaml"
        filepath.write_text(yaml_content)

        # Parse back
        parsed = yaml_to_scenario(filepath)

        # Check key fields survived
        assert parsed["name"] == sample_scenario["name"]
        assert parsed["input_params"]["initial_capital"] == sample_scenario["input_params"]["initial_capital"]
        assert parsed["input_params"]["annual_spending"] == sample_scenario["input_params"]["annual_spending"]
        assert parsed["input_params"]["state"] == sample_scenario["input_params"]["state"]

    def test_scenario_with_spouse_round_trip(self, temp_scenarios_dir, sample_scenario_with_spouse):
        """Test that a scenario with spouse survives round-trip conversion."""
        # Convert to YAML
        yaml_content = scenario_to_yaml(sample_scenario_with_spouse)

        # Write to file
        filepath = temp_scenarios_dir / "joint-roundtrip.yaml"
        filepath.write_text(yaml_content)

        # Parse back
        parsed = yaml_to_scenario(filepath)

        # Check spouse data survived
        assert parsed["input_params"]["has_spouse"] is True
        assert parsed["input_params"]["spouse"]["age"] == 58
        assert parsed["input_params"]["spouse"]["gender"] == "female"
