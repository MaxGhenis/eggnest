/** Copy and figures for the UK simulator's outcome summary. */

import type { UKSimulationInput, UKSimulationResult } from "./api-uk";

export interface UKOutcomeMetric {
  label: string;
  value: string;
  detail: string;
}

export interface UKOutcomeSummary {
  headline: UKOutcomeMetric;
  metrics: UKOutcomeMetric[];
  /** Shown only when some paths run short while their SIPP is locked. */
  sippLockedNote: string | null;
}

/** Age from which this model lets the SIPP be drawn (Minimum Pension Age). */
export const UK_MINIMUM_PENSION_AGE = 55;

export function formatGBP(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `£${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `£${(value / 1_000).toFixed(0)}k`;
  return `£${Math.round(value)}`;
}

export function formatPct(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

export function formatPct1(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/** A ten-year measure needs more than ten simulated years to mean anything. */
export function hasTenYearHorizon(result: UKSimulationResult): boolean {
  return (result.percentile_paths?.p50?.length ?? 0) > 10;
}

export function summarizeUKOutcome(
  input: UKSimulationInput,
  result: UKSimulationResult,
): UKOutcomeSummary {
  const withMortality = input.include_mortality ?? true;
  const tenYear = hasTenYearHorizon(result);
  const lifetimeTax = result.year_breakdown.reduce((sum, row) => sum + row.total_tax, 0);
  const locked = result.sipp_locked_shortfall_rate ?? 0;

  return {
    headline: {
      label: "Spending covered",
      value: formatPct(result.success_rate),
      detail: withMortality
        ? `of simulated paths meet your spending in every year you're alive, to age ${input.max_age}`
        : `of simulated paths meet your spending in every year to age ${input.max_age}`,
    },
    metrics: [
      {
        label: "Shortfall within 10 years",
        value: tenYear ? formatPct1(result.prob_10_year_failure) : "—",
        detail: tenYear
          ? "Chance spending first falls short"
          : "Needs a horizon over 10 years",
      },
      {
        label: `Covered to age ${input.max_age}`,
        value: formatPct(result.strict_horizon_success_rate),
        detail: "Ignoring mortality",
      },
      {
        label: "First-year withdrawal",
        value: `${result.initial_withdrawal_rate.toFixed(1)}%`,
        detail: "Of starting portfolio",
      },
      {
        label: "Lifetime tax",
        value: formatGBP(lifetimeTax),
        detail: "Sum of yearly medians · income tax & NI",
      },
    ],
    sippLockedNote:
      locked > 0
        ? `${locked < 0.1 ? formatPct1(locked) : formatPct(locked)} of paths fall short ` +
          `before age ${UK_MINIMUM_PENSION_AGE} while money is still in the SIPP, ` +
          `which can't be drawn until then.`
        : null,
  };
}
