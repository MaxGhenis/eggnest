"""Tests for MCP-facing EggNest tool wrappers."""

from eggnest.mcp_tools import (
    compare_roth_conversions_tool,
    compare_withdrawal_strategies_tool,
    describe_engine_tool,
    historical_backtest_tool,
    optimize_roth_conversions_report_tool,
    optimize_roth_conversions_tool,
    simulate_plan,
)
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
)


def test_describe_engine_tool_returns_metadata():
    """The MCP description tool should expose the engine capabilities."""
    result = describe_engine_tool()

    assert result["name"] == "EggNest"
    assert "simulate" in result["capabilities"]


def test_simulate_plan_delegates_to_engine(monkeypatch):
    """simulate_plan should validate payloads and serialize the engine result."""
    sample_result = SimulationResult(
        success_rate=0.9,
        median_final_value=1_500_000,
        mean_final_value=1_700_000,
        median_final_value_real=800_000,
        mean_final_value_real=900_000,
        percentiles={"p5": 50_000, "p25": 600_000, "p50": 1_500_000, "p75": 2_300_000, "p95": 3_500_000},
        percentiles_real={"p5": 25_000, "p25": 300_000, "p50": 800_000, "p75": 1_200_000, "p95": 1_900_000},
        median_depletion_age=None,
        total_withdrawn_median=1_200_000,
        total_taxes_median=220_000,
        percentile_paths={"p50": [1_000_000, 1_050_000]},
        year_breakdown=[],
        initial_withdrawal_rate=4.0,
        prob_10_year_failure=0.04,
    )

    class FakeEngine:
        def simulate(self, payload):
            assert payload["annual_spending"] == 60_000
            return sample_result

    monkeypatch.setattr("eggnest.mcp_tools.get_engine", lambda: FakeEngine())
    result = simulate_plan(
        {
            "initial_capital": 1_000_000,
            "annual_spending": 60_000,
            "current_age": 60,
            "max_age": 95,
            "gender": "male",
            "has_spouse": False,
            "has_annuity": False,
        }
    )

    assert result["success_rate"] == 0.9
    assert result["median_final_value_real"] == 800_000


def test_historical_backtest_tool_serializes_result(monkeypatch):
    """historical_backtest_tool should return JSON-shaped data."""
    sample_result = HistoricalBacktestResult(
        horizon_years=30,
        start_years=[1966, 1973],
        results=[
            HistoricalCohortResult(
                start_year=1966,
                success=False,
                final_value=0,
                final_value_real=0,
                total_withdrawn=1_000_000,
                total_taxes=210_000,
            )
        ],
        success_rate=0.5,
        median_final_value=400_000,
        median_final_value_real=180_000,
        total_withdrawn_median=1_050_000,
        total_taxes_median=205_000,
        strongest_start_year=1982,
        weakest_start_year=1966,
        median_path=[1_000_000, 900_000],
        median_path_real=[1_000_000, 850_000],
    )

    class FakeEngine:
        def historical_backtest(self, request):
            assert request.base_input.annual_spending == 55_000
            return sample_result

    monkeypatch.setattr("eggnest.mcp_tools.get_engine", lambda: FakeEngine())
    result = historical_backtest_tool(
        {
            "initial_capital": 1_000_000,
            "annual_spending": 55_000,
            "current_age": 60,
            "max_age": 90,
            "gender": "female",
            "has_spouse": False,
            "has_annuity": False,
        }
    )

    assert result["success_rate"] == 0.5
    assert result["weakest_start_year"] == 1966


