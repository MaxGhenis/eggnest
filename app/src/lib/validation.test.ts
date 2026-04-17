import { describe, it, expect } from "vitest";
import {
  validateSimulationInput,
  validateHolding,
  validateHoldings,
  validateLifeEventInput,
} from "./validation";
import type { SimulationInput, Holding, HouseholdInput } from "./api";

// Helper to create a valid base simulation input
function makeValidInput(overrides: Partial<SimulationInput> = {}): SimulationInput {
  return {
    current_age: 35,
    max_age: 90,
    annual_spending: 50000,
    home_value: 0,
    gender: "male",
    social_security_monthly: 2000,
    social_security_start_age: 67,
    pension_annual: 0,
    employment_income: 100000,
    employment_growth_rate: 0.02,
    retirement_age: 65,
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
    n_simulations: 1000,
    include_mortality: true,
    expected_return: 0.07,
    return_volatility: 0.15,
    dividend_yield: 0.02,
    stock_allocation: 0.7,
    ...overrides,
  };
}

describe("validateSimulationInput", () => {
  // Age validation
  describe("current_age", () => {
    it("returns no errors for valid age", () => {
      const errors = validateSimulationInput(makeValidInput({ current_age: 35 }));
      expect(errors.filter((e) => e.field === "current_age")).toHaveLength(0);
    });

    it("returns error for age below 18", () => {
      const errors = validateSimulationInput(makeValidInput({ current_age: 17 }));
      const ageErrors = errors.filter((e) => e.field === "current_age");
      expect(ageErrors).toHaveLength(1);
      expect(ageErrors[0].message).toMatch(/18.*100/);
    });

    it("returns error for age above 100", () => {
      const errors = validateSimulationInput(makeValidInput({ current_age: 101 }));
      const ageErrors = errors.filter((e) => e.field === "current_age");
      expect(ageErrors).toHaveLength(1);
    });

    it("returns error for non-integer age", () => {
      const errors = validateSimulationInput(makeValidInput({ current_age: 35.5 }));
      const ageErrors = errors.filter((e) => e.field === "current_age");
      expect(ageErrors).toHaveLength(1);
      expect(ageErrors[0].message).toMatch(/integer/i);
    });

    it("accepts edge case ages 18 and 100", () => {
      const errors18 = validateSimulationInput(makeValidInput({ current_age: 18 }));
      expect(errors18.filter((e) => e.field === "current_age")).toHaveLength(0);

      const errors100 = validateSimulationInput(makeValidInput({ current_age: 100, retirement_age: 100, max_age: 100 }));
      expect(errors100.filter((e) => e.field === "current_age")).toHaveLength(0);
    });
  });

  // Retirement age validation
  describe("retirement_age", () => {
    it("returns no errors when retirement age > current age", () => {
      const errors = validateSimulationInput(
        makeValidInput({ current_age: 35, retirement_age: 65 })
      );
      expect(errors.filter((e) => e.field === "retirement_age")).toHaveLength(0);
    });

    it("returns error when retirement age <= current age", () => {
      const errors = validateSimulationInput(
        makeValidInput({ current_age: 65, retirement_age: 65 })
      );
      const retErrors = errors.filter((e) => e.field === "retirement_age");
      expect(retErrors).toHaveLength(1);
      expect(retErrors[0].message).toMatch(/greater than.*current age/i);
    });

    it("returns error when retirement age > 100", () => {
      const errors = validateSimulationInput(
        makeValidInput({ current_age: 35, retirement_age: 101 })
      );
      const retErrors = errors.filter((e) => e.field === "retirement_age");
      expect(retErrors).toHaveLength(1);
    });
  });

  // Max age (spending horizon)
  describe("max_age", () => {
    it("returns error when max_age <= current_age", () => {
      const errors = validateSimulationInput(
        makeValidInput({ current_age: 80, max_age: 75 })
      );
      const maxAgeErrors = errors.filter((e) => e.field === "max_age");
      expect(maxAgeErrors).toHaveLength(1);
    });

    it("returns error when max_age > 120", () => {
      const errors = validateSimulationInput(
        makeValidInput({ max_age: 121 })
      );
      const maxAgeErrors = errors.filter((e) => e.field === "max_age");
      expect(maxAgeErrors).toHaveLength(1);
    });
  });

  // Spending validation
  describe("annual_spending", () => {
    it("returns no errors for positive spending", () => {
      const errors = validateSimulationInput(makeValidInput({ annual_spending: 50000 }));
      expect(errors.filter((e) => e.field === "annual_spending")).toHaveLength(0);
    });

    it("returns error for zero spending", () => {
      const errors = validateSimulationInput(makeValidInput({ annual_spending: 0 }));
      const spendingErrors = errors.filter((e) => e.field === "annual_spending");
      expect(spendingErrors).toHaveLength(1);
      expect(spendingErrors[0].message).toMatch(/greater than.*0/i);
    });

    it("returns error for negative spending", () => {
      const errors = validateSimulationInput(makeValidInput({ annual_spending: -1000 }));
      const spendingErrors = errors.filter((e) => e.field === "annual_spending");
      expect(spendingErrors).toHaveLength(1);
    });
  });

  // Income validation
  describe("employment_income", () => {
    it("returns no errors for zero income", () => {
      const errors = validateSimulationInput(makeValidInput({ employment_income: 0 }));
      expect(errors.filter((e) => e.field === "employment_income")).toHaveLength(0);
    });

    it("returns no errors for positive income", () => {
      const errors = validateSimulationInput(makeValidInput({ employment_income: 100000 }));
      expect(errors.filter((e) => e.field === "employment_income")).toHaveLength(0);
    });

    it("returns error for negative income", () => {
      const errors = validateSimulationInput(makeValidInput({ employment_income: -5000 }));
      const incomeErrors = errors.filter((e) => e.field === "employment_income");
      expect(incomeErrors).toHaveLength(1);
    });
  });

  describe("social_security_monthly", () => {
    it("returns no errors for zero benefit", () => {
      const errors = validateSimulationInput(makeValidInput({ social_security_monthly: 0 }));
      expect(errors.filter((e) => e.field === "social_security_monthly")).toHaveLength(0);
    });

    it("returns error for negative benefit", () => {
      const errors = validateSimulationInput(makeValidInput({ social_security_monthly: -1 }));
      const ssErrors = errors.filter((e) => e.field === "social_security_monthly");
      expect(ssErrors).toHaveLength(1);
      expect(ssErrors[0].message).toMatch(/0 or greater/i);
    });
  });

  describe("pension_annual", () => {
    it("returns no errors for zero pension", () => {
      const errors = validateSimulationInput(makeValidInput({ pension_annual: 0 }));
      expect(errors.filter((e) => e.field === "pension_annual")).toHaveLength(0);
    });

    it("returns error for negative pension", () => {
      const errors = validateSimulationInput(makeValidInput({ pension_annual: -1000 }));
      const pensionErrors = errors.filter((e) => e.field === "pension_annual");
      expect(pensionErrors).toHaveLength(1);
      expect(pensionErrors[0].message).toMatch(/0 or greater/i);
    });
  });

  describe("inflation assumptions", () => {
    it("returns no errors for a valid fixed inflation rate", () => {
      const errors = validateSimulationInput(
        makeValidInput({ inflation_model: "constant", inflation_rate: 0.03 })
      );
      expect(errors.filter((e) => e.field === "inflation_rate")).toHaveLength(0);
    });

    it("returns error for inflation rate above 10%", () => {
      const errors = validateSimulationInput(
        makeValidInput({ inflation_model: "constant", inflation_rate: 0.12 })
      );
      expect(errors.filter((e) => e.field === "inflation_rate")).toHaveLength(1);
    });

    it("returns error for pension COLA above 10%", () => {
      const errors = validateSimulationInput(
        makeValidInput({ pension_annual: 10000, pension_cola_rate: 0.12 })
      );
      expect(errors.filter((e) => e.field === "pension_cola_rate")).toHaveLength(1);
    });

    it("returns error for annuity COLA above 10%", () => {
      const errors = validateSimulationInput(
        makeValidInput({ has_annuity: true, annuity_cola_rate: 0.12 })
      );
      expect(errors.filter((e) => e.field === "annuity_cola_rate")).toHaveLength(1);
    });
  });

  // Initial capital / savings validation
  describe("initial_capital", () => {
    it("returns no errors for zero initial capital", () => {
      const errors = validateSimulationInput(makeValidInput({ initial_capital: 0 }));
      expect(errors.filter((e) => e.field === "initial_capital")).toHaveLength(0);
    });

    it("returns error for negative initial capital", () => {
      const errors = validateSimulationInput(makeValidInput({ initial_capital: -10000 }));
      const capitalErrors = errors.filter((e) => e.field === "initial_capital");
      expect(capitalErrors).toHaveLength(1);
    });
  });

  // Stock allocation
  describe("stock_allocation", () => {
    it("returns no errors for valid allocation (0-1)", () => {
      const errors = validateSimulationInput(makeValidInput({ stock_allocation: 0.7 }));
      expect(errors.filter((e) => e.field === "stock_allocation")).toHaveLength(0);
    });

    it("returns no errors for 0% allocation", () => {
      const errors = validateSimulationInput(makeValidInput({ stock_allocation: 0 }));
      expect(errors.filter((e) => e.field === "stock_allocation")).toHaveLength(0);
    });

    it("returns no errors for 100% allocation", () => {
      const errors = validateSimulationInput(makeValidInput({ stock_allocation: 1.0 }));
      expect(errors.filter((e) => e.field === "stock_allocation")).toHaveLength(0);
    });

    it("returns error for allocation > 1", () => {
      const errors = validateSimulationInput(makeValidInput({ stock_allocation: 1.1 }));
      const allocErrors = errors.filter((e) => e.field === "stock_allocation");
      expect(allocErrors).toHaveLength(1);
    });

    it("returns error for negative allocation", () => {
      const errors = validateSimulationInput(makeValidInput({ stock_allocation: -0.1 }));
      const allocErrors = errors.filter((e) => e.field === "stock_allocation");
      expect(allocErrors).toHaveLength(1);
    });
  });

  // Social security claiming age
  describe("social_security_start_age", () => {
    it("returns no errors for valid claiming age", () => {
      const errors = validateSimulationInput(makeValidInput({ social_security_start_age: 67 }));
      expect(errors.filter((e) => e.field === "social_security_start_age")).toHaveLength(0);
    });

    it("returns error for claiming age below 62", () => {
      const errors = validateSimulationInput(makeValidInput({ social_security_start_age: 61 }));
      const ssErrors = errors.filter((e) => e.field === "social_security_start_age");
      expect(ssErrors).toHaveLength(1);
      expect(ssErrors[0].message).toMatch(/62.*70/);
    });

    it("returns error for claiming age above 70", () => {
      const errors = validateSimulationInput(makeValidInput({ social_security_start_age: 71 }));
      const ssErrors = errors.filter((e) => e.field === "social_security_start_age");
      expect(ssErrors).toHaveLength(1);
    });
  });

  // State validation
  describe("state", () => {
    it("returns no errors for valid state", () => {
      const errors = validateSimulationInput(makeValidInput({ state: "CA" }));
      expect(errors.filter((e) => e.field === "state")).toHaveLength(0);
    });

    it("returns error for invalid state", () => {
      const errors = validateSimulationInput(makeValidInput({ state: "XX" }));
      const stateErrors = errors.filter((e) => e.field === "state");
      expect(stateErrors).toHaveLength(1);
      expect(stateErrors[0].message).toMatch(/valid.*state/i);
    });
  });

  // Spouse validation
  describe("spouse", () => {
    it("returns no errors when no spouse enabled", () => {
      const errors = validateSimulationInput(makeValidInput({ has_spouse: false }));
      expect(errors.filter((e) => e.field.startsWith("spouse"))).toHaveLength(0);
    });

    it("returns error for spouse age out of range", () => {
      const errors = validateSimulationInput(
        makeValidInput({
          has_spouse: true,
          spouse: {
            age: 15,
            gender: "female",
            social_security_monthly: 1500,
            social_security_start_age: 67,
            pension_annual: 0,
            employment_income: 0,
            employment_growth_rate: 0,
            retirement_age: 65,
          },
        })
      );
      const spouseErrors = errors.filter((e) => e.field === "spouse.age");
      expect(spouseErrors).toHaveLength(1);
      expect(spouseErrors[0].message).toMatch(/18.*100/);
    });

    it("returns error for spouse SS claiming age out of range", () => {
      const errors = validateSimulationInput(
        makeValidInput({
          has_spouse: true,
          spouse: {
            age: 60,
            gender: "female",
            social_security_monthly: 1500,
            social_security_start_age: 55,
            pension_annual: 0,
            employment_income: 0,
            employment_growth_rate: 0,
            retirement_age: 65,
          },
        })
      );
      const ssErrors = errors.filter((e) => e.field === "spouse.social_security_start_age");
      expect(ssErrors).toHaveLength(1);
    });

    it("returns error for spouse retirement age before spouse age", () => {
      const errors = validateSimulationInput(
        makeValidInput({
          has_spouse: true,
          spouse: {
            age: 62,
            gender: "female",
            social_security_monthly: 1500,
            social_security_start_age: 67,
            pension_annual: 0,
            employment_income: 40000,
            employment_growth_rate: 0,
            retirement_age: 60,
          },
        })
      );
      const retirementErrors = errors.filter((e) => e.field === "spouse.retirement_age");
      expect(retirementErrors).toHaveLength(1);
      expect(retirementErrors[0].message).toMatch(/greater than spouse age/i);
    });

    it("returns error for negative spouse employment income", () => {
      const errors = validateSimulationInput(
        makeValidInput({
          has_spouse: true,
          spouse: {
            age: 60,
            gender: "female",
            social_security_monthly: 1500,
            social_security_start_age: 67,
            pension_annual: 0,
            employment_income: -1,
            employment_growth_rate: 0,
            retirement_age: 65,
          },
        })
      );
      const incomeErrors = errors.filter((e) => e.field === "spouse.employment_income");
      expect(incomeErrors).toHaveLength(1);
      expect(incomeErrors[0].message).toMatch(/0 or greater/i);
    });
  });

  describe("annuity", () => {
    it("returns error for zero annuity payment when comparison is enabled", () => {
      const errors = validateSimulationInput(
        makeValidInput({
          has_annuity: true,
          annuity: {
            monthly_payment: 0,
            annuity_type: "life_with_guarantee",
            guarantee_years: 15,
          },
        })
      );
      const paymentErrors = errors.filter((e) => e.field === "annuity.monthly_payment");
      expect(paymentErrors).toHaveLength(1);
      expect(paymentErrors[0].message).toMatch(/greater than 0/i);
    });

    it("returns error for invalid guarantee period", () => {
      const errors = validateSimulationInput(
        makeValidInput({
          has_annuity: true,
          annuity: {
            monthly_payment: 1500,
            annuity_type: "fixed_period",
            guarantee_years: 31,
          },
        })
      );
      const guaranteeErrors = errors.filter((e) => e.field === "annuity.guarantee_years");
      expect(guaranteeErrors).toHaveLength(1);
      expect(guaranteeErrors[0].message).toMatch(/1 and 30/i);
    });

    it("returns no errors for valid annuity comparison", () => {
      const errors = validateSimulationInput(
        makeValidInput({
          has_annuity: true,
          annuity: {
            monthly_payment: 1500,
            annuity_type: "life_only",
            guarantee_years: 15,
          },
        })
      );
      expect(errors.filter((e) => e.field.startsWith("annuity."))).toHaveLength(0);
    });
  });

  // Full valid input should have zero errors
  describe("full valid input", () => {
    it("returns empty array for completely valid input", () => {
      const errors = validateSimulationInput(makeValidInput());
      expect(errors).toHaveLength(0);
    });
  });
});

