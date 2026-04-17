// @vitest-environment node

import { describe, expect, it } from "vitest";
import {
  assertDemoScenarioConsistency,
  createMockTracker,
  resolveDemoConfig,
} from "./demoHarness.mjs";
import {
  mockHistoricalBacktestResult,
  mockRothOptimizationResult,
  mockSimulationResult,
} from "./record-simulator-demo.fixtures.mjs";

describe("demoHarness", () => {
  it("keeps the demo baseline aligned across the main result and Roth comparison", () => {
    expect(() =>
      assertDemoScenarioConsistency({
        simulationResult: mockSimulationResult,
        historicalBacktestResult: mockHistoricalBacktestResult,
        rothOptimizationResult: mockRothOptimizationResult,
      }),
    ).not.toThrow();
  });

  it("fails fast when the Roth baseline drifts from the main simulation result", () => {
    const driftedRothResult = {
      ...mockRothOptimizationResult,
      results: [
        {
          ...mockRothOptimizationResult.results[0],
          monte_carlo: {
            ...mockRothOptimizationResult.results[0].monte_carlo,
            success_rate: 0.9,
          },
        },
        ...mockRothOptimizationResult.results.slice(1),
      ],
    };

    expect(() =>
      assertDemoScenarioConsistency({
        simulationResult: mockSimulationResult,
        historicalBacktestResult: mockHistoricalBacktestResult,
        rothOptimizationResult: driftedRothResult,
      }),
    ).toThrow(/Monte Carlo success_rate mismatch/);
  });

  it("tracks required mock hits and throws when a mock is missed", () => {
    const tracker = createMockTracker(["simulate", "backtest"]);
    tracker.hit("simulate");

    expect(() => tracker.assertAllHit()).toThrow(/backtest/);

    tracker.hit("backtest");
    expect(() => tracker.assertAllHit()).not.toThrow();
  });

  it("resolves demo URLs from env overrides", () => {
    const original = process.env.DEMO_APP_URL;
    process.env.DEMO_APP_URL = "https://demo.eggnest.co";

    try {
      expect(resolveDemoConfig()).toEqual({
        appUrl: "https://demo.eggnest.co",
        simulatorUrl: "https://demo.eggnest.co/simulator",
      });
    } finally {
      if (original === undefined) {
        delete process.env.DEMO_APP_URL;
      } else {
        process.env.DEMO_APP_URL = original;
      }
    }
  });
});
