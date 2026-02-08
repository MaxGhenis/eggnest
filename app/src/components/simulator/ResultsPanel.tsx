import { useMemo } from "react";
import Plot from "react-plotly.js";
import type {
  SimulationInput,
  SimulationResult,
  AnnuityInput,
  StateComparisonResult,
  SSTimingComparisonResult,
  AllocationComparisonResult,
} from "../../lib/api";
import { colors, chartColors } from "../../lib/design-tokens";
import {
  formatCurrency,
  formatPercent,
  getSuccessRateInterpretation,
  type AnnuityComparisonResult,
} from "../../lib/simulatorUtils";
import {
  AnnuityComparison,
  StateComparison,
  SSTimingComparison,
  AllocationComparison,
} from "./ComparisonPanel";

interface ResultsPanelProps {
  result: SimulationResult;
  params: SimulationInput;
  annuity: AnnuityInput;
  annuityResult: AnnuityComparisonResult | null;
  selectedYearIndex: number | null;
  setSelectedYearIndex: (index: number | null) => void;
  linkCopied: boolean;
  onCopyLink: () => void;
  onEditInputs: () => void;
  onWhatIf: (modifier: Partial<SimulationInput>) => void;
  // State comparison props
  stateComparisonResult: StateComparisonResult | null;
  isComparingStates: boolean;
  selectedCompareStates: string[];
  onCompareStates: (states?: string[]) => void;
  onToggleCompareState: (state: string) => void;
  onResetStateComparison: () => void;
  // SS timing props
  ssTimingResult: SSTimingComparisonResult | null;
  isComparingSSTiming: boolean;
  birthYear: number;
  setBirthYear: (year: number) => void;
  piaMonthly: number;
  setPiaMonthly: (pia: number) => void;
  onCompareSSTimings: () => void;
  onResetSSTimings: () => void;
  // Allocation props
  allocationResult: AllocationComparisonResult | null;
  isComparingAllocations: boolean;
  onCompareAllocations: () => void;
  onResetAllocations: () => void;
}

