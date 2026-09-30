import { describe, it, expect } from "vitest";
import type { HouseholdResult } from "./api";
import { benefitLabel, stateAndLocalTax } from "./household";

function result(overrides: Partial<HouseholdResult> = {}): HouseholdResult {
  return {
    federal_income_tax: 0,
    state_income_tax: 0,
    payroll_tax: 2142,
    total_taxes: 2142,
    benefits: {},
    total_benefits: 0,
    total_income: 28000,
    net_income: 25858,
    tax_breakdown: {},
    marginal_tax_rate: 0,
    effective_tax_rate: 0,
    citations: [],
    output_citations: {},
    ...overrides,
  };
}

describe("benefitLabel", () => {
  it("names refundable credits and programs in sentence case", () => {
    expect(benefitLabel("eitc")).toBe("Earned income tax credit");
    expect(benefitLabel("refundable_ctc")).toBe(
      "Child tax credit (refundable part)"
    );
    expect(benefitLabel("snap")).toBe("SNAP");
    expect(benefitLabel("household_refundable_state_tax_credits")).toBe(
      "State refundable tax credits"
    );
  });

  it("falls back to the key with spaces and a leading capital", () => {
    expect(benefitLabel("ca_care")).toBe("Ca care");
  });
});

describe("stateAndLocalTax", () => {
  it("adds other taxes to state income tax", () => {
    expect(stateAndLocalTax(result({ state_income_tax: 2775, other_taxes: 7 }))).toBe(
      2782
    );
  });

  it("treats a missing other_taxes field as zero", () => {
    expect(stateAndLocalTax(result({ state_income_tax: 2775 }))).toBe(2775);
  });

  it("makes the tax rows sum to total taxes", () => {
    const r = result({
      federal_income_tax: 7949,
      state_income_tax: 2775,
      other_taxes: 7,
      payroll_tax: 6712,
      total_taxes: 17443,
    });
    expect(r.federal_income_tax + stateAndLocalTax(r) + r.payroll_tax).toBe(
      r.total_taxes
    );
  });
});
