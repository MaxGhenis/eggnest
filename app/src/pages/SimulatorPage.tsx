import { useState, useEffect } from "react";
import Plot from "react-plotly.js";
import { Wizard, type WizardStep } from "../components/Wizard";
import { SimulationProgress } from "../components/SimulationProgress";
import { HoldingsEditor } from "../components/HoldingsEditor";
import { ResultsSkeleton } from "../components/ResultsSkeleton";
import {
  runSimulationWithProgress,
  compareAnnuity,
  compareStates,
  compareSSTimings,
  compareAllocations,
  NetworkError,
  TimeoutError,
  ValidationError,
  SimulationError,
  ApiError,
  type SimulationInput,
  type SimulationResult,
  type SpouseInput,
  type AnnuityInput,
  type StateComparisonResult,
  type SSTimingComparisonResult,
  type AllocationComparisonResult,
  type Holding,
} from "../lib/api";
import { colors, chartColors } from "../lib/design-tokens";
import "../styles/Simulator.css";
import "../styles/Wizard.css";
import "../styles/Skeleton.css";

// Saved scenario interface for localStorage
interface SavedScenario {
  name: string;
  savedAt: string;
  inputs: Partial<SimulationInput>;
  spouse?: SpouseInput;
  annuity?: AnnuityInput;
  portfolioMode?: "simple" | "detailed";
  holdings?: Holding[];
  withdrawalStrategy?: "taxable_first" | "traditional_first" | "roth_first" | "pro_rata";
}

const SCENARIOS_STORAGE_KEY = "eggnest_scenarios";

// In production, this is eggnest.co
const HOME_URL = import.meta.env.PROD
  ? "https://eggnest.co"
  : "http://localhost:5173";

const US_STATES = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
];