export function ResultsPanel({
  result,
  params,
  annuity,
  annuityResult,
  selectedYearIndex,
  setSelectedYearIndex,
  linkCopied,
  onCopyLink,
  onEditInputs,
  onWhatIf,
  stateComparisonResult,
  isComparingStates,
  selectedCompareStates,
  onCompareStates,
  onToggleCompareState,
  onResetStateComparison,
  ssTimingResult,
  isComparingSSTiming,
  birthYear,
  setBirthYear,
  piaMonthly,
  setPiaMonthly,
  onCompareSSTimings,
  onResetSSTimings,
  allocationResult,
  isComparingAllocations,
  onCompareAllocations,
  onResetAllocations,
}: ResultsPanelProps) {
  const interpretation = useMemo(
    () => getSuccessRateInterpretation(result.success_rate),
    [result.success_rate]
  );

  const successColor = useMemo(() => {
    if (result.success_rate >= 0.9) return "#10b981";
    if (result.success_rate >= 0.75) return "#f59e0b";
    return "#ef4444";
  }, [result.success_rate]);

  const ages = useMemo(
    () => result.percentile_paths.p50.map((_, i) => params.current_age + i),
    [result.percentile_paths.p50, params.current_age]
  );

  return (
    <div className="results-view">
      <div className="results-actions">
        <button className="back-to-wizard" onClick={onEditInputs}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Edit Inputs
        </button>
        <button className="copy-link-btn" onClick={onCopyLink}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
          {linkCopied ? "Link Copied!" : "Copy Link"}
        </button>
      </div>

      {/* Success interpretation banner */}
      <div className="success-interpretation" style={{ borderColor: interpretation.color }}>
        <div className="interpretation-header">
          <span className="interpretation-label" style={{ color: interpretation.color }}>
            {interpretation.label}
          </span>
          <span className="interpretation-rate" style={{ color: interpretation.color }}>
            {formatPercent(result.success_rate)} success rate
          </span>
        </div>
        <p className="interpretation-text">{interpretation.description}</p>
      </div>

      {/* Key metrics */}
      <div className="metrics-grid">
        <div className="metric-card primary" style={{ borderColor: successColor }}>
          <div className="metric-label">Success Rate</div>
          <div className="metric-value" style={{ color: successColor }}>
            {formatPercent(result.success_rate)}
          </div>
          <div className="metric-desc">Probability of not running out of money</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Initial Withdrawal Rate</div>
          <div className="metric-value">{result.initial_withdrawal_rate.toFixed(1)}%</div>
          <div className="metric-desc">From portfolio in year 1</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Median Final Value</div>
          <div className="metric-value">{formatCurrency(result.median_final_value)}</div>
          <div className="metric-desc">50th percentile at age {params.max_age}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">10-Year Depletion Risk</div>
          <div className="metric-value">{formatPercent(result.prob_10_year_failure)}</div>
          <div className="metric-desc">Probability of depletion within 10 years</div>
        </div>
      </div>

      {/* Portfolio chart */}
      <PortfolioChart
        result={result}
        ages={ages}
        selectedYearIndex={selectedYearIndex}
        setSelectedYearIndex={setSelectedYearIndex}
      />

      {/* Year detail panel */}
      {selectedYearIndex !== null && result.year_breakdown[selectedYearIndex] && (
        <YearDetailPanel
          year={result.year_breakdown[selectedYearIndex]}
          selectedYearIndex={selectedYearIndex}
          totalYears={result.year_breakdown.length}
          onClose={() => setSelectedYearIndex(null)}
          onPrevious={() => setSelectedYearIndex(Math.max(0, selectedYearIndex - 1))}
          onNext={() => setSelectedYearIndex(Math.min(result.year_breakdown.length - 1, selectedYearIndex + 1))}
        />
      )}

      {/* Summary table */}
      <OutcomeDistribution result={result} />

      {/* Taxes info */}
      <TaxSummary result={result} state={params.state} />

      {/* Year-by-Year Breakdown */}
      {result.year_breakdown && result.year_breakdown.length > 0 && (
        <YearBreakdownTable result={result} />
      )}

      {/* Annuity Comparison Results */}
      {annuityResult && (
        <AnnuityComparison
          annuityResult={annuityResult}
          guaranteeYears={annuity.guarantee_years}
        />
      )}

      {/* State Comparison */}
      <StateComparison
        params={params}
        stateComparisonResult={stateComparisonResult}
        isComparingStates={isComparingStates}
        selectedCompareStates={selectedCompareStates}
        onCompareStates={onCompareStates}
        onToggleCompareState={onToggleCompareState}
        onResetComparison={onResetStateComparison}
      />

      {/* SS Timing Comparison */}
      <SSTimingComparison
        ssTimingResult={ssTimingResult}
        isComparingSSTiming={isComparingSSTiming}
        birthYear={birthYear}
        setBirthYear={setBirthYear}
        piaMonthly={piaMonthly}
        setPiaMonthly={setPiaMonthly}
        onCompare={onCompareSSTimings}
        onReset={onResetSSTimings}
      />

      {/* Allocation Comparison */}
      <AllocationComparison
        allocationResult={allocationResult}
        isComparingAllocations={isComparingAllocations}
        onCompare={onCompareAllocations}
        onReset={onResetAllocations}
      />

      {result.median_depletion_age && (
        <div className="warning-banner">
          <strong>Warning:</strong> In scenarios where the portfolio is
          depleted, the median depletion occurs at age{" "}
          {result.median_depletion_age}. Consider reducing spending or
          increasing savings.
        </div>
      )}

      {/* What-if scenarios */}
      <WhatIfScenarios params={params} onWhatIf={onWhatIf} />

      {/* Next Steps CTA */}
      <NextStepsCTA hasAnnuity={params.has_annuity} />
    </div>
  );
}

// ============================================
// Sub-components (internal to results)
// ============================================

interface PortfolioChartProps {
  result: SimulationResult;
  ages: number[];
  selectedYearIndex: number | null;
  setSelectedYearIndex: (index: number | null) => void;
}

