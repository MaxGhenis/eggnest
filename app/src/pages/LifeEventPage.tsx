import { useState } from "react";
import {
  compareLifeEvent,
  calculateHousehold,
  type HouseholdInput,
  type PersonInput,
  type HouseholdResult,
  type LifeEventComparison,
} from "../lib/api";
// Note: colors available from ../lib/design-tokens if needed
import "../styles/LifeEvent.css";

const US_STATES = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
];

// In production, this is eggnest.co
const HOME_URL = import.meta.env.PROD
  ? "https://eggnest.co"
  : "http://localhost:5173";

type FilingStatus = "single" | "married_filing_jointly" | "married_filing_separately" | "head_of_household";

interface LifeEventScenario {
  id: string;
  name: string;
  description: string;
  emoji: string;
  beforeSetup: (base: HouseholdInput) => HouseholdInput;
  afterSetup: (base: HouseholdInput) => HouseholdInput;
}

const LIFE_EVENT_SCENARIOS: LifeEventScenario[] = [
  {
    id: "having-child",
    name: "Having a Child",
    description: "See how a new child affects your taxes and benefits",
    emoji: "👶",
    beforeSetup: (base) => ({
      ...base,
      filing_status: "single" as FilingStatus,
      people: [{ ...base.people[0], is_tax_unit_head: true }],
    }),
    afterSetup: (base) => ({
      ...base,
      filing_status: "head_of_household" as FilingStatus,
      people: [
        { ...base.people[0], is_tax_unit_head: true },
        { age: 0, employment_income: 0, is_tax_unit_dependent: true },
      ],
    }),
  },
  {
    id: "getting-married",
    name: "Getting Married",
    description: "Compare single vs married filing jointly",
    emoji: "💒",
    beforeSetup: (base) => ({
      ...base,
      filing_status: "single" as FilingStatus,
      people: [{ ...base.people[0], is_tax_unit_head: true }],
    }),
    afterSetup: (base) => ({
      ...base,
      filing_status: "married_filing_jointly" as FilingStatus,
      people: [
        { ...base.people[0], is_tax_unit_head: true },
        {
          age: base.people[0].age - 2,
          employment_income: Math.round((base.people[0].employment_income || 50000) * 0.8),
          is_tax_unit_spouse: true
        },
      ],
    }),
  },
  {
    id: "income-change",
    name: "Getting a Raise",
    description: "See how higher income changes your taxes",
    emoji: "📈",
    beforeSetup: (base) => base,
    afterSetup: (base) => ({
      ...base,
      people: base.people.map((p, i) =>
        i === 0
          ? { ...p, employment_income: Math.round((p.employment_income || 50000) * 1.25) }
          : p
      ),
    }),
  },
  {
    id: "retirement",
    name: "Retiring",
    description: "Compare working vs retirement income",
    emoji: "🏖️",
    beforeSetup: (base) => base,
    afterSetup: (base) => ({
      ...base,
      people: base.people.map((p, i) =>
        i === 0
          ? { ...p, employment_income: 0, social_security: 30000, pension_income: 24000 }
          : p
      ),
    }),
  },
];

