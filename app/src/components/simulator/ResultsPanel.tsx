"use client";

import { useMemo, useState, type ReactNode } from "react";
import dynamic from "next/dynamic";
import type { SimulationInput, SimulationResult } from "../../lib/api";
import { colors, chartColors } from "../../lib/design-tokens";
import {
  formatCurrency,
  formatPercent,
  buildFullParams,
} from "../../lib/simulatorUtils";
import { useSimulationContext } from "../../contexts/SimulationContext";
import { useComparisonContext } from "../../contexts/ComparisonContext";
import { usePortfolioContext } from "../../contexts/PortfolioContext";
import { useScenarioContext } from "../../contexts/ScenarioContext";
import {
  AnnuityComparison,
  StateComparison,
  SSTimingComparison,
  AllocationComparison,
  RothOptimizationComparison,
  WithdrawalStrategyComparison,
} from "./ComparisonPanel";
import { HistoricalBacktestPanel } from "./HistoricalBacktestPanel";
import {
  buildRothReportHref,
  buildRothReportRequestPayload,
} from "../../lib/rothReportLink";

// Dynamic import Plotly to avoid SSR issues
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface ResultsPanelProps {
  onEditInputs: () => void;
  onWhatIf: (modifier: Partial<SimulationInput>) => void;
}

const sectionCls = "section-card";

