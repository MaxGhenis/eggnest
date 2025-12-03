const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface SimulationInput {
  initial_capital: number;
  target_monthly_income: number;
  social_security_monthly: number;
  current_age: number;
  retirement_age: number;
  state: string;
  filing_status: string;
  n_simulations: number;
  n_years: number;
  expected_return: number;
  return_volatility: number;
  dividend_yield: number;
  inflation_rate: number;
}

export interface SimulationResult {
  success_rate: number;
  median_final_value: number;
  mean_final_value: number;
  percentiles: Record<string, number>;
  median_depletion_year: number | null;
  total_withdrawn_median: number;
  total_taxes_median: number;
  percentile_paths: Record<string, number[]>;
}

export async function runSimulation(
  params: SimulationInput,
  token?: string
): Promise<SimulationResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}/simulate`, {
    method: "POST",
    headers,
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    throw new Error(`Simulation failed: ${response.statusText}`);
  }

  return response.json();
}

export async function compareAnnuity(
  simulationInput: SimulationInput,
  annuityMonthlyPayment: number,
  annuityGuaranteeYears: number,
  token?: string
): Promise<{
  simulation_result: SimulationResult;
  annuity_total_guaranteed: number;
  probability_simulation_beats_annuity: number;
  simulation_median_total_income: number;
  recommendation: string;
}> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}/compare-annuity`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      simulation_input: simulationInput,
      annuity_monthly_payment: annuityMonthlyPayment,
      annuity_guarantee_years: annuityGuaranteeYears,
    }),
  });

  if (!response.ok) {
    throw new Error(`Comparison failed: ${response.statusText}`);
  }

  return response.json();
}
