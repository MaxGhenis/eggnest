/** Copy for the UK simulator's Pension Credit (guarantee credit) screen. */

import type { UKPensionCreditScreen } from "./api-uk";
import { formatGBP, formatPct, formatPct1 } from "./uk-outcome";

export type PensionCreditTone = "indicated" | "clear" | "not_screened";

export interface PensionCreditSummary {
  tone: PensionCreditTone;
  headline: string;
  detail: string | null;
}

/** "67" or "66 years and 7 months". */
export function formatQualifyingAge(years: number, months: number): string {
  if (!months) return `${years}`;
  return `${years} years and ${months} month${months === 1 ? "" : "s"}`;
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export function summarizePensionCredit(
  screen: UKPensionCreditScreen,
  maxAge: number,
): PensionCreditSummary {
  const qualifyingAge = formatQualifyingAge(
    screen.qualifying_age_years,
    screen.qualifying_age_months,
  );
  if (screen.status === "under_qualifying_age") {
    return {
      tone: "not_screened",
      headline:
        `Pension Credit starts at State Pension age, ${qualifyingAge} for you, ` +
        `which comes after this plan ends at ${maxAge}, so it isn't screened.`,
      detail: null,
    };
  }

  const weekly = formatGBP(screen.weekly_minimum_guarantee ?? 0);
  const paths = screen.paths_screened.toLocaleString("en-GB");
  const share = screen.share_of_paths_indicated;
  if (share <= 0) {
    return {
      tone: "clear",
      headline:
        `In none of the ${paths} simulated paths screened does income, as ` +
        `Pension Credit counts it, fall below the minimum guarantee ` +
        `(${weekly}/week) from your State Pension age (${qualifyingAge}).`,
      detail: null,
    };
  }

  const amounts = screen.median_annual_amount_by_age.filter((amount) => amount > 0);
  const typical = amounts.length ? median(amounts) : 0;
  const shareText = share < 0.1 ? formatPct1(share) : formatPct(share);
  const from =
    screen.first_age_indicated != null ? `, typically from age ${screen.first_age_indicated}` : "";
  return {
    tone: "indicated",
    headline:
      `In ${shareText} of ${paths} simulated paths, income as Pension Credit ` +
      `counts it falls below the minimum guarantee (${weekly}/week) in at ` +
      `least one year from your State Pension age (${qualifyingAge})${from}.`,
    detail:
      `Where it does, the guarantee credit would be around ` +
      `${formatGBP(typical)}/year. Checking eligibility with the DWP could ` +
      `matter more than withdrawal strategy in those years.`,
  };
}

/** A readable label for a citation id: engine rule ids lose their prefix. */
export function citationLabel(id: string): string {
  return id.replace(/^uk:/, "").replace("#", " — ");
}