function formatCurrency(value: number): string {
  const absValue = Math.abs(value);
  if (absValue >= 1_000_000) {
    return `${value < 0 ? "-" : ""}$${(absValue / 1_000_000).toFixed(1)}M`;
  }
  if (absValue >= 1_000) {
    return `${value < 0 ? "-" : ""}$${(absValue / 1_000).toFixed(0)}K`;
  }
  return `${value < 0 ? "-" : ""}$${absValue.toFixed(0)}`;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function LifeEventPage() {
  // Base household setup
  const [baseHousehold, setBaseHousehold] = useState<HouseholdInput>({
    state: "CA",
    year: 2025,
    filing_status: "single",
    people: [{
      age: 35,
      employment_income: 75000,
      is_tax_unit_head: true,
    }],
  });

  // Currently selected scenario
  const [selectedScenario, setSelectedScenario] = useState<LifeEventScenario | null>(null);

  // Results
  const [currentResult, setCurrentResult] = useState<HouseholdResult | null>(null);
  const [comparisonResult, setComparisonResult] = useState<LifeEventComparison | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // View state
  const [showSetup, setShowSetup] = useState(true);

  const updateBasePerson = (field: keyof PersonInput, value: number | boolean) => {
    setBaseHousehold(prev => ({
      ...prev,
      people: prev.people.map((p, i) =>
        i === 0 ? { ...p, [field]: value } : p
      ),
    }));
  };

  const calculateCurrent = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await calculateHousehold(baseHousehold);
      setCurrentResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calculation failed");
    } finally {
      setIsLoading(false);
    }
  };

  const runScenario = async (scenario: LifeEventScenario) => {
    setIsLoading(true);
    setError(null);
    setSelectedScenario(scenario);
    setComparisonResult(null);

    try {
      const before = scenario.beforeSetup(baseHousehold);
      const after = scenario.afterSetup(baseHousehold);

      const result = await compareLifeEvent(before, after, scenario.name);
      setComparisonResult(result);
      setShowSetup(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setIsLoading(false);
    }
  };

  const renderSetup = () => (
    <div className="life-event-setup">
      <div className="setup-section">
        <h2>Your Current Situation</h2>
        <p className="setup-subtitle">Tell us about yourself to see how life events affect your taxes</p>

        <div className="setup-form">
          <div className="form-row">
            <div className="form-field">
              <label>Your Age</label>
              <input
                type="number"
                value={baseHousehold.people[0].age}
                onChange={(e) => updateBasePerson("age", Number(e.target.value))}
                min={18}
                max={100}
              />
            </div>
            <div className="form-field">
              <label>State</label>
              <select
                value={baseHousehold.state}
                onChange={(e) => setBaseHousehold(prev => ({ ...prev, state: e.target.value }))}
              >
                {US_STATES.map((st) => (
                  <option key={st} value={st}>{st}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-field">
            <label>Annual Employment Income</label>
            <div className="input-prefix">
              <span>$</span>
              <input
                type="number"
                value={baseHousehold.people[0].employment_income || 0}
                onChange={(e) => updateBasePerson("employment_income", Number(e.target.value))}
                min={0}
                step={5000}
              />
            </div>
          </div>

          <div className="form-field">
            <label>Filing Status</label>
            <select
              value={baseHousehold.filing_status}
              onChange={(e) => setBaseHousehold(prev => ({
                ...prev,
                filing_status: e.target.value as FilingStatus
              }))}
            >
              <option value="single">Single</option>
              <option value="married_filing_jointly">Married Filing Jointly</option>
              <option value="head_of_household">Head of Household</option>
            </select>
          </div>

          <button
            className="btn-calculate"
            onClick={calculateCurrent}
            disabled={isLoading}
          >
            {isLoading ? "Calculating..." : "Calculate Current Taxes"}
          </button>
        </div>

        {currentResult && (
          <div className="current-summary">
            <h3>Your Current Tax Situation</h3>
            <div className="summary-grid">
              <div className="summary-item">
                <span className="summary-label">Total Income</span>
                <span className="summary-value">{formatCurrency(currentResult.total_income)}</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">Federal Tax</span>
                <span className="summary-value">{formatCurrency(currentResult.federal_income_tax)}</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">State Tax</span>
                <span className="summary-value">{formatCurrency(currentResult.state_income_tax)}</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">FICA</span>
                <span className="summary-value">{formatCurrency(currentResult.payroll_tax)}</span>
              </div>
              <div className="summary-item highlight">
                <span className="summary-label">Net Income</span>
                <span className="summary-value">{formatCurrency(currentResult.net_income)}</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">Effective Rate</span>
                <span className="summary-value">{formatPercent(currentResult.effective_tax_rate)}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="setup-section">
        <h2>Explore Life Events</h2>
        <p className="setup-subtitle">See how major life changes affect your taxes and benefits</p>

        <div className="scenario-grid">
          {LIFE_EVENT_SCENARIOS.map((scenario) => (
            <button
              key={scenario.id}
              className="scenario-card"
              onClick={() => runScenario(scenario)}
              disabled={isLoading}
            >
              <span className="scenario-emoji">{scenario.emoji}</span>
              <span className="scenario-name">{scenario.name}</span>
              <span className="scenario-desc">{scenario.description}</span>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  );

  const renderResults = () => {
    if (!comparisonResult || !selectedScenario) return null;

    const { before_result, after_result, tax_change, benefit_change, net_income_change } = comparisonResult;
    const isBetterOff = net_income_change > 0;

    return (
      <div className="life-event-results">
        <button className="back-button" onClick={() => setShowSetup(true)}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Back to Setup
        </button>

        <div className="results-header">
          <span className="results-emoji">{selectedScenario.emoji}</span>
          <h2>{selectedScenario.name}</h2>
          <p>{selectedScenario.description}</p>
        </div>

        {/* Main impact summary */}
        <div className={`impact-banner ${isBetterOff ? "positive" : "negative"}`}>
          <div className="impact-label">Net Income Impact</div>
          <div className="impact-value">
            {net_income_change >= 0 ? "+" : ""}{formatCurrency(net_income_change)}
            <span className="impact-direction">{isBetterOff ? " more" : " less"} per year</span>
          </div>
        </div>

        {/* Detailed comparison */}
        <div className="comparison-table-container">
          <table className="comparison-table">
            <thead>
              <tr>
                <th></th>
                <th>Before</th>
                <th>After</th>
                <th>Change</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="row-label">Total Income</td>
                <td>{formatCurrency(before_result.total_income)}</td>
                <td>{formatCurrency(after_result.total_income)}</td>
                <td className={after_result.total_income > before_result.total_income ? "positive" : after_result.total_income < before_result.total_income ? "negative" : ""}>
                  {after_result.total_income - before_result.total_income >= 0 ? "+" : ""}
                  {formatCurrency(after_result.total_income - before_result.total_income)}
                </td>
              </tr>
              <tr>
                <td className="row-label">Federal Income Tax</td>
                <td>{formatCurrency(before_result.federal_income_tax)}</td>
                <td>{formatCurrency(after_result.federal_income_tax)}</td>
                <td className={after_result.federal_income_tax < before_result.federal_income_tax ? "positive" : after_result.federal_income_tax > before_result.federal_income_tax ? "negative" : ""}>
                  {after_result.federal_income_tax - before_result.federal_income_tax >= 0 ? "+" : ""}
                  {formatCurrency(after_result.federal_income_tax - before_result.federal_income_tax)}
                </td>
              </tr>
              <tr>
                <td className="row-label">State Income Tax</td>
                <td>{formatCurrency(before_result.state_income_tax)}</td>
                <td>{formatCurrency(after_result.state_income_tax)}</td>
                <td className={after_result.state_income_tax < before_result.state_income_tax ? "positive" : after_result.state_income_tax > before_result.state_income_tax ? "negative" : ""}>
                  {after_result.state_income_tax - before_result.state_income_tax >= 0 ? "+" : ""}
                  {formatCurrency(after_result.state_income_tax - before_result.state_income_tax)}
                </td>
              </tr>
              <tr>
                <td className="row-label">Payroll Tax (FICA)</td>
                <td>{formatCurrency(before_result.payroll_tax)}</td>
                <td>{formatCurrency(after_result.payroll_tax)}</td>
                <td className={after_result.payroll_tax < before_result.payroll_tax ? "positive" : after_result.payroll_tax > before_result.payroll_tax ? "negative" : ""}>
                  {after_result.payroll_tax - before_result.payroll_tax >= 0 ? "+" : ""}
                  {formatCurrency(after_result.payroll_tax - before_result.payroll_tax)}
                </td>
              </tr>
              <tr className="total-row">
                <td className="row-label">Total Taxes</td>
                <td>{formatCurrency(before_result.total_taxes)}</td>
                <td>{formatCurrency(after_result.total_taxes)}</td>
                <td className={tax_change < 0 ? "positive" : tax_change > 0 ? "negative" : ""}>
                  {tax_change >= 0 ? "+" : ""}{formatCurrency(tax_change)}
                </td>
              </tr>
              <tr>
                <td className="row-label">Total Benefits</td>
                <td>{formatCurrency(before_result.total_benefits)}</td>
                <td>{formatCurrency(after_result.total_benefits)}</td>
                <td className={benefit_change > 0 ? "positive" : benefit_change < 0 ? "negative" : ""}>
                  {benefit_change >= 0 ? "+" : ""}{formatCurrency(benefit_change)}
                </td>
              </tr>
              <tr className="net-row">
                <td className="row-label">Net Income</td>
                <td>{formatCurrency(before_result.net_income)}</td>
                <td>{formatCurrency(after_result.net_income)}</td>
                <td className={net_income_change > 0 ? "positive" : net_income_change < 0 ? "negative" : ""}>
                  {net_income_change >= 0 ? "+" : ""}{formatCurrency(net_income_change)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Benefits breakdown */}
        {(Object.keys(before_result.benefits).length > 0 || Object.keys(after_result.benefits).length > 0) && (
          <div className="benefits-section">
            <h3>Benefits Breakdown</h3>
            <div className="benefits-grid">
              {Object.entries({ ...before_result.benefits, ...after_result.benefits })
                .filter(([_, v]) => v > 0 || (before_result.benefits[_] || 0) > 0)
                .map(([key]) => {
                  const beforeVal = before_result.benefits[key] || 0;
                  const afterVal = after_result.benefits[key] || 0;
                  const change = afterVal - beforeVal;
                  return (
                    <div key={key} className="benefit-item">
                      <span className="benefit-name">{key.replace(/_/g, " ")}</span>
                      <span className="benefit-before">{formatCurrency(beforeVal)}</span>
                      <span className="benefit-arrow">→</span>
                      <span className="benefit-after">{formatCurrency(afterVal)}</span>
                      <span className={`benefit-change ${change > 0 ? "positive" : change < 0 ? "negative" : ""}`}>
                        {change >= 0 ? "+" : ""}{formatCurrency(change)}
                      </span>
                    </div>
                  );
                })}
            </div>
          </div>
        )}

        {/* Marginal rates */}
        <div className="rates-section">
          <h3>Tax Rates</h3>
          <div className="rates-grid">
            <div className="rate-item">
              <span className="rate-label">Effective Tax Rate</span>
              <div className="rate-comparison">
                <span>{formatPercent(before_result.effective_tax_rate)}</span>
                <span className="rate-arrow">→</span>
                <span>{formatPercent(after_result.effective_tax_rate)}</span>
              </div>
            </div>
            <div className="rate-item">
              <span className="rate-label">Marginal Tax Rate</span>
              <div className="rate-comparison">
                <span>{formatPercent(before_result.marginal_tax_rate)}</span>
                <span className="rate-arrow">→</span>
                <span>{formatPercent(after_result.marginal_tax_rate)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Try another scenario */}
        <div className="try-another">
          <h3>Try Another Scenario</h3>
          <div className="scenario-buttons">
            {LIFE_EVENT_SCENARIOS.filter(s => s.id !== selectedScenario.id).map((scenario) => (
              <button
                key={scenario.id}
                className="scenario-btn"
                onClick={() => runScenario(scenario)}
                disabled={isLoading}
              >
                <span>{scenario.emoji}</span>
                <span>{scenario.name}</span>
              </button>
            ))}
          </div>
        </div>

        <p className="disclaimer">
          Tax calculations powered by PolicyEngine-US. Results are estimates for educational purposes.
          Consult a tax professional for personalized advice.
        </p>
      </div>
    );
  };

  return (
    <div className="life-event-page">
      <header className="page-header">
        <a href={HOME_URL} className="logo">
          <img src="/logo.svg" alt="EggNest" height="28" />
        </a>
        <span className="page-title">Tax & Benefits Calculator</span>
        <a href="#/" className="nav-link">Retirement Simulator</a>
      </header>

      <div className="page-content">
        {showSetup ? renderSetup() : renderResults()}
      </div>

      {isLoading && (
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <span>Calculating...</span>
        </div>
      )}
    </div>
  );
}
