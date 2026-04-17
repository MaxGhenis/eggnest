"""Tests for CLI commands using Click's test runner."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from eggnest.cli import main
from eggnest.models import (
    HistoricalBacktestResult,
    HistoricalCohortResult,
    HistoricalRothConversionSummary,
    HistoricalStrategySummary,
    RothConversionComparisonItem,
    RothConversionComparisonResult,
    RothConversionScenarioDelta,
    RothConversionScenarioSummary,
    RothOptimizationResult,
    SimulationResult,
    StrategyComparisonItem,
    StrategyComparisonResult,
    StrategyScenarioSummary,
    YearBreakdown,
)


def make_simulation_result() -> SimulationResult:
    return SimulationResult(
        success_rate=0.95,
        median_final_value=2_000_000,
        mean_final_value=2_500_000,
        median_final_value_real=1_100_000,
        mean_final_value_real=1_300_000,
        percentiles={
            "p5": 100_000,
            "p25": 1_000_000,
            "p50": 2_000_000,
            "p75": 3_500_000,
            "p95": 6_000_000,
        },
        percentiles_real={
            "p5": 50_000,
            "p25": 600_000,
            "p50": 1_100_000,
            "p75": 1_800_000,
            "p95": 2_900_000,
        },
        median_depletion_age=None,
        total_withdrawn_median=1_500_000,
        total_taxes_median=300_000,
        percentile_paths={"p50": [1_000_000, 1_100_000]},
        year_breakdown=[],
        initial_withdrawal_rate=3.0,
        prob_10_year_failure=0.02,
    )


def make_backtest_result() -> HistoricalBacktestResult:
    return HistoricalBacktestResult(
        horizon_years=30,
        start_years=[1966, 1973, 2000, 2008],
        results=[
            HistoricalCohortResult(
                start_year=1966,
                success=True,
                final_value=900_000,
                final_value_real=420_000,
                total_withdrawn=1_200_000,
                total_taxes=240_000,
            )
        ],
        success_rate=0.75,
        median_final_value=1_200_000,
        median_final_value_real=540_000,
        total_withdrawn_median=1_300_000,
        total_taxes_median=250_000,
        strongest_start_year=1982,
        weakest_start_year=1966,
        median_path=[1_000_000, 1_050_000],
        median_path_real=[1_000_000, 980_000],
    )


def make_strategy_result() -> StrategyComparisonResult:
    return StrategyComparisonResult(
        results=[
            StrategyComparisonItem(
                strategy="taxable_first",
                monte_carlo=StrategyScenarioSummary(
                    success_rate=0.91,
                    median_final_value=1_800_000,
                    median_final_value_real=900_000,
                    total_taxes_median=280_000,
                    total_withdrawn_median=1_200_000,
                ),
                historical=HistoricalStrategySummary(
                    success_rate=0.79,
                    median_final_value=1_500_000,
                    median_final_value_real=700_000,
                    total_taxes_median=260_000,
                    total_withdrawn_median=1_180_000,
                    cohort_count=40,
                    strongest_start_year=1982,
                    weakest_start_year=1966,
                    worst_final_value_real=120_000,
                ),
                blended_score=88.4,
            )
        ],
        top_scoring_strategy="taxable_first",
        lowest_modeled_tax_strategy="taxable_first",
        strongest_historical_strategy="taxable_first",
        summary="Taxable First leads this scorecard.",
    )


def make_roth_conversion_result() -> RothConversionComparisonResult:
    return RothConversionComparisonResult(
        results=[
            RothConversionComparisonItem(
                conversion_policy="fixed_amount",
                scenario_label="$25,000 per year",
                annual_conversion_amount=25_000,
                conversion_start_age=60,
                conversion_end_age=69,
                monte_carlo=RothConversionScenarioSummary(
                    success_rate=0.92,
                    median_final_value=1_850_000,
                    median_final_value_real=930_000,
                    total_taxes_median=295_000,
                    total_withdrawn_median=1_200_000,
                    total_roth_conversions_median=250_000,
                    year_breakdown=[
                        YearBreakdown(
                            age=66,
                            year_index=0,
                            portfolio_start=1_000_000,
                            portfolio_end=1_030_000,
                            portfolio_return=0.03,
                            total_income=60_000,
                            withdrawal=25_000,
                            total_tax=10_000,
                            net_income=75_000,
                            roth_conversion=25_000,
                            federal_bracket_headroom_used=25_000,
                            federal_marginal_rate_on_last_conversion_dollar=0.12,
                            medicare_part_b_premium=3_108,
                            medicare_part_b_irmaa_increment=888,
                            medicare_part_b_irmaa_bracket="$106,001-$133,000 MAGI",
                            medicare_part_d_premium_surcharge=423.6,
                            medicare_part_d_irmaa_bracket="$106,001-$133,000 MAGI",
                            medicare_total_premium=3_531.6,
                            medicare_premium_delta_vs_baseline=1_311.6,
                        )
                    ],
                ),
                historical=HistoricalRothConversionSummary(
                    success_rate=0.82,
                    median_final_value=1_550_000,
                    median_final_value_real=740_000,
                    total_taxes_median=285_000,
                    total_withdrawn_median=1_180_000,
                    total_roth_conversions_median=250_000,
                    cohort_count=40,
                    strongest_start_year=1982,
                    weakest_start_year=1966,
                    worst_final_value_real=150_000,
                ),
                blended_score=91.2,
                delta_vs_baseline=RothConversionScenarioDelta(
                    blended_score_delta=6.2,
                    monte_carlo_success_rate_delta=0.03,
                    historical_success_rate_delta=0.02,
                    monte_carlo_median_final_value_real_delta=50_000,
                    historical_median_final_value_real_delta=40_000,
                    monte_carlo_total_taxes_median_delta=20_000,
                    monte_carlo_total_roth_conversions_median_delta=250_000,
                    historical_worst_final_value_real_delta=30_000,
                ),
            )
        ],
        baseline_scenario_label="No annual conversion",
        baseline_conversion_amount=0,
        top_scoring_scenario_label="$25,000 per year",
        top_scoring_conversion_amount=25_000,
        lowest_modeled_tax_scenario_label="No annual conversion",
        lowest_modeled_tax_amount=0,
        strongest_historical_scenario_label="$25,000 per year",
        strongest_historical_conversion_amount=25_000,
        summary="$25,000 per year is the current score leader.",
    )


def make_roth_optimization_result() -> RothOptimizationResult:
    base_result = make_roth_conversion_result()
    payload = base_result.model_dump(mode="python")
    payload.update(
        {
            "candidate_count": 7,
            "candidate_start_ages": [60, 65],
            "window_lengths": [5, 10],
            "lowest_medicare_premium_scenario_label": "No annual conversion",
            "lowest_medicare_premium_conversion_amount": 0,
            "highest_real_ending_wealth_scenario_label": "$25,000 per year (ages 60-64)",
            "highest_real_ending_wealth_conversion_amount": 25_000,
            "top_scoring_scenario_label": "$25,000 per year (ages 60-64)",
            "top_scoring_conversion_amount": 25_000,
            "results": [
                base_result.results[0].model_copy(
                    update={"scenario_label": "$25,000 per year (ages 60-64)"}
                )
            ],
            "summary": (
                "$25,000 per year (ages 60-64) is the current score leader. "
                "Searched 7 candidates across start ages 60, 65 and window lengths 5, 10 years."
            ),
        }
    )
    return RothOptimizationResult(**payload)


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


class TestSimulateCommand:
    """Tests for the simulate command."""

    def test_simulate_help(self, runner):
        """Test simulate --help shows options."""
        result = runner.invoke(main, ["simulate", "--help"])
        assert result.exit_code == 0
        assert "scenario" in result.output.lower()
        assert "--output" in result.output
        assert "--api-url" in result.output

    def test_simulate_no_scenarios(self, runner, temp_scenarios_dir):
        """Test simulate with no scenarios available."""
        result = runner.invoke(
            main,
            ["--scenarios-dir", str(temp_scenarios_dir), "simulate"],
        )

        assert result.exit_code == 1
        assert "No scenario files found" in result.output

    def test_simulate_with_file(self, runner, temp_scenarios_dir):
        """Test simulate with a specific file using the local engine."""
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

        mock_engine = MagicMock()
        mock_engine.simulate.return_value = make_simulation_result()

        with patch("eggnest.cli.get_engine", return_value=mock_engine):
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
        assert "95.0% success rate" in result.output
        assert "2,000,000" in result.output

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
                    "--api-url",
                    "http://localhost:8000",
                ],
            )

        assert result.exit_code == 1
        assert "Could not connect to API" in result.output

    def test_simulate_saves_output(self, runner, temp_scenarios_dir, tmp_path):
        """Test simulate saves local-engine results to output file."""
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

        mock_engine = MagicMock()
        mock_engine.simulate.return_value = make_simulation_result()

        with patch("eggnest.cli.get_engine", return_value=mock_engine):
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

    def test_backtest_json_output(self, runner, temp_scenarios_dir):
        """Test historical backtest command emits JSON."""
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

        mock_engine = MagicMock()
        mock_engine.historical_backtest.return_value = make_backtest_result()

        with patch("eggnest.cli.get_engine", return_value=mock_engine):
            result = runner.invoke(
                main,
                [
                    "--scenarios-dir",
                    str(temp_scenarios_dir),
                    "backtest",
                    str(scenario_file),
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        assert '"success_rate": 0.75' in result.output
        assert '"weakest_start_year": 1966' in result.output

    def test_compare_strategies_json_output(self, runner, temp_scenarios_dir):
        """Test strategy comparison command emits JSON."""
        scenario_content = """