export function ResultsPanel({ onEditInputs, onWhatIf }: ResultsPanelProps) {
  const { params, spouse, annuity, simulation } = useSimulationContext();
  const comparisons = useComparisonContext();
  const portfolio = usePortfolioContext();
  const scenarios = useScenarioContext();
  const [isDeeperAnalysisOpen, setIsDeeperAnalysisOpen] = useState(false);

  const result = simulation.result!;
  const { annuityResult, selectedYearIndex, setSelectedYearIndex } = simulation;

  const hasTraditionalAccounts = useMemo(
    () =>
      portfolio.holdings.some(
        (holding) =>
          holding.account_type === "traditional_401k" ||
          holding.account_type === "traditional_ira"
      ),
    [portfolio.holdings]
  );
  const fullParams = useMemo(
    () =>
      buildFullParams(
        params,
        params.has_spouse ? spouse : undefined,
        annuity,
        portfolio.portfolioMode,
        portfolio.holdings,
        portfolio.withdrawalStrategy,
      ),
    [
      annuity,
      params,
      portfolio.holdings,
      portfolio.portfolioMode,
      portfolio.withdrawalStrategy,
      spouse,
    ],
  );
  const rothReportLink = useMemo(() => {
    if (!comparisons.rothOptimizationResult || typeof window === "undefined") {
      return null;
    }
    return buildRothReportHref(
      buildRothReportRequestPayload(fullParams, comparisons.rothOptimizationResult),
      window.location.origin,
    );
  }, [comparisons.rothOptimizationResult, fullParams]);
  const ages = useMemo(() => result.percentile_paths.p50.map((_, i) => params.current_age + i), [result.percentile_paths.p50, params.current_age]);
  const portfolioValue = useMemo(
    () =>
      portfolio.portfolioMode === "detailed" && portfolio.holdings.length > 0
        ? portfolio.holdings.reduce((sum, holding) => sum + holding.balance, 0)
        : params.initial_capital ?? 0,
    [params.initial_capital, portfolio.holdings, portfolio.portfolioMode],
  );

  return (
    <div className="space-y-6">
      {/* Actions row */}
      <div className="flex flex-wrap items-center gap-3">
        <button className="inline-flex items-center gap-2 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--color-text-muted)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text)] hover:shadow-[var(--shadow-md)]" onClick={onEditInputs}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
          Edit inputs
        </button>
        <button className="inline-flex items-center gap-2 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--color-text-muted)] shadow-[var(--shadow-sm)] transition-all hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text)] hover:shadow-[var(--shadow-md)]" onClick={scenarios.copyLinkToClipboard}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
          {scenarios.linkCopied ? "Link copied!" : "Copy link"}
        </button>
      </div>

      <HeroAnswer
        successRate={result.success_rate}
        tenYearRisk={result.prob_10_year_failure}
        medianFinalReal={result.median_final_value_real}
        initialWithdrawalRate={result.initial_withdrawal_rate}
        params={params}
        portfolioValue={portfolioValue}
      />

      {/* Portfolio chart */}
      <PortfolioChart result={result} ages={ages} selectedYearIndex={selectedYearIndex} setSelectedYearIndex={setSelectedYearIndex} />

      {/* Year detail */}
      {selectedYearIndex !== null && result.year_breakdown[selectedYearIndex] && (
        <YearDetailPanel year={result.year_breakdown[selectedYearIndex]} selectedYearIndex={selectedYearIndex}
          totalYears={result.year_breakdown.length} onClose={() => setSelectedYearIndex(null)}
          onPrevious={() => setSelectedYearIndex(Math.max(0, selectedYearIndex - 1))}
          onNext={() => setSelectedYearIndex(Math.min(result.year_breakdown.length - 1, selectedYearIndex + 1))} />
      )}

      {result.median_depletion_age && (
        <div className="flex gap-3 rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-light)] p-4 text-sm">
          <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-[var(--color-warning)] text-xs font-bold text-white">!</span>
          <div>
            <strong>Depletion risk:</strong> In scenarios where the portfolio
            is depleted, the median depletion occurs at age{" "}
            {result.median_depletion_age}. If you want to pressure-test this
            case, try lower spending or higher savings assumptions in another
            scenario.
          </div>
        </div>
      )}

      <WhatIfScenarios params={params} onWhatIf={onWhatIf} />

      <CollapsibleSection
        title="Deeper analysis"
        description="Backtests, strategy comparisons, audit tables, and third-party resources."
        isOpen={isDeeperAnalysisOpen}
        onToggle={() => setIsDeeperAnalysisOpen((current) => !current)}
      >
        <HistoricalBacktestPanel
          monteCarloResult={result}
          historicalBacktestResult={simulation.historicalBacktestResult}
          isLoading={simulation.isHistoricalBacktestLoading}
          error={simulation.historicalBacktestError}
          includeMortality={params.include_mortality}
        />

        {portfolio.portfolioMode === "detailed" && portfolio.holdings.length > 0 && (
          <WithdrawalStrategyComparison
            strategyComparisonResult={comparisons.strategyComparisonResult}
            isComparingStrategies={comparisons.isComparingStrategies}
            currentStrategy={portfolio.withdrawalStrategy}
            onCompare={comparisons.handleCompareStrategies}
            onReset={() => comparisons.setStrategyComparisonResult(null)}
          />
        )}

        {portfolio.portfolioMode === "detailed" && portfolio.holdings.length > 0 && hasTraditionalAccounts && (
          <RothOptimizationComparison
            rothOptimizationResult={comparisons.rothOptimizationResult}
            isOptimizingRoth={comparisons.isOptimizingRoth}
            onOptimize={comparisons.handleOptimizeRoth}
            onReset={() => comparisons.setRothOptimizationResult(null)}
            reportLink={rothReportLink}
          />
        )}

        {annuityResult && (
          <AnnuityComparison
            annuityResult={annuityResult}
            guaranteeYears={annuity.guarantee_years}
          />
        )}

        <StateComparison params={params} stateComparisonResult={comparisons.stateComparisonResult}
          isComparingStates={comparisons.isComparingStates} selectedCompareStates={comparisons.selectedCompareStates}
          onCompareStates={comparisons.handleCompareStates} onToggleCompareState={comparisons.toggleCompareState}
          onResetComparison={() => { comparisons.setStateComparisonResult(null); comparisons.setSelectedCompareStates([]); }} />

        <SSTimingComparison ssTimingResult={comparisons.ssTimingResult} isComparingSSTiming={comparisons.isComparingSSTiming}
          birthYear={comparisons.birthYear} setBirthYear={comparisons.setBirthYear} piaMonthly={comparisons.piaMonthly} setPiaMonthly={comparisons.setPiaMonthly}
          onCompare={comparisons.handleCompareSSTimings} onReset={() => comparisons.setSSTimingResult(null)} />

        <AllocationComparison allocationResult={comparisons.allocationResult} isComparingAllocations={comparisons.isComparingAllocations}
          onCompare={comparisons.handleCompareAllocations} onReset={() => comparisons.setAllocationResult(null)} />

        <OutcomeDistribution result={result} />
        <TaxSummary result={result} state={params.state} />
        {result.year_breakdown.length > 0 && <YearBreakdownTable result={result} />}

        <NextStepsCTA hasAnnuity={params.has_annuity} />
      </CollapsibleSection>
    </div>
  );
}

/* ============================================ */
/* Sub-components                               */
/* ============================================ */

