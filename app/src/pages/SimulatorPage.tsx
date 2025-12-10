import { useState } from "react";
import Plot from "react-plotly.js";
import { Wizard, type WizardStep } from "../components/Wizard";
import { SimulationProgress } from "../components/SimulationProgress";
import {
  runSimulationWithProgress,
  compareAnnuity,
  compareStates,
  compareSSTimings,
  compareAllocations,
  type SimulationInput,
  type SimulationResult,
  type SpouseInput,
  type AnnuityInput,
  type StateComparisonResult,
  type SSTimingComparisonResult,
  type AllocationComparisonResult,
} from "../lib/api";
import { colors, chartColors } from "../lib/design-tokens";
import "../styles/Simulator.css";
import "../styles/Wizard.css";

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
  expected_return: 0.05,
  return_volatility: 0.16,
  dividend_yield: 0.02,
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

interface AnnuityComparisonResult {
  simulation_result: SimulationResult;
  annuity_total_guaranteed: number;
  probability_simulation_beats_annuity: number;
  simulation_median_total_income: number;
  recommendation: string;
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
  const [error, setError] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(true);
  const [showPersonaPicker, setShowPersonaPicker] = useState(true);
  const [progress, setProgress] = useState({ currentYear: 0, totalYears: 0 });

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
      };

      // Use streaming API with progress updates
      for await (const event of runSimulationWithProgress(fullParams)) {
        if (event.type === "progress") {
          setProgress({ currentYear: event.year, totalYears: event.total_years });
        } else if (event.type === "complete") {
          setResult(event.result);
        }
      }
      setShowWizard(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed");
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
      setShowWizard(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed");
      setResult(null);
    } finally {
      setIsLoading(false);
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
      };

      // Use provided states, selected states, or default to no-tax states
      const states = statesToCompare ||
        (selectedCompareStates.length > 0 ? selectedCompareStates :
          NO_TAX_STATES.filter(s => s !== params.state).slice(0, 5));

      const comparison = await compareStates(fullParams, states);
      setStateComparisonResult(comparison);
    } catch (err) {
      setError(err instanceof Error ? err.message : "State comparison failed");
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
      };

      const comparison = await compareSSTimings(
        fullParams,
        birthYear,
        piaMonthly
      );
      setSSTimingResult(comparison);
    } catch (err) {
      setError(err instanceof Error ? err.message : "SS timing comparison failed");
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
      };

      const comparison = await compareAllocations(
        fullParams,
        [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
      );
      setAllocationResult(comparison);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Allocation comparison failed");
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
        const withdrawalRate = params.initial_capital > 0
          ? (params.annual_spending / params.initial_capital) * 100
          : 0;
        const rateContext = getWithdrawalRateContext(withdrawalRate);

        return (
          <div>
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

            {params.initial_capital > 0 && params.annual_spending > 0 && (
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
              Your estimated monthly benefit (check ssa.gov/myaccount)
            </div>
          </div>
          {params.social_security_monthly > 0 && (
            <div className="wizard-field">
              <label>Social Security Start Age</label>
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
              {spouse.social_security_monthly > 0 && (
                <div className="wizard-field">
                  <label>Spouse SS Start Age</label>
                  <select
                    value={spouse.social_security_start_age}
                    onChange={(e) =>
                      setSpouse({
                        ...spouse,
                        social_security_start_age: Number(e.target.value),
                      })
                    }
                  >
                    <option value={62}>62</option>
                    <option value={63}>63</option>
                    <option value={64}>64</option>
                    <option value={65}>65</option>
                    <option value={66}>66</option>
                    <option value={67}>67 (FRA)</option>
                    <option value={68}>68</option>
                    <option value={69}>69</option>
                    <option value={70}>70</option>
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
              <div className="wizard-review-row">
                <span className="wizard-review-label">Portfolio</span>
                <span className="wizard-review-value">
                  {formatCurrency(params.initial_capital)}
                </span>
              </div>
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

          {error && (
            <div className="error-banner" style={{ marginTop: "1rem" }}>
              <strong>Error:</strong> {error}
            </div>
          )}
        </div>
      ),
    },
  ];

  // What-if scenario helpers
  const runWhatIfScenario = (modifier: Partial<SimulationInput>) => {
    setParams((prev) => ({ ...prev, ...modifier }));
    setShowWizard(true);
  };

  // Results view
  const renderResults = () => {
    const interpretation = getSuccessRateInterpretation(result!.success_rate);

    return (
    <div className="results-view">
      <button className="back-to-wizard" onClick={() => setShowWizard(true)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        Edit Inputs
      </button>

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
      <div className="chart-container">
        <h3>Portfolio Value Over Time</h3>
        <Plot
          data={[
            {
              x: ages,
              y: result!.percentile_paths.p95,
              type: "scatter",
              mode: "lines",
              line: { color: "rgba(217, 119, 6, 0.2)", width: 0 },
              showlegend: false,
              hoverinfo: "skip",
            },
            {
              x: ages,
              y: result!.percentile_paths.p5,
              type: "scatter",
              mode: "lines",
              fill: "tonexty",
              fillcolor: "rgba(217, 119, 6, 0.1)",
              line: { color: "rgba(217, 119, 6, 0.2)", width: 0 },
              name: "5th-95th percentile",
            },
            {
              x: ages,
              y: result!.percentile_paths.p75,
              type: "scatter",
              mode: "lines",
              line: { color: "rgba(217, 119, 6, 0.3)", width: 1 },
              showlegend: false,
              hoverinfo: "skip",
            },
            {
              x: ages,
              y: result!.percentile_paths.p25,
              type: "scatter",
              mode: "lines",
              fill: "tonexty",
              fillcolor: "rgba(217, 119, 6, 0.15)",
              line: { color: "rgba(217, 119, 6, 0.3)", width: 1 },
              name: "25th-75th percentile",
            },
            {
              x: ages,
              y: result!.percentile_paths.p50,
              type: "scatter",
              mode: "lines",
              line: { color: chartColors.primary, width: 3 },
              name: "Median",
            },
          ]}
          layout={{
            autosize: true,
            height: 400,
            margin: { l: 80, r: 40, t: 20, b: 60 },
            font: { family: "Inter, system-ui, sans-serif" },
            xaxis: {
              title: { text: "Age", font: { family: "Inter, system-ui, sans-serif" } },
              gridcolor: colors.gray200,
              tickfont: { family: "Inter, system-ui, sans-serif" },
            },
            yaxis: {
              title: { text: "Portfolio Value", font: { family: "Inter, system-ui, sans-serif" } },
              gridcolor: colors.gray200,
              tickformat: "$,.0f",
              tickfont: { family: "Inter, system-ui, sans-serif" },
            },
            legend: {
              x: 0,
              y: 1.1,
              orientation: "h",
              font: { family: "Inter, system-ui, sans-serif" },
            },
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            hovermode: "x unified",
          }}
          config={{ responsive: true, displayModeBar: false }}
          style={{ width: "100%" }}
        />
      </div>

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
              <td>25% of outcomes are worse</td>
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
                initial_capital: Math.round(params.initial_capital * 1.1),
              })
            }
          >
            <span className="what-if-icon">💰</span>
            <span className="what-if-label">10% more savings</span>
            <span className="what-if-value">
              {formatCurrency(Math.round(params.initial_capital * 1.1))}
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
                <span>{formatCurrency(persona.params.initial_capital)} saved</span>
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
      </header>

      <div className="sim-content">
        {showPersonaPicker && showWizard && !result ? (
          renderPersonaPicker()
        ) : showWizard ? (
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
        ) : (
          result && renderResults()
        )}
      </div>
    </div>
  );
}
