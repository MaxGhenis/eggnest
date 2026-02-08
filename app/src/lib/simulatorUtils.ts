/**
 * Shared utility functions for the simulator.
 */
import type { SimulationInput, SpouseInput, SimulationResult } from "./api";
import {
  NetworkError,
  TimeoutError,
  ValidationError,
  SimulationError,
  ApiError,
} from "./api";
import { URL_PARAM_MAP } from "./constants";

// ============================================
// Types
// ============================================

export interface SavedScenario {
  name: string;
  savedAt: string;
  inputs: Partial<SimulationInput>;
  spouse?: SpouseInput;
  annuity?: {
    monthly_payment: number;
    annuity_type: "life_with_guarantee" | "fixed_period" | "life_only";
    guarantee_years: number;
  };
  portfolioMode?: "simple" | "detailed";
  holdings?: Array<{
    account_type: string;
    fund: string;
    balance: number;
  }>;
  withdrawalStrategy?: "taxable_first" | "traditional_first" | "roth_first" | "pro_rata";
}

export interface AnnuityComparisonResult {
  simulation_result: SimulationResult;
  annuity_total_guaranteed: number;
  probability_simulation_beats_annuity: number;
  simulation_median_total_income: number;
  recommendation: string;
}

export interface Persona {
  id: string;
  name: string;
  description: string;
  emoji: string;
  params: SimulationInput;
  spouse?: SpouseInput;
}

export interface ErrorInfo {
  title: string;
  message: string;
  suggestion: string;
  field?: string;
  technical?: string;
}

// ============================================
// Example personas for quick-start
// ============================================

export const EXAMPLE_PERSONAS: Persona[] = [
  {
    id: "early-retiree",
    name: "Early Retiree",
    description: "55-year-old leaving tech with $1.5M saved",
    emoji: "\u{1F3D6}\u{FE0F}",
    params: {
      initial_capital: 1500000,
      annual_spending: 80000,
      home_value: 0,
      current_age: 55,
      max_age: 95,
      gender: "male",
      social_security_monthly: 2800,
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
    },
  },
  {
    id: "retiring-couple",
    name: "Retiring Couple",
    description: "Both 62, $800K saved, ready to retire",
    emoji: "\u{1F46B}",
    params: {
      initial_capital: 800000,
      annual_spending: 70000,
      home_value: 0,
      current_age: 62,
      max_age: 95,
      gender: "male",
      social_security_monthly: 2400,
      social_security_start_age: 67,
      pension_annual: 0,
      employment_income: 0,
      employment_growth_rate: 0.03,
      retirement_age: 65,
      state: "TX",
      filing_status: "married_filing_jointly",
      has_spouse: true,
      has_annuity: false,
      n_simulations: 10000,
      include_mortality: true,
      expected_return: 0.07,
      return_volatility: 0.16,
      dividend_yield: 0.02,
      stock_allocation: 0.8,
    },
    spouse: {
      age: 60,
      gender: "female",
      social_security_monthly: 1800,
      social_security_start_age: 67,
      pension_annual: 0,
      employment_income: 0,
      employment_growth_rate: 0.03,
      retirement_age: 62,
    },
  },
  {
    id: "conservative-saver",
    name: "Conservative Saver",
    description: "67-year-old with pension and modest savings",
    emoji: "\u{1F3E6}",
    params: {
      initial_capital: 400000,
      annual_spending: 50000,
      home_value: 0,
      current_age: 67,
      max_age: 95,
      gender: "female",
      social_security_monthly: 2200,
      social_security_start_age: 67,
      pension_annual: 18000,
      employment_income: 0,
      employment_growth_rate: 0.03,
      retirement_age: 65,
      state: "FL",
      filing_status: "single",
      has_spouse: false,
      has_annuity: false,
      n_simulations: 10000,
      include_mortality: true,
      expected_return: 0.07,
      return_volatility: 0.16,
      dividend_yield: 0.02,
      stock_allocation: 0.8,
    },
  },
  {
    id: "high-earner",
    name: "High Earner",
    description: "50-year-old still working, $2M saved",
    emoji: "\u{1F4BC}",
    params: {
      initial_capital: 2000000,
      annual_spending: 120000,
      home_value: 0,
      current_age: 50,
      max_age: 95,
      gender: "male",
      social_security_monthly: 3500,
      social_security_start_age: 70,
      pension_annual: 0,
      employment_income: 300000,
      employment_growth_rate: 0.03,
      retirement_age: 60,
      state: "NY",
      filing_status: "married_filing_jointly",
      has_spouse: true,
      has_annuity: false,
      n_simulations: 10000,
      include_mortality: true,
      expected_return: 0.07,
      return_volatility: 0.16,
      dividend_yield: 0.02,
      stock_allocation: 0.8,
    },
    spouse: {
      age: 48,
      gender: "female",
      social_security_monthly: 2000,
      social_security_start_age: 67,
      pension_annual: 0,
      employment_income: 150000,
      employment_growth_rate: 0.03,
      retirement_age: 60,
    },
  },
];

