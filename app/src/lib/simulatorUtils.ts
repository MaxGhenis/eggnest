/**
 * Shared utility functions for the simulator.
 */
import type { SimulationInput, SpouseInput, AnnuityInput, Holding, SimulationResult } from "./api";
import {
  NetworkError,
  TimeoutError,
  ValidationError,
  SimulationError,
  ApiError,
} from "./api";
import { DEFAULT_PARAMS, URL_PARAM_MAP } from "./constants";
import type { PortfolioMode, WithdrawalStrategy } from "../hooks/usePortfolio";

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
  summary: string;
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
    name: "Early retiree",
    description: "55-year-old leaving tech with $1.5M saved",
    emoji: "\u{1F3D6}\u{FE0F}",
    params: {
      ...DEFAULT_PARAMS,
      initial_capital: 1500000,
      annual_spending: 80000,
      current_age: 55,
      social_security_monthly: 2800,
    },
  },
  {
    id: "retiring-couple",
    name: "Retiring couple",
    description: "Both 62, $800K saved, ready to retire",
    emoji: "\u{1F46B}",
    params: {
      ...DEFAULT_PARAMS,
      initial_capital: 800000,
      annual_spending: 70000,
      current_age: 62,
      social_security_monthly: 2400,
      state: "TX",
      filing_status: "married_filing_jointly",
      has_spouse: true,
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
    name: "Conservative saver",
    description: "67-year-old with pension and modest savings",
    emoji: "\u{1F3E6}",
    params: {
      ...DEFAULT_PARAMS,
      initial_capital: 400000,
      annual_spending: 50000,
      current_age: 67,
      gender: "female",
      social_security_monthly: 2200,
      pension_annual: 18000,
      state: "FL",
    },
  },
  {
    id: "high-earner",
    name: "High earner",
    description: "50-year-old still working, $2M saved",
    emoji: "\u{1F4BC}",
    params: {
      ...DEFAULT_PARAMS,
      initial_capital: 2000000,
      annual_spending: 120000,
      current_age: 50,
      social_security_monthly: 3500,
      social_security_start_age: 70,
      employment_income: 300000,
      retirement_age: 60,
      state: "NY",
      filing_status: "married_filing_jointly",
      has_spouse: true,
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
// Outcome helpers
// ============================================

export function getWithdrawalRateContext(rate: number): { warning: boolean; message: string } {
  if (rate <= 3) {
    return { warning: false, message: "Conservative relative to common historical rules of thumb" };
  } else if (rate <= 4) {
    return { warning: false, message: "Near the classic 4% rule range used in many retirement studies" };
  } else if (rate <= 5) {
    return { warning: true, message: "Above common historical rules of thumb" };
  } else if (rate <= 6) {
    return { warning: true, message: "Aggressive relative to common retirement planning heuristics" };
  } else {
    return { warning: true, message: "Very high relative to common retirement planning heuristics" };
  }
}

// ============================================
// Error helpers
// ============================================

export function getErrorInfo(error: unknown): ErrorInfo {
  // Handle typed API errors
  if (error instanceof NetworkError) {
    return {
      title: "Connection problem",
      message: "Unable to reach the simulation server.",
      suggestion: "Check your internet connection and try again. If the problem persists, the server may be temporarily unavailable.",
      technical: error.message,
    };
  }

  if (error instanceof TimeoutError) {
    return {
      title: "Request timed out",
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
      title: "Invalid input",
      message: error.message,
      suggestion: `${fieldHint} Please review your inputs and make sure all values are reasonable.`,
      field: error.field,
      technical: error.message,
    };
  }

  if (error instanceof SimulationError) {
    return {
      title: "Simulation error",
      message: "Something went wrong while running your simulation.",
      suggestion: "This is usually temporary. Please wait a moment and try again.",
      technical: error.message,
    };
  }

  if (error instanceof ApiError) {
    return {
      title: "Server error",
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
        title: "Connection problem",
        message: "We couldn't reach the simulation server.",
        suggestion: "Check your internet connection and try again.",
        technical: error,
      };
    }

    if (lowerError.includes("timeout") || lowerError.includes("timed out")) {
      return {
        title: "Request timed out",
        message: "The simulation took longer than expected.",
        suggestion: "Try running the simulation again.",
        technical: error,
      };
    }

    return {
      title: "Something went wrong",
      message: error,
      suggestion: "Please try again. If the problem continues, try refreshing the page.",
      technical: error,
    };
  }

  // Handle Error objects
  if (error instanceof Error) {
    return {
      title: "Something went wrong",
      message: error.message || "An unexpected error occurred.",
      suggestion: "Please try again. If the problem continues, try refreshing the page or adjusting your inputs.",
      technical: error.message,
    };
  }

  // Default fallback
  return {
    title: "Something went wrong",
    message: "We encountered an unexpected error while running your simulation.",
    suggestion: "Please try again. If the problem continues, try refreshing the page or adjusting your inputs.",
  };
}

// ============================================
// URL parameter helpers
// ============================================

export function parseUrlParams(): { params: Partial<SimulationInput>; spouse: Partial<SpouseInput> } {
  if (typeof window === "undefined") return { params: {}, spouse: {} };
  const urlParams = new URLSearchParams(window.location.search);
  const params: Partial<SimulationInput> = {};
  const spouse: Partial<SpouseInput> = {};

  // Number params (short keys)
  const numParams = ["cap", "spend", "home", "age", "max", "ss", "ssAge", "pension", "emp", "ret", "stocks", "infl", "penCola", "annCola"];

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
    } else if (shortKey === "spMode") {
      params.spending_mode = value as SimulationInput["spending_mode"];
    } else if (shortKey === "infMode") {
      params.inflation_model = value as SimulationInput["inflation_model"];
    } else if (shortKey === "state") {
      params.state = value;
    } else if (shortKey === "status") {
      params.filing_status = value as SimulationInput["filing_status"];
    } else if (shortKey === "ssCola") {
      params.social_security_inflation_adjusted = value === "1" || value === "true";
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
  if (params.spending_mode !== "real") {
    urlParams.set("spMode", params.spending_mode);
  }
  if (params.inflation_model !== "historical") {
    urlParams.set("infMode", params.inflation_model);
  }
  if (params.inflation_rate !== 0.025) {
    urlParams.set("infl", String(params.inflation_rate));
  }
  if (!params.social_security_inflation_adjusted) {
    urlParams.set("ssCola", "0");
  }
  if (params.pension_cola_rate !== 0) {
    urlParams.set("penCola", String(params.pension_cola_rate));
  }
  if (params.annuity_cola_rate !== 0) {
    urlParams.set("annCola", String(params.annuity_cola_rate));
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

// ============================================
// Simulation parameter helpers
// ============================================

/**
 * Build the full simulation parameters object from the UI state,
 * merging in spouse, annuity, holdings, and withdrawal strategy as needed.
 *
 * Used by both useSimulation and useComparisons hooks to avoid duplication.
 */
export function buildFullParams(
  params: SimulationInput,
  spouse: SpouseInput | undefined,
  annuity: AnnuityInput,
  portfolioMode: PortfolioMode,
  holdings: Holding[],
  withdrawalStrategy: WithdrawalStrategy,
): SimulationInput {
  const hasDetailedHoldings = portfolioMode === "detailed" && holdings.length > 0;
  return {
    ...params,
    spouse: params.has_spouse ? spouse : undefined,
    annuity: params.has_annuity ? annuity : undefined,
    holdings: hasDetailedHoldings ? holdings : undefined,
    initial_capital: hasDetailedHoldings ? undefined : params.initial_capital,
    withdrawal_strategy: hasDetailedHoldings ? withdrawalStrategy : undefined,
  };
}