function PortfolioChart({ result, ages, selectedYearIndex, setSelectedYearIndex }: PortfolioChartProps) {
  const chartData = useMemo(() => [
    // 95th percentile
    {
      x: ages,
      y: result.percentile_paths.p95,
      type: "scatter" as const,
      mode: "lines" as const,
      line: { color: "rgba(217, 119, 6, 0.4)", width: 1, dash: "dot" as const },
      name: "95th Percentile",
      legendgroup: "outer",
      hoverinfo: "skip" as const,
    },
    // 5th percentile
    {
      x: ages,
      y: result.percentile_paths.p5,
      type: "scatter" as const,
      mode: "lines" as const,
      fill: "tonexty" as const,
      fillcolor: "rgba(217, 119, 6, 0.08)",
      line: { color: "rgba(217, 119, 6, 0.4)", width: 1, dash: "dot" as const },
      name: "5th Percentile",
      legendgroup: "outer",
      hoverinfo: "skip" as const,
    },
    // 75th percentile
    {
      x: ages,
      y: result.percentile_paths.p75,
      type: "scatter" as const,
      mode: "lines" as const,
      line: { color: "rgba(217, 119, 6, 0.6)", width: 1.5 },
      name: "75th Percentile",
      legendgroup: "inner",
      hoverinfo: "skip" as const,
    },
    // 25th percentile
    {
      x: ages,
      y: result.percentile_paths.p25,
      type: "scatter" as const,
      mode: "lines" as const,
      fill: "tonexty" as const,
      fillcolor: "rgba(217, 119, 6, 0.15)",
      line: { color: "rgba(217, 119, 6, 0.6)", width: 1.5 },
      name: "25th Percentile",
      legendgroup: "inner",
      hoverinfo: "skip" as const,
    },
    // Median line
    {
      x: ages,
      y: result.percentile_paths.p50,
      type: "scatter" as const,
      mode: "lines" as const,
      line: { color: chartColors.primary, width: 3 },
      name: "Median (50th)",
      hoverinfo: "skip" as const,
    },
    // Invisible trace for unified tooltip
    {
      x: ages,
      y: result.percentile_paths.p50,
      type: "scatter" as const,
      mode: "markers" as const,
      marker: { size: 20, color: "transparent" },
      showlegend: false,
      hovertemplate: ages.map((age, i) => {
        const year = i;
        const p95 = result.percentile_paths.p95[i];
        const p75 = result.percentile_paths.p75[i];
        const p50 = result.percentile_paths.p50[i];
        const p25 = result.percentile_paths.p25[i];
        const p5 = result.percentile_paths.p5[i];
        return `<b>Age ${age}</b> (Year ${year + 1})<br>` +
          `<span style="color:#9a3412">95th:</span> ${formatCurrency(p95)}<br>` +
          `<span style="color:#c2410c">75th:</span> ${formatCurrency(p75)}<br>` +
          `<span style="color:#d97706"><b>Median:</b></span> <b>${formatCurrency(p50)}</b><br>` +
          `<span style="color:#c2410c">25th:</span> ${formatCurrency(p25)}<br>` +
          `<span style="color:#9a3412">5th:</span> ${formatCurrency(p5)}` +
          `<extra></extra>`;
      }),
    },
  ], [ages, result.percentile_paths]);

  const layout = useMemo(() => ({
    autosize: true,
    height: 420,
    margin: { l: 80, r: 40, t: 40, b: 60 },
    font: { family: "Inter, system-ui, sans-serif", size: 12 },
    xaxis: {
      title: { text: "Age", font: { family: "Inter, system-ui, sans-serif", size: 14 } },
      gridcolor: colors.gray200,
      tickfont: { family: "Inter, system-ui, sans-serif", size: 12 },
      showgrid: true,
      zeroline: false,
    },
    yaxis: {
      title: { text: "Portfolio Value", font: { family: "Inter, system-ui, sans-serif", size: 14 } },
      gridcolor: colors.gray200,
      tickformat: "$~s",
      tickfont: { family: "Inter, system-ui, sans-serif", size: 12 },
      rangemode: "tozero" as const,
      showgrid: true,
      zeroline: true,
      zerolinecolor: colors.gray300,
    },
    legend: {
      x: 0.5,
      y: 1.15,
      xanchor: "center" as const,
      orientation: "h" as const,
      font: { family: "Inter, system-ui, sans-serif", size: 11 },
      bgcolor: "rgba(255,255,255,0.9)",
      bordercolor: colors.gray200,
      borderwidth: 1,
      itemclick: "toggle" as const,
      itemdoubleclick: "toggleothers" as const,
    },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    hovermode: "x unified" as const,
    hoverlabel: {
      bgcolor: "white",
      bordercolor: colors.gray300,
      font: { family: "Inter, system-ui, sans-serif", size: 13, color: colors.gray800 },
      align: "left" as const,
    },
    shapes: selectedYearIndex !== null ? [
      {
        type: "line" as const,
        x0: ages[selectedYearIndex],
        x1: ages[selectedYearIndex],
        y0: 0,
        y1: 1,
        yref: "paper" as const,
        line: { color: chartColors.primary, width: 2, dash: "dash" as const },
      },
    ] : [],
  }), [ages, selectedYearIndex]);

  return (
    <div className="chart-container portfolio-chart">
      <h3>Portfolio Value Over Time</h3>
      <p className="chart-hint">Click on the chart to see year details. Click legend items to toggle visibility.</p>
      <Plot
        data={chartData}
        layout={layout}
        config={{ responsive: true, displayModeBar: false, scrollZoom: false }}
        style={{ width: "100%" }}
        onClick={(event) => {
          if (event.points && event.points.length > 0) {
            const pointIndex = event.points[0].pointIndex;
            if (typeof pointIndex === 'number' && pointIndex < result.year_breakdown.length) {
              setSelectedYearIndex(pointIndex);
            }
          }
        }}
      />
    </div>
  );
}

