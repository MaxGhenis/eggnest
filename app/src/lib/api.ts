const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Default timeout for API requests (30 seconds) */
const DEFAULT_TIMEOUT_MS = 30_000;

/** Longer timeout for comparison endpoints that run multiple simulations */
const LONG_TIMEOUT_MS = 120_000;

// ============================================
// Custom error classes for better error handling
// ============================================

/**
 * Base error class for API errors with additional context
 */
export class ApiError extends Error {
  readonly statusCode?: number;
  readonly originalError?: unknown;

  constructor(message: string, statusCode?: number, originalError?: unknown) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.originalError = originalError;
  }
}

/**
 * Network-related errors (offline, DNS failure, timeout, etc.)
 */
export class NetworkError extends ApiError {
  constructor(message: string = "Unable to connect to the server", originalError?: unknown) {
    super(message, undefined, originalError);
    this.name = "NetworkError";
  }
}

/**
 * Request timeout errors
 */
export class TimeoutError extends ApiError {
  constructor(message: string = "Request timed out", originalError?: unknown) {
    super(message, undefined, originalError);
    this.name = "TimeoutError";
  }
}

/**
 * Validation errors from the API (400-level errors with field information)
 */
export class ValidationError extends ApiError {
  readonly field?: string;
  readonly details?: Record<string, unknown>;

  constructor(
    message: string,
    field?: string,
    details?: Record<string, unknown>,
    statusCode?: number
  ) {
    super(message, statusCode);
    this.name = "ValidationError";
    this.field = field;
    this.details = details;
  }
}

/**
 * Server errors (500-level)
 */
export class SimulationError extends ApiError {
  constructor(message: string, statusCode?: number, originalError?: unknown) {
    super(message, statusCode, originalError);
    this.name = "SimulationError";
  }
}

/**
 * Parse error response from API and extract meaningful message
 */
async function parseErrorResponse(response: Response): Promise<{
  message: string;
  field?: string;
  details?: Record<string, unknown>;
}> {
  try {
    const data = await response.json();

    // FastAPI validation error format: { detail: [{ loc: [...], msg: "...", type: "..." }] }
    if (Array.isArray(data.detail)) {
      const firstError = data.detail[0];
      if (firstError && typeof firstError === "object") {
        const field = Array.isArray(firstError.loc)
          ? firstError.loc.filter((l: unknown) => l !== "body").join(".")
          : undefined;
        return {
          message: firstError.msg || "Validation error",
          field,
          details: { errors: data.detail },
        };
      }
    }

    // Simple error format: { detail: "message" }
    if (typeof data.detail === "string") {
      return { message: data.detail };
    }

    // Other formats
    if (data.message) {
      return { message: data.message };
    }
    if (data.error) {
      return { message: data.error };
    }

    return { message: response.statusText || "Unknown error" };
  } catch {
    return { message: response.statusText || "Unknown error" };
  }
}

/**
 * Create appropriate error from fetch failure
 */
function createFetchError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }

  const message = error instanceof Error ? error.message : String(error);
  const lowerMessage = message.toLowerCase();

  // Check for abort (user cancellation)
  if (
    error instanceof DOMException &&
    error.name === "AbortError"
  ) {
    return new TimeoutError(
      "The request was cancelled.",
      error
    );
  }

  // Check for network-related errors
  if (
    lowerMessage.includes("failed to fetch") ||
    lowerMessage.includes("network") ||
    lowerMessage.includes("net::") ||
    lowerMessage.includes("dns") ||
    lowerMessage.includes("econnrefused") ||
    lowerMessage.includes("enotfound")
  ) {
    return new NetworkError(
      "Unable to connect. Please check your internet connection.",
      error
    );
  }

  // Check for timeout errors
  if (
    lowerMessage.includes("timeout") ||
    lowerMessage.includes("timed out") ||
    lowerMessage.includes("aborted")
  ) {
    return new TimeoutError(
      "The request took too long. Please try again.",
      error
    );
  }

  // Generic error
  return new SimulationError(message, undefined, error);
}

/**
 * Create appropriate error from HTTP response
 */