name: Test
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
state: CA
filing_status: single
has_spouse: false
has_annuity: false
holdings:
  - account_type: taxable
    fund: sp500
    balance: 300000
    cost_basis: 250000
  - account_type: traditional_401k
    fund: treasury
    balance: 700000
"""
        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text(scenario_content)

        mock_engine = MagicMock()
        mock_engine.compare_withdrawal_strategies.return_value = make_strategy_result()

        with patch("eggnest.cli.get_engine", return_value=mock_engine):
            result = runner.invoke(
                main,
                [
                    "--scenarios-dir",
                    str(temp_scenarios_dir),
                    "compare-strategies",
                    str(scenario_file),
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        assert '"top_scoring_strategy": "taxable_first"' in result.output
        assert '"blended_score": 88.4' in result.output

    def test_compare_roth_conversions_json_output(self, runner, temp_scenarios_dir):
        """Test Roth conversion comparison command emits JSON."""
        scenario_content = """
name: Test
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
state: CA
filing_status: single
has_spouse: false
has_annuity: false
holdings:
  - account_type: taxable
    fund: sp500
    balance: 300000
    cost_basis: 250000
  - account_type: traditional_401k
    fund: treasury
    balance: 700000
"""
        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text(scenario_content)

        mock_engine = MagicMock()
        mock_engine.compare_roth_conversions.return_value = make_roth_conversion_result()

        with patch("eggnest.cli.get_engine", return_value=mock_engine):
            result = runner.invoke(
                main,
                [
                    "--scenarios-dir",
                    str(temp_scenarios_dir),
                    "compare-roth-conversions",
                    str(scenario_file),
                    "--policy",
                    "fill_12_percent_bracket",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        called_request = mock_engine.compare_roth_conversions.call_args[0][0]
        assert called_request.conversion_policies == ["fill_12_percent_bracket"]
        assert '"baseline_scenario_label": "No annual conversion"' in result.output
        assert '"top_scoring_scenario_label": "$25,000 per year"' in result.output
        assert '"top_scoring_conversion_amount": 25000.0' in result.output
        assert '"monte_carlo_total_taxes_median_delta": 20000.0' in result.output
        assert '"total_roth_conversions_median": 250000.0' in result.output
        assert '"medicare_premium_delta_vs_baseline": 1311.6' in result.output

    def test_compare_roth_conversions_human_output_shows_cliff_ledger(
        self, runner, temp_scenarios_dir
    ):
        """Human Roth output should render the representative cliff ledger."""
        scenario_content = """
