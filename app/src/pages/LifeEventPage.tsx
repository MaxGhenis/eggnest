import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  compareLifeEvent,
  calculateHousehold,
  type HouseholdInput,
  type PersonInput,
  type HouseholdResult,
  type LifeEventComparison,
} from "../lib/api";
import {
  validateLifeEventInput,
  getFieldError,
  type ValidationError,
} from "../lib/validation";
import { US_STATES, HOME_URL } from "../lib/constants";
// Note: colors available from ../lib/design-tokens if needed
import "../styles/LifeEvent.css";

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
    emoji: "\uD83D\uDC76",
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
    emoji: "\uD83D\uDC92",
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
    emoji: "\uD83D\uDCC8",
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
    emoji: "\uD83C\uDFD6\uFE0F",
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

  // Validation state
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [touchedFields, setTouchedFields] = useState<Set<string>>(new Set());

  const markTouched = useCallback((field: string) => {
    setTouchedFields((prev) => {
      const next = new Set(prev);
      next.add(field);
      return next;
    });
  }, []);

  const validateAndUpdate = useCallback((household: HouseholdInput) => {
    const errors = validateLifeEventInput(household);
    setValidationErrors(errors);
    return errors;
  }, []);

  const updateBasePerson = (field: keyof PersonInput, value: number | boolean) => {
    const updated = {
      ...baseHousehold,
      people: baseHousehold.people.map((p, i) =>
        i === 0 ? { ...p, [field]: value } : p
      ),
    };
    setBaseHousehold(updated);
    validateAndUpdate(updated);
  };

  const updateHouseholdField = (field: string, value: string) => {
    const updated = { ...baseHousehold, [field]: value };
    setBaseHousehold(updated);
    validateAndUpdate(updated);
  };

  const hasErrors = validationErrors.length > 0;

  const fieldError = (field: string): string | undefined => {
    if (!touchedFields.has(field)) return undefined;
    return getFieldError(validationErrors, field);
  };

  const calculateCurrent = async () => {
    const errors = validateAndUpdate(baseHousehold);
    if (errors.length > 0) {
      setTouchedFields(new Set(errors.map((e) => e.field)));
      return;
    }

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
    const errors = validateAndUpdate(baseHousehold);
    if (errors.length > 0) {
      setTouchedFields(new Set(errors.map((e) => e.field)));
      return;
    }

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
      <section className="setup-section" aria-labelledby="setup-heading">
        <h2 id="setup-heading">Your current situation</h2>
        <p className="setup-subtitle">Tell us about yourself to see how life events affect your taxes</p>

        <form
          className="setup-form"
          onSubmit={(e) => {
            e.preventDefault();
            calculateCurrent();
          }}
          noValidate
        >
          <div className="form-row">
            <div className="form-field">
              <label htmlFor="person-age">Your age</label>
              <input
                id="person-age"
                type="number"
                value={baseHousehold.people[0].age}
                onChange={(e) => updateBasePerson("age", Number(e.target.value))}
                onBlur={() => markTouched("people[0].age")}
                min={18}
                max={100}
                aria-invalid={fieldError("people[0].age") ? "true" : undefined}
                aria-describedby={fieldError("people[0].age") ? "person-age-error" : undefined}
              />
              {fieldError("people[0].age") && (
                <p id="person-age-error" className="field-error" role="alert">
                  {fieldError("people[0].age")}
                </p>
              )}
            </div>
            <div className="form-field">
              <label htmlFor="person-state">State</label>
              <select
                id="person-state"
                value={baseHousehold.state}
                onChange={(e) => updateHouseholdField("state", e.target.value)}
                onBlur={() => markTouched("state")}
                aria-invalid={fieldError("state") ? "true" : undefined}
                aria-describedby={fieldError("state") ? "state-error" : undefined}
              >
                {US_STATES.map((st) => (
                  <option key={st} value={st}>{st}</option>
                ))}
              </select>
              {fieldError("state") && (
                <p id="state-error" className="field-error" role="alert">
                  {fieldError("state")}
                </p>
              )}
            </div>
          </div>

          <div className="form-field">
            <label htmlFor="person-income">Annual employment income</label>
            <div className="input-prefix">
              <span aria-hidden="true">$</span>
              <input
                id="person-income"
                type="number"
                value={baseHousehold.people[0].employment_income || 0}
                onChange={(e) => updateBasePerson("employment_income", Number(e.target.value))}
                onBlur={() => markTouched("people[0].employment_income")}
                min={0}
                step={5000}
                aria-invalid={fieldError("people[0].employment_income") ? "true" : undefined}
                aria-describedby={fieldError("people[0].employment_income") ? "person-income-error" : undefined}
              />
            </div>
            {fieldError("people[0].employment_income") && (
              <p id="person-income-error" className="field-error" role="alert">
                {fieldError("people[0].employment_income")}
              </p>
            )}
          </div>

          <div className="form-field">
            <label htmlFor="filing-status">Filing status</label>
            <select
              id="filing-status"
              value={baseHousehold.filing_status}
              onChange={(e) => updateHouseholdField("filing_status", e.target.value)}
              aria-label="Tax filing status"
            >
              <option value="single">Single</option>
              <option value="married_filing_jointly">Married Filing Jointly</option>
              <option value="head_of_household">Head of Household</option>
            </select>
          </div>

          <button
            type="submit"
            className="btn-calculate"
            disabled={isLoading || hasErrors}
            aria-label={hasErrors ? "Fix form errors before calculating" : "Calculate current taxes"}
          >
            {isLoading ? "Calculating..." : "Calculate Current Taxes"}
          </button>
        </form>

        {currentResult && (
          <section className="current-summary" aria-labelledby="current-summary-heading">
            <h3 id="current-summary-heading">Your current tax situation</h3>
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
          </section>
        )}
      </section>

      <section className="setup-section" aria-labelledby="scenarios-heading">
        <h2 id="scenarios-heading">Explore life events</h2>
        <p className="setup-subtitle">See how major life changes affect your taxes and benefits</p>

        <div className="scenario-grid" role="group" aria-label="Life event scenarios">
          {LIFE_EVENT_SCENARIOS.map((scenario) => (
            <button
              key={scenario.id}
              className="scenario-card"
              onClick={() => runScenario(scenario)}
              disabled={isLoading || hasErrors}
              aria-label={`${scenario.name}: ${scenario.description}`}
            >
              <span className="scenario-emoji" aria-hidden="true">{scenario.emoji}</span>
              <span className="scenario-name">{scenario.name}</span>
              <span className="scenario-desc">{scenario.description}</span>
            </button>
          ))}
        </div>
      </section>

      {error && (
        <div className="error-banner" role="alert">
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
        <button className="back-button" onClick={() => setShowSetup(true)} aria-label="Back to setup">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Back to Setup
        </button>

        <div className="results-header">
          <span className="results-emoji" aria-hidden="true">{selectedScenario.emoji}</span>
          <h2>{selectedScenario.name}</h2>
          <p>{selectedScenario.description}</p>
        </div>

        {/* Main impact summary */}
        <div
          className={`impact-banner ${isBetterOff ? "positive" : "negative"}`}
          role="status"
          aria-label={`Net income impact: ${net_income_change >= 0 ? "+" : ""}${formatCurrency(net_income_change)} per year`}
        >
          <div className="impact-label">Net Income Impact</div>
          <div className="impact-value">
            {net_income_change >= 0 ? "+" : ""}{formatCurrency(net_income_change)}
            <span className="impact-direction">{isBetterOff ? " more" : " less"} per year</span>
          </div>
        </div>

        {/* Detailed comparison */}
        <section className="comparison-table-container" aria-labelledby="comparison-heading">
          <h3 id="comparison-heading" className="sr-only">Detailed tax comparison</h3>
          <table className="comparison-table" aria-label="Before and after tax comparison">
            <thead>
              <tr>
                <th scope="col">Category</th>
                <th scope="col">Before</th>
                <th scope="col">After</th>
                <th scope="col">Change</th>
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
        </section>

        {/* Benefits breakdown */}
        {(Object.keys(before_result.benefits).length > 0 || Object.keys(after_result.benefits).length > 0) && (
          <section className="benefits-section" aria-labelledby="benefits-heading">
            <h3 id="benefits-heading">Benefits breakdown</h3>
            <div className="benefits-grid">
              {Object.entries({ ...before_result.benefits, ...after_result.benefits })
                .filter(([key, v]) => v > 0 || (before_result.benefits[key] || 0) > 0)
                .map(([key]) => {
                  const beforeVal = before_result.benefits[key] || 0;
                  const afterVal = after_result.benefits[key] || 0;
                  const change = afterVal - beforeVal;
                  return (
                    <div key={key} className="benefit-item">
                      <span className="benefit-name">{key.replace(/_/g, " ")}</span>
                      <span className="benefit-before">{formatCurrency(beforeVal)}</span>
                      <span className="benefit-arrow" aria-hidden="true">{"\u2192"}</span>
                      <span className="benefit-after">{formatCurrency(afterVal)}</span>
                      <span className={`benefit-change ${change > 0 ? "positive" : change < 0 ? "negative" : ""}`}>
                        {change >= 0 ? "+" : ""}{formatCurrency(change)}
                      </span>
                    </div>
                  );
                })}
            </div>
          </section>
        )}

        {/* Marginal rates */}
        <section className="rates-section" aria-labelledby="rates-heading">
          <h3 id="rates-heading">Tax rates</h3>
          <div className="rates-grid">
            <div className="rate-item">
              <span className="rate-label">Effective Tax Rate</span>
              <div className="rate-comparison">
                <span>{formatPercent(before_result.effective_tax_rate)}</span>
                <span className="rate-arrow" aria-hidden="true">{"\u2192"}</span>
                <span>{formatPercent(after_result.effective_tax_rate)}</span>
              </div>
            </div>
            <div className="rate-item">
              <span className="rate-label">Marginal Tax Rate</span>
              <div className="rate-comparison">
                <span>{formatPercent(before_result.marginal_tax_rate)}</span>
                <span className="rate-arrow" aria-hidden="true">{"\u2192"}</span>
                <span>{formatPercent(after_result.marginal_tax_rate)}</span>
              </div>
            </div>
          </div>
        </section>

        {/* Try another scenario */}
        <section className="try-another" aria-labelledby="try-another-heading">
          <h3 id="try-another-heading">Try another scenario</h3>
          <div className="scenario-buttons">
            {LIFE_EVENT_SCENARIOS.filter(s => s.id !== selectedScenario.id).map((scenario) => (
              <button
                key={scenario.id}
                className="scenario-btn"
                onClick={() => runScenario(scenario)}
                disabled={isLoading}
                aria-label={`Run ${scenario.name} scenario`}
              >
                <span aria-hidden="true">{scenario.emoji}</span>
                <span>{scenario.name}</span>
              </button>
            ))}
          </div>
        </section>

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
        <a href={HOME_URL} className="logo" aria-label="EggNest home">
          <img src="/logo.svg" alt="EggNest" height="28" />
        </a>
        <span className="page-title">Tax & Benefits Calculator</span>
        <Link to="/" className="nav-link" aria-label="Go to retirement simulator">Retirement Simulator</Link>
      </header>

      <main className="page-content">
        {showSetup ? renderSetup() : renderResults()}
      </main>

      {isLoading && (
        <div className="loading-overlay" role="status" aria-label="Calculating">
          <div className="loading-spinner" aria-hidden="true" />
          <span>Calculating...</span>
        </div>
      )}
    </div>
  );
}