describe("validateHolding", () => {
  it("returns no errors for valid holding", () => {
    const holding: Holding = { account_type: "traditional_401k", fund: "vt", balance: 100000 };
    const errors = validateHolding(holding, 0);
    expect(errors).toHaveLength(0);
  });

  it("returns error for negative balance", () => {
    const holding: Holding = { account_type: "traditional_401k", fund: "vt", balance: -1000 };
    const errors = validateHolding(holding, 0);
    expect(errors).toHaveLength(1);
    expect(errors[0].field).toBe("holdings[0].balance");
    expect(errors[0].message).toMatch(/0/);
  });

  it("returns no errors for zero balance", () => {
    const holding: Holding = { account_type: "traditional_401k", fund: "vt", balance: 0 };
    const errors = validateHolding(holding, 0);
    expect(errors).toHaveLength(0);
  });

  it("returns no errors for valid taxable cost basis", () => {
    const holding: Holding = {
      account_type: "taxable",
      fund: "vt",
      balance: 100000,
      cost_basis: 80000,
    };
    const errors = validateHolding(holding, 0);
    expect(errors).toHaveLength(0);
  });

  it("returns error when taxable cost basis exceeds balance", () => {
    const holding: Holding = {
      account_type: "taxable",
      fund: "vt",
      balance: 100000,
      cost_basis: 120000,
    };
    const errors = validateHolding(holding, 0);
    expect(errors).toHaveLength(1);
    expect(errors[0].field).toBe("holdings[0].cost_basis");
  });

  it("returns error when cost basis is set on non-taxable holding", () => {
    const holding: Holding = {
      account_type: "roth_ira",
      fund: "vt",
      balance: 100000,
      cost_basis: 50000,
    };
    const errors = validateHolding(holding, 0);
    expect(errors).toHaveLength(1);
    expect(errors[0].field).toBe("holdings[0].cost_basis");
  });
});

