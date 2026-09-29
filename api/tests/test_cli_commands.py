"""Tests for CLI commands using Click's test runner."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from eggnest.cli import main


def core_us_response(result: dict) -> dict:
    """Wrap a legacy simulation result in the core HTTP response shape."""
    return {
        "engine": "us_retirement",
        "country": "USA",
        "outputs": {"us_simulation_result": result},
    }


@pytest.fixture
def runner():
    """Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_scenarios_dir(tmp_path):
    """Temporary scenarios directory."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    return scenarios_dir


class TestMainCommand:
    """Tests for the main CLI group."""

    def test_help(self, runner):
        """Test --help shows usage."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "EggNest" in result.output
        assert "Monte Carlo" in result.output

    def test_version_not_required(self, runner):
        """Test CLI works without version flag."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0


class TestAuthCommands:
    """Tests for auth subcommands."""

    def test_auth_help(self, runner):
        """Test auth --help shows subcommands."""
        result = runner.invoke(main, ["auth", "--help"])
        assert result.exit_code == 0
        assert "login" in result.output
        assert "logout" in result.output
        assert "whoami" in result.output

    def test_whoami_not_logged_in(self, runner, tmp_path, monkeypatch):
        """Test whoami when not logged in."""
        # Use temp credentials file
        creds_file = tmp_path / ".eggnest" / "credentials.json"
        monkeypatch.setattr("eggnest.auth.CREDENTIALS_FILE", creds_file)

        result = runner.invoke(main, ["auth", "whoami"])
        assert result.exit_code == 0
        assert "Not logged in" in result.output

    def test_logout_not_logged_in(self, runner, tmp_path, monkeypatch):
        """Test logout when not logged in."""
        creds_file = tmp_path / ".eggnest" / "credentials.json"
        monkeypatch.setattr("eggnest.auth.CREDENTIALS_FILE", creds_file)

        result = runner.invoke(main, ["auth", "logout"])
        assert result.exit_code == 0
        assert "Not currently logged in" in result.output


class TestInitCommand:
    """Tests for the init command."""

    def test_init_creates_scenario(self, runner, temp_scenarios_dir):
        """Test init creates a new scenario file."""
        result = runner.invoke(
            main,
            ["--scenarios-dir", str(temp_scenarios_dir), "init", "test-plan"],
        )

        assert result.exit_code == 0
        assert "Created scenario" in result.output

        scenario_file = temp_scenarios_dir / "test-plan.yaml"
        assert scenario_file.exists()

    def test_init_default_name(self, runner, temp_scenarios_dir):
        """Test init with default name."""
        result = runner.invoke(
            main,
            ["--scenarios-dir", str(temp_scenarios_dir), "init"],
        )

        assert result.exit_code == 0
        scenario_file = temp_scenarios_dir / "my-retirement.yaml"
        assert scenario_file.exists()

    def test_init_scenario_content(self, runner, temp_scenarios_dir):
        """Test that init creates valid scenario content."""
        runner.invoke(
            main,
            ["--scenarios-dir", str(temp_scenarios_dir), "init", "my-plan"],
        )

        scenario_file = temp_scenarios_dir / "my-plan.yaml"
        content = scenario_file.read_text()

        # Check key fields are present
        assert "name: my-plan" in content
        assert "initial_capital:" in content
        assert "annual_spending:" in content
        assert "current_age:" in content
        assert "social_security_monthly:" in content
        assert "state:" in content

    def test_init_does_not_overwrite_without_confirm(self, runner, temp_scenarios_dir):
        """Test that init doesn't overwrite existing file without confirmation."""
        # Create existing file
        scenario_file = temp_scenarios_dir / "existing.yaml"
        scenario_file.write_text("name: existing")

        # Try to overwrite, answer 'n' to confirmation
        result = runner.invoke(
            main,
            ["--scenarios-dir", str(temp_scenarios_dir), "init", "existing"],
            input="n\n",
        )

        assert result.exit_code == 0
        # Original content should remain
        assert scenario_file.read_text() == "name: existing"


