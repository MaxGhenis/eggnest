import type {
  CompensationAnalysisInput,
  CompensationEmployeeProfile,
  CompensationPackageInput,
} from "./api";

export interface EmployerRolePreset {
  id: string;
  title: string;
  function: string;
  benchmarkId: string;
  cashSalary: number;
  annualBonus: number;
  annualEquity: number;
  targetPercentile: string;
  marketLens: string;
  packageLens: string;
}

export const employerRolePresets: EmployerRolePreset[] = [
  {
    id: "ceo",
    title: "Executive Director / CEO",
    function: "Executive",
    benchmarkId: "CEO (nonprofit $10-50M)::Nonprofit",
    cashSalary: 250_000,
    annualBonus: 15_000,
    annualEquity: 0,
    targetPercentile: "Illustrative",
    marketLens: "Mission-driven executive package calibrated against nonprofit leadership rather than venture-style founder upside.",
    packageLens: "Useful as a top-of-ladder reference for a public-interest organization pricing senior leadership.",
  },
  {
    id: "cto",
    title: "Chief Technology Officer",
    function: "Technical leadership",
    benchmarkId: "CTO (mid-stage startup)::Nonprofit/mission",
    cashSalary: 340_000,
    annualBonus: 25_000,
    annualEquity: 0,
    targetPercentile: "Illustrative",
    marketLens: "Senior technical leadership package with real market pressure from equity-heavy outside options.",
    packageLens: "Shows how a mission-driven org can pay up for a scarce technical leader without mirroring venture packages one-for-one.",
  },
  {
    id: "vp-eng",
    title: "Engineering Director",
    function: "Engineering management",
    benchmarkId: "VP Engineering / Eng Director::Nonprofit/mission",
    cashSalary: 285_000,
    annualBonus: 20_000,
    annualEquity: 0,
    targetPercentile: "Illustrative",
    marketLens: "Management-layer engineering package for a team lead who owns delivery, quality, and hiring.",
    packageLens: "A good middle-management reference point between senior IC packages and the top technical executive.",
  },
  {
    id: "senior-ml",
    title: "Senior ML Engineer",
    function: "Applied modeling",
    benchmarkId: "Senior ML/AI Engineer::Nonprofit/mission",
    cashSalary: 260_000,
    annualBonus: 15_000,
    annualEquity: 0,
    targetPercentile: "Illustrative",
    marketLens: "Applied ML role with meaningful private-market pressure, especially where product quality depends on inference or ranking models.",
    packageLens: "Useful for teams that need production ML talent but still want a mission-oriented pay philosophy.",
  },
  {
    id: "senior-swe",
    title: "Senior Software Engineer",
    function: "Core engineering",
    benchmarkId: "Senior SWE (L5)::Nonprofit/mission",
    cashSalary: 210_000,
    annualBonus: 10_000,
    annualEquity: 0,
    targetPercentile: "Illustrative",
    marketLens: "Baseline senior builder package for a mission-driven engineering team.",
    packageLens: "Good reference point for the main engineering ladder before specialty or leadership premiums.",
  },
];

export const employerStateOptions = ["CA", "NY", "TX", "WA"] as const;

export function buildEmployerProfile(
  state: string
): CompensationEmployeeProfile {
  return {
    state,
    year: 2026,
    filing_status: "single",
    age: 35,
  };
}

export function buildEmployerPackage(
  preset: EmployerRolePreset
): CompensationPackageInput {
  return {
    name: preset.title,
    benchmark_id: preset.benchmarkId,
    salary: preset.cashSalary,
    annual_bonus: preset.annualBonus,
    annual_equity: preset.annualEquity,
    taxable_equity_treatment: "w2",
    employer_retirement_rate: 0.25,
    employer_retirement_cap: 47_500,
    employer_health_premiums: 24_000,
    other_employer_costs: 12_000,
  };
}

export function buildEmployerAnalysisInput(
  preset: EmployerRolePreset,
  state: string
): CompensationAnalysisInput {
  return {
    employee_profile: buildEmployerProfile(state),
    packages: [buildEmployerPackage(preset)],
  };
}

export function buildEmployerAnalysisInputForPresets(
  state: string
): CompensationAnalysisInput {
  return {
    employee_profile: buildEmployerProfile(state),
    packages: employerRolePresets.map(buildEmployerPackage),
  };
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}