function HeroAnswer({
  successRate,
  tenYearRisk,
  medianFinalReal,
  initialWithdrawalRate,
  params,
  portfolioValue,
}: {
  successRate: number;
  tenYearRisk: number;
  medianFinalReal: number;
  initialWithdrawalRate: number;
  params: SimulationInput;
  portfolioValue: number;
}) {
  const spendingLine =
    params.spending_mode === "real"
      ? `${formatCurrency(params.annual_spending)}/yr in today's dollars`
      : `${formatCurrency(params.annual_spending)}/yr flat nominal`;
  const inflationLine =
    params.inflation_model === "historical"
      ? "historical CPI sampling"
      : `fixed ${(params.inflation_rate * 100).toFixed(1)}% inflation`;

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-white p-6 shadow-[var(--shadow-sm)] md:p-8">
      <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">
        Outcome
      </div>
      <div className="mt-3 grid gap-6 md:grid-cols-[auto_1fr] md:items-center">
        <div>
          <div className="bg-gradient-golden bg-clip-text text-5xl font-bold tabular-nums text-transparent md:text-6xl">
            {formatPercent(successRate)}
          </div>
          <div className="mt-1 max-w-xs text-sm leading-snug text-[var(--color-text-muted)]">
            of simulated paths last through age {params.max_age}
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-3 sm:border-l sm:border-[var(--color-border-light)] sm:pl-6">
          <HeroMetric
            label="Median ending (real)"
            value={formatCurrency(medianFinalReal)}
            detail={`Today's $ at age ${params.max_age}`}
          />
          <HeroMetric
            label="10-year depletion risk"
            value={formatPercent(tenYearRisk)}
            detail="Running out within a decade"
          />
          <HeroMetric
            label="Year-1 withdrawal rate"
            value={`${initialWithdrawalRate.toFixed(1)}%`}
            detail="Off the starting portfolio"
          />
        </div>
      </div>
      <p className="mt-6 border-t border-[var(--color-border-light)] pt-4 text-xs leading-relaxed text-[var(--color-text-light)]">
        {formatCurrency(portfolioValue)} at age {params.current_age}, spending {spendingLine} in {params.state}. Inflation: {inflationLine}.
      </p>
    </div>
  );
}

function HeroMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div>
      <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">
        {label}
      </div>
      <div className="mt-1 text-xl font-semibold tabular-nums text-[var(--color-text)]">
        {value}
      </div>
      <div className="mt-0.5 text-xs text-[var(--color-text-muted)]">{detail}</div>
    </div>
  );
}

