"""Tests for the engine-first local modeling interface."""

import pytest

from eggnest.engine import EggnestEngine, describe_engine
from eggnest.models import (
    HistoricalRothConversionSummary,
    RothConversionComparisonItem,
    RothConversionInput,
    RothConversionScenarioDelta,
    RothConversionScenarioSummary,
    RothOptimizationInput,
    RothOptimizationResult,
    SimulationInput,
    SimulationResult,
    YearBreakdown,
)


def test_describe_engine_exposes_core_capabilities():
    """Engine description should advertise the primary local interfaces."""
    info = describe_engine()

    assert info["name"] == "EggNest"
    assert "simulate" in info["capabilities"]
    assert "historical_backtest" in info["capabilities"]
    assert "compare_withdrawal_strategies" in info["capabilities"]
    assert "compare_roth_conversions" in info["capabilities"]
    assert "optimize_roth_conversions" in info["capabilities"]
    assert "optimize_roth_conversions_report" in info["capabilities"]


def test_compare_withdrawal_strategies_requires_holdings():
    """Strategy comparison should reject legacy total-portfolio mode."""
    engine = EggnestEngine()
    comparison = {
        "base_input": SimulationInput(
            initial_capital=1_000_000,
            annual_spending=60_000,
            current_age=60,
            max_age=95,
            gender="male",
            has_spouse=False,
            has_annuity=False,
        ).model_dump(mode="json")
    }

    try:
        engine.compare_withdrawal_strategies(comparison)
    except ValueError as exc:
        assert "detailed holdings" in str(exc)
    else:
        raise AssertionError("Expected missing-holdings validation error")


def test_simulate_stamps_metadata(monkeypatch):
    """Engine simulate should stamp reproducibility metadata on results."""
    sample_result = SimulationResult(
        success_rate=0.9,
        median_final_value=1_500_000,
        mean_final_value=1_700_000,
        median_final_value_real=800_000,
        mean_final_value_real=900_000,
        percentiles={
            "p5": 50_000,
            "p25": 600_000,
            "p50": 1_500_000,
            "p75": 2_300_000,
            "p95": 3_500_000,
        },
        percentiles_real={
            "p5": 25_000,
            "p25": 300_000,
            "p50": 800_000,
            "p75": 1_200_000,
            "p95": 1_900_000,
        },
        median_depletion_age=None,
        total_withdrawn_median=1_200_000,
        total_taxes_median=220_000,
        percentile_paths={"p50": [1_000_000, 1_050_000]},
        year_breakdown=[],
        initial_withdrawal_rate=4.0,
        prob_10_year_failure=0.04,
    )

    class FakeSimulator:
        def __init__(self, params):
            self.params = params

        def run(self):
            return sample_result

    monkeypatch.setattr("eggnest.engine.MonteCarloSimulator", FakeSimulator)

    result = EggnestEngine().simulate(
        {
            "initial_capital": 1_000_000,
            "annual_spending": 60_000,
            "current_age": 60,
            "max_age": 95,
            "gender": "male",
            "has_spouse": False,
            "has_annuity": False,
            "random_seed": 123,
        }
    )

    assert result.metadata is not None
    assert result.metadata.random_seed == 123
    assert result.metadata.engine_version
    assert result.metadata.method_version
    assert "bootstrap returns" in result.metadata.assumptions_summary


