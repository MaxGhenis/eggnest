"""Helpers for export-friendly Roth optimization artifacts."""

from __future__ import annotations

from datetime import UTC, datetime

from .models import (
    RothOptimizationLeaders,
    RothOptimizationReportArtifact,
    RothOptimizationResult,
    RothOptimizationSearchSpace,
)


def build_roth_optimization_report_artifact(
    result: RothOptimizationResult,
    *,
    generated_at: str | None = None,
) -> RothOptimizationReportArtifact:
    """Build a stable export artifact from a Roth optimization result."""
    if generated_at is None:
        generated_at = datetime.now(UTC).isoformat()

    score_leader = next(
        (
            item
            for item in result.results
            if item.scenario_label == result.top_scoring_scenario_label
        ),
        None,
    )

    return RothOptimizationReportArtifact(
        generated_at=generated_at,
        baseline_scenario_label=result.baseline_scenario_label,
        summary=result.summary,
        metadata=result.metadata,
        search_space=RothOptimizationSearchSpace(
            candidate_count=result.candidate_count,
            candidate_start_ages=result.candidate_start_ages,
            window_lengths=result.window_lengths,
        ),
        leaders=RothOptimizationLeaders(
            score_leader=result.top_scoring_scenario_label,
            lowest_modeled_tax=result.lowest_modeled_tax_scenario_label,
            lowest_medicare_premium=result.lowest_medicare_premium_scenario_label,
            highest_real_ending_wealth=result.highest_real_ending_wealth_scenario_label,
            strongest_historical=result.strongest_historical_scenario_label,
        ),
        results=result.results,
        representative_cliff_ledger=(
            score_leader.monte_carlo.year_breakdown if score_leader is not None else []
        ),
    )
