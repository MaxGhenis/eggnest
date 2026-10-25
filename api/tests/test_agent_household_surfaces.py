"""Tests for agent-facing household resource surfaces."""

import json

from click.testing import CliRunner
from fastapi.testclient import TestClient

from eggnest.cli import main as cli_main
from eggnest.household import compare_earnings_grid, validate_household_payload
from eggnest.models import EarningsGridInput, HouseholdInput, PersonInput
from eggnest.programs import list_programs
from main import app

client = TestClient(app)


def household_input() -> HouseholdInput:
    return HouseholdInput(
        state="TX",
        year=2025,
        people=[
            PersonInput(age=28, employment_income=20_000, is_tax_unit_head=True),
            PersonInput(age=4, is_tax_unit_dependent=True),
        ],
    )


def test_program_catalog_exposes_household_resources():
    programs = list_programs(jurisdiction="us")

    household = next(
        program for program in programs if program.id == "us_household_resources"
    )
    assert household.engine == "us_household_resources"
    assert household.primary_output == "household_resources_result.net_income"


def test_program_outputs_name_fields_of_their_engine_results():
    """Agents read the outputs `GET /programs` names, so each must be a field
    of the result its engine returns, under that engine's output key."""
    from eggnest.core import uk_retirement, us_household_resources, us_retirement
    from eggnest.models import HouseholdResult, SimulationResult
    from eggnest.models_uk import UKSimulationResult

    results = {
        "us_household_resources": (us_household_resources.OUTPUT_KEY, HouseholdResult),
        "us_retirement": (us_retirement.OUTPUT_KEY, SimulationResult),
        "uk_retirement": (uk_retirement.OUTPUT_KEY, UKSimulationResult),
    }
    programs = list_programs()
    assert {program.engine for program in programs} == set(results)
    for program in programs:
        output_key, model = results[program.engine]
        key, _, primary = program.primary_output.partition(".")
        assert key == output_key, program.id
        names = [output.name for output in program.outputs]
        assert primary in names, program.id
        assert set(names) <= set(model.model_fields), (program.id, names)


def test_programs_endpoint_exposes_catalog():
    response = client.get("/programs?jurisdiction=us")

    assert response.status_code == 200
    assert any(program["id"] == "us_household_resources" for program in response.json())


def test_validate_household_payload_returns_next_questions():
    result = validate_household_payload({"people": [{"age": 30}]})

    assert result.status == "needs_input"
    assert "state" in result.missing_inputs
    assert "people[0].income" in result.missing_inputs
    assert result.high_impact_questions


def test_validate_household_endpoint_accepts_partial_payload():
    response = client.post("/household/validate", json={"people": [{"age": 30}]})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_input"
    assert "state" in data["missing_inputs"]


def test_compare_earnings_grid_returns_rows():
    result = compare_earnings_grid(
        EarningsGridInput(
            base_input=household_input(),
            income_min=0,
            income_max=2_000,
            step=1_000,
        )
    )

    assert len(result.rows) == 3
    assert result.rows[0].employment_income == 0
    assert result.rows[-1].employment_income == 2_000
    assert result.comparison_summary
    assert any(citation.id == "us:statutes/7/2017" for citation in result.citations)


def test_compare_earnings_grid_endpoint_returns_rows():
    response = client.post(
        "/compare-earnings-grid",
        json={
            "base_input": household_input().model_dump(),
            "income_min": 0,
            "income_max": 2_000,
            "step": 1_000,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["rows"]) == 3
    assert data["income_max"] == 2_000
    assert any(citation["id"] == "us:statutes/7/2017" for citation in data["citations"])


def test_programs_list_cli_outputs_json():
    result = CliRunner().invoke(cli_main, ["programs", "list", "--jurisdiction", "us"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert any(
        program["id"] == "us_household_resources" for program in payload["programs"]
    )


def test_household_validate_cli_outputs_json(tmp_path):
    household_file = tmp_path / "household.yaml"
    household_file.write_text(
        """
people:
  - age: 30
"""
    )

    result = CliRunner().invoke(
        cli_main,
        ["household", "validate", str(household_file)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "needs_input"
    assert "state" in payload["missing_inputs"]


def test_household_run_cli_outputs_legacy_json(tmp_path):
    household_file = tmp_path / "household.yaml"
    household_file.write_text(
        """
state: TX
year: 2025
people:
  - age: 28
    employment_income: 20000
    is_tax_unit_head: true
  - age: 4
    is_tax_unit_dependent: true
"""
    )

    result = CliRunner().invoke(
        cli_main,
        ["household", "run", str(household_file), "--output-format", "legacy"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total_income"] == 20_000
    assert "net_income" in payload


def test_compare_earnings_grid_cli_outputs_json(tmp_path):
    household_file = tmp_path / "household.yaml"
    household_file.write_text(
        """
state: TX
year: 2025
people:
  - age: 28
    employment_income: 20000
    is_tax_unit_head: true
  - age: 4
    is_tax_unit_dependent: true
"""
    )

    result = CliRunner().invoke(
        cli_main,
        [
            "compare",
            "earnings-grid",
            str(household_file),
            "--income-min",
            "0",
            "--income-max",
            "2000",
            "--step",
            "1000",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["rows"]) == 3
    assert payload["income_max"] == 2_000