// ============================================
// Formatting helpers
// ============================================

export function formatCurrency(value: number): string {
  if (Math.abs(value) >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(1)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `$${(value / 1_000).toFixed(0)}K`;
  }
  return `$${value.toFixed(0)}`;
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

// ============================================
// Interpretation helpers
// ============================================

export function getSuccessRateInterpretation(rate: number): { label: string; description: string; color: string } {
  if (rate >= 0.95) {
    return {
      label: "Excellent",
      description: "Very high confidence your money will last. You may even be able to spend more.",
      color: "#16a34a",
    };
  } else if (rate >= 0.90) {
    return {
      label: "Good",
      description: "Strong likelihood of success. This is generally considered a safe plan.",
      color: "#22c55e",
    };
  } else if (rate >= 0.80) {
    return {
      label: "Adequate",
      description: "Reasonable odds, but consider a small buffer. Minor adjustments could help.",
      color: "#84cc16",
    };
  } else if (rate >= 0.70) {
    return {
      label: "Marginal",
      description: "Some risk of running short. Consider reducing spending or increasing savings.",
      color: "#eab308",
    };
  } else if (rate >= 0.50) {
    return {
      label: "Risky",
      description: "Significant chance of depletion. Strongly consider adjusting your plan.",
      color: "#f97316",
    };
  } else {
    return {
      label: "High Risk",
      description: "More likely than not to run out of money. Substantial changes recommended.",
      color: "#ef4444",
    };
  }
}

export function getWithdrawalRateContext(rate: number): { warning: boolean; message: string } {
  if (rate <= 3) {
    return { warning: false, message: "Conservative - historically very safe" };
  } else if (rate <= 4) {
    return { warning: false, message: "The classic '4% rule' - generally considered safe" };
  } else if (rate <= 5) {
    return { warning: true, message: "Slightly aggressive - monitor carefully" };
  } else if (rate <= 6) {
    return { warning: true, message: "Aggressive - may require flexibility" };
  } else {
    return { warning: true, message: "Very high - requires careful monitoring" };
  }
}

// ============================================
// Error helpers
// ============================================

export function getErrorInfo(error: unknown): ErrorInfo {
  // Handle typed API errors
  if (error instanceof NetworkError) {
    return {
      title: "Connection Problem",
      message: "Unable to reach the simulation server.",
      suggestion: "Check your internet connection and try again. If the problem persists, the server may be temporarily unavailable.",
      technical: error.message,
    };
  }

  if (error instanceof TimeoutError) {
    return {
      title: "Request Timed Out",
      message: "The simulation took longer than expected to complete.",
      suggestion: "Try running the simulation again. For complex scenarios, consider reducing the number of simulations.",
      technical: error.message,
    };
  }

  if (error instanceof ValidationError) {
    const fieldHint = error.field
      ? `The issue is with "${error.field.replace(/_/g, " ")}".`
      : "";
    return {
      title: "Invalid Input",
      message: error.message,
      suggestion: `${fieldHint} Please review your inputs and make sure all values are reasonable.`,
      field: error.field,
      technical: error.message,
    };
  }

  if (error instanceof SimulationError) {
    return {
      title: "Simulation Error",
      message: "Something went wrong while running your simulation.",
      suggestion: "This is usually temporary. Please wait a moment and try again.",
      technical: error.message,
    };
  }

  if (error instanceof ApiError) {
    return {
      title: "Server Error",
      message: error.message || "An unexpected error occurred.",
      suggestion: "Please try again. If the problem continues, try refreshing the page.",
      technical: error.statusCode ? `Status: ${error.statusCode}` : undefined,
    };
  }

  // Handle string errors (legacy)
  if (typeof error === "string") {
    const lowerError = error.toLowerCase();

    if (lowerError.includes("network") || lowerError.includes("fetch") || lowerError.includes("failed to fetch")) {
      return {
        title: "Connection Problem",
        message: "We couldn't reach the simulation server.",
        suggestion: "Check your internet connection and try again.",
        technical: error,
      };
    }

    if (lowerError.includes("timeout") || lowerError.includes("timed out")) {
      return {
        title: "Request Timed Out",
        message: "The simulation took longer than expected.",
        suggestion: "Try running the simulation again.",
        technical: error,
      };
    }

    return {
      title: "Something Went Wrong",
      message: error,
      suggestion: "Please try again. If the problem continues, try refreshing the page.",
      technical: error,
    };
  }

  // Handle Error objects
  if (error instanceof Error) {
    return {
      title: "Something Went Wrong",
      message: error.message || "An unexpected error occurred.",
      suggestion: "Please try again. If the problem continues, try refreshing the page or adjusting your inputs.",
      technical: error.message,
    };
  }

  // Default fallback
  return {
    title: "Something Went Wrong",
    message: "We encountered an unexpected error while running your simulation.",
    suggestion: "Please try again. If the problem continues, try refreshing the page or adjusting your inputs.",
  };
}

// ============================================
// URL parameter helpers
// ============================================

export function parseUrlParams(): { params: Partial<SimulationInput>; spouse: Partial<SpouseInput> } {
  const urlParams = new URLSearchParams(window.location.search);
  const params: Partial<SimulationInput> = {};
  const spouse: Partial<SpouseInput> = {};

  // Number params (short keys)
  const numParams = ["cap", "spend", "home", "age", "max", "ss", "ssAge", "pension", "emp", "ret", "stocks"];

  for (const [shortKey, value] of urlParams.entries()) {
    if (!(shortKey in URL_PARAM_MAP)) continue;

    const longKey = URL_PARAM_MAP[shortKey as keyof typeof URL_PARAM_MAP];

    // Handle spouse params separately
    if (shortKey.startsWith("sp") && shortKey !== "spouse") {
      if (shortKey === "spAge") spouse.age = Number(value);
      else if (shortKey === "spGen") spouse.gender = value as "male" | "female";
      else if (shortKey === "spSS") spouse.social_security_monthly = Number(value);
      else if (shortKey === "spSSAge") spouse.social_security_start_age = Number(value);
      else if (shortKey === "spPension") spouse.pension_annual = Number(value);
      else if (shortKey === "spRet") spouse.retirement_age = Number(value);
      continue;
    }

    // Handle main params
    if (numParams.includes(shortKey)) {
      const numValue = Number(value);
      if (!isNaN(numValue)) {
        if (shortKey === "stocks") {
          // stocks is 0-100 in URL, 0-1 in params
          (params as Record<string, number>)[longKey] = numValue / 100;
        } else {
          (params as Record<string, number>)[longKey] = numValue;
        }
      }
    } else if (shortKey === "gen") {
      params.gender = value as "male" | "female";
    } else if (shortKey === "state") {
      params.state = value;
    } else if (shortKey === "status") {
      params.filing_status = value as SimulationInput["filing_status"];
    } else if (shortKey === "spouse") {
      params.has_spouse = value === "1" || value === "true";
    }
  }

  return { params, spouse };
}

export function buildUrlParams(params: SimulationInput, spouse?: SpouseInput): string {
  const urlParams = new URLSearchParams();

  // Only include non-default values
  if (params.initial_capital !== undefined && params.initial_capital !== 500000) {
    urlParams.set("cap", String(params.initial_capital));
  }
  if (params.annual_spending !== 60000) {
    urlParams.set("spend", String(params.annual_spending));
  }
  if (params.home_value && params.home_value !== 0) {
    urlParams.set("home", String(params.home_value));
  }
  if (params.current_age !== 65) {
    urlParams.set("age", String(params.current_age));
  }
  if (params.max_age !== 95) {
    urlParams.set("max", String(params.max_age));
  }
  if (params.gender !== "male") {
    urlParams.set("gen", params.gender);
  }
  if (params.state !== "CA") {
    urlParams.set("state", params.state);
  }
  if (params.filing_status !== "single") {
    urlParams.set("status", params.filing_status);
  }
  if (params.social_security_monthly !== 2000) {
    urlParams.set("ss", String(params.social_security_monthly));
  }
  if (params.social_security_start_age !== 67) {
    urlParams.set("ssAge", String(params.social_security_start_age));
  }
  if (params.pension_annual && params.pension_annual !== 0) {
    urlParams.set("pension", String(params.pension_annual));
  }
  if (params.employment_income && params.employment_income !== 0) {
    urlParams.set("emp", String(params.employment_income));
  }
  if (params.retirement_age !== 65) {
    urlParams.set("ret", String(params.retirement_age));
  }
  if (params.stock_allocation !== 0.8) {
    urlParams.set("stocks", String(Math.round(params.stock_allocation * 100)));
  }

  // Spouse params
  if (params.has_spouse && spouse) {
    urlParams.set("spouse", "1");
    if (spouse.age !== 63) urlParams.set("spAge", String(spouse.age));
    if (spouse.gender !== "female") urlParams.set("spGen", spouse.gender);
    if (spouse.social_security_monthly !== 1500) urlParams.set("spSS", String(spouse.social_security_monthly));
    if (spouse.social_security_start_age !== 67) urlParams.set("spSSAge", String(spouse.social_security_start_age));
    if (spouse.pension_annual && spouse.pension_annual !== 0) urlParams.set("spPension", String(spouse.pension_annual));
    if (spouse.retirement_age !== 65) urlParams.set("spRet", String(spouse.retirement_age));
  }

  return urlParams.toString();
}
