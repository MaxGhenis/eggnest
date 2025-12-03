import { useState } from "react";
import { Link } from "react-router-dom";
import Plot from "react-plotly.js";
import { runSimulation, compareAnnuity, type SimulationInput, type SimulationResult, type SpouseInput, type AnnuityInput } from "../lib/api";
import "../styles/Simulator.css";

const US_STATES = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
];

const DEFAULT_PARAMS: SimulationInput = {
  initial_capital: 500000,
  annual_spending: 60000,
  current_age: 65,
  max_age: 95,
  gender: "male",
  social_security_monthly: 2000,
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

// Annuity comparison result type
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
  const [annuityResult, setAnnuityResult] = useState<AnnuityComparisonResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Spouse state
  const [spouse, setSpouse] = useState<SpouseInput>({
    age: 63,
    gender: "female",
    social_security_monthly: 1500,
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

  const handleSimulate = async () => {
    setIsLoading(true);
    setError(null);
    setAnnuityResult(null);

    try {
      // Build full params with spouse and annuity
      const fullParams: SimulationInput = {
        ...params,
        spouse: params.has_spouse ? spouse : undefined,
        annuity: params.has_annuity ? annuity : undefined,
      };

      // If comparing to annuity, use the compare endpoint
      if (params.has_annuity && annuity.monthly_payment > 0) {
        const comparison = await compareAnnuity(
          fullParams,
          annuity.monthly_payment,
          annuity.guarantee_years
        );
        setResult(comparison.simulation_result);
        setAnnuityResult(comparison);
      } else {
        const simResult = await runSimulation(fullParams);
        setResult(simResult);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed");
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  const successColor =
    result && result.success_rate >= 0.9
      ? "#10b981"
      : result && result.success_rate >= 0.75
        ? "#f59e0b"
        : "#ef4444";

  // Calculate ages for x-axis
  const ages = result ? result.percentile_paths.p50.map((_, i) => params.current_age + i) : [];

  return (
    <div className="simulator">
      {/* Header */}
      <header className="sim-header">
        <Link to="/" className="sim-logo">
          FinSim
        </Link>
        <span className="sim-title">Retirement Simulator</span>
      </header>

      <div className="sim-layout">
        {/* Sidebar */}
        <aside className="sim-sidebar">
          <div className="sidebar-section">
            <h3>Demographics</h3>
            <div className="input-row">
              <div className="input-group">
                <label>Current Age</label>
                <input
                  type="number"
                  value={params.current_age}
                  onChange={(e) => updateParam("current_age", Number(e.target.value))}
                  min={18}
                  max={100}
                />
              </div>
              <div className="input-group">
                <label>Planning To Age</label>
                <input
                  type="number"
                  value={params.max_age}
                  onChange={(e) => updateParam("max_age", Number(e.target.value))}
                  min={params.current_age + 5}
                  max={120}
                />
              </div>
            </div>
            <div className="input-row">
              <div className="input-group">
                <label>Gender</label>
                <select
                  value={params.gender}
                  onChange={(e) => updateParam("gender", e.target.value as "male" | "female")}
                >
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                </select>
              </div>
              <div className="input-group">
                <label>State</label>
                <select
                  value={params.state}
                  onChange={(e) => updateParam("state", e.target.value)}
                >
                  {US_STATES.map((st) => (
                    <option key={st} value={st}>{st}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="input-group">
              <label>Filing Status</label>
              <select
                value={params.filing_status}
                onChange={(e) => updateParam("filing_status", e.target.value as SimulationInput["filing_status"])}
              >
                <option value="single">Single</option>
                <option value="married_filing_jointly">Married (Joint)</option>
                <option value="head_of_household">Head of Household</option>
              </select>
            </div>
          </div>

          <div className="sidebar-section">
            <h3>Assets & Spending</h3>
            <div className="input-group">
              <label>Current Portfolio</label>
              <div className="input-with-prefix">
                <span>$</span>
                <input
                  type="number"
                  value={params.initial_capital}
                  onChange={(e) => updateParam("initial_capital", Number(e.target.value))}
                  min={0}
                  step={10000}
                />
              </div>
            </div>
            <div className="input-group">
              <label>Annual Spending Need</label>
              <div className="input-with-prefix">
                <span>$</span>
                <input
                  type="number"
                  value={params.annual_spending}
                  onChange={(e) => updateParam("annual_spending", Number(e.target.value))}
                  min={0}
                  step={1000}
                />
              </div>
              <span className="input-hint">
                ${(params.annual_spending / 12).toLocaleString()}/month
              </span>
            </div>
          </div>

          <div className="sidebar-section">
            <h3>Income Sources</h3>
            <div className="input-group">
              <label>Monthly Social Security</label>
              <div className="input-with-prefix">
                <span>$</span>
                <input
                  type="number"
                  value={params.social_security_monthly}
                  onChange={(e) => updateParam("social_security_monthly", Number(e.target.value))}
                  min={0}
                  step={100}
                />
              </div>
              <span className="input-hint">
                Starts at retirement with COLA
              </span>
            </div>
            <div className="input-group">
              <label>Annual Pension</label>
              <div className="input-with-prefix">
                <span>$</span>
                <input
                  type="number"
                  value={params.pension_annual}
                  onChange={(e) => updateParam("pension_annual", Number(e.target.value))}
                  min={0}
                  step={1000}
                />
              </div>
            </div>
            <div className="input-group">
              <label>Annual Employment Income</label>
              <div className="input-with-prefix">
                <span>$</span>
                <input
                  type="number"
                  value={params.employment_income}
                  onChange={(e) => updateParam("employment_income", Number(e.target.value))}
                  min={0}
                  step={5000}
                />
              </div>
              {params.employment_income > 0 && (
                <span className="input-hint">
                  Until age {params.retirement_age}
                </span>
              )}
            </div>
            {params.employment_income > 0 && (
              <div className="input-group">
                <label>Retirement Age</label>
                <input
                  type="number"
                  value={params.retirement_age}
                  onChange={(e) => updateParam("retirement_age", Number(e.target.value))}
                  min={params.current_age}
                  max={80}
                />
              </div>
            )}
          </div>

          {/* Spouse Section */}
          <div className="sidebar-section">
            <h3>Spouse/Partner</h3>
            <div className="input-group">
              <label>
                <input
                  type="checkbox"
                  checked={params.has_spouse}
                  onChange={(e) => updateParam("has_spouse", e.target.checked)}
                  style={{ marginRight: "0.5rem" }}
                />
                Include Spouse
              </label>
            </div>
            {params.has_spouse && (
              <>
                <div className="input-row">
                  <div className="input-group">
                    <label>Spouse Age</label>
                    <input
                      type="number"
                      value={spouse.age}
                      onChange={(e) => setSpouse({ ...spouse, age: Number(e.target.value) })}
                      min={18}
                      max={100}
                    />
                  </div>
                  <div className="input-group">
                    <label>Spouse Gender</label>
                    <select
                      value={spouse.gender}
                      onChange={(e) => setSpouse({ ...spouse, gender: e.target.value as "male" | "female" })}
                    >
                      <option value="male">Male</option>
                      <option value="female">Female</option>
                    </select>
                  </div>
                </div>
                <div className="input-group">
                  <label>Spouse Monthly SS</label>
                  <div className="input-with-prefix">
                    <span>$</span>
                    <input
                      type="number"
                      value={spouse.social_security_monthly}
                      onChange={(e) => setSpouse({ ...spouse, social_security_monthly: Number(e.target.value) })}
                      min={0}
                      step={100}
                    />
                  </div>
                </div>
                <div className="input-group">
                  <label>Spouse Annual Pension</label>
                  <div className="input-with-prefix">
                    <span>$</span>
                    <input
                      type="number"
                      value={spouse.pension_annual}
                      onChange={(e) => setSpouse({ ...spouse, pension_annual: Number(e.target.value) })}
                      min={0}
                      step={1000}
                    />
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Annuity Section */}
          <div className="sidebar-section">
            <h3>Annuity Comparison</h3>
            <div className="input-group">
              <label>
                <input
                  type="checkbox"
                  checked={params.has_annuity}
                  onChange={(e) => updateParam("has_annuity", e.target.checked)}
                  style={{ marginRight: "0.5rem" }}
                />
                Compare to Annuity
              </label>
              <span className="input-hint">
                See if an annuity beats your portfolio
              </span>
            </div>
            {params.has_annuity && (
              <>
                <div className="input-group">
                  <label>Monthly Annuity Payment</label>
                  <div className="input-with-prefix">
                    <span>$</span>
                    <input
                      type="number"
                      value={annuity.monthly_payment}
                      onChange={(e) => setAnnuity({ ...annuity, monthly_payment: Number(e.target.value) })}
                      min={100}
                      step={100}
                    />
                  </div>
                </div>
                <div className="input-group">
                  <label>Annuity Type</label>
                  <select
                    value={annuity.annuity_type}
                    onChange={(e) => setAnnuity({ ...annuity, annuity_type: e.target.value as AnnuityInput["annuity_type"] })}
                  >
                    <option value="life_with_guarantee">Life with Guarantee</option>
                    <option value="fixed_period">Fixed Period</option>
                    <option value="life_only">Life Only</option>
                  </select>
                </div>
                {annuity.annuity_type !== "life_only" && (
                  <div className="input-group">
                    <label>Guarantee Period (years)</label>
                    <input
                      type="number"
                      value={annuity.guarantee_years}
                      onChange={(e) => setAnnuity({ ...annuity, guarantee_years: Number(e.target.value) })}
                      min={1}
                      max={30}
                    />
                  </div>
                )}
              </>
            )}
          </div>

          <div className="sidebar-section">
            <h3>Simulation Settings</h3>
            <div className="input-group">
              <label>
                <input
                  type="checkbox"
                  checked={params.include_mortality}
                  onChange={(e) => updateParam("include_mortality", e.target.checked)}
                  style={{ marginRight: "0.5rem" }}
                />
                Include Mortality Risk
              </label>
              <span className="input-hint">
                Accounts for probability of death each year
              </span>
            </div>
            <div className="input-row">
              <div className="input-group">
                <label>Expected Return</label>
                <div className="input-with-suffix">
                  <input
                    type="number"
                    value={(params.expected_return * 100).toFixed(1)}
                    onChange={(e) => updateParam("expected_return", Number(e.target.value) / 100)}
                    step={0.5}
                  />
                  <span>%</span>
                </div>
              </div>
              <div className="input-group">
                <label>Volatility</label>
                <div className="input-with-suffix">
                  <input
                    type="number"
                    value={(params.return_volatility * 100).toFixed(1)}
                    onChange={(e) => updateParam("return_volatility", Number(e.target.value) / 100)}
                    step={0.5}
                  />
                  <span>%</span>
                </div>
              </div>
            </div>
            <span className="input-hint">
              Real returns (after inflation)
            </span>
          </div>

          <button
            className="simulate-btn"
            onClick={handleSimulate}
            disabled={isLoading}
          >
            {isLoading ? "Running Simulation..." : "Run Simulation"}
          </button>
        </aside>

        {/* Main content */}
        <main className="sim-main">
          {error && (
            <div className="error-banner">
              <strong>Error:</strong> {error}
            </div>
          )}

          {!result && !isLoading && (
            <div className="empty-state">
              <div className="empty-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M3 3v18h18" />
                  <path d="M7 16l4-4 4 4 5-6" />
                </svg>
              </div>
              <h2>Configure your simulation</h2>
              <p>
                Enter your financial details in the sidebar, then click "Run
                Simulation" to see thousands of possible outcomes for your
                retirement.
              </p>
            </div>
          )}

          {isLoading && (
            <div className="loading-state">
              <div className="spinner" />
              <p>Running {params.n_simulations.toLocaleString()} simulations...</p>
            </div>
          )}

          {result && (
            <div className="results">
              {/* Key metrics */}
              <div className="metrics-grid">
                <div className="metric-card primary" style={{ borderColor: successColor }}>
                  <div className="metric-label">Success Rate</div>
                  <div className="metric-value" style={{ color: successColor }}>
                    {formatPercent(result.success_rate)}
                  </div>
                  <div className="metric-desc">
                    Probability of not running out of money
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Initial Withdrawal Rate</div>
                  <div className="metric-value">
                    {result.initial_withdrawal_rate.toFixed(1)}%
                  </div>
                  <div className="metric-desc">
                    From portfolio in year 1
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Median Final Value</div>
                  <div className="metric-value">
                    {formatCurrency(result.median_final_value)}
                  </div>
                  <div className="metric-desc">
                    50th percentile at age {params.max_age}
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">10-Year Failure Risk</div>
                  <div className="metric-value">
                    {formatPercent(result.prob_10_year_failure)}
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
                    // 5th-95th percentile band
                    {
                      x: ages,
                      y: result.percentile_paths.p95,
                      type: "scatter",
                      mode: "lines",
                      line: { color: "rgba(99, 102, 241, 0.2)", width: 0 },
                      showlegend: false,
                      hoverinfo: "skip",
                    },
                    {
                      x: ages,
                      y: result.percentile_paths.p5,
                      type: "scatter",
                      mode: "lines",
                      fill: "tonexty",
                      fillcolor: "rgba(99, 102, 241, 0.1)",
                      line: { color: "rgba(99, 102, 241, 0.2)", width: 0 },
                      name: "5th-95th percentile",
                    },
                    // 25th-75th percentile band
                    {
                      x: ages,
                      y: result.percentile_paths.p75,
                      type: "scatter",
                      mode: "lines",
                      line: { color: "rgba(99, 102, 241, 0.3)", width: 1 },
                      showlegend: false,
                      hoverinfo: "skip",
                    },
                    {
                      x: ages,
                      y: result.percentile_paths.p25,
                      type: "scatter",
                      mode: "lines",
                      fill: "tonexty",
                      fillcolor: "rgba(99, 102, 241, 0.15)",
                      line: { color: "rgba(99, 102, 241, 0.3)", width: 1 },
                      name: "25th-75th percentile",
                    },
                    // Median
                    {
                      x: ages,
                      y: result.percentile_paths.p50,
                      type: "scatter",
                      mode: "lines",
                      line: { color: "#6366f1", width: 3 },
                      name: "Median",
                    },
                  ]}
                  layout={{
                    autosize: true,
                    height: 400,
                    margin: { l: 80, r: 40, t: 20, b: 60 },
                    xaxis: {
                      title: { text: "Age" },
                      gridcolor: "#e5e7eb",
                    },
                    yaxis: {
                      title: { text: "Portfolio Value" },
                      gridcolor: "#e5e7eb",
                      tickformat: "$,.0f",
                    },
                    legend: {
                      x: 0,
                      y: 1.1,
                      orientation: "h",
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
                      <td>5th (worst case)</td>
                      <td>{formatCurrency(result.percentiles.p5)}</td>
                      <td>Only 5% of outcomes are worse than this</td>
                    </tr>
                    <tr>
                      <td>25th</td>
                      <td>{formatCurrency(result.percentiles.p25)}</td>
                      <td>25% of outcomes are worse</td>
                    </tr>
                    <tr className="highlight">
                      <td>50th (median)</td>
                      <td>{formatCurrency(result.percentiles.p50)}</td>
                      <td>The "typical" outcome</td>
                    </tr>
                    <tr>
                      <td>75th</td>
                      <td>{formatCurrency(result.percentiles.p75)}</td>
                      <td>25% of outcomes are better</td>
                    </tr>
                    <tr>
                      <td>95th (best case)</td>
                      <td>{formatCurrency(result.percentiles.p95)}</td>
                      <td>Only 5% of outcomes are better</td>
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
                    <span>{formatCurrency(result.total_withdrawn_median)}</span>
                  </div>
                  <div className="tax-row">
                    <span>Total Taxes Paid</span>
                    <span>{formatCurrency(result.total_taxes_median)}</span>
                  </div>
                  <div className="tax-row">
                    <span>Net After-Tax Income</span>
                    <span>
                      {formatCurrency(
                        result.total_withdrawn_median - result.total_taxes_median
                      )}
                    </span>
                  </div>
                </div>
                <p className="tax-note">
                  Tax calculations powered by PolicyEngine-US for accurate
                  federal and {params.state} state taxes.
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
                      <div className="comparison-value" style={{
                        color: annuityResult.probability_simulation_beats_annuity >= 0.6 ? "#10b981" :
                               annuityResult.probability_simulation_beats_annuity >= 0.4 ? "#f59e0b" : "#ef4444"
                      }}>
                        {formatPercent(annuityResult.probability_simulation_beats_annuity)}
                      </div>
                      <div className="comparison-desc">
                        Probability
                      </div>
                    </div>
                  </div>
                  <div className="recommendation">
                    <strong>Recommendation:</strong> {annuityResult.recommendation}
                  </div>
                </div>
              )}

              {result.median_depletion_age && (
                <div className="warning-banner">
                  <strong>Warning:</strong> In scenarios where the portfolio is
                  depleted, the median depletion occurs at age{" "}
                  {result.median_depletion_age}.
                  Consider reducing spending or increasing savings.
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
