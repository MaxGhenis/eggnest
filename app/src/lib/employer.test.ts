import { describe, expect, it } from "vitest";

import {
  buildEmployerAnalysisInput,
  buildEmployerAnalysisInputForPresets,
  buildEmployerPackage,
  buildEmployerProfile,
  employerRolePresets,
} from "./employer";

describe("buildEmployerProfile", () => {
  it("builds a default single-worker profile", () => {
    const profile = buildEmployerProfile("NY");

    expect(profile.state).toBe("NY");
    expect(profile.year).toBe(2026);
    expect(profile.filing_status).toBe("single");
    expect(profile.age).toBe(35);
  });
});

describe("buildEmployerPackage", () => {
  it("uses the preset benchmark and package defaults", () => {
    const preset = employerRolePresets.find((role) => role.id === "cto");
    expect(preset).toBeDefined();

    const pkg = buildEmployerPackage(preset!);

    expect(pkg.benchmark_id).toBe("CTO (mid-stage startup)::Nonprofit/mission");
    expect(pkg.salary).toBe(340_000);
    expect(pkg.annual_bonus).toBe(25_000);
    expect(pkg.employer_retirement_rate).toBe(0.25);
    expect(pkg.employer_retirement_cap).toBe(47_500);
    expect(pkg.employer_health_premiums).toBe(24_000);
    expect(pkg.other_employer_costs).toBe(12_000);
  });
});

describe("buildEmployerAnalysisInput", () => {
  it("builds a one-package analysis request", () => {
    const preset = employerRolePresets[0];
    const input = buildEmployerAnalysisInput(preset, "CA");

    expect(input.employee_profile.state).toBe("CA");
    expect(input.packages).toHaveLength(1);
    expect(input.packages[0].name).toBe(preset.title);
    expect(input.packages[0].benchmark_id).toBe(preset.benchmarkId);
  });
});

describe("buildEmployerAnalysisInputForPresets", () => {
  it("builds an analysis request across all role presets", () => {
    const input = buildEmployerAnalysisInputForPresets("TX");

    expect(input.employee_profile.state).toBe("TX");
    expect(input.packages).toHaveLength(employerRolePresets.length);
    expect(input.packages.map((pkg) => pkg.benchmark_id)).toEqual(
      employerRolePresets.map((preset) => preset.benchmarkId)
    );
  });
});
