/**
 * Shared constants used across the EggNest app.
 */
import type { SimulationInput, SpouseInput, AnnuityInput } from "./api";

export const US_STATES = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
] as const;

export type USState = (typeof US_STATES)[number];

// No-income-tax states for quick comparison
export const NO_TAX_STATES = ["FL", "TX", "NV", "WA", "WY", "SD", "AK", "TN", "NH"];

// Age constraints
export const MIN_AGE = 18;
export const MAX_AGE = 100;

// Social security claiming age range
export const SS_MIN_CLAIMING_AGE = 62;
export const SS_MAX_CLAIMING_AGE = 70;

// Allocation constraints
export const MIN_ALLOCATION = 0;
export const MAX_ALLOCATION = 100;

export const DEFAULT_PARAMS: SimulationInput = {
  initial_capital: 500000,
  annual_spending: 60000,
  home_value: 0,
  current_age: 65,
  max_age: 95,
  gender: "male",
  social_security_monthly: 2000,
  social_security_start_age: 67,
  pension_annual: 0,
  employment_income: 0,
  employment_growth_rate: 0.03,
  retirement_age: 65,
  state: "CA",
  filing_status: "single",
  has_spouse: false,
  has_annuity: false,
  n_simulations: 10000,
  include_mortality: true,
  expected_return: 0.07,
  return_volatility: 0.16,
  dividend_yield: 0.02,
  stock_allocation: 0.8,
};

export const DEFAULT_SPOUSE: SpouseInput = {
  age: 63,
  gender: "female",
  social_security_monthly: 1500,
  social_security_start_age: 67,
  pension_annual: 0,
  employment_income: 0,
  employment_growth_rate: 0.03,
  retirement_age: 65,
};

export const DEFAULT_ANNUITY: AnnuityInput = {
  monthly_payment: 3000,
  annuity_type: "life_with_guarantee",
  guarantee_years: 15,
};

export const SCENARIOS_STORAGE_KEY = "eggnest_scenarios";

// URL parameter mapping (short names for readability)
export const URL_PARAM_MAP = {
  cap: "initial_capital",
  spend: "annual_spending",
  home: "home_value",
  age: "current_age",
  max: "max_age",
  gen: "gender",
  state: "state",
  status: "filing_status",
  ss: "social_security_monthly",
  ssAge: "social_security_start_age",
  pension: "pension_annual",
  emp: "employment_income",
  ret: "retirement_age",
  stocks: "stock_allocation",
  spouse: "has_spouse",
  // Spouse params
  spAge: "spouse_age",
  spGen: "spouse_gender",
  spSS: "spouse_ss_monthly",
  spSSAge: "spouse_ss_start_age",
  spPension: "spouse_pension",
  spRet: "spouse_retirement_age",
} as const;
