"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
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

// Dynamic import Plotly to avoid SSR issues
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

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
  stateComparisonResult: StateComparisonResult | null;
  isComparingStates: boolean;
  selectedCompareStates: string[];
  onCompareStates: (states?: string[]) => void;
  onToggleCompareState: (state: string) => void;
  onResetStateComparison: () => void;
  ssTimingResult: SSTimingComparisonResult | null;
  isComparingSSTiming: boolean;
  birthYear: number;
  setBirthYear: (year: number) => void;
  piaMonthly: number;
  setPiaMonthly: (pia: number) => void;
  onCompareSSTimings: () => void;
  onResetSSTimings: () => void;
  allocationResult: AllocationComparisonResult | null;
  isComparingAllocations: boolean;
  onCompareAllocations: () => void;
  onResetAllocations: () => void;
}

const sectionCls = "section-card";

export function ResultsPanel({
  result, params, annuity, annuityResult,
  selectedYearIndex, setSelectedYearIndex, linkCopied, onCopyLink, onEditInputs, onWhatIf,
  stateComparisonResult, isComparingStates, selectedCompareStates,
  onCompareStates, onToggleCompareState, onResetStateComparison,
  ssTimingResult, isComparingSSTiming, birthYear, setBirthYear, piaMonthly, setPiaMonthly,
  onCompareSSTimings, onResetSSTimings,
  allocationResult, isComparingAllocations, onCompareAllocations, onResetAllocations,
}: ResultsPanelProps) {
  const interpretation = useMemo(() => getSuccessRateInterpretation(result.success_rate), [result.success_rate]);
  const successColor = useMemo(() => result.success_rate >= 0.9 ? "#10b981" : result.success_rate >= 0.75 ? "#f59e0b" : "#ef4444", [result.success_rate]);
  const ages = useMemo(() => result.percentile_paths.p50.map((_, i) => params.current_age + i), [result.percentile_paths.p50, params.current_age]);

  return (
    <div className="space-y-6">
      {/* Actions row */}
      <div className="flex flex-wrap items-center gap-3">
        <button className="inline-flex items-center gap-2 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--color-text-muted)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text)] hover:shadow-[var(--shadow-md)]" onClick={onEditInputs}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
          Edit Inputs
        </button>
        <button className="inline-flex items-center gap-2 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--color-text-muted)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text)] hover:shadow-[var(--shadow-md)]" onClick={onCopyLink}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
          {linkCopied ? "Link Copied!" : "Copy Link"}
        </button>
      </div>

      {/* Success banner */}
      <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-[var(--color-bg-card)] shadow-[var(--shadow-sm)]">
        <div className="h-1.5" style={{ background: `linear-gradient(90deg, ${interpretation.color}, ${interpretation.color}88)` }} />
        <div className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-lg font-bold" style={{ color: interpretation.color }}>{interpretation.label}</span>
            <span className="rounded-full px-3 py-1 text-sm font-bold" style={{ color: interpretation.color, background: `${interpretation.color}12` }}>{formatPercent(result.success_rate)}</span>
          </div>
          <p className="mt-1.5 text-sm text-[var(--color-text-muted)]">{interpretation.description}</p>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="metric-card metric-card-primary" style={{ borderColor: successColor }}>
          <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">Success Rate</div>
          <div className="mt-1.5 text-2xl font-bold tabular-nums" style={{ color: successColor }}>{formatPercent(result.success_rate)}</div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">Probability of not running out</div>
        </div>
        <div className="metric-card">
          <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">Withdrawal Rate</div>
          <div className="mt-1.5 text-2xl font-bold tabular-nums text-[var(--color-text)]">{result.initial_withdrawal_rate.toFixed(1)}%</div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">From portfolio in year 1</div>
        </div>
        <div className="metric-card">
          <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">Median Final</div>
          <div className="mt-1.5 text-2xl font-bold tabular-nums text-[var(--color-text)]">{formatCurrency(result.median_final_value)}</div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">50th pctl at age {params.max_age}</div>
        </div>
        <div className="metric-card">
          <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">10-Yr Depletion Risk</div>
          <div className="mt-1.5 text-2xl font-bold tabular-nums text-[var(--color-text)]">{formatPercent(result.prob_10_year_failure)}</div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">Depletion within 10 years</div>
        </div>
      </div>

      {/* Portfolio chart */}
      <PortfolioChart result={result} ages={ages} selectedYearIndex={selectedYearIndex} setSelectedYearIndex={setSelectedYearIndex} />

      {/* Year detail */}
      {selectedYearIndex !== null && result.year_breakdown[selectedYearIndex] && (
        <YearDetailPanel year={result.year_breakdown[selectedYearIndex]} selectedYearIndex={selectedYearIndex}
          totalYears={result.year_breakdown.length} onClose={() => setSelectedYearIndex(null)}
          onPrevious={() => setSelectedYearIndex(Math.max(0, selectedYearIndex - 1))}
          onNext={() => setSelectedYearIndex(Math.min(result.year_breakdown.length - 1, selectedYearIndex + 1))} />
      )}

      <OutcomeDistribution result={result} />
      <TaxSummary result={result} state={params.state} />

      {result.year_breakdown && result.year_breakdown.length > 0 && <YearBreakdownTable result={result} />}

      {annuityResult && <AnnuityComparison annuityResult={annuityResult} guaranteeYears={annuity.guarantee_years} />}

      <StateComparison params={params} stateComparisonResult={stateComparisonResult}
        isComparingStates={isComparingStates} selectedCompareStates={selectedCompareStates}
        onCompareStates={onCompareStates} onToggleCompareState={onToggleCompareState}
        onResetComparison={onResetStateComparison} />

      <SSTimingComparison ssTimingResult={ssTimingResult} isComparingSSTiming={isComparingSSTiming}
        birthYear={birthYear} setBirthYear={setBirthYear} piaMonthly={piaMonthly} setPiaMonthly={setPiaMonthly}
        onCompare={onCompareSSTimings} onReset={onResetSSTimings} />

      <AllocationComparison allocationResult={allocationResult} isComparingAllocations={isComparingAllocations}
        onCompare={onCompareAllocations} onReset={onResetAllocations} />

      {result.median_depletion_age && (
        <div className="flex gap-3 rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-light)] p-4 text-sm">
          <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-[var(--color-warning)] text-xs font-bold text-white">!</span>
          <div>
            <strong>Depletion risk:</strong> In scenarios where the portfolio is depleted, the median depletion occurs at age {result.median_depletion_age}. Consider reducing spending or increasing savings.
          </div>
        </div>
      )}

      <WhatIfScenarios params={params} onWhatIf={onWhatIf} />
      <NextStepsCTA hasAnnuity={params.has_annuity} />
    </div>
  );
}