class TestListCommand:
    """Tests for the list command."""

    def test_list_empty(self, runner, temp_scenarios_dir):
        """Test list with no scenarios."""
        result = runner.invoke(
            main,
            ["--scenarios-dir", str(temp_scenarios_dir), "list"],
        )

        assert result.exit_code == 0
        assert "No scenarios found" in result.output

    def test_list_with_scenarios(self, runner, temp_scenarios_dir):
        """Test list with scenarios present."""
        # Create some scenarios
        (temp_scenarios_dir / "plan1.yaml").write_text("name: First Plan")
        (temp_scenarios_dir / "plan2.yaml").write_text("name: Second Plan")

        result = runner.invoke(
            main,
            ["--scenarios-dir", str(temp_scenarios_dir), "list"],
        )

        assert result.exit_code == 0
        assert "plan1.yaml" in result.output
        assert "plan2.yaml" in result.output


class TestSyncCommands:
    """Tests for sync subcommands."""

    def test_sync_help(self, runner):
        """Test sync --help shows subcommands."""
        result = runner.invoke(main, ["sync", "--help"])
        assert result.exit_code == 0
        assert "pull" in result.output
        assert "push" in result.output
        assert "status" in result.output

    def test_sync_status_not_logged_in(
        self, runner, temp_scenarios_dir, tmp_path, monkeypatch
    ):
        """Test sync status shows local scenarios when not logged in."""
        # Use temp credentials file
        creds_file = tmp_path / ".eggnest" / "credentials.json"
        monkeypatch.setattr("eggnest.auth.CREDENTIALS_FILE", creds_file)

        # Create a local scenario
        (temp_scenarios_dir / "local.yaml").write_text("name: Local Scenario")

        result = runner.invoke(
            main,
            ["--scenarios-dir", str(temp_scenarios_dir), "sync", "status"],
        )

        assert result.exit_code == 0
        assert "Local scenarios" in result.output
        assert "Local Scenario" in result.output
        assert "Login to see cloud scenarios" in result.output

    def test_sync_pull_requires_login(
        self, runner, temp_scenarios_dir, tmp_path, monkeypatch
    ):
        """Test sync pull requires login."""
        creds_file = tmp_path / ".eggnest" / "credentials.json"
        monkeypatch.setattr("eggnest.auth.CREDENTIALS_FILE", creds_file)

        result = runner.invoke(
            main,
            ["--scenarios-dir", str(temp_scenarios_dir), "sync", "pull"],
        )

        assert result.exit_code == 1
        assert "Not logged in" in result.output

    def test_sync_push_requires_login(
        self, runner, temp_scenarios_dir, tmp_path, monkeypatch
    ):
        """Test sync push requires login."""
        creds_file = tmp_path / ".eggnest" / "credentials.json"
        monkeypatch.setattr("eggnest.auth.CREDENTIALS_FILE", creds_file)

        result = runner.invoke(
            main,
            ["--scenarios-dir", str(temp_scenarios_dir), "sync", "push"],
        )

        assert result.exit_code == 1
        assert "Not logged in" in result.output


class TestCoreCommands:
    """Tests for machine-readable core engine commands."""

    def test_core_schema_outputs_json_schema(self, runner):
        """Test core schema emits parseable JSON Schema."""
        result = runner.invoke(main, ["core", "schema", "scenario"])

        assert result.exit_code == 0
        schema = json.loads(result.output)
        assert schema["title"] == "EngineScenario"
        assert "engine" in schema["properties"]

    def test_core_run_accepts_raw_us_input_from_stdin(self, runner):
        """Test core run supports stdin and legacy JSON output."""
        scenario_content = """
initial_capital: 1000000
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
state: CA
filing_status: single
n_simulations: 100
has_spouse: false
has_annuity: false
"""
        core_response = core_us_response(
            {
                "success_rate": 0.95,
                "median_final_value": 2000000,
                "initial_withdrawal_rate": 3.0,
                "percentiles": {"p5": 0, "p25": 1, "p50": 2, "p75": 3, "p95": 4},
            }
        )

        with patch("eggnest.cli.run_core_scenario", return_value=core_response):
            result = runner.invoke(
                main,
                [
                    "core",
                    "run",
                    "-",
                    "--engine",
                    "us_retirement",
                    "--output-format",
                    "legacy",
                ],
                input=scenario_content,
            )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["success_rate"] == 0.95

    def test_core_run_writes_envelope_to_output_file(self, runner, tmp_path):
        """Test core run can write the full envelope for tool callers."""
        scenario_file = tmp_path / "scenario.yaml"
        scenario_file.write_text("""
initial_capital: 1000000
annual_spending: 60000
current_age: 60
max_age: 95
state: CA
n_simulations: 100
""")
        output_file = tmp_path / "result.json"
        core_response = core_us_response(
            {
                "success_rate": 0.95,
                "median_final_value": 2000000,
                "initial_withdrawal_rate": 3.0,
                "percentiles": {"p5": 0, "p25": 1, "p50": 2, "p75": 3, "p95": 4},
            }
        )

        with patch("eggnest.cli.run_core_scenario", return_value=core_response):
            result = runner.invoke(
                main,
                [
                    "core",
                    "run",
                    str(scenario_file),
                    "--output",
                    str(output_file),
                ],
            )

        assert result.exit_code == 0
        assert result.output == ""
        payload = json.loads(output_file.read_text())
        assert payload["engine"] == "us_retirement"