async function createResponseError(response: Response): Promise<ApiError> {
  const { message, field, details } = await parseErrorResponse(response);

  if (response.status >= 400 && response.status < 500) {
    // Client errors (validation, bad request, etc.)
    if (response.status === 422 || field) {
      return new ValidationError(message, field, details, response.status);
    }
    return new ApiError(message, response.status);
  }

  if (response.status >= 500) {
    // Server errors
    return new SimulationError(
      message || "Something went wrong on our end. Please try again.",
      response.status
    );
  }

  return new ApiError(message, response.status);
}

// ============================================
// Generic API fetch helper
// ============================================

interface ApiFetchOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  timeoutMs?: number;
  token?: string;
}

/**
 * Generic fetch helper that standardizes base URL handling, error parsing,
 * AbortController support, and timeout handling for all API calls.
 */
async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const {
    method = "GET",
    body,
    headers: extraHeaders,
    signal: externalSignal,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    token,
  } = options;

  // Build headers
  const headers: Record<string, string> = { ...extraHeaders };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Set up timeout via AbortController
  const timeoutController = new AbortController();
  const timeoutId = setTimeout(() => timeoutController.abort(), timeoutMs);

  // Combine external signal with timeout signal
  let signal: AbortSignal = timeoutController.signal;
  if (externalSignal) {
    // If the external signal is already aborted, throw immediately
    if (externalSignal.aborted) {
      clearTimeout(timeoutId);
      throw new TimeoutError("The request was cancelled.");
    }
    // Use AbortSignal.any if available (modern browsers), otherwise fall back
    if (typeof AbortSignal.any === "function") {
      signal = AbortSignal.any([timeoutController.signal, externalSignal]);
    } else {
      // Fallback: listen to external signal to abort the timeout controller
      externalSignal.addEventListener("abort", () => timeoutController.abort(), { once: true });
    }
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (error) {
    clearTimeout(timeoutId);
    throw createFetchError(error);
  }

  clearTimeout(timeoutId);

  if (!response.ok) {
    throw await createResponseError(response);
  }

  return response.json() as Promise<T>;
}

// ============================================
// Type definitions
// ============================================

export type AccountType =
  | "traditional_401k"
  | "traditional_ira"
  | "roth_401k"
  | "roth_ira"
  | "taxable";

export type FundType = "vt" | "sp500" | "bnd" | "treasury";

export interface Holding {
  account_type: AccountType;
  fund: FundType;
  balance: number;
}

export interface SpouseInput {
  age: number;
  gender: "male" | "female";
  social_security_monthly: number;
  social_security_start_age: number;
  pension_annual: number;
  employment_income: number;
  employment_growth_rate: number;
  retirement_age: number;
}

export interface AnnuityInput {
  monthly_payment: number;
  annuity_type: "life_with_guarantee" | "fixed_period" | "life_only";
  guarantee_years: number;
}

export interface SimulationInput {
  // Holdings-based portfolio (preferred)
  holdings?: Holding[];
  withdrawal_strategy?: "traditional_first" | "roth_first" | "taxable_first" | "pro_rata";

  // Legacy: simple portfolio (for backward compatibility)
  initial_capital?: number;
  annual_spending: number;
  home_value: number;
  current_age: number;
  max_age: number;
  gender: "male" | "female";

  // Income sources
  social_security_monthly: number;
  social_security_start_age: number;
  pension_annual: number;
  employment_income: number;
  employment_growth_rate: number;
  retirement_age: number;

  // Tax settings
  state: string;
  filing_status: "single" | "married_filing_jointly" | "head_of_household";

  // Spouse
  has_spouse: boolean;
  spouse?: SpouseInput;

  // Annuity
  has_annuity: boolean;
  annuity?: AnnuityInput;

  // Simulation settings
  n_simulations: number;
  include_mortality: boolean;

  // Market assumptions
  expected_return: number;
  return_volatility: number;
  dividend_yield: number;
  stock_allocation: number;
  stock_index?: "sp500" | "vt";  // vt = Vanguard Total World (default)
  bond_index?: "treasury" | "bnd";  // bnd = Vanguard Total Bond Market (default)