def test_compare_withdrawal_strategies_ranks_results(monkeypatch):
    """Strategy comparison should build scored results from summary helpers."""
    engine = EggnestEngine()
    base_input = SimulationInput(
        annual_spending=60_000,
        current_age=60,
        max_age=95,
        gender="male",
        has_spouse=False,
        has_annuity=False,
        holdings=[
            {
                "account_type": "taxable",
                "fund": "sp500",
                "balance": 250_000,
                "cost_basis": 200_000,
            },
            {
                "account_type": "traditional_401k",
                "fund": "treasury",
                "balance": 750_000,
            },
        ],
    )

    def fake_simulation_summary(params_payload):
        strategy = params_payload["withdrawal_strategy"]
        if strategy == "taxable_first":
            return {
                "success_rate": 0.91,
                "median_final_value": 1_800_000,
                "median_final_value_real": 900_000,
                "total_taxes_median": 280_000,
                "total_medicare_premiums_median": 12_000,
                "total_withdrawn_median": 1_200_000,
                "percentiles": {"p5": 100_000, "p95": 3_000_000},
            }
        return {
            "success_rate": 0.86,
            "median_final_value": 1_600_000,
            "median_final_value_real": 820_000,
            "total_taxes_median": 310_000,
            "total_medicare_premiums_median": 15_000,
            "total_withdrawn_median": 1_230_000,
            "percentiles": {"p5": 100_000, "p95": 2_800_000},
        }

    def fake_historical_summary(params_payload):
        strategy = params_payload["withdrawal_strategy"]
        if strategy == "taxable_first":
            return {
                "success_rate": 0.79,
                "median_final_value": 1_500_000,
                "median_final_value_real": 700_000,
                "total_taxes_median": 260_000,
                "total_medicare_premiums_median": 11_000,
                "total_withdrawn_median": 1_180_000,
                "cohort_count": 40,
                "strongest_start_year": 1982,
                "weakest_start_year": 1966,
                "worst_final_value_real": 120_000,
            }
        return {
            "success_rate": 0.72,
            "median_final_value": 1_350_000,
            "median_final_value_real": 640_000,
            "total_taxes_median": 290_000,
            "total_medicare_premiums_median": 14_000,
            "total_withdrawn_median": 1_200_000,
            "cohort_count": 40,
            "strongest_start_year": 1982,
            "weakest_start_year": 1973,
            "worst_final_value_real": 80_000,
        }

    monkeypatch.setattr(
        "eggnest.engine._run_simulation_summary",
        fake_simulation_summary,
    )
    monkeypatch.setattr(
        "eggnest.engine._run_historical_backtest_summary",
        fake_historical_summary,
    )

    result = engine.compare_withdrawal_strategies(
        {
            "base_input": base_input.model_dump(mode="json"),
            "strategies": ["taxable_first", "pro_rata"],
        }
    )

    assert result.top_scoring_strategy == "taxable_first"
    assert result.results[0].strategy == "taxable_first"
    assert result.results[0].blended_score > result.results[1].blended_score


def test_compare_roth_conversions_requires_holdings():
    """Roth conversion comparison should reject legacy total-portfolio mode."""
    engine = EggnestEngine()
    comparison = {
        "base_input": SimulationInput(
            initial_capital=1_000_000,
            annual_spending=60_000,
            current_age=60,
            max_age=95,
            gender="male",
            has_spouse=False,
            has_annuity=False,
        ).model_dump(mode="json")
    }

    try:
        engine.compare_roth_conversions(comparison)
    except ValueError as exc:
        assert "detailed holdings" in str(exc)
    else:
        raise AssertionError("Expected missing-holdings validation error")


def test_roth_conversion_inputs_allow_post_rmd_start_when_end_is_omitted():
    """Default end-age logic should respect an explicit post-RMD conversion start age."""
    base_input = SimulationInput(
        annual_spending=60_000,
        current_age=60,
        max_age=95,
        gender="male",
        has_spouse=False,
        has_annuity=False,
        holdings=[
            {
                "account_type": "traditional_401k",
                "fund": "treasury",
                "balance": 750_000,
            },
        ],
    )

    request = RothConversionInput(
        base_input=base_input,
        annual_conversion_amounts=[25_000],
        conversion_start_age=75,
    )

    assert request.conversion_start_age == 75


