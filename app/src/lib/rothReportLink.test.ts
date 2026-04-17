import { describe, expect, it } from "vitest";
import type { RothOptimizationResult, SimulationInput } from "./api";
import {
  buildRothReportHref,
  buildRothReportRequestPayload,
  decodeRothReportRequestPayload,
} from "./rothReportLink";

const baseInput: SimulationInput = {
  annual_spending: 90000,
  home_value: 0,
  current_age: 60,
  max_age: 95,
  gender: "female",
  social_security_monthly: 2400,
  social_security_start_age: 67,
  pension_annual: 0,
  employment_income: 0,
  employment_growth_rate: 0.03,
  retirement_age: 60,
  spending_mode: "real",
  inflation_model: "historical",
  inflation_rate: 0.025,
  social_security_inflation_adjusted: true,
  pension_cola_rate: 0,
  annuity_cola_rate: 0,
  state: "CA",
  filing_status: "single",
  has_spouse: false,
  has_annuity: false,
  n_simulations: 500,
  include_mortality: true,
  expected_return: 0.07,
  return_volatility: 0.16,
  dividend_yield: 0.02,
  stock_allocation: 0.8,
  stock_index: "sp500",
  bond_index: "treasury",
  holdings: [
    { account_type: "taxable", fund: "sp500", balance: 350000, cost_basis: 260000 },
    { account_type: "traditional_401k", fund: "treasury", balance: 850000 },
    { account_type: "roth_ira", fund: "sp500", balance: 100000 },
  ],
  withdrawal_strategy: "taxable_first",
};

const rothOptimizationResult: RothOptimizationResult = {
  results: [
    {
      conversion_policy: "fixed_amount",
      scenario_label: "No annual conversion",
      annual_conversion_amount: 0,
      conversion_start_age: 60,
      conversion_end_age: 64,
      monte_carlo: {
        success_rate: 0.9,
        median_final_value: 900000,
        median_final_value_real: 420000,
        total_taxes_median: 180000,
        total_withdrawn_median: 1400000,
        total_medicare_premiums_median: 14000,
        total_roth_conversions_median: 0,
        year_breakdown: [],
      },
      historical: {
        success_rate: 0.78,
        median_final_value: 680000,
        median_final_value_real: 270000,
        total_taxes_median: 176000,
        total_withdrawn_median: 1390000,
        total_medicare_premiums_median: 13400,
        total_roth_conversions_median: 0,
        cohort_count: 42,
        strongest_start_year: 1982,
        weakest_start_year: 1966,
        worst_final_value_real: 90000,
      },
      blended_score: 80.2,
      delta_vs_baseline: {
        blended_score_delta: 0,
        monte_carlo_success_rate_delta: 0,
        historical_success_rate_delta: 0,
        monte_carlo_median_final_value_real_delta: 0,
        historical_median_final_value_real_delta: 0,
        monte_carlo_total_taxes_median_delta: 0,
        monte_carlo_total_medicare_premiums_median_delta: 0,
        monte_carlo_total_roth_conversions_median_delta: 0,
        historical_total_medicare_premiums_median_delta: 0,
        historical_worst_final_value_real_delta: 0,
      },
    },
    {
      conversion_policy: "fixed_amount",
      scenario_label: "$25,000 per year (ages 60-64)",
      annual_conversion_amount: 25000,
      conversion_start_age: 60,
      conversion_end_age: 64,
      monte_carlo: {
        success_rate: 0.93,
        median_final_value: 980000,
        median_final_value_real: 470000,
        total_taxes_median: 205000,
        total_withdrawn_median: 1410000,
        total_medicare_premiums_median: 15500,
        total_roth_conversions_median: 125000,
        year_breakdown: [],
      },
      historical: {
        success_rate: 0.8,
        median_final_value: 700000,
        median_final_value_real: 280000,
        total_taxes_median: 200000,
        total_withdrawn_median: 1400000,
        total_medicare_premiums_median: 14800,
        total_roth_conversions_median: 125000,
        cohort_count: 42,
        strongest_start_year: 1982,
        weakest_start_year: 1966,
        worst_final_value_real: 95000,
      },
      blended_score: 84.6,
      delta_vs_baseline: {
        blended_score_delta: 4.4,
        monte_carlo_success_rate_delta: 0.03,
        historical_success_rate_delta: 0.02,
        monte_carlo_median_final_value_real_delta: 50000,
        historical_median_final_value_real_delta: 10000,
        monte_carlo_total_taxes_median_delta: 25000,
        monte_carlo_total_medicare_premiums_median_delta: 1500,
        monte_carlo_total_roth_conversions_median_delta: 125000,
        historical_total_medicare_premiums_median_delta: 1400,
        historical_worst_final_value_real_delta: 5000,
      },
    },
    {
      conversion_policy: "fill_12_percent_bracket",
      scenario_label: "Fill 12% bracket (ages 60-64)",
      annual_conversion_amount: null,
      conversion_start_age: 60,
      conversion_end_age: 64,
      monte_carlo: {
        success_rate: 0.94,
        median_final_value: 1000000,
        median_final_value_real: 480000,
        total_taxes_median: 208000,
        total_withdrawn_median: 1415000,
        total_medicare_premiums_median: 16000,
        total_roth_conversions_median: 210000,
        year_breakdown: [],
      },
      historical: {
        success_rate: 0.82,
        median_final_value: 720000,
        median_final_value_real: 290000,
        total_taxes_median: 202000,
        total_withdrawn_median: 1405000,
        total_medicare_premiums_median: 15000,
        total_roth_conversions_median: 210000,
        cohort_count: 42,
        strongest_start_year: 1982,
        weakest_start_year: 1966,
        worst_final_value_real: 98000,
      },
      blended_score: 85.1,
      delta_vs_baseline: {
        blended_score_delta: 4.9,
        monte_carlo_success_rate_delta: 0.04,
        historical_success_rate_delta: 0.04,
        monte_carlo_median_final_value_real_delta: 60000,
        historical_median_final_value_real_delta: 20000,
        monte_carlo_total_taxes_median_delta: 28000,
        monte_carlo_total_medicare_premiums_median_delta: 2000,
        monte_carlo_total_roth_conversions_median_delta: 210000,
        historical_total_medicare_premiums_median_delta: 1600,
        historical_worst_final_value_real_delta: 8000,
      },
    },
  ],
  baseline_scenario_label: "No annual conversion",
  baseline_conversion_amount: 0,
  top_scoring_scenario_label: "Fill 12% bracket (ages 60-64)",
  top_scoring_conversion_amount: null,
  lowest_modeled_tax_scenario_label: "No annual conversion",
  lowest_modeled_tax_amount: 0,
  strongest_historical_scenario_label: "Fill 12% bracket (ages 60-64)",
  strongest_historical_conversion_amount: null,
  candidate_count: 12,
  candidate_start_ages: [60, 62],
  window_lengths: [5, 10],
  lowest_medicare_premium_scenario_label: "No annual conversion",
  lowest_medicare_premium_conversion_amount: 0,
  highest_real_ending_wealth_scenario_label: "Fill 12% bracket (ages 60-64)",
  highest_real_ending_wealth_conversion_amount: null,
  metadata: {
    engine_version: "0.1.0",
    method_version: "2026-04-09",
    random_seed: 20260409,
    assumptions_summary: "bootstrap returns, historical inflation, real spending, CA / single",
  },
  summary:
    "Fill 12% bracket (ages 60-64) is the current score leader.",
};