interface YearDetailPanelProps {
  year: SimulationResult["year_breakdown"][0];
  selectedYearIndex: number;
  totalYears: number;
  onClose: () => void;
  onPrevious: () => void;
  onNext: () => void;
}

function YearDetailPanel({ year, selectedYearIndex, totalYears, onClose, onPrevious, onNext }: YearDetailPanelProps) {
  return (
    <div className="year-detail-panel">
      <div className="year-detail-header">
        <h3>Age {year.age} Details</h3>
        <button className="close-btn" onClick={onClose} aria-label="Close">
          \u00d7
        </button>
      </div>
      <div className="year-detail-grid">
        <div className="year-detail-section">
          <h4>Portfolio</h4>
          <div className="detail-row">
            <span>Start of Year</span>
            <span>{formatCurrency(year.portfolio_start)}</span>
          </div>
          <div className="detail-row">
            <span>End of Year</span>
            <span>{formatCurrency(year.portfolio_end)}</span>
          </div>
          <div className="detail-row">
            <span>Return</span>
            <span style={{ color: year.portfolio_return >= 0 ? '#10b981' : '#ef4444' }}>
              {(year.portfolio_return * 100).toFixed(1)}%
            </span>
          </div>
        </div>
        <div className="year-detail-section">
          <h4>Income</h4>
          {year.employment_income > 0 && (
            <div className="detail-row">
              <span>Employment</span>
              <span>{formatCurrency(year.employment_income)}</span>
            </div>
          )}
          {year.social_security > 0 && (
            <div className="detail-row">
              <span>Social Security</span>
              <span>{formatCurrency(year.social_security)}</span>
            </div>
          )}
          {year.pension > 0 && (
            <div className="detail-row">
              <span>Pension</span>
              <span>{formatCurrency(year.pension)}</span>
            </div>
          )}
          {year.dividends > 0 && (
            <div className="detail-row">
              <span>Dividends</span>
              <span>{formatCurrency(year.dividends)}</span>
            </div>
          )}
          {year.annuity > 0 && (
            <div className="detail-row">
              <span>Annuity</span>
              <span>{formatCurrency(year.annuity)}</span>
            </div>
          )}
          <div className="detail-row total">
            <span>Total Income</span>
            <span>{formatCurrency(year.total_income)}</span>
          </div>
        </div>
        <div className="year-detail-section">
          <h4>Withdrawals & Taxes</h4>
          <div className="detail-row">
            <span>Withdrawal</span>
            <span>{formatCurrency(year.withdrawal)}</span>
          </div>
          <div className="detail-row">
            <span>Federal Tax</span>
            <span>{formatCurrency(year.federal_tax)}</span>
          </div>
          <div className="detail-row">
            <span>State Tax</span>
            <span>{formatCurrency(year.state_tax)}</span>
          </div>
          <div className="detail-row total">
            <span>Total Tax</span>
            <span>{formatCurrency(year.total_tax)}</span>
          </div>
          <div className="detail-row">
            <span>Effective Rate</span>
            <span>{(year.effective_tax_rate * 100).toFixed(1)}%</span>
          </div>
        </div>
      </div>
      <div className="year-nav">
        <button
          disabled={selectedYearIndex === 0}
          onClick={onPrevious}
        >
          \u2190 Previous Year
        </button>
        <button
          disabled={selectedYearIndex === totalYears - 1}
          onClick={onNext}
        >
          Next Year \u2192
        </button>
      </div>
    </div>
  );
}