def test_compare_roth_conversions_ranks_results(monkeypatch):
    """Roth comparison should support mixed fixed-amount and bracket-fill scenarios."""
    engine = EggnestEngine()
    base_input = SimulationInput(
        annual_spending=60_000,
        current_age=60,
        max_age=95,
        gender="male",
        has_spouse=False,
        has_annuity=False,
        holdings=[
            {
                "account_type": "taxable",
                "fund": "sp500",
                "balance": 250_000,
                "cost_basis": 200_000,
            },
            {
                "account_type": "traditional_401k",
                "fund": "treasury",
                "balance": 750_000,
            },
        ],
    )

    def fake_simulation_result(params_payload):
        policy = params_payload["roth_conversion_policy"]
        amount = params_payload["roth_conversion_amount"]
        if policy == "fill_12_percent_bracket":
            return SimulationResult(
                success_rate=0.94,
                median_final_value=1_920_000,
                mean_final_value=1_970_000,
                median_final_value_real=970_000,
                mean_final_value_real=1_000_000,
                percentiles={
                    "p5": 105_000,
                    "p25": 690_000,
                    "p50": 1_920_000,
                    "p75": 2_460_000,
                    "p95": 3_050_000,
                },
                percentiles_real={
                    "p5": 52_000,
                    "p25": 360_000,
                    "p50": 970_000,
                    "p75": 1_340_000,
                    "p95": 1_740_000,
                },
                median_depletion_age=None,
                total_withdrawn_median=1_180_000,
                total_taxes_median=270_000,
                total_medicare_premiums_median=16_000,
                total_roth_conversions_median=310_000,
                percentile_paths={"p50": [1_000_000, 1_120_000]},
                year_breakdown=[
                    YearBreakdown(
                        age=66,
                        year_index=0,
                        portfolio_start=1_000_000,
                        portfolio_end=1_120_000,
                        portfolio_return=0.12,
                        total_income=60_000,
                        withdrawal=25_000,
                        total_tax=10_000,
                        net_income=75_000,
                        roth_conversion=25_000,
                        medicare_part_b_premium=3_108,
                        medicare_part_d_premium_surcharge=423.6,
                        medicare_total_premium=3_531.6,
                    )
                ],
                initial_withdrawal_rate=4.0,
                prob_10_year_failure=0.01,
            )
        if amount == 25_000:
            return SimulationResult(
                success_rate=0.92,
                median_final_value=1_850_000,
                mean_final_value=1_900_000,
                median_final_value_real=930_000,
                mean_final_value_real=960_000,
                percentiles={
                    "p5": 100_000,
                    "p25": 650_000,
                    "p50": 1_850_000,
                    "p75": 2_400_000,
                    "p95": 3_000_000,
                },
                percentiles_real={
                    "p5": 50_000,
                    "p25": 350_000,
                    "p50": 930_000,
                    "p75": 1_300_000,
                    "p95": 1_700_000,
                },
                median_depletion_age=None,
                total_withdrawn_median=1_200_000,
                total_taxes_median=295_000,
                total_medicare_premiums_median=14_000,
                total_roth_conversions_median=250_000,
                percentile_paths={"p50": [1_000_000, 1_100_000]},
                year_breakdown=[
                    YearBreakdown(
                        age=66,
                        year_index=0,
                        portfolio_start=1_000_000,
                        portfolio_end=1_100_000,
                        portfolio_return=0.10,
                        total_income=60_000,
                        withdrawal=25_000,
                        total_tax=10_000,
                        net_income=75_000,
                        roth_conversion=25_000,
                        medicare_part_b_premium=3_000,
                        medicare_part_d_premium_surcharge=200.0,
                        medicare_total_premium=3_200.0,
                    )
                ],
                initial_withdrawal_rate=4.0,
                prob_10_year_failure=0.01,
            )
        return SimulationResult(
            success_rate=0.89,
            median_final_value=1_780_000,
            mean_final_value=1_820_000,
            median_final_value_real=880_000,
            mean_final_value_real=910_000,
            percentiles={
                "p5": 90_000,
                "p25": 600_000,
                "p50": 1_780_000,
                "p75": 2_350_000,
                "p95": 2_900_000,
            },
            percentiles_real={
                "p5": 45_000,
                "p25": 320_000,
                "p50": 880_000,
                "p75": 1_250_000,
                "p95": 1_650_000,
            },
            median_depletion_age=None,
            total_withdrawn_median=1_210_000,
            total_taxes_median=255_000,
            total_medicare_premiums_median=9_000,
            total_roth_conversions_median=0,
            percentile_paths={"p50": [1_000_000, 1_090_000]},
            year_breakdown=[
                YearBreakdown(
                    age=66,
                    year_index=0,
                    portfolio_start=1_000_000,
                    portfolio_end=1_090_000,
                    portfolio_return=0.09,
                    total_income=60_000,
                    withdrawal=0,
                    total_tax=8_000,
                    net_income=52_000,
                    medicare_part_b_premium=2_220,
                    medicare_total_premium=2_220,
                )
            ],
            initial_withdrawal_rate=4.0,
            prob_10_year_failure=0.02,
        )

    def fake_historical_summary(params_payload):
        policy = params_payload["roth_conversion_policy"]
        amount = params_payload["roth_conversion_amount"]
        if policy == "fill_12_percent_bracket":
            return {
                "success_rate": 0.84,
                "median_final_value": 1_600_000,
                "median_final_value_real": 770_000,
                "total_taxes_median": 265_000,
                "total_medicare_premiums_median": 15_000,
                "total_withdrawn_median": 1_170_000,
                "total_roth_conversions_median": 310_000,
                "cohort_count": 40,
                "strongest_start_year": 1982,
                "weakest_start_year": 1966,
                "worst_final_value_real": 170_000,
            }
        if amount == 25_000:
            return {
                "success_rate": 0.82,
                "median_final_value": 1_550_000,
                "median_final_value_real": 740_000,
                "total_taxes_median": 285_000,
                "total_medicare_premiums_median": 13_000,
                "total_withdrawn_median": 1_180_000,
                "total_roth_conversions_median": 250_000,
                "cohort_count": 40,
                "strongest_start_year": 1982,
                "weakest_start_year": 1966,
                "worst_final_value_real": 150_000,
            }
        return {
            "success_rate": 0.75,
            "median_final_value": 1_450_000,
            "median_final_value_real": 680_000,
            "total_taxes_median": 245_000,
            "total_medicare_premiums_median": 9_000,
            "total_withdrawn_median": 1_190_000,
            "total_roth_conversions_median": 0,
            "cohort_count": 40,
            "strongest_start_year": 1982,
            "weakest_start_year": 1973,
            "worst_final_value_real": 90_000,
        }

    monkeypatch.setattr(
        "eggnest.engine._run_simulation_result",
        fake_simulation_result,
    )
    monkeypatch.setattr(
        "eggnest.engine._run_historical_backtest_summary",
        fake_historical_summary,
    )

    result = engine.compare_roth_conversions(
        {
            "base_input": base_input.model_dump(mode="json"),
            "annual_conversion_amounts": [0, 25_000],
            "conversion_policies": ["fill_12_percent_bracket"],
            "conversion_start_age": 60,
            "conversion_end_age": 69,
        }
    )

    assert result.top_scoring_scenario_label == "Fill 12% bracket"
    assert result.top_scoring_conversion_amount is None
    assert result.baseline_scenario_label == "No annual conversion"
    assert result.baseline_conversion_amount == 0
    assert result.results[0].scenario_label == "Fill 12% bracket"
    assert result.results[0].conversion_policy == "fill_12_percent_bracket"
    assert result.results[0].monte_carlo.total_roth_conversions_median == 310_000
    assert (
        result.results[0].delta_vs_baseline.monte_carlo_median_final_value_real_delta
        == 90_000
    )
    assert (
        result.results[0].delta_vs_baseline.monte_carlo_total_taxes_median_delta
        == 15_000
    )
    assert (
        result.results[0].delta_vs_baseline.monte_carlo_total_medicare_premiums_median_delta
        == 7_000
    )
    assert (
        result.results[0].monte_carlo.year_breakdown[0].medicare_premium_delta_vs_baseline
        == pytest.approx(1_311.6)
    )
    assert result.results[0].blended_score > result.results[1].blended_score
    assert result.metadata is not None
    assert result.metadata.random_seed is not None
    assert "roth scenarios" in result.metadata.assumptions_summary


