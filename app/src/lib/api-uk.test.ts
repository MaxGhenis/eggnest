import { afterEach, describe, expect, it, vi } from "vitest";
import { runUKSimulation, type UKSimulationInput, type UKSimulationResult } from "./api-uk";

const input: UKSimulationInput = {
  current_age: 65,
  max_age: 90,
  isa_balance: 100_000,
  sipp_balance: 200_000,
  gia_balance: 50_000,
  annual_spending: 30_000,
};

const result: UKSimulationResult = {
  metadata: { n_simulations: 100 },
  success_rate: 0.91,
  strict_horizon_success_rate: 0.88,
  median_final_value: 250_000,
  median_final_value_real: 190_000,
  percentiles: { p5: 0, p25: 100_000, p50: 250_000, p75: 400_000, p95: 700_000 },
  percentiles_real: { p5: 0, p25: 76_000, p50: 190_000, p75: 304_000, p95: 532_000 },
  percentile_paths: { p5: [350_000], p25: [350_000], p50: [350_000], p75: [350_000], p95: [350_000] },
  tax_percentile_paths: { p5: [0], p25: [1_000], p50: [2_000], p75: [3_000], p95: [4_000] },
  earnings_percentile_paths: { p5: [0], p25: [0], p50: [0], p75: [0], p95: [0] },
  percentile_path_start_years: null,
  year_breakdown: [
    {
      year_index: 0,
      age: 65,
      portfolio_start: 350_000,
      portfolio_end: 340_000,
      spending_target: 30_000,
      total_income: 30_000,
      withdrawal: 30_000,
      total_tax: 2_000,
      inflation_rate: 0.025,
      portfolio_return: 0.04,
      effective_tax_rate: 0.06,
      state_pension: 0,
      employment_income: 0,
      sipp_withdrawal: 10_000,
      isa_withdrawal: 20_000,
      gia_withdrawal: 0,
    },
  ],
  initial_withdrawal_rate: 8.6,
  prob_10_year_failure: 0.04,
};

describe("runUKSimulation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts UK simulation input and parses the result contract", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ outputs: { uk_simulation_result: result } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(runUKSimulation(input)).resolves.toMatchObject({
      success_rate: 0.91,
      strict_horizon_success_rate: 0.88,
      median_final_value_real: 190_000,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/core/simulate",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schema_version: "eggnest.scenario.v1",
          engine: "uk_retirement",
          country: "GBR",
          inputs: input,
        }),
      }),
    );
  });

  it("throws on non-2xx responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("nope", { status: 500 }));

    await expect(runUKSimulation(input)).rejects.toThrow("UK simulation failed: 500");
  });
});
