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

/** A share of paths as a whole percentage that never rounds a non-zero
 *  share to "0%" or a share short of all paths to "100%". */
export function formatShare(value: number): string {
  if (value > 0 && value < 0.005) return "<1%";
  if (value < 1 && value >= 0.995) return ">99%";
  return formatPct(value);
}

export function formatPct1(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/** formatShare to one decimal: a non-zero share never reads "0.0%" and a
 *  share short of all paths never reads "100.0%". */
export function formatShare1(value: number): string {
  if (value > 0 && value < 0.0005) return "<0.1%";
  if (value < 1 && value >= 0.9995) return ">99.9%";
  return formatPct1(value);
}

/** A ten-year measure needs more than ten simulated years to mean anything. */
export function hasTenYearHorizon(result: UKSimulationResult): boolean {
  return (result.percentile_paths?.p50?.length ?? 0) > 10;
}

/**
 * Whether the API scores success by unmet spending. APIs from before that
 * change score it by the portfolio running out and do not report
 * sipp_locked_shortfall_rate; their rates keep the depletion wording, so
 * the copy is right whichever is deployed first.
 */
export function scoresUnmetSpending(result: UKSimulationResult): boolean {
  return result.sipp_locked_shortfall_rate !== undefined;
}

export function summarizeUKOutcome(
  input: UKSimulationInput,
  result: UKSimulationResult,
): UKOutcomeSummary {
  const withMortality = input.include_mortality ?? true;
  const tenYear = hasTenYearHorizon(result);
  const lifetimeTax = result.year_breakdown.reduce((sum, row) => sum + row.total_tax, 0);
  const locked = result.sipp_locked_shortfall_rate ?? 0;
  const unmet = scoresUnmetSpending(result);

  return {
    headline: unmet
      ? {
          label: "Spending covered",
          value: formatShare(result.success_rate),
          detail: withMortality
            ? `of simulated paths meet your spending in every year you're alive, to age ${input.max_age}`
            : `of simulated paths meet your spending in every year to age ${input.max_age}`,
        }
      : {
          label: "Chance of lasting",
          value: formatShare(result.success_rate),
          detail: withMortality
            ? `of simulated paths avoid depletion before death or age ${input.max_age}`
            : `of simulated paths last through age ${input.max_age}`,
        },
    metrics: [
      {
        label: unmet ? "Shortfall within 10 years" : "10-year depletion",
        value: tenYear ? formatShare1(result.prob_10_year_failure) : "—",
        detail: tenYear
          ? unmet
            ? "Chance spending first falls short"
            : "Chance of running out"
          : "Needs a horizon over 10 years",
      },
      {
        label: unmet ? `Covered to age ${input.max_age}` : `Lasts to age ${input.max_age}`,
        value: formatShare(result.strict_horizon_success_rate),
        detail: "Ignoring mortality",
      },
      {
        label: "Spending rate",
        value: `${result.initial_withdrawal_rate.toFixed(1)}%`,
        detail: "First-year spending ÷ starting portfolio",
      },
      {
        label: "Lifetime tax",
        value: formatGBP(lifetimeTax),
        detail: `Income tax & NI · sum of yearly medians to age ${input.max_age}, in cash terms`,
      },
    ],
    sippLockedNote:
      locked > 0
        ? `${locked < 0.1 ? formatShare1(locked) : formatShare(locked)} of paths fall short ` +
          `before age ${UK_MINIMUM_PENSION_AGE} while money is still in the SIPP, ` +
          `which can't be drawn until then.`
        : null,
  };
}