def test_optimize_roth_conversions_searches_windows(monkeypatch):
    """Roth optimization should search bounded age windows and expose objective leaders."""
    engine = EggnestEngine()
    base_input = SimulationInput(
        annual_spending=60_000,
        current_age=60,
        max_age=95,
        gender="male",
        has_spouse=False,
        has_annuity=False,
        holdings=[
            {
                "account_type": "taxable",
                "fund": "sp500",
                "balance": 250_000,
                "cost_basis": 200_000,
            },
            {
                "account_type": "traditional_401k",
                "fund": "treasury",
                "balance": 750_000,
            },
        ],
    )

    def fake_simulation_result(params_payload):
        start_age = params_payload["roth_conversion_start_age"]
        end_age = params_payload["roth_conversion_end_age"]
        amount = params_payload["roth_conversion_amount"]
        policy = params_payload["roth_conversion_policy"]
        duration = end_age - start_age + 1
        score_bonus = 80_000 if policy == "fill_12_percent_bracket" and start_age == 60 else 0
        medicare = 9_000 + duration * 100 + amount / 1_000
        if policy == "fill_12_percent_bracket":
            medicare += 1_500
        if abs(amount) < 1e-9 and policy == "fixed_amount":
            medicare = 8_000

        return SimulationResult(
            success_rate=0.88 + (0.03 if score_bonus else 0),
            median_final_value=1_700_000 + score_bonus,
            mean_final_value=1_740_000 + score_bonus,
            median_final_value_real=850_000 + score_bonus,
            mean_final_value_real=870_000 + score_bonus,
            percentiles={
                "p5": 90_000,
                "p25": 600_000,
                "p50": 1_700_000 + score_bonus,
                "p75": 2_250_000 + score_bonus,
                "p95": 2_900_000 + score_bonus,
            },
            percentiles_real={
                "p5": 45_000,
                "p25": 310_000,
                "p50": 850_000 + score_bonus,
                "p75": 1_180_000 + score_bonus,
                "p95": 1_560_000 + score_bonus,
            },
            median_depletion_age=None,
            total_withdrawn_median=1_200_000,
            total_taxes_median=240_000 + amount / 2_000 + (15_000 if score_bonus else 0),
            total_medicare_premiums_median=medicare,
            total_roth_conversions_median=amount * duration,
            percentile_paths={"p50": [1_000_000, 1_050_000]},
            year_breakdown=[
                YearBreakdown(
                    age=start_age,
                    year_index=0,
                    portfolio_start=1_000_000,
                    portfolio_end=1_050_000,
                    portfolio_return=0.05,
                    total_income=60_000,
                    withdrawal=amount,
                    total_tax=9_000,
                    net_income=51_000,
                    roth_conversion=amount,
                    medicare_total_premium=medicare / max(duration, 1),
                )
            ],
            initial_withdrawal_rate=4.0,
            prob_10_year_failure=0.02,
        )

    def fake_historical_summary(params_payload):
        start_age = params_payload["roth_conversion_start_age"]
        amount = params_payload["roth_conversion_amount"]
        policy = params_payload["roth_conversion_policy"]
        score_bonus = 70_000 if policy == "fill_12_percent_bracket" and start_age == 60 else 0
        return {
            "success_rate": 0.76 + (0.04 if score_bonus else 0),
            "median_final_value": 1_420_000 + score_bonus,
            "median_final_value_real": 690_000 + score_bonus,
            "total_taxes_median": 230_000 + amount / 2_500,
            "total_medicare_premiums_median": 8_500 + amount / 1_200,
            "total_withdrawn_median": 1_180_000,
            "total_roth_conversions_median": amount * 5,
            "cohort_count": 40,
            "strongest_start_year": 1982,
            "weakest_start_year": 1966,
            "worst_final_value_real": 120_000 + score_bonus,
        }

    monkeypatch.setattr("eggnest.engine._run_simulation_result", fake_simulation_result)
    monkeypatch.setattr(
        "eggnest.engine._run_historical_backtest_summary",
        fake_historical_summary,
    )

    result = engine.optimize_roth_conversions(
        RothOptimizationInput(
            base_input=base_input,
            annual_conversion_amounts=[0, 25_000],
            conversion_policies=["fill_12_percent_bracket"],
            candidate_start_ages=[60, 65],
            window_lengths=[5],
        )
    )

    assert result.candidate_count == 9
    assert result.candidate_start_ages == [60, 65]
    assert result.window_lengths == [5]
    assert result.top_scoring_scenario_label == "Fill 12% bracket (ages 60-64)"


def test_optimize_roth_conversions_report_wraps_result(monkeypatch):
    """Engine should expose a report artifact for Roth optimization."""
    engine = EggnestEngine()
    base_input = SimulationInput(
        annual_spending=60_000,
        current_age=60,
        max_age=95,
        gender="male",
        has_spouse=False,
        has_annuity=False,
        holdings=[
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
    )

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
                delta_vs_baseline=RothConversionScenarioDelta(),
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

    monkeypatch.setattr(engine, "optimize_roth_conversions", lambda payload: sample_result)
    artifact = engine.optimize_roth_conversions_report(
        {"base_input": base_input.model_dump(mode="json")}
    )

    assert artifact.artifact_type == "eggnest_roth_optimization_report"
    assert artifact.leaders.score_leader == "$25,000 per year (ages 60-64)"
    assert artifact.search_space.candidate_count == 7
    assert artifact.leaders.lowest_medicare_premium == "No annual conversion"
    assert (
        artifact.leaders.highest_real_ending_wealth
        == "$25,000 per year (ages 60-64)"
    )
    assert artifact.results[0].scenario_label == "$25,000 per year (ages 60-64)"
