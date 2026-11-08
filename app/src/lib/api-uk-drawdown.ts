/** Client for the one-year UK drawdown calculator. */

import { apiFetch, LONG_TIMEOUT_MS } from "./api";

export type DrawSource = "sipp" | "isa" | "gia" | "cash";
export type DrawPattern = "regular" | "one_off";
export type DrawRegion = "England" | "Wales" | "Northern Ireland";
export type DrawMarkerKind = "pot_income_covered" | "guarantee_credit_ends";

export interface UKDrawdownYearInput {
  birth_date: string;
  region: DrawRegion;
  tax_year: 2026;
  state_pension: number;
  other_pension_income: number;
  employment_income: number;
  savings_interest: number;
  dividend_income: number;
  sipp_balance: number;
  isa_balance: number;
  gia_balance: number;
  cash_savings: number;
  draw_source: DrawSource;
  draw_amount: number;
  sipp_draw_pattern: DrawPattern;
  sipp_tax_free_fraction: number;
  lump_sum_allowance_remaining: number;
  gilt_yield_percent: number;
  annuity_income_per_1000: number | null;
}

export interface DrawdownCitation {
  id: string;
  url: string;
}

export interface DrawdownFigure {
  amount: number;
  engine: string;
  citations: DrawdownCitation[];
}

export interface DrawdownOutcome {
  draw: number;
  taxable_draw: number;
  income_tax: number;
  employee_ni: number;
  pension_credit: number;
  money_to_spend: number;
}

export interface DrawdownSlice {
  draw_from: number;
  draw_to: number;
  kept: number;
  to_tax: number;
  to_pension_credit: number;
}

export interface DrawdownMarker {
  kind: DrawMarkerKind;
  draw: number;
}

export interface DrawdownPensionCreditWorking {
  status: "calculated" | "under_qualifying_age";
  qualifying_date: string;
  eligible_weeks: number;
  weekly_minimum_guarantee: number | null;
  annual_annuity_income: number;
  annuity_income_per_1000: number;
  annuity_age: number;
  state_pension: number;
  other_pension_income: number;
  earnings_counted: number;
  regular_pot_income: number;
  notional_pot_income: number;
  tax_deducted: number;
  deemed_income_first_week: number;
  deemed_income_last_week: number;
  capital_first_week: number;
  capital_last_week: number;
}

export interface UKDrawdownYearResult {
  tax_year_label: string;
  draw_source: DrawSource;
  sipp_draw_pattern: DrawPattern;
  pot_left: number;
  income_tax: DrawdownFigure;
  employee_ni: DrawdownFigure;
  pension_credit: DrawdownFigure;
  money_to_spend: number;
  at_chosen_draw: DrawdownOutcome;
  with_no_draw: DrawdownOutcome;
  next_1000: DrawdownSlice | null;
  pension_credit_working: DrawdownPensionCreditWorking;
  sweep: DrawdownOutcome[];
  bands: DrawdownSlice[];
  markers: DrawdownMarker[];
  assumptions: {
    tax_free_fraction_applied: number;
    money_spent_evenly_through_year: boolean;
    gilt_yield_percent_used: number | null;
  };
}

interface DrawdownEnvelope {
  outputs: { uk_drawdown_year_result: UKDrawdownYearResult };
  caveats: string[];
  sources: { name: string; url: string | null; version: string | null; notes: string | null }[];
}

export interface UKDrawdownRun {
  result: UKDrawdownYearResult;
  caveats: string[];
  sources: DrawdownEnvelope["sources"];
}

export function buildUKDrawdownScenario(inputs: UKDrawdownYearInput) {
  return {
    schema_version: "eggnest.scenario.v1",
    engine: "uk_drawdown_year",
    country: "GBR",
    inputs,
    tags: {},
  };
}

export async function runUKDrawdownYear(
  inputs: UKDrawdownYearInput,
  signal?: AbortSignal,
): Promise<UKDrawdownRun> {
  const envelope = await apiFetch<DrawdownEnvelope>("/core/simulate", {
    method: "POST",
    body: buildUKDrawdownScenario(inputs),
    signal,
    timeoutMs: LONG_TIMEOUT_MS,
  });
  return {
    result: envelope.outputs.uk_drawdown_year_result,
    caveats: envelope.caveats,
    sources: envelope.sources,
  };
}