name: Test
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
state: CA
filing_status: single
has_spouse: false
has_annuity: false
holdings:
  - account_type: taxable
    fund: sp500
    balance: 300000
    cost_basis: 250000
  - account_type: traditional_401k
    fund: treasury
    balance: 700000
"""
        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text(scenario_content)

        mock_engine = MagicMock()
        mock_engine.compare_roth_conversions.return_value = make_roth_conversion_result()

        with patch("eggnest.cli.get_engine", return_value=mock_engine):
            result = runner.invoke(
                main,
                [
                    "--scenarios-dir",
                    str(temp_scenarios_dir),
                    "compare-roth-conversions",
                    str(scenario_file),
                    "--policy",
                    "fill_12_percent_bracket",
                ],
            )

        assert result.exit_code == 0
        assert "Representative cliff ledger" in result.output
        assert "Medicare deltas are relative to No annual conversion." in result.output
        assert "12.0%" in result.output
        assert "$+1,312" in result.output

    def test_optimize_roth_conversions_json_output(self, runner, temp_scenarios_dir):
        """Roth optimization command should emit JSON and forward search inputs."""
        scenario_content = """
name: Test
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
state: CA
filing_status: single
has_spouse: false
has_annuity: false
holdings:
  - account_type: taxable
    fund: sp500
    balance: 300000
    cost_basis: 250000
  - account_type: traditional_401k
    fund: treasury
    balance: 700000
