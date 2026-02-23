"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import {
  compareLifeEvent,
  calculateHousehold,
  type HouseholdInput,
  type PersonInput,
  type HouseholdResult,
  type LifeEventComparison,
} from "../../lib/api";
import {
  validateLifeEventInput,
  getFieldError,
  type ValidationError,
} from "../../lib/validation";
import { US_STATES, HOME_URL } from "../../lib/constants";

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
    id: "having-child", name: "Having a Child", description: "See how a new child affects your taxes and benefits", emoji: "\uD83D\uDC76",
    beforeSetup: (base) => ({ ...base, filing_status: "single" as FilingStatus, people: [{ ...base.people[0], is_tax_unit_head: true }] }),
    afterSetup: (base) => ({ ...base, filing_status: "head_of_household" as FilingStatus, people: [{ ...base.people[0], is_tax_unit_head: true }, { age: 0, employment_income: 0, is_tax_unit_dependent: true }] }),
  },
  {
    id: "getting-married", name: "Getting Married", description: "Compare single vs married filing jointly", emoji: "\uD83D\uDC92",
    beforeSetup: (base) => ({ ...base, filing_status: "single" as FilingStatus, people: [{ ...base.people[0], is_tax_unit_head: true }] }),
    afterSetup: (base) => ({ ...base, filing_status: "married_filing_jointly" as FilingStatus, people: [{ ...base.people[0], is_tax_unit_head: true }, { age: base.people[0].age - 2, employment_income: Math.round((base.people[0].employment_income || 50000) * 0.8), is_tax_unit_spouse: true }] }),
  },
  {
    id: "income-change", name: "Getting a Raise", description: "See how higher income changes your taxes", emoji: "\uD83D\uDCC8",
    beforeSetup: (base) => base,
    afterSetup: (base) => ({ ...base, people: base.people.map((p, i) => i === 0 ? { ...p, employment_income: Math.round((p.employment_income || 50000) * 1.25) } : p) }),
  },
  {
    id: "retirement", name: "Retiring", description: "Compare working vs retirement income", emoji: "\uD83C\uDFD6\uFE0F",
    beforeSetup: (base) => base,
    afterSetup: (base) => ({ ...base, people: base.people.map((p, i) => i === 0 ? { ...p, employment_income: 0, social_security: 30000, pension_income: 24000 } : p) }),
  },
];

function formatCurrencyLocal(value: number): string {
  const absValue = Math.abs(value);
  if (absValue >= 1_000_000) return `${value < 0 ? "-" : ""}$${(absValue / 1_000_000).toFixed(1)}M`;
  if (absValue >= 1_000) return `${value < 0 ? "-" : ""}$${(absValue / 1_000).toFixed(0)}K`;
  return `${value < 0 ? "-" : ""}$${absValue.toFixed(0)}`;
}

