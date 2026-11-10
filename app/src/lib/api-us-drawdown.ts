/** Client for the one-year US drawdown calculator. */

import { apiFetch, LONG_TIMEOUT_MS } from "./api";

export type USDrawSource = "traditional" | "roth" | "taxable" | "cash";
export type USFilingStatus = "single" | "married_filing_jointly";
export type USDrawOwner = "you" | "spouse";
export type USMarkerKind =
  "benefit_ends" | "coverage_ends" | "medicare_surcharge_step" | "required_minimum_reached";
export type USCoverage = "medicaid" | "msp";

export interface USDrawdownPerson {
  birth_year: number;
  social_security: number;
  pension_income: number;
  government_pension_income: number;
  earnings: number;
  traditional_balance: number;
  roth_balance: number;
  other_traditional_withdrawals: number;
  roth_conversion: number;
}

export interface USDrawdownYearInput {
  tax_year: 2026;
  state: string;
  filing_status: USFilingStatus;
  you: USDrawdownPerson;
  spouse: USDrawdownPerson | null;
  taxable_interest: number;
  tax_exempt_interest: number;
  dividends: number;
  taxable_balance: number;
  taxable_gain_share: number;
  cash_savings: number;
  draw_source: USDrawSource;
  draw_owner: USDrawOwner;
  draw_amount: number;
}

export interface USCitation {
  id: string;
  source: string;
  title: string;
  url: string;
}

export interface USDrawdownFigure {
  amount: number;
  engine: string;
  citations: USCitation[];
}

export interface USDrawdownOutcome {
  draw: number;
  taxable_draw: number;
  federal_income_tax: number;
  state_income_tax: number;
  other_taxes: number;
  benefits: number;
  /** The benefits above by PolicyEngine-US program; every row lists the same programs. */
  benefits_by_program: Record<string, number>;
  taxable_social_security: number;
  medicare_income: number;
  later_medicare_surcharge: number;
  money_to_spend: number;
}

export interface USDrawdownSlice {
  draw_from: number;
  draw_to: number;
  kept: number;
  to_tax: number;
  to_benefits: number;
  social_security_taxed: number;
}

export interface USDrawdownMarker {
  kind: USMarkerKind;
  draw: number;
  program: string | null;
  amount: number | null;
}

export interface USRequiredMinimum {
  person: USDrawOwner;
  age: number;
  balance: number;
  divisor: number;
  amount: number;
  /** Traditional withdrawals entered besides the draw. */
  other_withdrawals: number;
  withdrawn: number;
  shortfall: number;
  excise_tax_rate: number;
  excise_tax_on_shortfall: number;
}

export interface USMedicareSurcharge {
  premium_year: number;
  rates_year: number;
  people_on_medicare: number;
  lines: number[];
  at_chosen_draw: number;
  with_no_draw: number;
}

export interface USDrawdownYearResult {
  tax_year: number;
  state: string;
  filing_status: USFilingStatus;
  draw_source: USDrawSource;
  draw_owner: USDrawOwner;
  account_left: number;
  federal_income_tax: USDrawdownFigure;
  state_income_tax: USDrawdownFigure;
  other_taxes: USDrawdownFigure;
  benefits: USDrawdownFigure;
  coverage_at_chosen_draw: Record<USCoverage, boolean>;
  coverage_with_no_draw: Record<USCoverage, boolean>;
  money_to_spend: number;
  at_chosen_draw: USDrawdownOutcome;
  with_no_draw: USDrawdownOutcome;
  next_1000: USDrawdownSlice | null;
  medicare_surcharge: USMedicareSurcharge;
  required_minimums: USRequiredMinimum[];
  sweep: USDrawdownOutcome[];
  bands: USDrawdownSlice[];
  markers: USDrawdownMarker[];
  assumptions: {
    taxable_gain_share_applied: number | null;
    savings_tested_on: string;
    retirement_accounts_count_for_ssi_tests: boolean;
    dividends_qualified: boolean;
    money_spent_evenly_through_year: boolean;
  };
}

export interface USDrawdownSource {
  name: string;
  url: string | null;
  version: string | null;
  notes: string | null;
}

interface USDrawdownEnvelope {
  outputs: { us_drawdown_year_result: USDrawdownYearResult };
  caveats: string[];
  citations: USCitation[];
  sources: USDrawdownSource[];
}

export interface USDrawdownRun {
  result: USDrawdownYearResult;
  caveats: string[];
  citations: USCitation[];
  sources: USDrawdownSource[];
}

export function buildUSDrawdownScenario(inputs: USDrawdownYearInput) {
  return {
    schema_version: "eggnest.scenario.v1",
    engine: "us_drawdown_year",
    country: "USA",
    inputs,
    tags: {},
  };
}

export async function runUSDrawdownYear(
  inputs: USDrawdownYearInput,
  signal?: AbortSignal,
): Promise<USDrawdownRun> {
  const envelope = await apiFetch<USDrawdownEnvelope>("/core/simulate", {
    method: "POST",
    body: buildUSDrawdownScenario(inputs),
    signal,
    timeoutMs: LONG_TIMEOUT_MS,
  });
  return {
    result: envelope.outputs.us_drawdown_year_result,
    caveats: envelope.caveats,
    citations: envelope.citations,
    sources: envelope.sources,
  };
}