describe("rothReportLink", () => {
  it("builds a deterministic request payload from a Roth optimization result", () => {
    const payload = buildRothReportRequestPayload(baseInput, rothOptimizationResult);

    expect(payload.baseInput.random_seed).toBe(20260409);
    expect(payload.options.annualConversionAmounts).toEqual([0, 25000]);
    expect(payload.options.conversionPolicies).toEqual(["fill_12_percent_bracket"]);
    expect(payload.options.candidateStartAges).toEqual([60, 62]);
    expect(payload.options.windowLengths).toEqual([5, 10]);
  });

  it("round-trips through a permalink-safe encoding", () => {
    const payload = buildRothReportRequestPayload(baseInput, rothOptimizationResult);
    const href = buildRothReportHref(payload, "https://eggnest.co");
    const encoded = new URL(href).searchParams.get("report");

    expect(encoded).toBeTruthy();
    expect(decodeRothReportRequestPayload(encoded!)).toEqual(payload);
  });

  it("preserves an empty policy list when the search only used fixed amounts", () => {
    const fixedOnlyResult: RothOptimizationResult = {
      ...rothOptimizationResult,
      results: rothOptimizationResult.results.filter((item) => item.conversion_policy === "fixed_amount"),
    };

    const payload = buildRothReportRequestPayload(baseInput, fixedOnlyResult);

    expect(payload.options.annualConversionAmounts).toEqual([0, 25000]);
    expect(payload.options.conversionPolicies).toEqual([]);
  });

  it("infers fixed-amount scenarios from annual conversion amounts even if the policy marker is missing", () => {
    const fixtureLikeResult = {
      ...rothOptimizationResult,
      results: rothOptimizationResult.results.map((item, index) =>
        index < 2 ? { ...item, conversion_policy: null } : item,
      ),
    } as unknown as RothOptimizationResult;

    const payload = buildRothReportRequestPayload(baseInput, fixtureLikeResult);

    expect(payload.options.annualConversionAmounts).toEqual([0, 25000]);
    expect(payload.options.conversionPolicies).toEqual(["fill_12_percent_bracket"]);
  });

  it("round-trips through the browser-safe base64url path when Buffer is unavailable", () => {
    const originalBuffer = globalThis.Buffer;
    const payload = {
      ...buildRothReportRequestPayload(baseInput, rothOptimizationResult),
      baseInput: {
        ...baseInput,
        state: "Québec",
      },
      options: {
        annualConversionAmounts: [0, 25000],
        conversionPolicies: [],
        candidateStartAges: [60],
        windowLengths: [5],
      },
    };

    Object.defineProperty(globalThis, "Buffer", {
      value: undefined,
      configurable: true,
    });

    try {
      const href = buildRothReportHref(payload, "https://eggnest.co");
      const encoded = new URL(href).searchParams.get("report");

      expect(encoded).toBeTruthy();
      expect(decodeRothReportRequestPayload(encoded!)).toEqual(payload);
    } finally {
      Object.defineProperty(globalThis, "Buffer", {
        value: originalBuffer,
        configurable: true,
      });
    }
  });
});