def test_compare_withdrawal_strategies_tool_serializes_result(monkeypatch):
    """Strategy comparison MCP tool should emit plain JSON."""
    sample_result = StrategyComparisonResult(
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

    class FakeEngine:
        def compare_withdrawal_strategies(self, request):
            assert request.base_input.holdings is not None
            return sample_result

    monkeypatch.setattr("eggnest.mcp_tools.get_engine", lambda: FakeEngine())
    result = compare_withdrawal_strategies_tool(
        base_input={
            "annual_spending": 60_000,
            "current_age": 60,
            "max_age": 95,
            "gender": "male",
            "has_spouse": False,
            "has_annuity": False,
            "holdings": [
                {
                    "account_type": "taxable",
                    "fund": "sp500",
                    "balance": 300_000,
                    "cost_basis": 250_000,
                }
            ],
        }
    )

    assert result["top_scoring_strategy"] == "taxable_first"
    assert result["results"][0]["blended_score"] == 88.4


def test_compare_roth_conversions_tool_serializes_result(monkeypatch):
    """Roth conversion MCP tool should emit plain JSON."""
    sample_result = RothConversionComparisonResult(
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

    class FakeEngine:
        def compare_roth_conversions(self, request):
            assert request.base_input.holdings is not None
            return sample_result

    monkeypatch.setattr("eggnest.mcp_tools.get_engine", lambda: FakeEngine())
    result = compare_roth_conversions_tool(
        base_input={
            "annual_spending": 60_000,
            "current_age": 60,
            "max_age": 95,
            "gender": "male",
            "has_spouse": False,
            "has_annuity": False,
            "holdings": [
                {
                    "account_type": "taxable",
                    "fund": "sp500",
                    "balance": 300_000,
                    "cost_basis": 250_000,
                },
                {
                    "account_type": "traditional_401k",
                    "fund": "treasury",
                    "balance": 700_000,
                },
            ],
        },
        annual_conversion_amounts=[0, 25_000],
        conversion_policies=["fill_12_percent_bracket"],
        conversion_start_age=60,
        conversion_end_age=69,
    )

    assert result["top_scoring_scenario_label"] == "$25,000 per year"
    assert result["baseline_scenario_label"] == "No annual conversion"
    assert result["top_scoring_conversion_amount"] == 25_000
    assert (
        result["results"][0]["delta_vs_baseline"][
            "monte_carlo_total_taxes_median_delta"
        ]
        == 20_000
    )


def test_optimize_roth_conversions_tool_serializes_result(monkeypatch):
    """Roth optimization MCP tool should emit plain JSON."""
    sample_result = RothOptimizationResult(
        results=[
            RothConversionComparisonItem(
                conversion_policy="fixed_amount",
                scenario_label="$25,000 per year (ages 60-64)",
                annual_conversion_amount=25_000,
                conversion_start_age=60,
                conversion_end_age=64,
                monte_carlo=RothConversionScenarioSummary(
                    success_rate=0.92,
                    median_final_value=1_850_000,
                    median_final_value_real=930_000,
                    total_taxes_median=295_000,
                    total_withdrawn_median=1_200_000,
                    total_roth_conversions_median=125_000,
                ),
                historical=HistoricalRothConversionSummary(
                    success_rate=0.82,
                    median_final_value=1_550_000,
                    median_final_value_real=740_000,
                    total_taxes_median=285_000,
                    total_withdrawn_median=1_180_000,
                    total_roth_conversions_median=125_000,
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
                    monte_carlo_total_roth_conversions_median_delta=125_000,
                    historical_worst_final_value_real_delta=30_000,
                ),
            )
        ],
        baseline_scenario_label="No annual conversion",
        baseline_conversion_amount=0,
        top_scoring_scenario_label="$25,000 per year (ages 60-64)",
        top_scoring_conversion_amount=25_000,
        lowest_modeled_tax_scenario_label="No annual conversion",
        lowest_modeled_tax_amount=0,
        strongest_historical_scenario_label="$25,000 per year (ages 60-64)",
        strongest_historical_conversion_amount=25_000,
        candidate_count=7,
        candidate_start_ages=[60, 65],
        window_lengths=[5, 10],
        lowest_medicare_premium_scenario_label="No annual conversion",
        lowest_medicare_premium_conversion_amount=0,
        highest_real_ending_wealth_scenario_label="$25,000 per year (ages 60-64)",
        highest_real_ending_wealth_conversion_amount=25_000,
        summary="$25,000 per year (ages 60-64) is the current score leader.",
    )

    class FakeEngine:
        def optimize_roth_conversions(self, request):
            assert request.base_input.holdings is not None
            return sample_result

    monkeypatch.setattr("eggnest.mcp_tools.get_engine", lambda: FakeEngine())
    result = optimize_roth_conversions_tool(
        base_input={
            "annual_spending": 60_000,
            "current_age": 60,
            "max_age": 95,
            "gender": "male",
            "has_spouse": False,
            "has_annuity": False,
            "holdings": [
                {
                    "account_type": "taxable",
                    "fund": "sp500",
                    "balance": 300_000,
                    "cost_basis": 250_000,
                },
                {
                    "account_type": "traditional_401k",
                    "fund": "treasury",
                    "balance": 700_000,
                },
            ],
        },
        annual_conversion_amounts=[0, 25_000],
        candidate_start_ages=[60, 65],
        window_lengths=[5, 10],
    )

    assert result["candidate_count"] == 7


def test_optimize_roth_conversions_report_tool_serializes_artifact(monkeypatch):
    """Roth optimization report MCP tool should emit the export artifact shape."""
    sample_result = RothOptimizationResult(
        results=[
            RothConversionComparisonItem(
                conversion_policy="fixed_amount",
                scenario_label="$25,000 per year (ages 60-64)",
                annual_conversion_amount=25_000,
                conversion_start_age=60,
                conversion_end_age=64,
                monte_carlo=RothConversionScenarioSummary(
                    success_rate=0.92,
                    median_final_value=1_850_000,
                    median_final_value_real=930_000,
                    total_taxes_median=295_000,
                    total_withdrawn_median=1_200_000,
                    total_roth_conversions_median=125_000,
                    year_breakdown=[],
                ),
                historical=HistoricalRothConversionSummary(
                    success_rate=0.82,
                    median_final_value=1_550_000,
                    median_final_value_real=740_000,
                    total_taxes_median=285_000,
                    total_withdrawn_median=1_180_000,
                    total_roth_conversions_median=125_000,
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
                    monte_carlo_total_roth_conversions_median_delta=125_000,
                    historical_worst_final_value_real_delta=30_000,
                ),
            )
        ],
        baseline_scenario_label="No annual conversion",
        baseline_conversion_amount=0,
        top_scoring_scenario_label="$25,000 per year (ages 60-64)",
        top_scoring_conversion_amount=25_000,
        lowest_modeled_tax_scenario_label="No annual conversion",
        lowest_modeled_tax_amount=0,
        strongest_historical_scenario_label="$25,000 per year (ages 60-64)",
        strongest_historical_conversion_amount=25_000,
        candidate_count=7,
        candidate_start_ages=[60, 65],
        window_lengths=[5, 10],
        lowest_medicare_premium_scenario_label="No annual conversion",
        lowest_medicare_premium_conversion_amount=0,
        highest_real_ending_wealth_scenario_label="$25,000 per year (ages 60-64)",
        highest_real_ending_wealth_conversion_amount=25_000,
        summary="$25,000 per year (ages 60-64) is the current score leader.",
    )

    class FakeEngine:
        def optimize_roth_conversions(self, request):
            assert request.base_input.holdings is not None
            return sample_result

    monkeypatch.setattr("eggnest.mcp_tools.get_engine", lambda: FakeEngine())
    result = optimize_roth_conversions_report_tool(
        base_input={
            "annual_spending": 60_000,
            "current_age": 60,
            "max_age": 95,
            "gender": "male",
            "has_spouse": False,
            "has_annuity": False,
            "holdings": [
                {
                    "account_type": "taxable",
                    "fund": "sp500",
                    "balance": 300_000,
                    "cost_basis": 250_000,
                },
                {
                    "account_type": "traditional_401k",
                    "fund": "treasury",
                    "balance": 700_000,
                },
            ],
        },
        annual_conversion_amounts=[0, 25_000],
        candidate_start_ages=[60, 65],
        window_lengths=[5, 10],
    )

    assert result["artifact_type"] == "eggnest_roth_optimization_report"
    assert result["search_space"]["candidate_count"] == 7
    assert result["leaders"]["score_leader"] == "$25,000 per year (ages 60-64)"
    assert result["search_space"]["candidate_start_ages"] == [60, 65]
    assert result["leaders"]["lowest_medicare_premium"] == "No annual conversion"
    assert result["results"][0]["monte_carlo"]["total_roth_conversions_median"] == 125_000
    assert result["results"][0]["monte_carlo"]["year_breakdown"] == []