function OutcomeDistribution({ result }: { result: SimulationResult }) {
  return (
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
            <td>{formatCurrency(result.percentiles.p5)}</td>
            <td>95% of outcomes exceed this</td>
          </tr>
          <tr>
            <td>25th</td>
            <td>{formatCurrency(result.percentiles.p25)}</td>
            <td>75% of outcomes are better</td>
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
            <td>95th (optimistic)</td>
            <td>{formatCurrency(result.percentiles.p95)}</td>
            <td>Only 5% of outcomes exceed this</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function TaxSummary({ result, state }: { result: SimulationResult; state: string }) {
  return (
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
            {formatCurrency(result.total_withdrawn_median - result.total_taxes_median)}
          </span>
        </div>
      </div>
      <p className="tax-note">
        Tax calculations powered by PolicyEngine-US for accurate federal and{" "}
        {state} state taxes.
      </p>
    </div>
  );
}

function YearBreakdownTable({ result }: { result: SimulationResult }) {
  return (
    <div className="summary-section year-breakdown">
      <details>
        <summary>
          <h3 style={{ display: "inline" }}>Year-by-Year Breakdown (Median)</h3>
          <span className="expand-hint">Click to expand</span>
        </summary>
        <div className="breakdown-table-wrapper">
          <table className="breakdown-table">
            <thead>
              <tr>
                <th>Age</th>
                <th>Portfolio Start</th>
                <th>Income</th>
                <th>Withdrawal</th>
                <th>Taxes</th>
                <th>Tax Rate</th>
                <th>Portfolio End</th>
              </tr>
            </thead>
            <tbody>
              {result.year_breakdown.map((year) => (
                <tr key={year.year_index}>
                  <td>{year.age}</td>
                  <td>{formatCurrency(year.portfolio_start)}</td>
                  <td title={`Employment: ${formatCurrency(year.employment_income)}, SS: ${formatCurrency(year.social_security)}, Pension: ${formatCurrency(year.pension)}, Dividends: ${formatCurrency(year.dividends)}`}>
                    {formatCurrency(year.total_income)}
                  </td>
                  <td>{formatCurrency(year.withdrawal)}</td>
                  <td title={`Federal: ${formatCurrency(year.federal_tax)}, State: ${formatCurrency(year.state_tax)}`}>
                    {formatCurrency(year.total_tax)}
                  </td>
                  <td>{(year.effective_tax_rate * 100).toFixed(1)}%</td>
                  <td
                    style={{
                      color: year.portfolio_end <= 0 ? "#ef4444" : "inherit",
                      fontWeight: year.portfolio_end <= 0 ? 600 : 400,
                    }}
                  >
                    {formatCurrency(year.portfolio_end)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

function WhatIfScenarios({ params, onWhatIf }: { params: SimulationInput; onWhatIf: (mod: Partial<SimulationInput>) => void }) {
  return (
    <div className="what-if-section">
      <h3>Explore Scenarios</h3>
      <p className="what-if-description">
        See how changes affect your success rate
      </p>
      <div className="what-if-buttons">
        <button
          className="what-if-btn"
          onClick={() => onWhatIf({ annual_spending: Math.round(params.annual_spending * 0.9) })}
        >
          <span className="what-if-icon">{"\u2193"}</span>
          <span className="what-if-label">Spend 10% less</span>
          <span className="what-if-value">
            {formatCurrency(Math.round(params.annual_spending * 0.9))}/yr
          </span>
        </button>
        <button
          className="what-if-btn"
          onClick={() => onWhatIf({ annual_spending: Math.round(params.annual_spending * 1.1) })}
        >
          <span className="what-if-icon">{"\u2191"}</span>
          <span className="what-if-label">Spend 10% more</span>
          <span className="what-if-value">
            {formatCurrency(Math.round(params.annual_spending * 1.1))}/yr
          </span>
        </button>
        <button
          className="what-if-btn"
          onClick={() => onWhatIf({ initial_capital: Math.round((params.initial_capital ?? 0) * 1.1) })}
        >
          <span className="what-if-icon">{"\uD83D\uDCB0"}</span>
          <span className="what-if-label">10% more savings</span>
          <span className="what-if-value">
            {formatCurrency(Math.round((params.initial_capital ?? 0) * 1.1))}
          </span>
        </button>
        {params.social_security_start_age < 70 && (
          <button
            className="what-if-btn"
            onClick={() => onWhatIf({ social_security_start_age: 70 })}
          >
            <span className="what-if-icon">{"\uD83D\uDD50"}</span>
            <span className="what-if-label">Delay SS to 70</span>
            <span className="what-if-value">+24% benefit</span>
          </button>
        )}
      </div>
    </div>
  );
}

function NextStepsCTA({ hasAnnuity }: { hasAnnuity: boolean }) {
  return (
    <div className="summary-section next-steps">
      <h3>Take the Next Step</h3>
      <div className="cta-grid">
        <a
          href="https://www.nerdwallet.com/best/investing/financial-advisors-for-retirement"
          target="_blank"
          rel="noopener noreferrer"
          className="cta-card"
        >
          <div className="cta-icon">{"\uD83D\uDC64"}</div>
          <div className="cta-content">
            <div className="cta-title">Talk to a Fiduciary Advisor</div>
            <div className="cta-desc">
              Get personalized advice from a fee-only advisor who works in your interest.
            </div>
          </div>
          <span className="cta-arrow">{"\u2192"}</span>
        </a>
        <a
          href="https://investor.vanguard.com/investment-products/index-funds"
          target="_blank"
          rel="noopener noreferrer"
          className="cta-card"
        >
          <div className="cta-icon">{"\uD83D\uDCC8"}</div>
          <div className="cta-content">
            <div className="cta-title">Low-Cost Index Funds</div>
            <div className="cta-desc">
              Simple, diversified investing with minimal fees.
            </div>
          </div>
          <span className="cta-arrow">{"\u2192"}</span>
        </a>
        {hasAnnuity && (
          <a
            href="https://www.immediateannuities.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="cta-card"
          >
            <div className="cta-icon">{"\uD83D\uDEE1\uFE0F"}</div>
            <div className="cta-content">
              <div className="cta-title">Compare Annuity Quotes</div>
              <div className="cta-desc">
                Get quotes from multiple insurers for guaranteed income.
              </div>
            </div>
            <span className="cta-arrow">{"\u2192"}</span>
          </a>
        )}
      </div>
      <p className="cta-disclaimer">
        These are educational resources, not endorsements. We may receive referral fees
        from some links, which helps keep EggNest free.
      </p>
    </div>
  );
}