describe("validateHoldings", () => {
  it("returns no errors for valid holdings array", () => {
    const holdings: Holding[] = [
      { account_type: "traditional_401k", fund: "vt", balance: 100000 },
      { account_type: "roth_ira", fund: "sp500", balance: 50000 },
    ];
    const errors = validateHoldings(holdings);
    expect(errors).toHaveLength(0);
  });

  it("returns errors for holdings with negative balances", () => {
    const holdings: Holding[] = [
      { account_type: "traditional_401k", fund: "vt", balance: -1000 },
      { account_type: "roth_ira", fund: "sp500", balance: 50000 },
    ];
    const errors = validateHoldings(holdings);
    expect(errors).toHaveLength(1);
    expect(errors[0].field).toBe("holdings[0].balance");
  });

  it("returns no errors for empty holdings array", () => {
    const errors = validateHoldings([]);
    expect(errors).toHaveLength(0);
  });
});

describe("validateLifeEventInput", () => {
  function makeValidHousehold(overrides: Partial<HouseholdInput> = {}): HouseholdInput {
    return {
      state: "CA",
      year: 2025,
      filing_status: "single",
      people: [
        { age: 35, employment_income: 75000, is_tax_unit_head: true },
      ],
      ...overrides,
    };
  }

  it("returns no errors for valid household input", () => {
    const errors = validateLifeEventInput(makeValidHousehold());
    expect(errors).toHaveLength(0);
  });

  it("returns error for person age below 18 (for adults)", () => {
    const errors = validateLifeEventInput(
      makeValidHousehold({
        people: [{ age: 15, employment_income: 50000, is_tax_unit_head: true }],
      })
    );
    const ageErrors = errors.filter((e) => e.field === "people[0].age");
    expect(ageErrors).toHaveLength(1);
    expect(ageErrors[0].message).toMatch(/18.*100/);
  });

  it("allows age 0 for dependents", () => {
    const errors = validateLifeEventInput(
      makeValidHousehold({
        people: [
          { age: 35, employment_income: 75000, is_tax_unit_head: true },
          { age: 0, employment_income: 0, is_tax_unit_dependent: true },
        ],
      })
    );
    const ageErrors = errors.filter((e) => e.field === "people[1].age");
    expect(ageErrors).toHaveLength(0);
  });

  it("returns error for negative employment income", () => {
    const errors = validateLifeEventInput(
      makeValidHousehold({
        people: [{ age: 35, employment_income: -5000, is_tax_unit_head: true }],
      })
    );
    const incErrors = errors.filter((e) => e.field === "people[0].employment_income");
    expect(incErrors).toHaveLength(1);
  });

  it("returns error for invalid state", () => {
    const errors = validateLifeEventInput(makeValidHousehold({ state: "ZZ" }));
    const stateErrors = errors.filter((e) => e.field === "state");
    expect(stateErrors).toHaveLength(1);
  });
});