"""
        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text(scenario_content)

        mock_engine = MagicMock()
        mock_engine.optimize_roth_conversions.return_value = make_roth_optimization_result()

        with patch("eggnest.cli.get_engine", return_value=mock_engine):
            result = runner.invoke(
                main,
                [
                    "--scenarios-dir",
                    str(temp_scenarios_dir),
                    "optimize-roth-conversions",
                    str(scenario_file),
                    "--candidate-start-age",
                    "60",
                    "--candidate-start-age",
                    "65",
                    "--window-length",
                    "5",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        called_request = mock_engine.optimize_roth_conversions.call_args[0][0]
        assert called_request.candidate_start_ages == [60, 65]
        assert called_request.window_lengths == [5]
        assert '"candidate_count": 7' in result.output
        assert (
            '"lowest_medicare_premium_scenario_label": "No annual conversion"'
            in result.output
        )

    def test_optimize_roth_conversions_human_output_shows_search_space(
        self, runner, temp_scenarios_dir
    ):
        """Human Roth optimization output should show search-space context."""
        scenario_content = """
name: Test
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
state: CA
filing_status: single
has_spouse: false
has_annuity: false
holdings:
  - account_type: taxable
    fund: sp500
    balance: 300000
    cost_basis: 250000
  - account_type: traditional_401k
    fund: treasury
    balance: 700000
"""
        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text(scenario_content)

        mock_engine = MagicMock()
        mock_engine.optimize_roth_conversions.return_value = make_roth_optimization_result()

        with patch("eggnest.cli.get_engine", return_value=mock_engine):
            result = runner.invoke(
                main,
                [
                    "--scenarios-dir",
                    str(temp_scenarios_dir),
                    "optimize-roth-conversions",
                    str(scenario_file),
                ],
            )

        assert result.exit_code == 0
        assert "Search space: 7 candidates" in result.output
        assert "Medicare Δ" in result.output
        assert "Lowest Medicare premiums: No annual conversion." in result.output

    def test_optimize_roth_conversions_report_json_output(
        self, runner, temp_scenarios_dir
    ):
        """Roth optimization report-json output should emit the export artifact."""
        scenario_content = """
name: Test
annual_spending: 60000
current_age: 60
max_age: 95
gender: male
state: CA
filing_status: single
has_spouse: false
has_annuity: false
holdings:
  - account_type: taxable
    fund: sp500
    balance: 300000
    cost_basis: 250000
  - account_type: traditional_401k
    fund: treasury
    balance: 700000
"""
        scenario_file = temp_scenarios_dir / "test.yaml"
        scenario_file.write_text(scenario_content)

        mock_engine = MagicMock()
        mock_engine.optimize_roth_conversions.return_value = make_roth_optimization_result()

        with patch("eggnest.cli.get_engine", return_value=mock_engine):
            result = runner.invoke(
                main,
                [
                    "--scenarios-dir",
                    str(temp_scenarios_dir),
                    "optimize-roth-conversions",
                    str(scenario_file),
                    "--format",
                    "report-json",
                ],
            )

        assert result.exit_code == 0
        assert '"artifact_type": "eggnest_roth_optimization_report"' in result.output
        assert '"leaders"' in result.output
        assert '"search_space"' in result.output