const DEFAULT_PARAMS: SimulationInput = {
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

// Example personas for quick-start
interface Persona {
  id: string;
  name: string;
  description: string;
  emoji: string;
  params: SimulationInput;
  spouse?: SpouseInput;
}

const EXAMPLE_PERSONAS: Persona[] = [
  {
    id: "early-retiree",
    name: "Early Retiree",
    description: "55-year-old leaving tech with $1.5M saved",
    emoji: "🏖️",
    params: {
      ...DEFAULT_PARAMS,
      initial_capital: 1500000,
      annual_spending: 80000,
      current_age: 55,
      max_age: 95,
      gender: "male",
      social_security_monthly: 2800,
      social_security_start_age: 67,
      state: "CA",
      filing_status: "single",
      has_spouse: false,
    },
  },
  {
    id: "retiring-couple",
    name: "Retiring Couple",
    description: "Both 62, $800K saved, ready to retire",
    emoji: "👫",
    params: {
      ...DEFAULT_PARAMS,
      initial_capital: 800000,
      annual_spending: 70000,
      current_age: 62,
      max_age: 95,
      gender: "male",
      social_security_monthly: 2400,
      social_security_start_age: 67,
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
    name: "Conservative Saver",
    description: "67-year-old with pension and modest savings",
    emoji: "🏦",
    params: {
      ...DEFAULT_PARAMS,
      initial_capital: 400000,
      annual_spending: 50000,
      current_age: 67,
      max_age: 95,
      gender: "female",
      social_security_monthly: 2200,
      social_security_start_age: 67,
      pension_annual: 18000,
      state: "FL",
      filing_status: "single",
      has_spouse: false,
    },
  },
  {
    id: "high-earner",
    name: "High Earner",
    description: "50-year-old still working, $2M saved",
    emoji: "💼",
    params: {
      ...DEFAULT_PARAMS,
      initial_capital: 2000000,
      annual_spending: 120000,
      current_age: 50,
      max_age: 95,
      gender: "male",
      social_security_monthly: 3500,
      social_security_start_age: 70,
      employment_income: 300000,
      employment_growth_rate: 0.03,
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

// Helper to interpret success rate
function getSuccessRateInterpretation(rate: number): { label: string; description: string; color: string } {
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

// Calculate withdrawal rate context
function getWithdrawalRateContext(rate: number): { warning: boolean; message: string } {
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

function formatCurrency(value: number): string {
  if (Math.abs(value) >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(1)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `$${(value / 1_000).toFixed(0)}K`;
  }
  return `$${value.toFixed(0)}`;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}


// Error info type for structured error display
interface ErrorInfo {
  title: string;
  message: string;
  suggestion: string;
  field?: string;
  technical?: string;
}

// Get user-friendly error information based on error type
function getErrorInfo(error: unknown): ErrorInfo {
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
interface AnnuityComparisonResult {
  simulation_result: SimulationResult;
  annuity_total_guaranteed: number;
  probability_simulation_beats_annuity: number;
  simulation_median_total_income: number;
  recommendation: string;
}

// URL parameter mapping (short names for readability)
const URL_PARAM_MAP = {
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

// Parse URL params into simulation input
function parseUrlParams(): { params: Partial<SimulationInput>; spouse: Partial<SpouseInput> } {
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

// Build URL params from simulation input
function buildUrlParams(params: SimulationInput, spouse?: SpouseInput): string {
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

export function SimulatorPage() {
  const [params, setParams] = useState<SimulationInput>(DEFAULT_PARAMS);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [annuityResult, setAnnuityResult] =
    useState<AnnuityComparisonResult | null>(null);
  const [stateComparisonResult, setStateComparisonResult] =
    useState<StateComparisonResult | null>(null);
  const [isComparingStates, setIsComparingStates] = useState(false);
  const [selectedCompareStates, setSelectedCompareStates] = useState<string[]>([]);
  const [ssTimingResult, setSSTimingResult] =
    useState<SSTimingComparisonResult | null>(null);
  const [isComparingSSTiming, setIsComparingSSTiming] = useState(false);
  const [birthYear, setBirthYear] = useState<number>(1960);
  const [piaMonthly, setPiaMonthly] = useState<number>(2000);
  const [allocationResult, setAllocationResult] =
    useState<AllocationComparisonResult | null>(null);
  const [isComparingAllocations, setIsComparingAllocations] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [showWizard, setShowWizard] = useState(true);
  const [showPersonaPicker, setShowPersonaPicker] = useState(true);
  const [progress, setProgress] = useState({ currentYear: 0, totalYears: 0 });
  const [selectedYearIndex, setSelectedYearIndex] = useState<number | null>(null);

  // SS receiving status (for users already receiving benefits)
  const [isReceivingSS, setIsReceivingSS] = useState(false);
  const [isSpouseReceivingSS, setIsSpouseReceivingSS] = useState(false);

  // Portfolio mode: "simple" uses initial_capital, "detailed" uses holdings
  const [portfolioMode, setPortfolioMode] = useState<"simple" | "detailed">("simple");
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [withdrawalStrategy, setWithdrawalStrategy] = useState<"taxable_first" | "traditional_first" | "roth_first" | "pro_rata">("taxable_first");

  // Saved scenarios state
  const [savedScenarios, setSavedScenarios] = useState<SavedScenario[]>([]);
  const [scenarioName, setScenarioName] = useState("");
  const [showSaveDialog, setShowSaveDialog] = useState(false);

  // Load saved scenarios from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(SCENARIOS_STORAGE_KEY);
      if (stored) {
        setSavedScenarios(JSON.parse(stored));
      }
    } catch (e) {
      console.error("Failed to load saved scenarios:", e);
    }
  }, []);

  // URL state for copy link
  const [linkCopied, setLinkCopied] = useState(false);

  // Load URL params on mount (they override defaults)
  useEffect(() => {
    const urlData = parseUrlParams();
    if (Object.keys(urlData.params).length > 0) {
      setParams((prev) => ({ ...prev, ...urlData.params }));
      // Skip persona picker if URL has params
      setShowPersonaPicker(false);
    }
    if (Object.keys(urlData.spouse).length > 0) {
      setSpouse((prev) => ({ ...prev, ...urlData.spouse }));
    }
  }, []);

  // Spouse state
  const [spouse, setSpouse] = useState<SpouseInput>({
    age: 63,
    gender: "female",
    social_security_monthly: 1500,
    social_security_start_age: 67,
    pension_annual: 0,
    employment_income: 0,
    employment_growth_rate: 0.03,
    retirement_age: 65,
  });

  // Annuity state
  const [annuity, setAnnuity] = useState<AnnuityInput>({
    monthly_payment: 3000,
    annuity_type: "life_with_guarantee",
    guarantee_years: 15,
  });

  const updateParam = <K extends keyof SimulationInput>(
    key: K,
    value: SimulationInput[K]
  ) => {
    setParams((prev) => ({ ...prev, [key]: value }));
  };

  // Save scenario to localStorage
  const saveScenario = (name: string) => {
    const scenario: SavedScenario = {
      name,
      savedAt: new Date().toISOString(),
      inputs: { ...params },
      spouse: params.has_spouse ? spouse : undefined,
      annuity: params.has_annuity ? annuity : undefined,
      portfolioMode,
      holdings: portfolioMode === "detailed" ? holdings : undefined,
      withdrawalStrategy: portfolioMode === "detailed" ? withdrawalStrategy : undefined,
    };

    const updated = [...savedScenarios.filter(s => s.name !== name), scenario];
    setSavedScenarios(updated);
    localStorage.setItem(SCENARIOS_STORAGE_KEY, JSON.stringify(updated));
    setScenarioName("");
    setShowSaveDialog(false);
  };

  // Load scenario from saved
  const loadSavedScenario = (scenario: SavedScenario) => {
    if (scenario.inputs) {
      setParams({ ...DEFAULT_PARAMS, ...scenario.inputs } as SimulationInput);
    }
    if (scenario.spouse) {
      setSpouse(scenario.spouse);
    }
    if (scenario.annuity) {
      setAnnuity(scenario.annuity);
    }
    if (scenario.portfolioMode) {
      setPortfolioMode(scenario.portfolioMode);
    }
    if (scenario.holdings) {
      setHoldings(scenario.holdings);
    }
    if (scenario.withdrawalStrategy) {
      setWithdrawalStrategy(scenario.withdrawalStrategy);
    }
    setShowPersonaPicker(false);
  };

  // Delete scenario
  const deleteScenario = (name: string) => {
    const updated = savedScenarios.filter(s => s.name !== name);
    setSavedScenarios(updated);
    localStorage.setItem(SCENARIOS_STORAGE_KEY, JSON.stringify(updated));
  };

  // Load a persona and optionally run simulation immediately
  const loadPersona = (persona: Persona, runImmediately: boolean = false) => {
    setParams(persona.params);
    if (persona.spouse) {
      setSpouse(persona.spouse);
    }
    setShowPersonaPicker(false);
    if (runImmediately) {
      // Small delay to let state update
      setTimeout(() => {
        handleSimulateWithParams(persona.params, persona.spouse);
      }, 0);
    }
  };

  // Simulate with specific params (used by persona quick-run)
  const handleSimulateWithParams = async (simParams: SimulationInput, simSpouse?: SpouseInput) => {
    setIsLoading(true);
    setError(null);
    setAnnuityResult(null);
    setProgress({ currentYear: 0, totalYears: simParams.max_age - simParams.current_age });

    try {
      const fullParams: SimulationInput = {
        ...simParams,
        spouse: simParams.has_spouse ? simSpouse : undefined,
        annuity: simParams.has_annuity ? annuity : undefined,
        // Include holdings if in detailed mode
        holdings: portfolioMode === "detailed" && holdings.length > 0 ? holdings : undefined,
        initial_capital: portfolioMode === "detailed" && holdings.length > 0 ? undefined : simParams.initial_capital,
        // Include withdrawal strategy only when in detailed mode with holdings
        withdrawal_strategy: portfolioMode === "detailed" && holdings.length > 0 ? withdrawalStrategy : undefined,
      };

      // Use streaming API with progress updates
      for await (const event of runSimulationWithProgress(fullParams)) {
        if (event.type === "progress") {
          setProgress({ currentYear: event.year, totalYears: event.total_years });
        } else if (event.type === "complete") {
          setResult(event.result);
        }
      }
      // Update URL with current params for sharing
      const urlString = buildUrlParams(simParams, simParams.has_spouse ? simSpouse : undefined);
      const newUrl = urlString ? `${window.location.pathname}?${urlString}` : window.location.pathname;
      window.history.replaceState(null, "", newUrl);
      setShowWizard(false);
    } catch (err) {
      setError(err);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSimulate = async () => {
    setIsLoading(true);
    setError(null);
    setAnnuityResult(null);
    setProgress({ currentYear: 0, totalYears: params.max_age - params.current_age });

    try {
      const fullParams: SimulationInput = {
        ...params,
        spouse: params.has_spouse ? spouse : undefined,
        annuity: params.has_annuity ? annuity : undefined,
        // Include holdings if in detailed mode
        holdings: portfolioMode === "detailed" && holdings.length > 0 ? holdings : undefined,
        // Clear initial_capital if using holdings (backend uses holdings.total)
        initial_capital: portfolioMode === "detailed" && holdings.length > 0 ? undefined : params.initial_capital,
        // Include withdrawal strategy only when in detailed mode with holdings
        withdrawal_strategy: portfolioMode === "detailed" && holdings.length > 0 ? withdrawalStrategy : undefined,
      };

      if (params.has_annuity && annuity.monthly_payment > 0) {
        // Annuity comparison doesn't support streaming yet, use regular API
        const comparison = await compareAnnuity(
          fullParams,
          annuity.monthly_payment,
          annuity.guarantee_years
        );
        setResult(comparison.simulation_result);
        setAnnuityResult(comparison);
      } else {
        // Use streaming API with progress updates
        for await (const event of runSimulationWithProgress(fullParams)) {
          if (event.type === "progress") {
            setProgress({ currentYear: event.year, totalYears: event.total_years });
          } else if (event.type === "complete") {
            setResult(event.result);
          }
        }
      }
      // Update URL with current params for sharing
      const urlString = buildUrlParams(params, params.has_spouse ? spouse : undefined);
      const newUrl = urlString ? `${window.location.pathname}?${urlString}` : window.location.pathname;
      window.history.replaceState(null, "", newUrl);
      setShowWizard(false);
    } catch (err) {
      setError(err);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  // Copy current URL to clipboard
  const copyLinkToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy link:", err);
    }
  };

  // No-income-tax states for quick comparison
  const NO_TAX_STATES = ["FL", "TX", "NV", "WA", "WY", "SD", "AK", "TN", "NH"];

  const handleCompareStates = async (statesToCompare?: string[]) => {
    if (!result) return;

    setIsComparingStates(true);
    setStateComparisonResult(null);

    try {
      const fullParams: SimulationInput = {
        ...params,
        spouse: params.has_spouse ? spouse : undefined,
        annuity: params.has_annuity ? annuity : undefined,
        holdings: portfolioMode === "detailed" && holdings.length > 0 ? holdings : undefined,
        initial_capital: portfolioMode === "detailed" && holdings.length > 0 ? undefined : params.initial_capital,
        withdrawal_strategy: portfolioMode === "detailed" && holdings.length > 0 ? withdrawalStrategy : undefined,
      };

      // Use provided states, selected states, or default to no-tax states
      const states = statesToCompare ||
        (selectedCompareStates.length > 0 ? selectedCompareStates :
          NO_TAX_STATES.filter(s => s !== params.state).slice(0, 5));

      const comparison = await compareStates(fullParams, states);
      setStateComparisonResult(comparison);
    } catch (err) {
      setError(err);
    } finally {
      setIsComparingStates(false);
    }
  };

  const toggleCompareState = (state: string) => {
    setSelectedCompareStates(prev =>
      prev.includes(state)
        ? prev.filter(s => s !== state)
        : prev.length < 5 ? [...prev, state] : prev
    );
  };

  const handleCompareSSTimings = async () => {
    if (!result) return;

    setIsComparingSSTiming(true);
    setSSTimingResult(null);

    try {
      const fullParams: SimulationInput = {
        ...params,
        spouse: params.has_spouse ? spouse : undefined,
        annuity: params.has_annuity ? annuity : undefined,
        holdings: portfolioMode === "detailed" && holdings.length > 0 ? holdings : undefined,
        initial_capital: portfolioMode === "detailed" && holdings.length > 0 ? undefined : params.initial_capital,
        withdrawal_strategy: portfolioMode === "detailed" && holdings.length > 0 ? withdrawalStrategy : undefined,
      };

      const comparison = await compareSSTimings(
        fullParams,
        birthYear,
        piaMonthly
      );
      setSSTimingResult(comparison);
    } catch (err) {
      setError(err);
    } finally {
      setIsComparingSSTiming(false);
    }
  };

  const handleCompareAllocations = async () => {
    if (!result) return;

    setIsComparingAllocations(true);
    setAllocationResult(null);

    try {
      const fullParams: SimulationInput = {
        ...params,
        spouse: params.has_spouse ? spouse : undefined,
        annuity: params.has_annuity ? annuity : undefined,
        holdings: portfolioMode === "detailed" && holdings.length > 0 ? holdings : undefined,
        initial_capital: portfolioMode === "detailed" && holdings.length > 0 ? undefined : params.initial_capital,
        withdrawal_strategy: portfolioMode === "detailed" && holdings.length > 0 ? withdrawalStrategy : undefined,
      };

      const comparison = await compareAllocations(
        fullParams,
        [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
      );
      setAllocationResult(comparison);
    } catch (err) {
      setError(err);
    } finally {
      setIsComparingAllocations(false);
    }
  };

  const successColor =
    result && result.success_rate >= 0.9
      ? "#10b981"
      : result && result.success_rate >= 0.75
        ? "#f59e0b"
        : "#ef4444";

  const ages = result
    ? result.percentile_paths.p50.map((_, i) => params.current_age + i)
    : [];

  // Wizard steps
  const wizardSteps: WizardStep[] = [
    {
      id: "about",
      title: "About You",
      subtitle: "Let's start with some basic information",
      content: (
        <div>
          <div className="wizard-field-row">
            <div className="wizard-field">
              <label>Current Age</label>
              <input
                type="number"
                value={params.current_age}
                onChange={(e) =>
                  updateParam("current_age", Number(e.target.value))
                }
                min={18}
                max={100}
              />
            </div>
            <div className="wizard-field">
              <label>Planning To Age</label>
              <input
                type="number"
                value={params.max_age}
                onChange={(e) =>
                  updateParam("max_age", Number(e.target.value))
                }
                min={params.current_age + 5}
                max={120}
              />
            </div>
          </div>
          <div className="wizard-field-row">
            <div className="wizard-field">
              <label>Gender</label>
              <select
                value={params.gender}
                onChange={(e) =>
                  updateParam("gender", e.target.value as "male" | "female")
                }
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
              <div className="wizard-field-hint">Used for mortality estimates</div>
            </div>
            <div className="wizard-field">
              <label>State</label>
              <select
                value={params.state}
                onChange={(e) => updateParam("state", e.target.value)}
              >
                {US_STATES.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>
              <div className="wizard-field-hint">For state tax calculations</div>
            </div>
          </div>
          <div className="wizard-field">
            <label>Filing Status</label>
            <select
              value={params.filing_status}
              onChange={(e) =>
                updateParam(
                  "filing_status",
                  e.target.value as SimulationInput["filing_status"]
                )
              }
            >
              <option value="single">Single</option>
              <option value="married_filing_jointly">Married (Joint)</option>
              <option value="head_of_household">Head of Household</option>
            </select>
          </div>
        </div>
      ),
    },
    {
      id: "money",
      title: "Your Money",
      subtitle: "How much have you saved, and how much do you need?",
      content: (() => {
        const totalPortfolio = portfolioMode === "detailed" && holdings.length > 0
          ? holdings.reduce((sum, h) => sum + h.balance, 0)
          : (params.initial_capital ?? 0);
        const withdrawalRate = totalPortfolio > 0
          ? (params.annual_spending / totalPortfolio) * 100
          : 0;
        const rateContext = getWithdrawalRateContext(withdrawalRate);

        return (
          <div>
            {/* Portfolio Mode Toggle */}
            <div className="wizard-field">
              <label>Portfolio Entry Mode</label>
              <div className="portfolio-mode-toggle">
                <button
                  type="button"
                  className={`mode-btn ${portfolioMode === "simple" ? "active" : ""}`}
                  onClick={() => setPortfolioMode("simple")}
                >
                  Simple
                </button>
                <button
                  type="button"
                  className={`mode-btn ${portfolioMode === "detailed" ? "active" : ""}`}
                  onClick={() => setPortfolioMode("detailed")}
                >
                  By Account Type
                </button>
              </div>
              <div className="wizard-field-hint">
                {portfolioMode === "simple"
                  ? "Enter a single total value"
                  : "Enter each account separately for tax-optimized withdrawals"}
              </div>
            </div>

            {portfolioMode === "simple" ? (
              <>
                <div className="wizard-field">
                  <label>Current Portfolio Value</label>
                  <div className="wizard-field-prefix">
                    <span>$</span>
                    <input
                      type="number"
                      value={params.initial_capital}
                      onChange={(e) =>
                        updateParam("initial_capital", Number(e.target.value))
                      }
                      min={0}
                      step={10000}
                    />
                  </div>
                  <div className="wizard-field-hint">
                    Total savings and investments
                  </div>
                </div>
                <div className="wizard-field">
                  <label>Investment Mix: {Math.round(params.stock_allocation * 100)}% Stocks / {Math.round((1 - params.stock_allocation) * 100)}% Bonds</label>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={params.stock_allocation * 100}
                    onChange={(e) =>
                      updateParam("stock_allocation", Number(e.target.value) / 100)
                    }
                    style={{ width: "100%" }}
                  />
                  <div className="wizard-field-hint">
                    More stocks = higher growth potential but more volatility
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="wizard-field">
                  <label>Your Holdings</label>
                  <div className="detailed-mode-explainer">
                    <p className="explainer-benefit">
                      Track each account separately for tax-optimized withdrawal ordering
                    </p>
                    <p className="explainer-feature">
                      RMDs automatically calculated for traditional accounts at age 73+
                    </p>
                  </div>
                  <HoldingsEditor holdings={holdings} onChange={setHoldings} />
                </div>

                <div className="wizard-field">
                  <label htmlFor="withdrawal-strategy">Withdrawal Strategy</label>
                  <select
                    id="withdrawal-strategy"
                    value={withdrawalStrategy}
                    onChange={(e) =>
                      setWithdrawalStrategy(
                        e.target.value as "taxable_first" | "traditional_first" | "roth_first" | "pro_rata"
                      )
                    }
                  >
                    <option value="taxable_first">
                      Taxable First - Lets tax-advantaged accounts grow longer
                    </option>
                    <option value="traditional_first">
                      Traditional First - Reduces future RMDs
                    </option>
                    <option value="roth_first">
                      Roth First - Preserves tax-deferred growth
                    </option>
                    <option value="pro_rata">
                      Pro Rata - Withdraw proportionally from all accounts
                    </option>
                  </select>
                  <div className="wizard-field-hint">
                    Controls which accounts are withdrawn from first when you need money
                  </div>
                </div>
              </>
            )}

            <div className="wizard-field">
              <label>Home Equity</label>
              <div className="wizard-field-prefix">
                <span>$</span>
                <input
                  type="number"
                  value={params.home_value}
                  onChange={(e) =>
                    updateParam("home_value", Number(e.target.value))
                  }
                  min={0}
                  step={10000}
                />
              </div>
              <div className="wizard-field-hint">
                Home value minus mortgage (not used in simulation, shown in net worth)
              </div>
            </div>
            <div className="wizard-field">
              <label>Annual Spending Need</label>
              <div className="wizard-field-prefix">
                <span>$</span>
                <input
                  type="number"
                  value={params.annual_spending}
                  onChange={(e) =>
                    updateParam("annual_spending", Number(e.target.value))
                  }
                  min={0}
                  step={1000}
                />
              </div>
              <div className="wizard-field-hint">
                That's ${(params.annual_spending / 12).toLocaleString()} per month
              </div>
            </div>

            {totalPortfolio > 0 && params.annual_spending > 0 && (
              <div className={`validation-context ${rateContext.warning ? 'warning' : 'success'}`}>
                <div className="validation-rate">
                  <strong>{withdrawalRate.toFixed(1)}%</strong> withdrawal rate
                </div>
                <div className="validation-message">{rateContext.message}</div>
              </div>
            )}
          </div>
        );
      })(),
    },
    {
      id: "income",
      title: "Income Sources",
      subtitle: "What income sources do you have?",
      content: (
        <div>
          <div className="wizard-field">
            <label>Monthly Social Security</label>
            <div className="wizard-field-prefix">
              <span>$</span>
              <input
                type="number"
                value={params.social_security_monthly}
                onChange={(e) =>
                  updateParam("social_security_monthly", Number(e.target.value))
                }
                min={0}
                step={100}
              />
            </div>
            <div className="wizard-field-hint">
              {isReceivingSS
                ? "Your current monthly benefit amount"
                : "Your estimated PIA at full retirement age (check ssa.gov/myaccount)"}
            </div>
          </div>
          {params.social_security_monthly > 0 && params.current_age >= 62 && (
            <div className="wizard-field">
              <label>
                <input
                  type="checkbox"
                  checked={isReceivingSS}
                  onChange={(e) => {
                    setIsReceivingSS(e.target.checked);
                    if (e.target.checked) {
                      // Auto-set start age to current age so simulation includes SS from start
                      updateParam("social_security_start_age", params.current_age);
                    }
                  }}
                  style={{ marginRight: "8px" }}
                />
                Already receiving Social Security
              </label>
            </div>
          )}
          {params.social_security_monthly > 0 && !isReceivingSS && (
            <div className="wizard-field">
              <label>Planned Start Age</label>
              <select
                value={params.social_security_start_age}
                onChange={(e) =>
                  updateParam("social_security_start_age", Number(e.target.value))
                }
              >
                <option value={62}>62 (reduced ~30%)</option>
                <option value={63}>63 (reduced ~25%)</option>
                <option value={64}>64 (reduced ~20%)</option>
                <option value={65}>65 (reduced ~13%)</option>
                <option value={66}>66 (reduced ~7%)</option>
                <option value={67}>67 (full retirement age)</option>
                <option value={68}>68 (8% bonus)</option>
                <option value={69}>69 (16% bonus)</option>
                <option value={70}>70 (24% bonus)</option>
              </select>
              <div className="wizard-field-hint">
                Claiming earlier reduces benefits; waiting increases them
              </div>
            </div>
          )}
          <div className="wizard-field">
            <label>Annual Pension</label>
            <div className="wizard-field-prefix">
              <span>$</span>
              <input
                type="number"
                value={params.pension_annual}
                onChange={(e) =>
                  updateParam("pension_annual", Number(e.target.value))
                }
                min={0}
                step={1000}
              />
            </div>
            <div className="wizard-field-hint">
              Enter 0 if you don't have a pension
            </div>
          </div>
          <div className="wizard-field">
            <label>Current Employment Income</label>
            <div className="wizard-field-prefix">
              <span>$</span>
              <input
                type="number"
                value={params.employment_income}
                onChange={(e) =>
                  updateParam("employment_income", Number(e.target.value))
                }
                min={0}
                step={5000}
              />
            </div>
            <div className="wizard-field-hint">
              If still working, enter your annual salary
            </div>
          </div>
          {params.employment_income > 0 && (
            <div className="wizard-field">
              <label>Retirement Age</label>
              <input
                type="number"
                value={params.retirement_age}
                onChange={(e) =>
                  updateParam("retirement_age", Number(e.target.value))
                }
                min={params.current_age}
                max={80}
              />
              <div className="wizard-field-hint">
                When employment income will stop
              </div>
            </div>
          )}
        </div>
      ),
    },
    {
      id: "spouse",
      title: "Spouse",
      subtitle: "Retiring with a partner? Include their details.",
      optional: true,
      content: (
        <div>
          <label className="wizard-checkbox">
            <input
              type="checkbox"
              checked={params.has_spouse}
              onChange={(e) => updateParam("has_spouse", e.target.checked)}
            />
            <div className="wizard-checkbox-content">
              <div className="wizard-checkbox-label">Include Spouse</div>
              <div className="wizard-checkbox-hint">
                Model finances for both of you together
              </div>
            </div>
          </label>

          {params.has_spouse && (
            <div style={{ marginTop: "1.5rem" }}>
              <div className="wizard-field-row">
                <div className="wizard-field">
                  <label>Spouse Age</label>
                  <input
                    type="number"
                    value={spouse.age}
                    onChange={(e) =>
                      setSpouse({ ...spouse, age: Number(e.target.value) })
                    }
                    min={18}
                    max={100}
                  />
                </div>
                <div className="wizard-field">
                  <label>Spouse Gender</label>
                  <select
                    value={spouse.gender}
                    onChange={(e) =>
                      setSpouse({
                        ...spouse,
                        gender: e.target.value as "male" | "female",
                      })
                    }
                  >
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
              </div>
              <div className="wizard-field">
                <label>Spouse Monthly Social Security</label>
                <div className="wizard-field-prefix">
                  <span>$</span>
                  <input
                    type="number"
                    value={spouse.social_security_monthly}
                    onChange={(e) =>
                      setSpouse({
                        ...spouse,
                        social_security_monthly: Number(e.target.value),
                      })
                    }
                    min={0}
                    step={100}
                  />
                </div>
              </div>
              {spouse.social_security_monthly > 0 && spouse.age >= 62 && (
                <div className="wizard-field">
                  <label>
                    <input
                      type="checkbox"
                      checked={isSpouseReceivingSS}
                      onChange={(e) => {
                        setIsSpouseReceivingSS(e.target.checked);
                        if (e.target.checked) {
                          setSpouse({
                            ...spouse,
                            social_security_start_age: spouse.age,
                          });
                        }
                      }}
                      style={{ marginRight: "8px" }}
                    />
                    Already receiving Social Security
                  </label>
                </div>
              )}
              {spouse.social_security_monthly > 0 && !isSpouseReceivingSS && (
                <div className="wizard-field">
                  <label>Planned Start Age</label>
                  <select
                    value={spouse.social_security_start_age}
                    onChange={(e) =>
                      setSpouse({
                        ...spouse,
                        social_security_start_age: Number(e.target.value),
                      })
                    }
                  >
                    <option value={62}>62 (reduced ~30%)</option>
                    <option value={63}>63 (reduced ~25%)</option>
                    <option value={64}>64 (reduced ~20%)</option>
                    <option value={65}>65 (reduced ~13%)</option>
                    <option value={66}>66 (reduced ~7%)</option>
                    <option value={67}>67 (full retirement age)</option>
                    <option value={68}>68 (8% bonus)</option>
                    <option value={69}>69 (16% bonus)</option>
                    <option value={70}>70 (24% bonus)</option>
                  </select>
                </div>
              )}
              <div className="wizard-field">
                <label>Spouse Annual Pension</label>
                <div className="wizard-field-prefix">
                  <span>$</span>
                  <input
                    type="number"
                    value={spouse.pension_annual}
                    onChange={(e) =>
                      setSpouse({
                        ...spouse,
                        pension_annual: Number(e.target.value),
                      })
                    }
                    min={0}
                    step={1000}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      ),
    },
    {
      id: "annuity",
      title: "Annuity",
      subtitle: "Compare your portfolio to a guaranteed annuity",
      optional: true,
      content: (
        <div>
          <label className="wizard-checkbox">
            <input
              type="checkbox"
              checked={params.has_annuity}
              onChange={(e) => updateParam("has_annuity", e.target.checked)}
            />
            <div className="wizard-checkbox-content">
              <div className="wizard-checkbox-label">Compare to Annuity</div>
              <div className="wizard-checkbox-hint">
                See if buying an annuity might be better than investing
              </div>
            </div>
          </label>

          {params.has_annuity && (
            <div style={{ marginTop: "1.5rem" }}>
              <div className="wizard-field">
                <label>Monthly Annuity Payment</label>
                <div className="wizard-field-prefix">
                  <span>$</span>
                  <input
                    type="number"
                    value={annuity.monthly_payment}
                    onChange={(e) =>
                      setAnnuity({
                        ...annuity,
                        monthly_payment: Number(e.target.value),
                      })
                    }
                    min={100}
                    step={100}
                  />
                </div>
                <div className="wizard-field-hint">
                  Get a quote from an insurance company
                </div>
              </div>
              <div className="wizard-field">
                <label>Annuity Type</label>
                <select
                  value={annuity.annuity_type}
                  onChange={(e) =>
                    setAnnuity({
                      ...annuity,
                      annuity_type: e.target
                        .value as AnnuityInput["annuity_type"],
                    })
                  }
                >
                  <option value="life_with_guarantee">
                    Life with Guarantee
                  </option>
                  <option value="fixed_period">Fixed Period</option>
                  <option value="life_only">Life Only</option>
                </select>
              </div>
              {annuity.annuity_type !== "life_only" && (
                <div className="wizard-field">
                  <label>Guarantee Period (years)</label>
                  <input
                    type="number"
                    value={annuity.guarantee_years}
                    onChange={(e) =>
                      setAnnuity({
                        ...annuity,
                        guarantee_years: Number(e.target.value),
                      })
                    }
                    min={1}
                    max={30}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      ),
    },
    {
      id: "review",
      title: "Review",
      subtitle: "Check your inputs and run the simulation",
      content: (
        <div>
          <div className="wizard-review">
            <div className="wizard-review-section">
              <div className="wizard-review-title">About You</div>
              <div className="wizard-review-row">
                <span className="wizard-review-label">Age Range</span>
                <span className="wizard-review-value">
                  {params.current_age} to {params.max_age}
                </span>
              </div>
              <div className="wizard-review-row">
                <span className="wizard-review-label">Location</span>
                <span className="wizard-review-value">
                  {params.state}, {params.filing_status.replace(/_/g, " ")}
                </span>
              </div>
            </div>

            <div className="wizard-review-section">
              <div className="wizard-review-title">Finances</div>
              {portfolioMode === "detailed" && holdings.length > 0 ? (
                <>
                  <div className="wizard-review-row">
                    <span className="wizard-review-label">Portfolio</span>
                    <span className="wizard-review-value">
                      {formatCurrency(holdings.reduce((sum, h) => sum + h.balance, 0))}
                    </span>
                  </div>
                  <div className="wizard-review-row" style={{ fontSize: "0.875rem", color: "#6b7280" }}>
                    <span className="wizard-review-label">&nbsp;&nbsp;Holdings</span>
                    <span className="wizard-review-value">{holdings.length} accounts</span>
                  </div>
                </>
              ) : (
                <div className="wizard-review-row">
                  <span className="wizard-review-label">Portfolio</span>
                  <span className="wizard-review-value">
                    {formatCurrency(params.initial_capital ?? 0)}
                  </span>
                </div>
              )}
              <div className="wizard-review-row">
                <span className="wizard-review-label">Annual Spending</span>
                <span className="wizard-review-value">
                  {formatCurrency(params.annual_spending)}
                </span>
              </div>
              <div className="wizard-review-row">
                <span className="wizard-review-label">Social Security</span>
                <span className="wizard-review-value">
                  ${params.social_security_monthly.toLocaleString()}/mo @ age {params.social_security_start_age}
                </span>
              </div>
              {params.pension_annual > 0 && (
                <div className="wizard-review-row">
                  <span className="wizard-review-label">Pension</span>
                  <span className="wizard-review-value">
                    {formatCurrency(params.pension_annual)}/yr
                  </span>
                </div>
              )}
            </div>

            {params.has_spouse && (
              <div className="wizard-review-section">
                <div className="wizard-review-title">Spouse</div>
                <div className="wizard-review-row">
                  <span className="wizard-review-label">Age</span>
                  <span className="wizard-review-value">{spouse.age}</span>
                </div>
                <div className="wizard-review-row">
                  <span className="wizard-review-label">Social Security</span>
                  <span className="wizard-review-value">
                    ${spouse.social_security_monthly.toLocaleString()}/mo
                  </span>
                </div>
              </div>
            )}

            {params.has_annuity && (
              <div className="wizard-review-section">
                <div className="wizard-review-title">Annuity Comparison</div>
                <div className="wizard-review-row">
                  <span className="wizard-review-label">Monthly Payment</span>
                  <span className="wizard-review-value">
                    ${annuity.monthly_payment.toLocaleString()}
                  </span>
                </div>
              </div>
            )}
          </div>

          {error ? (() => {
            const errorInfo = getErrorInfo(error);
            return (
              <div className="error-banner" style={{ marginTop: "1rem" }}>
                <strong>{errorInfo.title}:</strong> {errorInfo.message}
                {errorInfo.field && (
                  <span style={{ display: "block", marginTop: "0.5rem", fontStyle: "italic" }}>
                    Check: {errorInfo.field.replace(/_/g, " ")}
                  </span>
                )}
              </div>
            );
          })() : null}
        </div>
      ),
    },
  ];

  // What-if scenario helpers
  const runWhatIfScenario = (modifier: Partial<SimulationInput>) => {
    setParams((prev) => ({ ...prev, ...modifier }));
    setShowWizard(true);
  };

  // Error state view - displays user-friendly error with retry option
  const renderErrorState = () => {
    const errorInfo = getErrorInfo(error);

    return (
      <div className="error-state">
        <div className="error-state-card">
          <div className="error-state-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h2 className="error-state-title">{errorInfo.title}</h2>
          <p className="error-state-message">{errorInfo.message}</p>

          {errorInfo.technical && errorInfo.technical !== errorInfo.message && (
            <div className="error-state-details">
              <div className="error-state-details-label">Technical Details</div>
              <p className="error-state-details-text">{errorInfo.technical}</p>
            </div>
          )}

          <div className="error-state-suggestion">
            <strong>What to do:</strong> {errorInfo.suggestion}
          </div>

          <div className="error-state-actions">
            <button
              className="error-state-btn-primary"
              onClick={() => {
                setError(null);
                handleSimulate();
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="1 4 1 10 7 10" />
                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
              </svg>
              Try Again
            </button>
            <button
              className="error-state-btn-secondary"
              onClick={() => {
                setError(null);
                setShowWizard(true);
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
              Edit Inputs
            </button>
          </div>
        </div>
      </div>
    );
  };

  // Results view
  const renderResults = () => {
    const interpretation = getSuccessRateInterpretation(result!.success_rate);

    return (
    <div className="results-view">
      <div className="results-actions">
        <button className="back-to-wizard" onClick={() => setShowWizard(true)}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Edit Inputs
        </button>
        <button className="copy-link-btn" onClick={copyLinkToClipboard}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
          {linkCopied ? "Link Copied!" : "Copy Link"}
        </button>
      </div>

      {/* Success interpretation banner */}
      <div className="success-interpretation" style={{ borderColor: interpretation.color }}>
        <div className="interpretation-header">
          <span className="interpretation-label" style={{ color: interpretation.color }}>
            {interpretation.label}
          </span>
          <span className="interpretation-rate" style={{ color: interpretation.color }}>
            {formatPercent(result!.success_rate)} success rate
          </span>
        </div>
        <p className="interpretation-text">{interpretation.description}</p>
      </div>

      {/* Key metrics */}
      <div className="metrics-grid">
        <div
          className="metric-card primary"
          style={{ borderColor: successColor }}
        >
          <div className="metric-label">Success Rate</div>
          <div className="metric-value" style={{ color: successColor }}>
            {formatPercent(result!.success_rate)}
          </div>
          <div className="metric-desc">
            Probability of not running out of money
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Initial Withdrawal Rate</div>
          <div className="metric-value">
            {result!.initial_withdrawal_rate.toFixed(1)}%
          </div>
          <div className="metric-desc">From portfolio in year 1</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Median Final Value</div>
          <div className="metric-value">
            {formatCurrency(result!.median_final_value)}
          </div>
          <div className="metric-desc">
            50th percentile at age {params.max_age}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">10-Year Depletion Risk</div>
          <div className="metric-value">
            {formatPercent(result!.prob_10_year_failure)}
          </div>
          <div className="metric-desc">
            Probability of depletion within 10 years
          </div>
        </div>
      </div>

      {/* Portfolio chart */}
      <div className="chart-container portfolio-chart">
        <h3>Portfolio Value Over Time</h3>
        <p className="chart-hint">Click on the chart to see year details. Click legend items to toggle visibility.</p>
        <Plot
          data={[
            // 95th percentile - top line of outer band
            {
              x: ages,
              y: result!.percentile_paths.p95,
              type: "scatter",
              mode: "lines",
              line: { color: "rgba(217, 119, 6, 0.4)", width: 1, dash: "dot" },
              name: "95th Percentile",
              legendgroup: "outer",
              hoverinfo: "skip",
            },
            // 5th percentile - creates outer band fill
            {
              x: ages,
              y: result!.percentile_paths.p5,
              type: "scatter",
              mode: "lines",
              fill: "tonexty",
              fillcolor: "rgba(217, 119, 6, 0.08)",
              line: { color: "rgba(217, 119, 6, 0.4)", width: 1, dash: "dot" },
              name: "5th Percentile",
              legendgroup: "outer",
              hoverinfo: "skip",
            },
            // 75th percentile - top line of inner band
            {
              x: ages,
              y: result!.percentile_paths.p75,
              type: "scatter",
              mode: "lines",
              line: { color: "rgba(217, 119, 6, 0.6)", width: 1.5 },
              name: "75th Percentile",
              legendgroup: "inner",
              hoverinfo: "skip",
            },
            // 25th percentile - creates inner band fill
            {
              x: ages,
              y: result!.percentile_paths.p25,
              type: "scatter",
              mode: "lines",
              fill: "tonexty",
              fillcolor: "rgba(217, 119, 6, 0.15)",
              line: { color: "rgba(217, 119, 6, 0.6)", width: 1.5 },
              name: "25th Percentile",
              legendgroup: "inner",
              hoverinfo: "skip",
            },
            // Median line - most prominent
            {
              x: ages,
              y: result!.percentile_paths.p50,
              type: "scatter",
              mode: "lines",
              line: { color: chartColors.primary, width: 3 },
              name: "Median (50th)",
              hoverinfo: "skip",
            },
            // Invisible trace for unified tooltip showing all percentiles
            {
              x: ages,
              y: result!.percentile_paths.p50,
              type: "scatter",
              mode: "markers",
              marker: { size: 20, color: "transparent" },
              showlegend: false,
              hovertemplate: ages.map((age, i) => {
                const year = i;
                const p95 = result!.percentile_paths.p95[i];
                const p75 = result!.percentile_paths.p75[i];
                const p50 = result!.percentile_paths.p50[i];
                const p25 = result!.percentile_paths.p25[i];
                const p5 = result!.percentile_paths.p5[i];
                return `<b>Age ${age}</b> (Year ${year + 1})<br>` +
                  `<span style="color:#9a3412">95th:</span> ${formatCurrency(p95)}<br>` +
                  `<span style="color:#c2410c">75th:</span> ${formatCurrency(p75)}<br>` +
                  `<span style="color:#d97706"><b>Median:</b></span> <b>${formatCurrency(p50)}</b><br>` +
                  `<span style="color:#c2410c">25th:</span> ${formatCurrency(p25)}<br>` +
                  `<span style="color:#9a3412">5th:</span> ${formatCurrency(p5)}` +
                  `<extra></extra>`;
              }),
            },
          ]}
          layout={{
            autosize: true,
            height: 420,
            margin: { l: 80, r: 40, t: 40, b: 60 },
            font: { family: "Inter, system-ui, sans-serif", size: 12 },
            xaxis: {
              title: { text: "Age", font: { family: "Inter, system-ui, sans-serif", size: 14 } },
              gridcolor: colors.gray200,
              tickfont: { family: "Inter, system-ui, sans-serif", size: 12 },
              showgrid: true,
              zeroline: false,
            },
            yaxis: {
              title: { text: "Portfolio Value", font: { family: "Inter, system-ui, sans-serif", size: 14 } },
              gridcolor: colors.gray200,
              tickformat: "$~s",
              tickfont: { family: "Inter, system-ui, sans-serif", size: 12 },
              rangemode: "tozero",
              showgrid: true,
              zeroline: true,
              zerolinecolor: colors.gray300,
            },
            legend: {
              x: 0.5,
              y: 1.15,
              xanchor: "center",
              orientation: "h",
              font: { family: "Inter, system-ui, sans-serif", size: 11 },
              bgcolor: "rgba(255,255,255,0.9)",
              bordercolor: colors.gray200,
              borderwidth: 1,
              itemclick: "toggle",
              itemdoubleclick: "toggleothers",
            },
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            hovermode: "x unified",
            hoverlabel: {
              bgcolor: "white",
              bordercolor: colors.gray300,
              font: { family: "Inter, system-ui, sans-serif", size: 13, color: colors.gray800 },
              align: "left",
            },
            // Show vertical line for selected year
            shapes: selectedYearIndex !== null ? [
              {
                type: "line",
                x0: ages[selectedYearIndex],
                x1: ages[selectedYearIndex],
                y0: 0,
                y1: 1,
                yref: "paper",
                line: { color: chartColors.primary, width: 2, dash: "dash" },
              },
            ] : [],
          }}
          config={{ responsive: true, displayModeBar: false, scrollZoom: false }}
          style={{ width: "100%" }}
          onClick={(event) => {
            if (event.points && event.points.length > 0) {
              const pointIndex = event.points[0].pointIndex;
              if (typeof pointIndex === 'number' && pointIndex < result!.year_breakdown.length) {
                setSelectedYearIndex(pointIndex);
              }
            }
          }}
        />
      </div>

      {/* Year detail panel */}
      {selectedYearIndex !== null && result!.year_breakdown[selectedYearIndex] && (() => {
        const year = result!.year_breakdown[selectedYearIndex];
        return (
          <div className="year-detail-panel">
            <div className="year-detail-header">
              <h3>Age {year.age} Details</h3>
              <button
                className="close-btn"
                onClick={() => setSelectedYearIndex(null)}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <div className="year-detail-grid">
              <div className="year-detail-section">
                <h4>Portfolio</h4>
                <div className="detail-row">
                  <span>Start of Year</span>
                  <span>{formatCurrency(year.portfolio_start)}</span>
                </div>
                <div className="detail-row">
                  <span>End of Year</span>
                  <span>{formatCurrency(year.portfolio_end)}</span>
                </div>
                <div className="detail-row">
                  <span>Return</span>
                  <span style={{ color: year.portfolio_return >= 0 ? '#10b981' : '#ef4444' }}>
                    {(year.portfolio_return * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
              <div className="year-detail-section">
                <h4>Income</h4>
                {year.employment_income > 0 && (
                  <div className="detail-row">
                    <span>Employment</span>
                    <span>{formatCurrency(year.employment_income)}</span>
                  </div>
                )}
                {year.social_security > 0 && (
                  <div className="detail-row">
                    <span>Social Security</span>
                    <span>{formatCurrency(year.social_security)}</span>
                  </div>
                )}
                {year.pension > 0 && (
                  <div className="detail-row">
                    <span>Pension</span>
                    <span>{formatCurrency(year.pension)}</span>
                  </div>
                )}
                {year.dividends > 0 && (
                  <div className="detail-row">
                    <span>Dividends</span>
                    <span>{formatCurrency(year.dividends)}</span>
                  </div>
                )}
                {year.annuity > 0 && (
                  <div className="detail-row">
                    <span>Annuity</span>
                    <span>{formatCurrency(year.annuity)}</span>
                  </div>
                )}
                <div className="detail-row total">
                  <span>Total Income</span>
                  <span>{formatCurrency(year.total_income)}</span>
                </div>
              </div>
              <div className="year-detail-section">
                <h4>Withdrawals & Taxes</h4>
                <div className="detail-row">
                  <span>Withdrawal</span>
                  <span>{formatCurrency(year.withdrawal)}</span>
                </div>
                <div className="detail-row">
                  <span>Federal Tax</span>
                  <span>{formatCurrency(year.federal_tax)}</span>
                </div>
                <div className="detail-row">
                  <span>State Tax</span>
                  <span>{formatCurrency(year.state_tax)}</span>
                </div>
                <div className="detail-row total">
                  <span>Total Tax</span>
                  <span>{formatCurrency(year.total_tax)}</span>
                </div>
                <div className="detail-row">
                  <span>Effective Rate</span>
                  <span>{(year.effective_tax_rate * 100).toFixed(1)}%</span>
                </div>
              </div>
            </div>
            <div className="year-nav">
              <button
                disabled={selectedYearIndex === 0}
                onClick={() => setSelectedYearIndex(prev => prev !== null ? Math.max(0, prev - 1) : null)}
              >
                ← Previous Year
              </button>
              <button
                disabled={selectedYearIndex === result!.year_breakdown.length - 1}
                onClick={() => setSelectedYearIndex(prev => prev !== null ? Math.min(result!.year_breakdown.length - 1, prev + 1) : null)}
              >
                Next Year →
              </button>
            </div>
          </div>
        );
      })()}

      {/* Summary table */}
      <div className="summary-section">
        <h3>Outcome Distribution</h3>
        <table className="summary-table">
          <thead>
            <tr>
              <th>Percentile</th>
              <th>Final Portfolio</th>
              <th>Interpretation</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>5th (conservative)</td>
              <td>{formatCurrency(result!.percentiles.p5)}</td>
              <td>95% of outcomes exceed this</td>
            </tr>
            <tr>
              <td>25th</td>
              <td>{formatCurrency(result!.percentiles.p25)}</td>
              <td>75% of outcomes are better</td>
            </tr>
            <tr className="highlight">
              <td>50th (median)</td>
              <td>{formatCurrency(result!.percentiles.p50)}</td>
              <td>The "typical" outcome</td>
            </tr>
            <tr>
              <td>75th</td>
              <td>{formatCurrency(result!.percentiles.p75)}</td>
              <td>25% of outcomes are better</td>
            </tr>
            <tr>
              <td>95th (optimistic)</td>
              <td>{formatCurrency(result!.percentiles.p95)}</td>
              <td>Only 5% of outcomes exceed this</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Taxes info */}
      <div className="summary-section">
        <h3>Tax Summary (Median)</h3>
        <div className="tax-info">
          <div className="tax-row">
            <span>Total Withdrawals</span>
            <span>{formatCurrency(result!.total_withdrawn_median)}</span>
          </div>
          <div className="tax-row">
            <span>Total Taxes Paid</span>
            <span>{formatCurrency(result!.total_taxes_median)}</span>
          </div>
          <div className="tax-row">
            <span>Net After-Tax Income</span>
            <span>
              {formatCurrency(
                result!.total_withdrawn_median - result!.total_taxes_median
              )}
            </span>
          </div>
        </div>
        <p className="tax-note">
          Tax calculations powered by PolicyEngine-US for accurate federal and{" "}
          {params.state} state taxes.
        </p>
      </div>

      {/* Year-by-Year Breakdown */}
      {result!.year_breakdown && result!.year_breakdown.length > 0 && (
        <div className="summary-section year-breakdown">
          <details>
            <summary>
              <h3 style={{ display: "inline" }}>Year-by-Year Breakdown (Median)</h3>
              <span className="expand-hint">Click to expand</span>
            </summary>
            <div className="breakdown-table-wrapper">
              <table className="breakdown-table">
                <thead>
                  <tr>
                    <th>Age</th>
                    <th>Portfolio Start</th>
                    <th>Income</th>
                    <th>Withdrawal</th>
                    <th>Taxes</th>
                    <th>Tax Rate</th>
                    <th>Portfolio End</th>
                  </tr>
                </thead>
                <tbody>
                  {result!.year_breakdown.map((year) => (
                    <tr key={year.year_index}>
                      <td>{year.age}</td>
                      <td>{formatCurrency(year.portfolio_start)}</td>
                      <td title={`Employment: ${formatCurrency(year.employment_income)}, SS: ${formatCurrency(year.social_security)}, Pension: ${formatCurrency(year.pension)}, Dividends: ${formatCurrency(year.dividends)}`}>
                        {formatCurrency(year.total_income)}
                      </td>
                      <td>{formatCurrency(year.withdrawal)}</td>
                      <td title={`Federal: ${formatCurrency(year.federal_tax)}, State: ${formatCurrency(year.state_tax)}`}>
                        {formatCurrency(year.total_tax)}
                      </td>
                      <td>{(year.effective_tax_rate * 100).toFixed(1)}%</td>
                      <td
                        style={{
                          color: year.portfolio_end <= 0 ? "#ef4444" : "inherit",
                          fontWeight: year.portfolio_end <= 0 ? 600 : 400,
                        }}
                      >
                        {formatCurrency(year.portfolio_end)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      )}

      {/* Annuity Comparison Results */}
      {annuityResult && (
        <div className="summary-section annuity-comparison">
          <h3>Annuity Comparison</h3>
          <div className="comparison-grid">
            <div className="comparison-card">
              <div className="comparison-label">Annuity Guaranteed Total</div>
              <div className="comparison-value">
                {formatCurrency(annuityResult.annuity_total_guaranteed)}
              </div>
              <div className="comparison-desc">
                Over {annuity.guarantee_years} year guarantee period
              </div>
            </div>
            <div className="comparison-card">
              <div className="comparison-label">Portfolio Median Total</div>
              <div className="comparison-value">
                {formatCurrency(annuityResult.simulation_median_total_income)}
              </div>
              <div className="comparison-desc">
                Median total income from portfolio
              </div>
            </div>
            <div className="comparison-card highlight">
              <div className="comparison-label">Portfolio Beats Annuity</div>
              <div
                className="comparison-value"
                style={{
                  color:
                    annuityResult.probability_simulation_beats_annuity >= 0.6
                      ? "#10b981"
                      : annuityResult.probability_simulation_beats_annuity >=
                          0.4
                        ? "#f59e0b"
                        : "#ef4444",
                }}
              >
                {formatPercent(
                  annuityResult.probability_simulation_beats_annuity
                )}
              </div>
              <div className="comparison-desc">Probability</div>
            </div>
          </div>
          <div className="recommendation">
            <strong>Recommendation:</strong> {annuityResult.recommendation}
          </div>
        </div>
      )}

      {/* State Comparison */}
      <div className="summary-section state-comparison">
        <h3>Compare States</h3>
        <p className="section-desc">
          See how relocating could affect your taxes and outcomes.
        </p>

        {!stateComparisonResult && !isComparingStates && (
          <div className="state-picker">
            <div className="state-picker-row">
              <button
                className="btn-secondary"
                onClick={() => handleCompareStates()}
                disabled={isComparingStates}
              >
                Compare to No-Income-Tax States
              </button>
            </div>

            <div className="state-picker-divider">or select specific states</div>

            <div className="state-chips">
              {US_STATES.filter(s => s !== params.state).map(state => (
                <button
                  key={state}
                  className={`state-chip ${selectedCompareStates.includes(state) ? 'selected' : ''} ${NO_TAX_STATES.includes(state) ? 'no-tax' : ''}`}
                  onClick={() => toggleCompareState(state)}
                  disabled={!selectedCompareStates.includes(state) && selectedCompareStates.length >= 5}
                >
                  {state}
                </button>
              ))}
            </div>

            {selectedCompareStates.length > 0 && (
              <button
                className="btn-primary"
                onClick={() => handleCompareStates(selectedCompareStates)}
                disabled={isComparingStates}
              >
                Compare {selectedCompareStates.length} State{selectedCompareStates.length > 1 ? 's' : ''}
              </button>
            )}
          </div>
        )}

        {isComparingStates && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            Comparing states...
          </div>
        )}

        {stateComparisonResult && (
          <div className="state-comparison-results">
            <table className="state-table">
              <thead>
                <tr>
                  <th>State</th>
                  <th>Total Taxes</th>
                  <th>Tax Savings</th>
                  <th>Success Rate</th>
                </tr>
              </thead>
              <tbody>
                {stateComparisonResult.results
                  .sort((a, b) =>
                    stateComparisonResult.tax_savings_vs_base[b.state] -
                    stateComparisonResult.tax_savings_vs_base[a.state]
                  )
                  .map((r) => (
                  <tr key={r.state} className={r.state === params.state ? "current-state" : ""}>
                    <td>
                      {r.state}
                      {r.state === params.state && " (current)"}
                    </td>
                    <td>{formatCurrency(r.total_taxes_median)}</td>
                    <td
                      style={{
                        color: stateComparisonResult.tax_savings_vs_base[r.state] > 0
                          ? "#10b981"
                          : stateComparisonResult.tax_savings_vs_base[r.state] < 0
                            ? "#ef4444"
                            : "inherit",
                        fontWeight: stateComparisonResult.tax_savings_vs_base[r.state] !== 0 ? 600 : 400,
                      }}
                    >
                      {stateComparisonResult.tax_savings_vs_base[r.state] > 0 && "+"}
                      {formatCurrency(stateComparisonResult.tax_savings_vs_base[r.state])}
                    </td>
                    <td>{formatPercent(r.success_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="tax-note">
              Tax savings show lifetime difference compared to {params.state}.
              Positive values mean you save money by relocating.
            </p>
            <button
              className="btn-secondary"
              onClick={() => {
                setStateComparisonResult(null);
                setSelectedCompareStates([]);
              }}
              style={{ marginTop: '1rem' }}
            >
              Compare Different States
            </button>
          </div>
        )}
      </div>

      {/* Social Security Timing Comparison */}
      <div className="summary-section ss-timing">
        <h3>When Should You Claim Social Security?</h3>
        <p className="section-desc">
          Compare how different claiming ages affect your lifetime benefits and portfolio.
        </p>

        {!ssTimingResult && !isComparingSSTiming && (
          <div className="ss-timing-inputs">
            <div className="ss-timing-row">
              <div className="wizard-field">
                <label>Your Birth Year</label>
                <input
                  type="number"
                  value={birthYear}
                  onChange={(e) => setBirthYear(Number(e.target.value))}
                  min={1930}
                  max={2000}
                />
                <div className="wizard-field-hint">
                  Used to determine your Full Retirement Age
                </div>
              </div>
              <div className="wizard-field">
                <label>Estimated Benefit at FRA (PIA)</label>
                <div className="wizard-field-prefix">
                  <span>$</span>
                  <input
                    type="number"
                    value={piaMonthly}
                    onChange={(e) => setPiaMonthly(Number(e.target.value))}
                    min={0}
                    max={10000}
                    step={100}
                  />
                </div>
                <div className="wizard-field-hint">
                  Your benefit if you claim at full retirement age (check ssa.gov/myaccount)
                </div>
              </div>
            </div>
            <button
              className="btn-primary"
              onClick={handleCompareSSTimings}
              disabled={isComparingSSTiming || piaMonthly <= 0}
            >
              Compare Claiming Ages
            </button>
          </div>
        )}

        {isComparingSSTiming && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            Comparing claiming ages (this takes a few minutes)...
          </div>
        )}

        {ssTimingResult && (
          <div className="ss-timing-results">
            <div className="ss-timing-summary">
              <div className="ss-timing-fra">
                <span className="label">Your Full Retirement Age:</span>
                <span className="value">
                  {Math.floor(ssTimingResult.full_retirement_age)} years
                  {ssTimingResult.full_retirement_age % 1 > 0 &&
                    ` ${Math.round((ssTimingResult.full_retirement_age % 1) * 12)} months`}
                </span>
              </div>
              <div className="ss-timing-optimal">
                <span className="label">Optimal for success rate:</span>
                <span className="value highlight">
                  Claim at age {ssTimingResult.optimal_claiming_age}
                </span>
              </div>
              {ssTimingResult.optimal_for_longevity !== ssTimingResult.optimal_claiming_age && (
                <div className="ss-timing-optimal">
                  <span className="label">Optimal if you live long:</span>
                  <span className="value">
                    Claim at age {ssTimingResult.optimal_for_longevity}
                  </span>
                </div>
              )}
            </div>

            <table className="ss-timing-table">
              <thead>
                <tr>
                  <th>Claiming Age</th>
                  <th>Monthly Benefit</th>
                  <th>Adjustment</th>
                  <th>Success Rate</th>
                  <th>Lifetime SS Income</th>
                  <th>Breakeven vs 62</th>
                </tr>
              </thead>
              <tbody>
                {ssTimingResult.results.map((r) => (
                  <tr
                    key={r.claiming_age}
                    className={
                      r.claiming_age === ssTimingResult.optimal_claiming_age
                        ? "optimal"
                        : r.claiming_age === Math.round(ssTimingResult.full_retirement_age)
                          ? "fra"
                          : ""
                    }
                  >
                    <td>
                      {r.claiming_age}
                      {r.claiming_age === Math.round(ssTimingResult.full_retirement_age) && (
                        <span className="fra-badge">FRA</span>
                      )}
                      {r.claiming_age === ssTimingResult.optimal_claiming_age && (
                        <span className="optimal-badge">Best</span>
                      )}
                    </td>
                    <td>${r.monthly_benefit.toLocaleString()}/mo</td>
                    <td
                      style={{
                        color:
                          r.adjustment_factor < 1
                            ? "#ef4444"
                            : r.adjustment_factor > 1
                              ? "#10b981"
                              : "inherit",
                      }}
                    >
                      {r.adjustment_factor < 1
                        ? `-${((1 - r.adjustment_factor) * 100).toFixed(0)}%`
                        : r.adjustment_factor > 1
                          ? `+${((r.adjustment_factor - 1) * 100).toFixed(0)}%`
                          : "—"}
                    </td>
                    <td>{formatPercent(r.success_rate)}</td>
                    <td>{formatCurrency(r.total_ss_income_median)}</td>
                    <td>
                      {r.breakeven_vs_62
                        ? `Age ${r.breakeven_vs_62}`
                        : r.claiming_age === 62
                          ? "—"
                          : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="tax-note">
              Early claiming (before FRA) permanently reduces your benefit. Delayed claiming (after FRA, up to 70)
              permanently increases it by 8% per year. Breakeven shows when total cumulative benefits from waiting exceed claiming at 62.
            </p>

            <button
              className="btn-secondary"
              onClick={() => setSSTimingResult(null)}
              style={{ marginTop: "1rem" }}
            >
              Change Assumptions
            </button>
          </div>
        )}
      </div>

      {/* Asset Allocation Comparison */}
      <div className="summary-section allocation-comparison">
        <h3>How Does Asset Allocation Affect Your Plan?</h3>
        <p className="section-description">
          Compare different stock/bond mixes to find the right balance of growth and safety for your situation.
        </p>

        {!allocationResult && (
          <button
            className="btn-primary"
            onClick={handleCompareAllocations}
            disabled={isComparingAllocations}
          >
            {isComparingAllocations ? "Comparing..." : "Compare Allocations"}
          </button>
        )}

        {allocationResult && (
          <div className="allocation-results">
            <div className="allocation-summary">
              <div className="allocation-optimal">
                <span className="allocation-optimal-label">Optimal for Success</span>
                <span className="allocation-optimal-value">
                  {Math.round(allocationResult.optimal_for_success * 100)}% Stocks
                </span>
              </div>
              {allocationResult.optimal_for_safety !== allocationResult.optimal_for_success && (
                <div className="allocation-optimal">
                  <span className="allocation-optimal-label">Optimal for Safety</span>
                  <span className="allocation-optimal-value">
                    {Math.round(allocationResult.optimal_for_safety * 100)}% Stocks
                  </span>
                </div>
              )}
            </div>

            <table className="allocation-table">
              <thead>
                <tr>
                  <th>Allocation</th>
                  <th>Success Rate</th>
                  <th>Median Final</th>
                  <th>Worst Case (5th)</th>
                  <th>Best Case (95th)</th>
                  <th>Volatility</th>
                </tr>
              </thead>
              <tbody>
                {allocationResult.results.map((r) => (
                  <tr
                    key={r.stock_allocation}
                    className={
                      r.stock_allocation === allocationResult.optimal_for_success
                        ? "optimal-row"
                        : ""
                    }
                  >
                    <td>
                      {Math.round(r.stock_allocation * 100)}% / {Math.round(r.bond_allocation * 100)}%
                      {r.stock_allocation === allocationResult.optimal_for_success && (
                        <span className="optimal-badge">Best</span>
                      )}
                    </td>
                    <td
                      style={{
                        color:
                          r.success_rate >= 0.9
                            ? "#10b981"
                            : r.success_rate >= 0.8
                              ? "#84cc16"
                              : r.success_rate >= 0.7
                                ? "#eab308"
                                : "#ef4444",
                      }}
                    >
                      {formatPercent(r.success_rate)}
                    </td>
                    <td>{formatCurrency(r.median_final_value)}</td>
                    <td style={{ color: r.percentile_5_final_value <= 0 ? "#ef4444" : "inherit" }}>
                      {formatCurrency(r.percentile_5_final_value)}
                    </td>
                    <td>{formatCurrency(r.percentile_95_final_value)}</td>
                    <td>{(r.volatility * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="allocation-recommendation">
              {allocationResult.recommendation}
            </p>

            <p className="tax-note">
              Stocks historically offer higher returns but more volatility. Bonds provide stability but lower growth.
              A balanced allocation can reduce risk while maintaining reasonable growth potential.
            </p>

            <button
              className="btn-secondary"
              onClick={() => setAllocationResult(null)}
              style={{ marginTop: "1rem" }}
            >
              Hide Results
            </button>
          </div>
        )}
      </div>

      {result!.median_depletion_age && (
        <div className="warning-banner">
          <strong>Warning:</strong> In scenarios where the portfolio is
          depleted, the median depletion occurs at age{" "}
          {result!.median_depletion_age}. Consider reducing spending or
          increasing savings.
        </div>
      )}

      {/* What-if scenarios */}
      <div className="what-if-section">
        <h3>Explore Scenarios</h3>
        <p className="what-if-description">
          See how changes affect your success rate
        </p>
        <div className="what-if-buttons">
          <button
            className="what-if-btn"
            onClick={() =>
              runWhatIfScenario({
                annual_spending: Math.round(params.annual_spending * 0.9),
              })
            }
          >
            <span className="what-if-icon">↓</span>
            <span className="what-if-label">Spend 10% less</span>
            <span className="what-if-value">
              {formatCurrency(Math.round(params.annual_spending * 0.9))}/yr
            </span>
          </button>
          <button
            className="what-if-btn"
            onClick={() =>
              runWhatIfScenario({
                annual_spending: Math.round(params.annual_spending * 1.1),
              })
            }
          >
            <span className="what-if-icon">↑</span>
            <span className="what-if-label">Spend 10% more</span>
            <span className="what-if-value">
              {formatCurrency(Math.round(params.annual_spending * 1.1))}/yr
            </span>
          </button>
          <button
            className="what-if-btn"
            onClick={() =>
              runWhatIfScenario({
                initial_capital: Math.round((params.initial_capital ?? 0) * 1.1),
              })
            }
          >
            <span className="what-if-icon">💰</span>
            <span className="what-if-label">10% more savings</span>
            <span className="what-if-value">
              {formatCurrency(Math.round((params.initial_capital ?? 0) * 1.1))}
            </span>
          </button>
          {params.social_security_start_age < 70 && (
            <button
              className="what-if-btn"
              onClick={() =>
                runWhatIfScenario({
                  social_security_start_age: 70,
                })
              }
            >
              <span className="what-if-icon">🕐</span>
              <span className="what-if-label">Delay SS to 70</span>
              <span className="what-if-value">+24% benefit</span>
            </button>
          )}
        </div>
      </div>

      {/* Next Steps CTA */}
      <div className="summary-section next-steps">
        <h3>Take the Next Step</h3>
        <div className="cta-grid">
          <a
            href="https://www.nerdwallet.com/best/investing/financial-advisors-for-retirement"
            target="_blank"
            rel="noopener noreferrer"
            className="cta-card"
          >
            <div className="cta-icon">👤</div>
            <div className="cta-content">
              <div className="cta-title">Talk to a Fiduciary Advisor</div>
              <div className="cta-desc">
                Get personalized advice from a fee-only advisor who works in your interest.
              </div>
            </div>
            <span className="cta-arrow">→</span>
          </a>
          <a
            href="https://investor.vanguard.com/investment-products/index-funds"
            target="_blank"
            rel="noopener noreferrer"
            className="cta-card"
          >
            <div className="cta-icon">📈</div>
            <div className="cta-content">
              <div className="cta-title">Low-Cost Index Funds</div>
              <div className="cta-desc">
                Simple, diversified investing with minimal fees.
              </div>
            </div>
            <span className="cta-arrow">→</span>
          </a>
          {params.has_annuity && (
            <a
              href="https://www.immediateannuities.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="cta-card"
            >
              <div className="cta-icon">🛡️</div>
              <div className="cta-content">
                <div className="cta-title">Compare Annuity Quotes</div>
                <div className="cta-desc">
                  Get quotes from multiple insurers for guaranteed income.
                </div>
              </div>
              <span className="cta-arrow">→</span>
            </a>
          )}
        </div>
        <p className="cta-disclaimer">
          These are educational resources, not endorsements. We may receive referral fees
          from some links, which helps keep EggNest free.
        </p>
      </div>
    </div>
  );
  };

  // Render persona picker
  const renderPersonaPicker = () => (
    <div className="persona-picker">
      <div className="persona-header">
        <h2>See your financial outlook in seconds</h2>
        <p>Choose a profile similar to yours, or start from scratch</p>
      </div>

      <div className="persona-grid">
        {EXAMPLE_PERSONAS.map((persona) => (
          <div key={persona.id} className="persona-card">
            <div className="persona-emoji">{persona.emoji}</div>
            <div className="persona-info">
              <h3>{persona.name}</h3>
              <p>{persona.description}</p>
              <div className="persona-stats">
                <span>{formatCurrency(persona.params.initial_capital ?? 0)} saved</span>
                <span>{formatCurrency(persona.params.annual_spending)}/yr spending</span>
              </div>
            </div>
            <div className="persona-actions">
              <button
                className="persona-btn-run"
                onClick={() => loadPersona(persona, true)}
                disabled={isLoading}
              >
                {isLoading ? "Running..." : "Run Simulation"}
              </button>
              <button
                className="persona-btn-customize"
                onClick={() => loadPersona(persona, false)}
              >
                Customize First
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="persona-divider">
        <span>or</span>
      </div>

      <button
        className="persona-start-scratch"
        onClick={() => setShowPersonaPicker(false)}
      >
        Start from scratch with your own numbers
      </button>

      {isLoading && (
        <div className="persona-loading">
          <SimulationProgress
            currentYear={progress.currentYear}
            totalYears={progress.totalYears}
          />
        </div>
      )}
    </div>
  );

  return (
    <div className="simulator">
      {/* Header */}
      <header className="sim-header">
        <a href={HOME_URL} className="sim-logo">
          <img src="/logo.svg" alt="EggNest" height="28" />
        </a>
        <span className="sim-title">Financial Simulator</span>
        <a href="#/life-event" className="sim-nav-link">Tax & Benefits Calculator</a>
      </header>

      <div className="sim-content">
        {showPersonaPicker && showWizard && !result ? (
          renderPersonaPicker()
        ) : showWizard ? (
          <>
            {/* Saved Scenarios Section */}
            <div className="saved-scenarios-section">
              <div className="saved-scenarios-header">
                <div className="saved-scenarios-actions">
                  <button
                    className="btn-save-scenario"
                    onClick={() => setShowSaveDialog(true)}
                    title="Save current scenario"
                  >
                    Save Scenario
                  </button>
                  {savedScenarios.length > 0 && (
                    <select
                      className="scenario-select"
                      value=""
                      onChange={(e) => {
                        const scenario = savedScenarios.find(s => s.name === e.target.value);
                        if (scenario) {
                          loadSavedScenario(scenario);
                        }
                      }}
                    >
                      <option value="" disabled>Load Saved...</option>
                      {savedScenarios.map((s) => (
                        <option key={s.name} value={s.name}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </div>

              {/* Save Dialog */}
              {showSaveDialog && (
                <div className="save-dialog">
                  <input
                    type="text"
                    placeholder="Scenario name..."
                    value={scenarioName}
                    onChange={(e) => setScenarioName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && scenarioName.trim()) {
                        saveScenario(scenarioName.trim());
                      } else if (e.key === "Escape") {
                        setShowSaveDialog(false);
                        setScenarioName("");
                      }
                    }}
                    autoFocus
                  />
                  <button
                    className="btn-confirm-save"
                    onClick={() => scenarioName.trim() && saveScenario(scenarioName.trim())}
                    disabled={!scenarioName.trim()}
                  >
                    Save
                  </button>
                  <button
                    className="btn-cancel-save"
                    onClick={() => {
                      setShowSaveDialog(false);
                      setScenarioName("");
                    }}
                  >
                    Cancel
                  </button>
                </div>
              )}

              {/* Saved Scenarios List (shown when there are saved scenarios) */}
              {savedScenarios.length > 0 && (
                <div className="saved-scenarios-list">
                  {savedScenarios.map((scenario) => (
                    <div key={scenario.name} className="saved-scenario-item">
                      <button
                        className="scenario-load-btn"
                        onClick={() => loadSavedScenario(scenario)}
                      >
                        <span className="scenario-name">{scenario.name}</span>
                        <span className="scenario-date">
                          {new Date(scenario.savedAt).toLocaleDateString()}
                        </span>
                      </button>
                      <button
                        className="scenario-delete-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteScenario(scenario.name);
                        }}
                        title="Delete scenario"
                      >
                        x
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <Wizard
              steps={wizardSteps}
              onComplete={handleSimulate}
              isLoading={isLoading}
              completeButtonText="Run Simulation"
              loadingButtonText="Running simulation..."
              loadingContent={
                <SimulationProgress
                  currentYear={progress.currentYear}
                  totalYears={progress.totalYears}
                />
              }
            />
          </>
        ) : isLoading && !result ? (
          <ResultsSkeleton
            currentYear={progress.currentYear}
            totalYears={progress.totalYears}
          />
        ) : error && !result ? (
          renderErrorState()
        ) : (
          result && renderResults()
        )}
      </div>
    </div>
  );
}