/* ============================================ */
/* Sub-components                               */
/* ============================================ */

function PortfolioChart({ result, ages, selectedYearIndex, setSelectedYearIndex }: {
  result: SimulationResult; ages: number[]; selectedYearIndex: number | null; setSelectedYearIndex: (index: number | null) => void;
}) {
  const chartData = useMemo(() => [
    { x: ages, y: result.percentile_paths.p95, type: "scatter" as const, mode: "lines" as const, line: { color: "rgba(217,119,6,0.4)", width: 1, dash: "dot" as const }, name: "95th Percentile", legendgroup: "outer", hoverinfo: "skip" as const },
    { x: ages, y: result.percentile_paths.p5, type: "scatter" as const, mode: "lines" as const, fill: "tonexty" as const, fillcolor: "rgba(217,119,6,0.08)", line: { color: "rgba(217,119,6,0.4)", width: 1, dash: "dot" as const }, name: "5th Percentile", legendgroup: "outer", hoverinfo: "skip" as const },
    { x: ages, y: result.percentile_paths.p75, type: "scatter" as const, mode: "lines" as const, line: { color: "rgba(217,119,6,0.6)", width: 1.5 }, name: "75th Percentile", legendgroup: "inner", hoverinfo: "skip" as const },
    { x: ages, y: result.percentile_paths.p25, type: "scatter" as const, mode: "lines" as const, fill: "tonexty" as const, fillcolor: "rgba(217,119,6,0.15)", line: { color: "rgba(217,119,6,0.6)", width: 1.5 }, name: "25th Percentile", legendgroup: "inner", hoverinfo: "skip" as const },
    { x: ages, y: result.percentile_paths.p50, type: "scatter" as const, mode: "lines" as const, line: { color: chartColors.primary, width: 3 }, name: "Median (50th)", hoverinfo: "skip" as const },
    {
      x: ages, y: result.percentile_paths.p50, type: "scatter" as const, mode: "markers" as const,
      marker: { size: 20, color: "transparent" }, showlegend: false,
      hovertemplate: ages.map((age, i) => {
        const p95 = result.percentile_paths.p95[i]; const p75 = result.percentile_paths.p75[i];
        const p50 = result.percentile_paths.p50[i]; const p25 = result.percentile_paths.p25[i];
        const p5 = result.percentile_paths.p5[i];
        return `<b>Age ${age}</b> (Year ${i + 1})<br><span style="color:#9a3412">95th:</span> ${formatCurrency(p95)}<br><span style="color:#c2410c">75th:</span> ${formatCurrency(p75)}<br><span style="color:#d97706"><b>Median:</b></span> <b>${formatCurrency(p50)}</b><br><span style="color:#c2410c">25th:</span> ${formatCurrency(p25)}<br><span style="color:#9a3412">5th:</span> ${formatCurrency(p5)}<extra></extra>`;
      }),
    },
  ], [ages, result.percentile_paths]);

  const layout = useMemo(() => ({
    autosize: true, height: 420, margin: { l: 80, r: 40, t: 40, b: 60 },
    font: { family: "DM Sans, system-ui, sans-serif", size: 12 },
    xaxis: { title: { text: "Age", font: { family: "DM Sans, system-ui, sans-serif", size: 14 } }, gridcolor: colors.gray200, tickfont: { family: "DM Sans, system-ui, sans-serif", size: 12 }, showgrid: true, zeroline: false },
    yaxis: { title: { text: "Portfolio Value", font: { family: "DM Sans, system-ui, sans-serif", size: 14 } }, gridcolor: colors.gray200, tickformat: "$~s", tickfont: { family: "DM Sans, system-ui, sans-serif", size: 12 }, rangemode: "tozero" as const, showgrid: true, zeroline: true, zerolinecolor: colors.gray300 },
    legend: { x: 0.5, y: 1.15, xanchor: "center" as const, orientation: "h" as const, font: { family: "DM Sans, system-ui, sans-serif", size: 11 }, bgcolor: "rgba(255,255,255,0.9)", bordercolor: colors.gray200, borderwidth: 1, itemclick: "toggle" as const, itemdoubleclick: "toggleothers" as const },
    paper_bgcolor: "transparent", plot_bgcolor: "transparent", hovermode: "x unified" as const,
    hoverlabel: { bgcolor: "white", bordercolor: colors.gray300, font: { family: "DM Sans, system-ui, sans-serif", size: 13, color: colors.gray800 }, align: "left" as const },
    shapes: selectedYearIndex !== null ? [{ type: "line" as const, x0: ages[selectedYearIndex], x1: ages[selectedYearIndex], y0: 0, y1: 1, yref: "paper" as const, line: { color: chartColors.primary, width: 2, dash: "dash" as const } }] : [],
  }), [ages, selectedYearIndex]);

  return (
    <div className={sectionCls}>
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-lg font-semibold">Portfolio value over time</h3>
        <span className="text-xs text-[var(--color-text-light)]">Click chart for year details</span>
      </div>
      <div className="plotly-chart-wrapper -mx-2">
        <Plot data={chartData} layout={layout} config={{ responsive: true, displayModeBar: false, scrollZoom: false }} style={{ width: "100%" }}
          onClick={(event: { points?: Array<{ pointIndex?: number }> }) => {
            if (event.points && event.points.length > 0) {
              const pointIndex = event.points[0].pointIndex;
              if (typeof pointIndex === "number" && pointIndex < result.year_breakdown.length) setSelectedYearIndex(pointIndex);
            }
          }} />
      </div>
    </div>
  );
}

function DetailRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={`flex justify-between py-1 text-sm ${highlight ? "font-semibold border-t border-[var(--color-border)]" : ""}`}>
      <span className="text-[var(--color-text-muted)]">{label}</span>
      <span className="text-[var(--color-text)]">{value}</span>
    </div>
  );
}

function YearDetailPanel({ year, selectedYearIndex, totalYears, onClose, onPrevious, onNext }: {
  year: SimulationResult["year_breakdown"][0]; selectedYearIndex: number; totalYears: number;
  onClose: () => void; onPrevious: () => void; onNext: () => void;
}) {
  return (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-primary-200)] bg-[var(--color-bg-card)] shadow-[var(--shadow-md)]">
      <div className="border-b border-[var(--color-primary-100)] bg-[var(--color-primary-50)] px-6 py-3">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-[var(--color-primary-dark)]">Age {year.age} details</h3>
          <button className="flex h-7 w-7 items-center justify-center rounded-full text-[var(--color-primary)] hover:bg-[var(--color-primary-100)]" onClick={onClose} aria-label="Close">&times;</button>
        </div>
      </div>
      <div className="p-6">
      <div className="grid gap-6 sm:grid-cols-3">
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-light)] mb-2">Portfolio</h4>
          <DetailRow label="Start of Year" value={formatCurrency(year.portfolio_start)} />
          <DetailRow label="End of Year" value={formatCurrency(year.portfolio_end)} />
          <DetailRow label="Return" value={`${(year.portfolio_return * 100).toFixed(1)}%`} />
        </div>
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-light)] mb-2">Income</h4>
          {year.employment_income > 0 && <DetailRow label="Employment" value={formatCurrency(year.employment_income)} />}
          {year.social_security > 0 && <DetailRow label="Social Security" value={formatCurrency(year.social_security)} />}
          {year.pension > 0 && <DetailRow label="Pension" value={formatCurrency(year.pension)} />}
          {year.dividends > 0 && <DetailRow label="Dividends" value={formatCurrency(year.dividends)} />}
          {year.annuity > 0 && <DetailRow label="Annuity" value={formatCurrency(year.annuity)} />}
          <DetailRow label="Total Income" value={formatCurrency(year.total_income)} highlight />
        </div>
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-light)] mb-2">Withdrawals & Taxes</h4>
          <DetailRow label="Withdrawal" value={formatCurrency(year.withdrawal)} />
          <DetailRow label="Federal Tax" value={formatCurrency(year.federal_tax)} />
          <DetailRow label="State Tax" value={formatCurrency(year.state_tax)} />
          <DetailRow label="Total Tax" value={formatCurrency(year.total_tax)} highlight />
          <DetailRow label="Effective Rate" value={`${(year.effective_tax_rate * 100).toFixed(1)}%`} />
        </div>
      </div>
      <div className="mt-4 flex justify-between">
        <button className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-4 py-1.5 text-sm font-medium text-[var(--color-text-muted)] transition-all hover:bg-[var(--color-gray-50)] disabled:opacity-40" disabled={selectedYearIndex === 0} onClick={onPrevious}>
          &larr; Previous
        </button>
        <button className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-4 py-1.5 text-sm font-medium text-[var(--color-text-muted)] transition-all hover:bg-[var(--color-gray-50)] disabled:opacity-40" disabled={selectedYearIndex === totalYears - 1} onClick={onNext}>
          Next &rarr;
        </button>
      </div>
      </div>
    </div>
  );
}

