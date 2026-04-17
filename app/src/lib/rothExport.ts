import type { RothOptimizationResult } from "./api";

export interface RothOptimizationExportArtifact {
  artifact_type: "eggnest_roth_optimization_report";
  generated_at: string;
  baseline_scenario_label: string | null;
  summary: string;
  metadata: RothOptimizationResult["metadata"];
  search_space: {
    candidate_count: number;
    candidate_start_ages: number[];
    window_lengths: number[];
  };
  leaders: {
    score_leader: string;
    lowest_modeled_tax: string;
    lowest_medicare_premium: string;
    highest_real_ending_wealth: string;
    strongest_historical: string;
  };
  results: RothOptimizationResult["results"];
  representative_cliff_ledger: RothOptimizationResult["results"][number]["monte_carlo"]["year_breakdown"];
}

function csvEscape(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return "";
  const stringValue = String(value);
  if (/[",\n]/.test(stringValue)) {
    return `"${stringValue.replace(/"/g, '""')}"`;
  }
  return stringValue;
}

export function buildRothOptimizationExportArtifact(
  result: RothOptimizationResult,
  generatedAt: string = new Date().toISOString()
): RothOptimizationExportArtifact {
  const scoreLeader =
    result.results.find(
      (item) => item.scenario_label === result.top_scoring_scenario_label
    ) ?? null;

  return {
    artifact_type: "eggnest_roth_optimization_report",
    generated_at: generatedAt,
    baseline_scenario_label: result.baseline_scenario_label,
    summary: result.summary,
    metadata: result.metadata ?? null,
    search_space: {
      candidate_count: result.candidate_count,
      candidate_start_ages: result.candidate_start_ages,
      window_lengths: result.window_lengths,
    },
    leaders: {
      score_leader: result.top_scoring_scenario_label,
      lowest_modeled_tax: result.lowest_modeled_tax_scenario_label,
      lowest_medicare_premium: result.lowest_medicare_premium_scenario_label,
      highest_real_ending_wealth: result.highest_real_ending_wealth_scenario_label,
      strongest_historical: result.strongest_historical_scenario_label,
    },
    results: result.results,
    representative_cliff_ledger: scoreLeader?.monte_carlo.year_breakdown ?? [],
  };
}

export function serializeRothOptimizationCsv(
  result: RothOptimizationResult
): string {
  const headers = [
    "scenario_label",
    "conversion_policy",
    "annual_conversion_amount",
    "conversion_start_age",
    "conversion_end_age",
    "monte_carlo_success_rate",
    "historical_success_rate",
    "monte_carlo_median_final_value_real_delta",
    "monte_carlo_total_taxes_median_delta",
    "monte_carlo_total_medicare_premiums_median_delta",
    "total_roth_conversions_median",
    "blended_score",
    "is_score_leader",
    "is_lowest_modeled_tax",
    "is_lowest_medicare_premium",
    "is_highest_real_ending_wealth",
    "is_strongest_historical",
    "baseline_scenario_label",
  ];

  const rows = result.results.map((item) =>
    [
      item.scenario_label,
      item.conversion_policy,
      item.annual_conversion_amount,
      item.conversion_start_age,
      item.conversion_end_age,
      item.monte_carlo.success_rate,
      item.historical.success_rate,
      item.delta_vs_baseline.monte_carlo_median_final_value_real_delta,
      item.delta_vs_baseline.monte_carlo_total_taxes_median_delta,
      item.delta_vs_baseline.monte_carlo_total_medicare_premiums_median_delta,
      item.monte_carlo.total_roth_conversions_median,
      item.blended_score,
      item.scenario_label === result.top_scoring_scenario_label,
      item.scenario_label === result.lowest_modeled_tax_scenario_label,
      item.scenario_label === result.lowest_medicare_premium_scenario_label,
      item.scenario_label === result.highest_real_ending_wealth_scenario_label,
      item.scenario_label === result.strongest_historical_scenario_label,
      result.baseline_scenario_label,
    ]
      .map(csvEscape)
      .join(",")
  );

  return [headers.join(","), ...rows].join("\n");
}

export function makeRothOptimizationExportFilename(
  extension: "json" | "csv",
  generatedAt: string = new Date().toISOString()
): string {
  const datestamp = generatedAt.slice(0, 10);
  return `eggnest-roth-optimization-${datestamp}.${extension}`;
}

export function downloadTextFile(
  filename: string,
  content: string,
  mimeType: string
): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
