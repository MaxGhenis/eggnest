import { describe, expect, it } from "vitest";
import type { UKSimulationInput, UKSimulationResult, UKYearBreakdown } from "./api-uk";
import { hasTenYearHorizon, summarizeUKOutcome } from "./uk-outcome";

const input: UKSimulationInput = {
  current_age: 65,
  max_age: 90,
  isa_balance: 100_000,
  sipp_balance: 200_000,
  gia_balance: 50_000,
  annual_spending: 30_000,
};

function row(age: number, totalTax: number): UKYearBreakdown {
  return {
    year_index: age - 65,
    age,
    portfolio_start: 350_000,
    portfolio_end: 340_000,
    spending_target: 30_000,
    total_income: 30_000,
    withdrawal: 30_000,
    total_tax: totalTax,
    inflation_rate: 0.025,
    portfolio_return: 0.04,
    effective_tax_rate: 0.06,
    state_pension: 0,
    employment_income: 0,
    sipp_withdrawal: 10_000,
    isa_withdrawal: 20_000,
    gia_withdrawal: 0,
  };
}

function resultWithYears(years: number, overrides: Partial<UKSimulationResult> = {}) {
  const path = Array.from({ length: years }, () => 350_000);
  const bands = { p5: path, p25: path, p50: path, p75: path, p95: path };
  const result: UKSimulationResult = {
    metadata: {},
    success_rate: 0.91,
    strict_horizon_success_rate: 0.88,
    median_final_value: 250_000,
    median_final_value_real: 190_000,
    percentiles: {},
    percentiles_real: {},
    percentile_paths: bands,
    tax_percentile_paths: bands,
    earnings_percentile_paths: bands,
    year_breakdown: Array.from({ length: years }, (_, i) => row(65 + i, 2_000)),
    initial_withdrawal_rate: 8.6,
    prob_10_year_failure: 0.043,
    ...overrides,
  };
  return result;
}

describe("summarizeUKOutcome", () => {
  it("describes success as spending met in every living year", () => {
    const summary = summarizeUKOutcome(input, resultWithYears(26));
    expect(summary.headline).toEqual({
      label: "Spending covered",
      value: "91%",
      detail: "of simulated paths meet your spending in every year you're alive, to age 90",
    });
    expect(summary.headline.detail).not.toMatch(/depletion|last/i);
  });

  it("drops the mortality clause when mortality is off", () => {
    const summary = summarizeUKOutcome(
      { ...input, include_mortality: false },
      resultWithYears(26),
    );
    expect(summary.headline.detail).toBe(
      "of simulated paths meet your spending in every year to age 90",
    );
  });

  it("labels the other rates with the same shortfall definition", () => {
    const [tenYear, strict, firstYear, tax] = summarizeUKOutcome(
      input,
      resultWithYears(26),
    ).metrics;
    expect(tenYear).toEqual({
      label: "Shortfall within 10 years",
      value: "4.3%",
      detail: "Chance spending first falls short",
    });
    expect(strict).toEqual({
      label: "Covered to age 90",
      value: "88%",
      detail: "Ignoring mortality",
    });
    expect(firstYear.value).toBe("8.6%");
    // 26 years x £2,000 of yearly median tax.
    expect(tax).toEqual({
      label: "Lifetime tax",
      value: "£52k",
      detail: "Sum of yearly medians · income tax & NI",
    });
  });

  it("hides the ten-year figure when the horizon is ten years or shorter", () => {
    for (const years of [1, 2, 10]) {
      const result = resultWithYears(years);
      expect(hasTenYearHorizon(result)).toBe(false);
      const [tenYear] = summarizeUKOutcome(input, result).metrics;
      expect(tenYear.value).toBe("—");
      expect(tenYear.detail).toBe("Needs a horizon over 10 years");
    }
    expect(hasTenYearHorizon(resultWithYears(11))).toBe(true);
  });

  it("notes SIPP-locked shortfalls only when there are some", () => {
    expect(summarizeUKOutcome(input, resultWithYears(26)).sippLockedNote).toBeNull();
    expect(
      summarizeUKOutcome(input, resultWithYears(26, { sipp_locked_shortfall_rate: 0 }))
        .sippLockedNote,
    ).toBeNull();
    expect(
      summarizeUKOutcome(input, resultWithYears(26, { sipp_locked_shortfall_rate: 0.12 }))
        .sippLockedNote,
    ).toBe(
      "12% of paths fall short before age 55 while money is still in the SIPP, which can't be drawn until then.",
    );
    // Small shares keep a decimal rather than rounding to 0%.
    expect(
      summarizeUKOutcome(input, resultWithYears(26, { sipp_locked_shortfall_rate: 0.004 }))
        .sippLockedNote,
    ).toMatch(/^0\.4% of paths/);
  });

  it("works against an API that predates the new fields", () => {
    const result = resultWithYears(26);
    delete (result as Partial<UKSimulationResult>).sipp_locked_shortfall_rate;
    const summary = summarizeUKOutcome(input, result);
    expect(summary.sippLockedNote).toBeNull();
    expect(summary.metrics).toHaveLength(4);
  });
});