function OutcomeDistribution({ result }: { result: SimulationResult }) {
  return (
    <div className={sectionCls}>
      <h3 className="text-lg font-semibold mb-4">Outcome distribution</h3>
      <div className="overflow-x-auto">
        <table className="w-full table-auto-style">
          <thead><tr><th>Percentile</th><th>Final Portfolio</th><th>Interpretation</th></tr></thead>
          <tbody>
            <tr><td>5th (conservative)</td><td>{formatCurrency(result.percentiles.p5)}</td><td className="text-[var(--color-text-muted)]">95% of outcomes exceed this</td></tr>
            <tr><td>25th</td><td>{formatCurrency(result.percentiles.p25)}</td><td className="text-[var(--color-text-muted)]">75% of outcomes are better</td></tr>
            <tr className="!bg-[var(--color-primary-50)] font-semibold"><td>50th (median)</td><td>{formatCurrency(result.percentiles.p50)}</td><td className="text-[var(--color-text-muted)]">The "typical" outcome</td></tr>
            <tr><td>75th</td><td>{formatCurrency(result.percentiles.p75)}</td><td className="text-[var(--color-text-muted)]">25% of outcomes are better</td></tr>
            <tr><td>95th (optimistic)</td><td>{formatCurrency(result.percentiles.p95)}</td><td className="text-[var(--color-text-muted)]">Only 5% exceed this</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TaxSummary({ result, state }: { result: SimulationResult; state: string }) {
  return (
    <div className={sectionCls}>
      <h3 className="text-lg font-semibold mb-4">Tax summary (median)</h3>
      <div className="space-y-2">
        {[
          ["Total Withdrawals", formatCurrency(result.total_withdrawn_median)],
          ["Total Taxes Paid", formatCurrency(result.total_taxes_median)],
          ["Net After-Tax Income", formatCurrency(result.total_withdrawn_median - result.total_taxes_median)],
        ].map(([label, value]) => (
          <div key={label} className="flex justify-between py-1.5 text-sm">
            <span className="text-[var(--color-text-muted)]">{label}</span>
            <span className="font-medium text-[var(--color-text)]">{value}</span>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-[var(--color-text-light)]">
        Tax calculations powered by PolicyEngine-US for accurate federal and {state} state taxes.
      </p>
    </div>
  );
}

function YearBreakdownTable({ result }: { result: SimulationResult }) {
  return (
    <div className={sectionCls}>
      <details>
        <summary className="cursor-pointer">
          <h3 className="inline text-lg font-semibold">Year-by-year breakdown (median)</h3>
          <span className="ml-2 text-xs text-[var(--color-text-light)]">Click to expand</span>
        </summary>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full table-auto-style">
            <thead><tr><th>Age</th><th>Start</th><th>Income</th><th>Withdrawal</th><th>Taxes</th><th>Rate</th><th>End</th></tr></thead>
            <tbody>
              {result.year_breakdown.map((year) => (
                <tr key={year.year_index}>
                  <td>{year.age}</td>
                  <td>{formatCurrency(year.portfolio_start)}</td>
                  <td title={`Employment: ${formatCurrency(year.employment_income)}, SS: ${formatCurrency(year.social_security)}`}>{formatCurrency(year.total_income)}</td>
                  <td>{formatCurrency(year.withdrawal)}</td>
                  <td>{formatCurrency(year.total_tax)}</td>
                  <td>{(year.effective_tax_rate * 100).toFixed(1)}%</td>
                  <td style={{ color: year.portfolio_end <= 0 ? "#ef4444" : "inherit", fontWeight: year.portfolio_end <= 0 ? 600 : 400 }}>{formatCurrency(year.portfolio_end)}</td>
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
    <div className={sectionCls}>
      <h3 className="text-lg font-semibold">Explore scenarios</h3>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">See how changes affect your success rate</p>
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { label: "Spend 10% less", value: `${formatCurrency(Math.round(params.annual_spending * 0.9))}/yr`, icon: "\u2193", mod: { annual_spending: Math.round(params.annual_spending * 0.9) } },
          { label: "Spend 10% more", value: `${formatCurrency(Math.round(params.annual_spending * 1.1))}/yr`, icon: "\u2191", mod: { annual_spending: Math.round(params.annual_spending * 1.1) } },
          { label: "10% more savings", value: formatCurrency(Math.round((params.initial_capital ?? 0) * 1.1)), icon: "\uD83D\uDCB0", mod: { initial_capital: Math.round((params.initial_capital ?? 0) * 1.1) } },
          ...(params.social_security_start_age < 70 ? [{ label: "Delay SS to 70", value: "+24% benefit", icon: "\uD83D\uDD50", mod: { social_security_start_age: 70 } }] : []),
        ].map(({ label, value, icon, mod }) => (
          <button key={label}
            className="flex flex-col items-center gap-2 rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-card)] p-4 text-center transition-all hover:border-[var(--color-primary-200)] hover:shadow-[var(--shadow-md)] hover:-translate-y-0.5"
            onClick={() => onWhatIf(mod)}>
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-primary-50)] text-base" aria-hidden="true">{icon}</span>
            <span className="text-sm font-medium text-[var(--color-text)]">{label}</span>
            <span className="text-xs font-semibold text-[var(--color-primary)]">{value}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function NextStepsCTA({ hasAnnuity }: { hasAnnuity: boolean }) {
  return (
    <div className={sectionCls}>
      <h3 className="text-lg font-semibold mb-4">Take the next step</h3>
      <div className="space-y-3">
        {[
          { href: "https://www.nerdwallet.com/best/investing/financial-advisors-for-retirement", icon: "\uD83D\uDC64", title: "Talk to a fiduciary advisor", desc: "Get personalized advice from a fee-only advisor who works in your interest." },
          { href: "https://investor.vanguard.com/investment-products/index-funds", icon: "\uD83D\uDCC8", title: "Low-cost index funds", desc: "Simple, diversified investing with minimal fees." },
          ...(hasAnnuity ? [{ href: "https://www.immediateannuities.com/", icon: "\uD83D\uDEE1\uFE0F", title: "Compare annuity quotes", desc: "Get quotes from multiple insurers for guaranteed income." }] : []),
        ].map(({ href, icon, title, desc }) => (
          <a key={href} href={href} target="_blank" rel="noopener noreferrer"
            className="group flex items-center gap-4 rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-white p-4 transition-all hover:border-[var(--color-primary-200)] hover:shadow-[var(--shadow-md)]">
            <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--color-primary-50)] text-xl transition-colors group-hover:bg-[var(--color-primary-100)]" aria-hidden="true">{icon}</span>
            <div className="flex-1">
              <div className="font-semibold text-[var(--color-text)]">{title}</div>
              <div className="text-sm text-[var(--color-text-muted)]">{desc}</div>
            </div>
            <span className="text-[var(--color-text-light)] transition-transform group-hover:translate-x-0.5" aria-hidden="true">&rarr;</span>
          </a>
        ))}
      </div>
      <p className="mt-4 text-xs text-[var(--color-text-light)]">
        These are educational resources, not endorsements. We may receive referral fees from some links, which helps keep EggNest free.
      </p>
    </div>
  );
}
