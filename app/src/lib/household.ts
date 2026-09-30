import type { HouseholdResult } from "./api";

/**
 * Display names for the benefit keys returned by /calculate-household.
 * Keys are PolicyEngine-US variable names; refundable tax credits are
 * included because the API counts them once, as benefits.
 */
const BENEFIT_LABELS: Record<string, string> = {
  // Refundable tax credits
  eitc: "Earned income tax credit",
  refundable_ctc: "Child tax credit (refundable part)",
  refundable_american_opportunity_credit:
    "American opportunity credit (refundable part)",
  recovery_rebate_credit: "Recovery rebate credit",
  refundable_payroll_tax_credit: "Refundable payroll tax credit",
  cdcc: "Child and dependent care credit",
  household_refundable_state_tax_credits: "State refundable tax credits",
  other_federal_refundable_credits: "Other federal refundable credits",
  // Benefit programs
  snap: "SNAP",
  ssi: "Supplemental Security Income",
  tanf: "TANF",
  wic: "WIC",
  free_school_meals: "Free school meals",
  reduced_price_school_meals: "Reduced-price school meals",
  household_state_benefits: "State benefits",
  housing_assistance: "Housing assistance",
  commodity_supplemental_food_program: "Commodity Supplemental Food Program",
  household_head_start_benefits: "Head Start",
  unemployment_compensation: "Unemployment compensation",
  acp: "Affordable Connectivity Program",
  ebb: "Emergency Broadband Benefit",
  other_benefits: "Other benefits",
  // Income PolicyEngine computes that the user did not enter
  ak_permanent_fund_dividend: "Alaska Permanent Fund Dividend",
  other_computed_income: "Other income",
};

/** Human-readable, sentence-case label for a benefit key. */
export function benefitLabel(key: string): string {
  const label = BENEFIT_LABELS[key];
  if (label) return label;
  const words = key.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * State income tax plus other_taxes (state use tax, local income and
 * occupational taxes, and any reform flat tax), so that federal + state and
 * local + payroll equals total_taxes.
 */
export function stateAndLocalTax(result: HouseholdResult): number {
  return result.state_income_tax + (result.other_taxes ?? 0);
}