  // Legacy fields for backward compatibility
  n_years?: number;
  inflation_rate?: number;
}

export interface YearBreakdown {
  age: number;
  year_index: number;
  portfolio_start: number;
  portfolio_end: number;
  portfolio_return: number;
  employment_income: number;
  social_security: number;
  pension: number;
  dividends: number;
  annuity: number;
  total_income: number;
  withdrawal: number;
  federal_tax: number;
  state_tax: number;
  total_tax: number;
  effective_tax_rate: number;
  net_income: number;
}

export interface SimulationResult {
  success_rate: number;
  median_final_value: number;
  mean_final_value: number;
  percentiles: Record<string, number>;
  median_depletion_age: number | null;
  median_depletion_year: number | null;
  total_withdrawn_median: number;
  total_taxes_median: number;
  percentile_paths: Record<string, number[]>;
  year_breakdown: YearBreakdown[];
  initial_withdrawal_rate: number;
  prob_10_year_failure: number;
}

export interface MortalityRates {
  ages: number[];
  rates: number[];
  survival_curve: number[];
}

export interface ProgressEvent {
  type: "progress";
  year: number;
  total_years: number;
}

export interface CompleteEvent {
  type: "complete";
  result: SimulationResult;
}

export type SimulationEvent = ProgressEvent | CompleteEvent;

// ============================================
// API functions
// ============================================

export async function runSimulation(
  params: SimulationInput,
  token?: string,
  signal?: AbortSignal
): Promise<SimulationResult> {
  return apiFetch<SimulationResult>("/simulate", {
    method: "POST",
    body: params,
    token,
    signal,
    timeoutMs: LONG_TIMEOUT_MS,
  });
}

export async function* runSimulationWithProgress(
  params: SimulationInput,
  token?: string
): AsyncGenerator<SimulationEvent, void, unknown> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}/simulate/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(params),
    });
  } catch (error) {
    throw createFetchError(error);
  }

  if (!response.ok) {
    throw await createResponseError(response);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new SimulationError("Failed to get response reader");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE messages
      const lines = buffer.split("\n");
      buffer = lines.pop() || ""; // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data.trim()) {
            try {
              const event = JSON.parse(data) as SimulationEvent;
              yield event;
            } catch (e) {
              console.error("Failed to parse SSE event:", data, e);
            }
          }
        }
      }
    }
  } catch (error) {
    throw createFetchError(error);
  }
}

export async function getMortalityRates(
  gender: "male" | "female",
  startAge: number = 65,
  endAge: number = 100,
  signal?: AbortSignal
): Promise<MortalityRates> {
  return apiFetch<MortalityRates>(
    `/mortality/${gender}?start_age=${startAge}&end_age=${endAge}`,
    { signal }
  );
}

export async function compareAnnuity(
  simulationInput: SimulationInput,
  annuityMonthlyPayment: number,
  annuityGuaranteeYears: number,
  token?: string,
  signal?: AbortSignal
): Promise<{
  simulation_result: SimulationResult;
  annuity_total_guaranteed: number;
  probability_simulation_beats_annuity: number;
  simulation_median_total_income: number;
  recommendation: string;
}> {
  return apiFetch("/compare-annuity", {
    method: "POST",
    body: {
      simulation_input: simulationInput,
      annuity_monthly_payment: annuityMonthlyPayment,
      annuity_guarantee_years: annuityGuaranteeYears,
    },
    token,
    signal,
    timeoutMs: LONG_TIMEOUT_MS,
  });
}

export interface StateResult {
  state: string;
  success_rate: number;
  median_final_value: number;
  total_taxes_median: number;
  total_withdrawn_median: number;
  net_after_tax_median: number;
}

export interface StateComparisonResult {
  base_state: string;
  results: StateResult[];
  tax_savings_vs_base: Record<string, number>;
}