class TestSimulateCommand:
    """Tests for the simulate command."""

    def test_simulate_help(self, runner):
        """Test simulate --help shows options."""
        result = runner.invoke(main, ["simulate", "--help"])
        assert result.exit_code == 0
        assert "scenario" in result.output.lower()
        assert "--output" in result.output
        assert "--api-url" in result.output
        assert "--job" in result.output

    def test_simulate_no_scenarios(self, runner, temp_scenarios_dir):
        """Test simulate with no scenarios available."""
        result = runner.invoke(
            main,
            ["--scenarios-dir", str(temp_scenarios_dir), "simulate"],
        )

        assert result.exit_code == 1
        assert "No scenario files found" in result.output

    def test_simulate_with_file(self, runner, temp_scenarios_dir):
        """Test simulate with a specific file (mocked API)."""
        # Create a valid scenario
        scenario_content = """
name: Test Scenario
initial_capital: 1000000
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
social_security_monthly: 2500
social_security_start_age: 67
pension_annual: 0
employment_income: 0
employment_growth_rate: 0.03
retirement_age: 65
state: CA
filing_status: single
expected_return: 0.05
return_volatility: 0.16
dividend_yield: 0.02
n_simulations: 100
include_mortality: true
has_spouse: false
has_annuity: false
"""
        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text(scenario_content)

        # Mock the httpx.post call
        mock_response = MagicMock()
        mock_response.json.return_value = core_us_response(
            {
                "success_rate": 0.95,
                "median_final_value": 2000000,
                "mean_final_value": 2500000,
                "initial_withdrawal_rate": 3.0,
                "percentiles": {
                    "p5": 100000,
                    "p25": 1000000,
                    "p50": 2000000,
                    "p75": 3500000,
                    "p95": 6000000,
                },
                "percentile_paths": {},
                "total_withdrawn_median": 1500000,
                "total_taxes_median": 300000,
            }
        )
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_response) as mock_post:
            result = runner.invoke(
                main,
                [
                    "--scenarios-dir",
                    str(temp_scenarios_dir),
                    "simulate",
                    str(scenario_file),
                ],
            )

        assert result.exit_code == 0
        call = mock_post.call_args
        assert call.args[0] == "http://localhost:8000/core/simulate"
        assert call.kwargs["json"]["engine"] == "us_retirement"
        assert call.kwargs["json"]["inputs"]["current_age"] == 60
        assert "95.0% success rate" in result.output
        assert "2,000,000" in result.output

    def test_simulate_with_remote_job_output(self, runner, temp_scenarios_dir):
        """Test simulate can use the pollable core job API."""
        scenario_content = """
name: Test Scenario
initial_capital: 1000000
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
has_spouse: false
has_annuity: false
n_simulations: 100
"""
        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text(scenario_content)

        job_response = MagicMock()
        job_response.json.return_value = {
            "job_id": "job-1",
            "status": "queued",
            "progress": 0,
            "message": "Queued",
        }
        job_response.raise_for_status = MagicMock()

        running_response = MagicMock()
        running_response.json.return_value = {
            "job_id": "job-1",
            "status": "running",
            "progress": 0.35,
            "message": "Calculating PolicyEngine taxes",
        }
        running_response.raise_for_status = MagicMock()

        complete_response = MagicMock()
        complete_response.json.return_value = {
            "job_id": "job-1",
            "status": "succeeded",
            "progress": 1,
            "message": "Complete",
            "result": core_us_response(
                {
                    "success_rate": 0.95,
                    "median_final_value": 2000000,
                    "mean_final_value": 2500000,
                    "initial_withdrawal_rate": 3.0,
                    "percentiles": {
                        "p5": 100000,
                        "p25": 1000000,
                        "p50": 2000000,
                        "p75": 3500000,
                        "p95": 6000000,
                    },
                    "percentile_paths": {},
                    "total_withdrawn_median": 1500000,
                    "total_taxes_median": 300000,
                }
            ),
        }
        complete_response.raise_for_status = MagicMock()

        with (
            patch("httpx.post", return_value=job_response) as mock_post,
            patch(
                "httpx.get", side_effect=[running_response, complete_response]
            ) as mock_get,
            patch("time.sleep"),
        ):
            result = runner.invoke(
                main,
                [
                    "--scenarios-dir",
                    str(temp_scenarios_dir),
                    "simulate",
                    str(scenario_file),
                    "--job",
                    "--output-format",
                    "result",
                ],
            )

        assert result.exit_code == 0
        assert mock_post.call_args.args[0] == "http://localhost:8000/core/jobs"
        assert mock_get.call_args.args[0] == "http://localhost:8000/core/jobs/job-1"
        payload = json.loads(result.output)
        assert payload["success_rate"] == 0.95
        assert payload["median_final_value"] == 2000000

    def test_simulate_api_connection_error(self, runner, temp_scenarios_dir):
        """Test simulate handles API connection error gracefully."""
        import httpx

        # Create a valid scenario
        scenario_content = """
name: Test
initial_capital: 1000000
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
has_spouse: false
has_annuity: false
"""
        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text(scenario_content)

        with patch("httpx.post", side_effect=httpx.ConnectError("Connection refused")):
            result = runner.invoke(
                main,
                [
                    "--scenarios-dir",
                    str(temp_scenarios_dir),
                    "simulate",
                    str(scenario_file),
                ],
            )

        assert result.exit_code == 1
        assert "Could not connect to API" in result.output

    def test_simulate_saves_output(self, runner, temp_scenarios_dir, tmp_path):
        """Test simulate saves results to output file."""
        # Create a valid scenario
        scenario_content = """
name: Test
initial_capital: 1000000
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
has_spouse: false
has_annuity: false
"""
        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text(scenario_content)
        output_file = tmp_path / "results.json"

        mock_response = MagicMock()
        mock_response.json.return_value = core_us_response(
            {
                "success_rate": 0.95,
                "median_final_value": 2000000,
                "mean_final_value": 2500000,
                "initial_withdrawal_rate": 3.0,
                "percentiles": {
                    "p5": 0,
                    "p25": 1000000,
                    "p50": 2000000,
                    "p75": 3000000,
                    "p95": 5000000,
                },
                "percentile_paths": {},
                "total_withdrawn_median": 1500000,
                "total_taxes_median": 300000,
            }
        )
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_response):
            result = runner.invoke(
                main,
                [
                    "--scenarios-dir",
                    str(temp_scenarios_dir),
                    "simulate",
                    str(scenario_file),
                    "--output",
                    str(output_file),
                ],
            )

        assert result.exit_code == 0
        assert output_file.exists()

        saved_results = json.loads(output_file.read_text())
        assert saved_results["success_rate"] == 0.95

    def test_simulate_local_machine_readable_envelope(self, runner, temp_scenarios_dir):
        """Test simulate can emit pure JSON without requiring the API server."""
        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text("""
name: Test
initial_capital: 1000000
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
state: CA
n_simulations: 100
has_spouse: false
has_annuity: false
""")
        core_response = core_us_response(
            {
                "success_rate": 0.95,
                "median_final_value": 2000000,
                "initial_withdrawal_rate": 3.0,
                "percentiles": {"p5": 0, "p25": 1, "p50": 2, "p75": 3, "p95": 4},
            }
        )

        with patch("eggnest.cli.run_core_scenario", return_value=core_response):
            result = runner.invoke(
                main,
                [
                    "--scenarios-dir",
                    str(temp_scenarios_dir),
                    "simulate",
                    str(scenario_file),
                    "--local",
                    "--output-format",
                    "envelope",
                ],
            )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["engine"] == "us_retirement"
        assert payload["outputs"]["us_simulation_result"]["success_rate"] == 0.95