function PortfolioChart({ result, ages, selectedYearIndex, setSelectedYearIndex }: {
  result: SimulationResult; ages: number[]; selectedYearIndex: number | null; setSelectedYearIndex: (index: number | null) => void;
}) {
  const chartData = useMemo(() => [
    { x: ages, y: result.percentile_paths.p95, type: "scatter" as const, mode: "lines" as const, line: { color: "rgba(217,119,6,0.4)", width: 1, dash: "dot" as const }, name: "95th percentile", legendgroup: "outer", hoverinfo: "skip" as const },
    { x: ages, y: result.percentile_paths.p5, type: "scatter" as const, mode: "lines" as const, fill: "tonexty" as const, fillcolor: "rgba(217,119,6,0.08)", line: { color: "rgba(217,119,6,0.4)", width: 1, dash: "dot" as const }, name: "5th percentile", legendgroup: "outer", hoverinfo: "skip" as const },
    { x: ages, y: result.percentile_paths.p75, type: "scatter" as const, mode: "lines" as const, line: { color: "rgba(217,119,6,0.6)", width: 1.5 }, name: "75th percentile", legendgroup: "inner", hoverinfo: "skip" as const },
    { x: ages, y: result.percentile_paths.p25, type: "scatter" as const, mode: "lines" as const, fill: "tonexty" as const, fillcolor: "rgba(217,119,6,0.15)", line: { color: "rgba(217,119,6,0.6)", width: 1.5 }, name: "25th percentile", legendgroup: "inner", hoverinfo: "skip" as const },
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
    yaxis: { title: { text: "Portfolio value", font: { family: "DM Sans, system-ui, sans-serif", size: 14 } }, gridcolor: colors.gray200, tickformat: "$~s", tickfont: { family: "DM Sans, system-ui, sans-serif", size: 12 }, rangemode: "tozero" as const, showgrid: true, zeroline: true, zerolinecolor: colors.gray300 },
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

function CollapsibleSection({
  title,
  description,
  isOpen,
  onToggle,
  children,
}: {
  title: string;
  description: string;
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-white shadow-[var(--shadow-sm)]">
      <button
        type="button"
        className="flex w-full items-start justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-[var(--color-bg-alt)]/60"
        onClick={onToggle}
        aria-expanded={isOpen}
      >
        <div>
          <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">
            {title}
          </div>
          <p className="mt-1 text-sm leading-relaxed text-[var(--color-text-muted)]">
            {description}
          </p>
        </div>
        <span className="flex items-center gap-2 rounded-full border border-[var(--color-border-light)] bg-[var(--color-bg-alt)] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          {isOpen ? "Hide" : "Open"}
          <span aria-hidden="true">{isOpen ? "−" : "+"}</span>
        </span>
      </button>
      {isOpen && (
        <div className="border-t border-[var(--color-border-light)] bg-[var(--color-bg-alt)]/40 px-4 py-5 space-y-6">
          {children}
        </div>
      )}
    </section>
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
          <DetailRow label="Start of year" value={formatCurrency(year.portfolio_start)} />
          <DetailRow label="End of year" value={formatCurrency(year.portfolio_end)} />
          <DetailRow label="Return" value={`${(year.portfolio_return * 100).toFixed(1)}%`} />
          <DetailRow label="Inflation" value={`${(year.inflation_rate * 100).toFixed(1)}%`} />
        </div>
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-light)] mb-2">Income</h4>
          {year.employment_income > 0 && <DetailRow label="Employment" value={formatCurrency(year.employment_income)} />}
          {year.social_security > 0 && <DetailRow label="Social Security" value={formatCurrency(year.social_security)} />}
          {year.pension > 0 && <DetailRow label="Pension" value={formatCurrency(year.pension)} />}
          {year.dividends > 0 && <DetailRow label="Dividends" value={formatCurrency(year.dividends)} />}
          {year.annuity > 0 && <DetailRow label="Annuity" value={formatCurrency(year.annuity)} />}
          <DetailRow label="Total income" value={formatCurrency(year.total_income)} highlight />
        </div>
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-light)] mb-2">Withdrawals & Taxes</h4>
          <DetailRow label="Spend target" value={formatCurrency(year.spending_target)} />
          <DetailRow label="Spend target (real)" value={formatCurrency(year.spending_target_real)} />
          <DetailRow label="Withdrawal" value={formatCurrency(year.withdrawal)} />
          <DetailRow label="Federal tax" value={formatCurrency(year.federal_tax)} />
          <DetailRow label="State tax" value={formatCurrency(year.state_tax)} />
          <DetailRow label="Total tax" value={formatCurrency(year.total_tax)} highlight />
          <DetailRow label="Effective rate" value={`${(year.effective_tax_rate * 100).toFixed(1)}%`} />
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
          <thead><tr><th>Percentile</th><th>Final portfolio (nominal)</th><th>Final portfolio (real)</th><th>Interpretation</th></tr></thead>
          <tbody>
            <tr><td>5th (conservative)</td><td>{formatCurrency(result.percentiles.p5)}</td><td>{formatCurrency(result.percentiles_real.p5)}</td><td className="text-[var(--color-text-muted)]">95% of outcomes exceed this</td></tr>
            <tr><td>25th</td><td>{formatCurrency(result.percentiles.p25)}</td><td>{formatCurrency(result.percentiles_real.p25)}</td><td className="text-[var(--color-text-muted)]">75% of outcomes are better</td></tr>
            <tr className="!bg-[var(--color-primary-50)] font-semibold"><td>50th (median)</td><td>{formatCurrency(result.percentiles.p50)}</td><td>{formatCurrency(result.percentiles_real.p50)}</td><td className="text-[var(--color-text-muted)]">The &quot;typical&quot; outcome</td></tr>
            <tr><td>75th</td><td>{formatCurrency(result.percentiles.p75)}</td><td>{formatCurrency(result.percentiles_real.p75)}</td><td className="text-[var(--color-text-muted)]">25% of outcomes are better</td></tr>
            <tr><td>95th (optimistic)</td><td>{formatCurrency(result.percentiles.p95)}</td><td>{formatCurrency(result.percentiles_real.p95)}</td><td className="text-[var(--color-text-muted)]">Only 5% exceed this</td></tr>
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
          ["Total withdrawals", formatCurrency(result.total_withdrawn_median)],
          ["Total taxes paid", formatCurrency(result.total_taxes_median)],
          ["Net after-tax income", formatCurrency(result.total_withdrawn_median - result.total_taxes_median)],
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
            <thead><tr><th>Age</th><th>Start</th><th>Spend target</th><th>Income</th><th>Withdrawal</th><th>Taxes</th><th>Rate</th><th>End</th></tr></thead>
            <tbody>
              {result.year_breakdown.map((year) => (
                <tr key={year.year_index}>
                  <td>{year.age}</td>
                  <td>{formatCurrency(year.portfolio_start)}</td>
                  <td title={`Real: ${formatCurrency(year.spending_target_real)}, inflation: ${(year.inflation_rate * 100).toFixed(1)}%`}>{formatCurrency(year.spending_target)}</td>
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
      <h3 className="mb-4 text-lg font-semibold">Further resources</h3>
      <div className="space-y-3">
        {[
          { href: "https://www.nerdwallet.com/best/investing/financial-advisors-for-retirement", icon: "\uD83D\uDC64", title: "Advisor directories", desc: "Find third-party directories if you want professional guidance beyond the calculator." },
          { href: "https://investor.vanguard.com/investment-products/index-funds", icon: "\uD83D\uDCC8", title: "Index fund reference", desc: "Read a third-party primer on diversified, low-cost fund structures." },
          ...(hasAnnuity ? [{ href: "https://www.immediateannuities.com/", icon: "\uD83D\uDEE1\uFE0F", title: "Annuity quote reference", desc: "Review third-party annuity quote marketplaces for payout comparisons." }] : []),
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