export async function compareStates(
  baseInput: SimulationInput,
  statesToCompare: string[],
  signal?: AbortSignal
): Promise<StateComparisonResult> {
  return apiFetch<StateComparisonResult>("/compare-states", {
    method: "POST",
    body: {
      base_input: baseInput,
      compare_states: statesToCompare,
    },
    signal,
    timeoutMs: LONG_TIMEOUT_MS,
  });
}

// Social Security timing types
export interface SSTimingResult {
  claiming_age: number;
  monthly_benefit: number;
  annual_benefit: number;
  adjustment_factor: number;
  success_rate: number;
  median_final_value: number;
  total_ss_income_median: number;
  total_taxes_median: number;
  breakeven_vs_62: number | null;
}

export interface SSTimingComparisonResult {
  birth_year: number;
  full_retirement_age: number;
  pia_monthly: number;
  results: SSTimingResult[];
  optimal_claiming_age: number;
  optimal_for_longevity: number;
}

export async function compareSSTimings(
  baseInput: SimulationInput,
  birthYear: number,
  piaMonthly: number,
  claimingAges?: number[],
  signal?: AbortSignal
): Promise<SSTimingComparisonResult> {
  return apiFetch<SSTimingComparisonResult>("/compare-ss-timing", {
    method: "POST",
    body: {
      base_input: baseInput,
      birth_year: birthYear,
      pia_monthly: piaMonthly,
      ...(claimingAges && { claiming_ages: claimingAges }),
    },
    signal,
    timeoutMs: LONG_TIMEOUT_MS,
  });
}

// Asset allocation types
export interface AllocationResult {
  stock_allocation: number;
  bond_allocation: number;
  success_rate: number;
  median_final_value: number;
  percentile_5_final_value: number;
  percentile_95_final_value: number;
  volatility: number;
  expected_return: number;
}

export interface AllocationComparisonResult {
  results: AllocationResult[];
  optimal_for_success: number;
  optimal_for_safety: number;
  recommendation: string;
}

export async function compareAllocations(
  baseInput: SimulationInput,
  allocations?: number[],
  signal?: AbortSignal
): Promise<AllocationComparisonResult> {
  return apiFetch<AllocationComparisonResult>("/compare-allocations", {
    method: "POST",
    body: {
      base_input: baseInput,
      ...(allocations && { allocations }),
    },
    signal,
    timeoutMs: LONG_TIMEOUT_MS,
  });
}

// === Life event tax calculator types ===

export interface PersonInput {
  age: number;
  employment_income?: number;
  self_employment_income?: number;
  social_security?: number;
  pension_income?: number;
  investment_income?: number;
  capital_gains?: number;
  is_tax_unit_head?: boolean;
  is_tax_unit_spouse?: boolean;
  is_tax_unit_dependent?: boolean;
}

export interface HouseholdInput {
  state: string;
  year?: number;
  filing_status?: "single" | "married_filing_jointly" | "married_filing_separately" | "head_of_household";
  people: PersonInput[];
}

export interface HouseholdResult {
  federal_income_tax: number;
  state_income_tax: number;
  payroll_tax: number;
  total_taxes: number;
  benefits: Record<string, number>;
  total_benefits: number;
  total_income: number;
  net_income: number;
  tax_breakdown: Record<string, number>;
  marginal_tax_rate: number;
  effective_tax_rate: number;
}

export interface LifeEventComparison {
  event_name: string;
  before_result: HouseholdResult;
  after_result: HouseholdResult;
  tax_change: number;
  benefit_change: number;
  net_income_change: number;
}

export async function calculateHousehold(
  household: HouseholdInput,
  signal?: AbortSignal
): Promise<HouseholdResult> {
  return apiFetch<HouseholdResult>("/calculate-household", {
    method: "POST",
    body: household,
    signal,
  });
}

export async function compareLifeEvent(
  before: HouseholdInput,
  after: HouseholdInput,
  eventName: string = "Life event",
  signal?: AbortSignal
): Promise<LifeEventComparison> {
  return apiFetch<LifeEventComparison>("/compare-life-event", {
    method: "POST",
    body: {
      before,
      after,
      event_name: eventName,
    },
    signal,
    timeoutMs: LONG_TIMEOUT_MS,
  });
}