function formatPercentLocal(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

const fieldCls = "space-y-1.5";
const labelCls = "block text-sm font-medium text-[var(--color-text-muted)]";
const inputCls = "w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm transition-colors focus:border-[var(--color-primary)] focus:outline-none";
const selectCls = inputCls;
const sectionCls = "section-card";

export default function LifeEventPage() {
  const [baseHousehold, setBaseHousehold] = useState<HouseholdInput>({
    state: "CA", year: 2025, filing_status: "single",
    people: [{ age: 35, employment_income: 75000, is_tax_unit_head: true }],
  });

  const [selectedScenario, setSelectedScenario] = useState<LifeEventScenario | null>(null);
  const [currentResult, setCurrentResult] = useState<HouseholdResult | null>(null);
  const [comparisonResult, setComparisonResult] = useState<LifeEventComparison | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSetup, setShowSetup] = useState(true);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [touchedFields, setTouchedFields] = useState<Set<string>>(new Set());

  const markTouched = useCallback((field: string) => {
    setTouchedFields((prev) => { const next = new Set(prev); next.add(field); return next; });
  }, []);

  const validateAndUpdate = useCallback((household: HouseholdInput) => {
    const errors = validateLifeEventInput(household);
    setValidationErrors(errors);
    return errors;
  }, []);

  const updateBasePerson = (field: keyof PersonInput, value: number | boolean) => {
    const updated = { ...baseHousehold, people: baseHousehold.people.map((p, i) => i === 0 ? { ...p, [field]: value } : p) };
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
    if (errors.length > 0) { setTouchedFields(new Set(errors.map((e) => e.field))); return; }
    setIsLoading(true); setError(null);
    try { const result = await calculateHousehold(baseHousehold); setCurrentResult(result); }
    catch (err) { setError(err instanceof Error ? err.message : "Calculation failed"); }
    finally { setIsLoading(false); }
  };

  const runScenario = async (scenario: LifeEventScenario) => {
    const errors = validateAndUpdate(baseHousehold);
    if (errors.length > 0) { setTouchedFields(new Set(errors.map((e) => e.field))); return; }
    setIsLoading(true); setError(null); setSelectedScenario(scenario); setComparisonResult(null);
    try {
      const before = scenario.beforeSetup(baseHousehold);
      const after = scenario.afterSetup(baseHousehold);
      const result = await compareLifeEvent(before, after, scenario.name);
      setComparisonResult(result); setShowSetup(false);
    }
    catch (err) { setError(err instanceof Error ? err.message : "Comparison failed"); }
    finally { setIsLoading(false); }
  };

  const renderSetup = () => (
    <div className="space-y-8">
      {/* Page hero */}
      <div className="text-center">
        <div className="mb-3 inline-block rounded-full border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] px-4 py-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-primary)]">
          PolicyEngine-powered
        </div>
        <h1 className="text-2xl font-semibold text-[var(--color-text)] md:text-3xl" style={{ letterSpacing: "-0.03em" }}>
          How will life changes
          <br />
          <span className="bg-gradient-golden bg-clip-text text-transparent">affect your taxes?</span>
        </h1>
      </div>

      <div className={sectionCls}>
        <h2 className="text-lg font-semibold">Your current situation</h2>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">Tell us about yourself to see how life events affect your taxes</p>

        <form className="mt-6 space-y-5" onSubmit={(e) => { e.preventDefault(); calculateCurrent(); }} noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className={fieldCls}>
              <label htmlFor="person-age" className={labelCls}>Your age</label>
              <input id="person-age" type="number" value={baseHousehold.people[0].age}
                onChange={(e) => updateBasePerson("age", Number(e.target.value))}
                onBlur={() => markTouched("people[0].age")} min={18} max={100} className={inputCls}
                aria-invalid={fieldError("people[0].age") ? "true" : undefined} />
              {fieldError("people[0].age") && <p className="text-xs text-[var(--color-danger)]" role="alert">{fieldError("people[0].age")}</p>}
            </div>
            <div className={fieldCls}>
              <label htmlFor="person-state" className={labelCls}>State</label>
              <select id="person-state" value={baseHousehold.state}
                onChange={(e) => updateHouseholdField("state", e.target.value)}
                onBlur={() => markTouched("state")} className={selectCls}>
                {US_STATES.map((st) => <option key={st} value={st}>{st}</option>)}
              </select>
              {fieldError("state") && <p className="text-xs text-[var(--color-danger)]" role="alert">{fieldError("state")}</p>}
            </div>
          </div>
          <div className={fieldCls}>
            <label htmlFor="person-income" className={labelCls}>Annual employment income</label>
            <div className="flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white focus-within:border-[var(--color-primary)]">
              <span className="pl-3 text-sm text-[var(--color-text-light)]" aria-hidden="true">$</span>
              <input id="person-income" type="number" value={baseHousehold.people[0].employment_income || 0}
                onChange={(e) => updateBasePerson("employment_income", Number(e.target.value))}
                onBlur={() => markTouched("people[0].employment_income")} min={0} step={5000}
                className="w-full border-none bg-transparent px-2 py-2.5 text-sm focus:outline-none" />
            </div>
            {fieldError("people[0].employment_income") && <p className="text-xs text-[var(--color-danger)]" role="alert">{fieldError("people[0].employment_income")}</p>}
          </div>
          <div className={fieldCls}>
            <label htmlFor="filing-status" className={labelCls}>Filing status</label>
            <select id="filing-status" value={baseHousehold.filing_status}
              onChange={(e) => updateHouseholdField("filing_status", e.target.value)} className={selectCls}>
              <option value="single">Single</option>
              <option value="married_filing_jointly">Married Filing Jointly</option>
              <option value="head_of_household">Head of Household</option>
            </select>
          </div>
          <button type="submit"
            className="w-full rounded-[var(--radius-md)] bg-gradient-golden py-3.5 text-sm font-semibold text-white shadow-[var(--shadow-sm)] transition-all hover:shadow-[var(--shadow-md)] hover:brightness-110 disabled:opacity-50"
            disabled={isLoading || hasErrors}>
            {isLoading ? "Calculating..." : "Calculate current taxes"}
          </button>
        </form>

        {currentResult && (
          <div className="mt-6">
            <div className="divider-fade mb-5" />
            <h3 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-light)]">Your current tax situation</h3>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {[
                { label: "Total income", value: formatCurrencyLocal(currentResult.total_income) },
                { label: "Federal tax", value: formatCurrencyLocal(currentResult.federal_income_tax) },
                { label: "State tax", value: formatCurrencyLocal(currentResult.state_income_tax) },
                { label: "FICA", value: formatCurrencyLocal(currentResult.payroll_tax) },
                { label: "Net income", value: formatCurrencyLocal(currentResult.net_income), highlight: true },
                { label: "Effective rate", value: formatPercentLocal(currentResult.effective_tax_rate) },
              ].map(({ label, value, highlight }) => (
                <div key={label} className={`metric-card ${highlight ? "metric-card-primary bg-[var(--color-primary-50)]" : ""}`}>
                  <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">{label}</div>
                  <div className={`mt-1 text-lg font-bold tabular-nums ${highlight ? "text-[var(--color-primary)]" : "text-[var(--color-text)]"}`}>{value}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className={sectionCls}>
        <h2 className="text-lg font-semibold">Explore life events</h2>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">See how major life changes affect your taxes and benefits</p>
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4" role="group" aria-label="Life event scenarios">
          {LIFE_EVENT_SCENARIOS.map((scenario) => (
            <button key={scenario.id}
              className="flex flex-col items-center gap-2.5 rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-card)] p-5 text-center transition-all hover:border-[var(--color-primary-200)] hover:shadow-[var(--shadow-md)] hover:-translate-y-0.5 disabled:opacity-50"
              onClick={() => runScenario(scenario)} disabled={isLoading || hasErrors}
              aria-label={`${scenario.name}: ${scenario.description}`}>
              <span className="flex h-11 w-11 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--color-primary-50)] text-xl" aria-hidden="true">{scenario.emoji}</span>
              <span className="text-sm font-semibold text-[var(--color-text)]">{scenario.name}</span>
              <span className="text-xs text-[var(--color-text-muted)]">{scenario.description}</span>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-light)] p-4 text-sm text-[var(--color-danger)]" role="alert">
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  );

  const renderResults = () => {
    if (!comparisonResult || !selectedScenario) return null;
    const { before_result, after_result, net_income_change } = comparisonResult;
    const isBetterOff = net_income_change > 0;

    return (
      <div className="space-y-6">
        <button className="inline-flex items-center gap-2 text-sm font-medium text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)]"
          onClick={() => setShowSetup(true)} aria-label="Back to setup">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4" aria-hidden="true"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
          Back to Setup
        </button>

        <div className="text-center">
          <span className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-[var(--radius-md)] bg-[var(--color-primary-50)] text-3xl" aria-hidden="true">{selectedScenario.emoji}</span>
          <h2 className="text-2xl font-semibold">{selectedScenario.name}</h2>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">{selectedScenario.description}</p>
        </div>

        {/* Impact banner */}
        <div className={`overflow-hidden rounded-[var(--radius-lg)] text-center ${isBetterOff ? "border border-[var(--color-success)]" : "border border-[var(--color-danger)]"}`}
          role="status">
          <div className="h-1" style={{ background: isBetterOff ? "var(--color-success)" : "var(--color-danger)" }} />
          <div className={`p-6 ${isBetterOff ? "bg-[var(--color-success-light)]" : "bg-[var(--color-danger-light)]"}`}>
            <div className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">Net income impact</div>
            <div className={`mt-2 text-3xl font-bold tabular-nums ${isBetterOff ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}`}>
              {net_income_change >= 0 ? "+" : ""}{formatCurrencyLocal(net_income_change)}
              <span className="ml-1 text-base font-normal">{isBetterOff ? " more" : " less"} per year</span>
            </div>
          </div>
        </div>

        {/* Comparison table */}
        <div className={sectionCls}>
          <div className="overflow-x-auto">
            <table className="w-full table-auto-style">
              <thead><tr><th>Category</th><th>Before</th><th>After</th><th>Change</th></tr></thead>
              <tbody>
                {[
                  { label: "Total Income", before: before_result.total_income, after: after_result.total_income, positive: "more" as const },
                  { label: "Federal Tax", before: before_result.federal_income_tax, after: after_result.federal_income_tax, positive: "less" as const },
                  { label: "State Tax", before: before_result.state_income_tax, after: after_result.state_income_tax, positive: "less" as const },
                  { label: "Payroll Tax", before: before_result.payroll_tax, after: after_result.payroll_tax, positive: "less" as const },
                  { label: "Total Taxes", before: before_result.total_taxes, after: after_result.total_taxes, positive: "less" as const, bold: true },
                  { label: "Total Benefits", before: before_result.total_benefits, after: after_result.total_benefits, positive: "more" as const },
                  { label: "Net Income", before: before_result.net_income, after: after_result.net_income, positive: "more" as const, bold: true },
                ].map(({ label, before, after, positive, bold }) => {
                  const change = after - before;
                  const isGood = positive === "more" ? change > 0 : change < 0;
                  return (
                    <tr key={label} className={bold ? "font-semibold !bg-[var(--color-gray-50)]" : ""}>
                      <td>{label}</td>
                      <td>{formatCurrencyLocal(before)}</td>
                      <td>{formatCurrencyLocal(after)}</td>
                      <td style={{ color: isGood ? "#10b981" : change !== 0 ? "#ef4444" : "inherit" }}>
                        {change >= 0 ? "+" : ""}{formatCurrencyLocal(change)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Benefits breakdown */}
        {(Object.keys(before_result.benefits).length > 0 || Object.keys(after_result.benefits).length > 0) && (
          <div className={sectionCls}>
            <h3 className="text-lg font-semibold mb-4">Benefits breakdown</h3>

            <div className="space-y-2">
              {Object.entries({ ...before_result.benefits, ...after_result.benefits })
                .filter(([key, v]) => v > 0 || (before_result.benefits[key] || 0) > 0)
                .map(([key]) => {
                  const beforeVal = before_result.benefits[key] || 0;
                  const afterVal = after_result.benefits[key] || 0;
                  const change = afterVal - beforeVal;
                  return (
                    <div key={key} className="flex items-center justify-between text-sm">
                      <span className="text-[var(--color-text-muted)] capitalize">{key.replace(/_/g, " ")}</span>
                      <div className="flex items-center gap-3">
                        <span>{formatCurrencyLocal(beforeVal)}</span>
                        <span className="text-[var(--color-text-light)]" aria-hidden="true">&rarr;</span>
                        <span>{formatCurrencyLocal(afterVal)}</span>
                        <span className={`font-medium ${change > 0 ? "text-[var(--color-success)]" : change < 0 ? "text-[var(--color-danger)]" : ""}`}>
                          {change >= 0 ? "+" : ""}{formatCurrencyLocal(change)}
                        </span>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        )}

        {/* Tax rates */}
        <div className={sectionCls}>
          <h3 className="text-lg font-semibold mb-4">Tax rates</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            {[
              { label: "Effective tax rate", before: formatPercentLocal(before_result.effective_tax_rate), after: formatPercentLocal(after_result.effective_tax_rate) },
              { label: "Marginal tax rate", before: formatPercentLocal(before_result.marginal_tax_rate), after: formatPercentLocal(after_result.marginal_tax_rate) },
            ].map(({ label, before, after }) => (
              <div key={label} className="rounded-[var(--radius-md)] bg-[var(--color-gray-50)] p-4">
                <div className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-light)]">{label}</div>
                <div className="mt-2 flex items-center gap-3 text-lg font-bold tabular-nums">
                  <span>{before}</span>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4 text-[var(--color-text-light)]" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                  <span>{after}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Try another */}
        <div className={sectionCls}>
          <h3 className="text-lg font-semibold mb-3">Try another scenario</h3>
          <div className="flex flex-wrap gap-3">
            {LIFE_EVENT_SCENARIOS.filter(s => s.id !== selectedScenario.id).map((scenario) => (
              <button key={scenario.id}
                className="inline-flex items-center gap-2 rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-white px-4 py-2.5 text-sm font-medium shadow-[var(--shadow-sm)] transition-all hover:border-[var(--color-primary-200)] hover:shadow-[var(--shadow-md)] hover:-translate-y-0.5 disabled:opacity-50"
                onClick={() => runScenario(scenario)} disabled={isLoading}>
                <span className="flex h-6 w-6 items-center justify-center rounded bg-[var(--color-primary-50)] text-xs" aria-hidden="true">{scenario.emoji}</span>
                <span>{scenario.name}</span>
              </button>
            ))}
          </div>
        </div>

        <p className="text-xs text-center text-[var(--color-text-light)]">
          Tax calculations powered by PolicyEngine-US. Results are estimates for educational purposes. Consult a tax professional for personalized advice.
        </p>
      </div>
    );
  };

  return (
    <div className="min-h-screen">
      <header className="header-glass sticky top-0 z-50 border-b border-[var(--color-border-light)]">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 md:px-6">
          <a href={HOME_URL} className="flex items-center gap-2.5 transition-opacity hover:opacity-80" aria-label="EggNest home">
            <img src="/logo.svg" alt="EggNest" height="28" className="h-7" />
          </a>
          <span className="hidden text-xs font-semibold uppercase tracking-widest text-[var(--color-text-muted)] sm:block">Tax & Benefits Calculator</span>
          <Link href="/" className="rounded-full border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] px-4 py-1.5 text-xs font-semibold text-[var(--color-primary)] transition-all hover:bg-[var(--color-primary)] hover:text-white hover:border-[var(--color-primary)]">
            Retirement Simulator
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10 md:px-6 md:py-12">
        {showSetup ? renderSetup() : renderResults()}
      </main>

      {isLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/10 backdrop-blur-sm" role="status" aria-label="Calculating">
          <div className="flex flex-col items-center gap-3 rounded-[var(--radius-xl)] border border-[var(--color-border-light)] bg-white px-8 py-6 shadow-[var(--shadow-xl)]">
            <div className="h-8 w-8 animate-spin-slow rounded-full border-[3px] border-[var(--color-primary-200)] border-t-[var(--color-primary)]" aria-hidden="true" />
            <div className="text-center">
              <span className="text-sm font-semibold text-[var(--color-text)]">Calculating taxes...</span>
              <div className="mt-0.5 text-xs text-[var(--color-text-light)]">Powered by PolicyEngine</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
