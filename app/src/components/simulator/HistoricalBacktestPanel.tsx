"use client";

import type {
  HistoricalBacktestResult,
  HistoricalCohortResult,
  SimulationResult,
} from "../../lib/api";
import {
  formatCurrency,
  formatPercent,
  getErrorInfo,
} from "../../lib/simulatorUtils";

const sectionCls = "section-card";
const labelCls = "text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]";
const valueCls = "mt-1.5 text-2xl font-bold tabular-nums text-[var(--color-text)]";

interface HistoricalBacktestPanelProps {
  monteCarloResult: SimulationResult;
  historicalBacktestResult: HistoricalBacktestResult | null;
  isLoading: boolean;
  error: unknown;
  includeMortality: boolean;
}

function formatSignedPercentPoints(value: number): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)} pts`;
}

function formatSignedCurrency(value: number): string {
  return `${value >= 0 ? "+" : "-"}${formatCurrency(Math.abs(value)).replace("$", "$")}`;
}

function pickNotableCohorts(result: HistoricalBacktestResult): HistoricalCohortResult[] {
  const cohortByYear = new Map(result.results.map((cohort) => [cohort.start_year, cohort]));
  const stressYears = [1966, 1973, 2000, 2008]
    .map((year) => cohortByYear.get(year))
    .filter((cohort): cohort is HistoricalCohortResult => cohort !== undefined);

  if (stressYears.length > 0) {
    return stressYears;
  }

  return [...result.results]
    .sort((a, b) => a.final_value_real - b.final_value_real)
    .slice(0, 4)
    .sort((a, b) => a.start_year - b.start_year);
}

export function HistoricalBacktestPanel({
  monteCarloResult,
  historicalBacktestResult,
  isLoading,
  error,
  includeMortality,
}: HistoricalBacktestPanelProps) {
  if (!historicalBacktestResult && !isLoading && !error) {
    return null;
  }

  if (isLoading) {
    return (
      <section className={sectionCls}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold">Monte Carlo vs historical cohorts</h3>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">
              Replaying this exact plan over every valid historical start year.
            </p>
          </div>
          <div className="h-6 w-6 animate-spin-slow rounded-full border-2 border-[var(--color-primary-200)] border-t-[var(--color-primary)]" />
        </div>
      </section>
    );
  }

  if (error) {
    const errorInfo = getErrorInfo(error);

    return (
      <section className={`${sectionCls} border-[var(--color-warning)] bg-[var(--color-warning-light)]/30`}>
        <h3 className="text-lg font-semibold">Monte Carlo vs historical cohorts</h3>
        <p className="mt-2 text-sm text-[var(--color-text-muted)]">
          Historical replay is unavailable right now. {errorInfo.message}
        </p>
      </section>
    );
  }

  if (!historicalBacktestResult) {
    return null;
  }

  const notableCohorts = pickNotableCohorts(historicalBacktestResult);
  const successGap = historicalBacktestResult.success_rate - monteCarloResult.success_rate;
  const realMedianGap = historicalBacktestResult.median_final_value_real - monteCarloResult.median_final_value_real;
  const comparisonRows = [
    {
      label: "Success rate",
      monteCarlo: formatPercent(monteCarloResult.success_rate),
      historical: formatPercent(historicalBacktestResult.success_rate),
      gap: formatSignedPercentPoints(successGap),
      positive: successGap >= 0,
    },
    {
      label: "Median final (real)",
      monteCarlo: formatCurrency(monteCarloResult.median_final_value_real),
      historical: formatCurrency(historicalBacktestResult.median_final_value_real),
      gap: formatSignedCurrency(realMedianGap),
      positive: realMedianGap >= 0,
    },
    {
      label: "Median final (nominal)",
      monteCarlo: formatCurrency(monteCarloResult.median_final_value),
      historical: formatCurrency(historicalBacktestResult.median_final_value),
      gap: formatSignedCurrency(historicalBacktestResult.median_final_value - monteCarloResult.median_final_value),
      positive: historicalBacktestResult.median_final_value >= monteCarloResult.median_final_value,
    },
    {
      label: "Median lifetime taxes",
      monteCarlo: formatCurrency(monteCarloResult.total_taxes_median),
      historical: formatCurrency(historicalBacktestResult.total_taxes_median),
      gap: formatSignedCurrency(historicalBacktestResult.total_taxes_median - monteCarloResult.total_taxes_median),
      positive: historicalBacktestResult.total_taxes_median <= monteCarloResult.total_taxes_median,
    },
  ];

  return (
    <section className={sectionCls}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">Monte Carlo vs historical cohorts</h3>
          <p className="mt-1 max-w-2xl text-sm text-[var(--color-text-muted)]">
            Monte Carlo samples many possible futures. Historical replay uses exact market and CPI sequences from each valid retirement start year.
          </p>
        </div>
        <div className="rounded-full bg-[var(--color-gray-50)] px-3 py-1 text-xs font-medium text-[var(--color-text-muted)]">
          {historicalBacktestResult.start_years.length} historical cohorts
        </div>
      </div>

      <div className="mt-4 rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-alt)] px-4 py-3 text-sm text-[var(--color-text-muted)]">
        Historical replay comes in <span className={successGap >= 0 ? "font-semibold text-[var(--color-success)]" : "font-semibold text-[var(--color-danger)]"}>{formatSignedPercentPoints(successGap)}</span> versus Monte Carlo on success rate and{" "}
        <span className={realMedianGap >= 0 ? "font-semibold text-[var(--color-success)]" : "font-semibold text-[var(--color-danger)]"}>{formatSignedCurrency(realMedianGap)}</span> on median real ending wealth.
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-4">
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-white p-4">
          <div className={labelCls}>Historical success</div>
          <div className={valueCls}>{formatPercent(historicalBacktestResult.success_rate)}</div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">Across all replayed start years</div>
        </div>
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-white p-4">
          <div className={labelCls}>Strongest start year</div>
          <div className={valueCls}>{historicalBacktestResult.strongest_start_year}</div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">Highest ending value</div>
        </div>
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-white p-4">
          <div className={labelCls}>Weakest start year</div>
          <div className={valueCls}>{historicalBacktestResult.weakest_start_year}</div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">Lowest ending value</div>
        </div>
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-white p-4">
          <div className={labelCls}>Median final (real)</div>
          <div className={valueCls}>{formatCurrency(historicalBacktestResult.median_final_value_real)}</div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">Today&apos;s dollars after {historicalBacktestResult.horizon_years} years</div>
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[1.25fr_0.95fr]">
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-white p-4">
          <h4 className="text-sm font-semibold text-[var(--color-text)]">Side-by-side summary</h4>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full table-auto text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border-light)] text-[var(--color-text-light)]">
                  <th className="pb-2 pr-4 font-medium">Metric</th>
                  <th className="pb-2 pr-4 font-medium">Monte Carlo</th>
                  <th className="pb-2 pr-4 font-medium">Historical</th>
                  <th className="pb-2 font-medium">Gap</th>
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row) => (
                  <tr key={row.label} className="border-b border-[var(--color-border-light)]/70 last:border-b-0">
                    <td className="py-2.5 pr-4 text-[var(--color-text-muted)]">{row.label}</td>
                    <td className="py-2.5 pr-4 font-medium text-[var(--color-text)]">{row.monteCarlo}</td>
                    <td className="py-2.5 pr-4 font-medium text-[var(--color-text)]">{row.historical}</td>
                    <td className={`py-2.5 font-medium ${row.positive ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}`}>
                      {row.gap}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-white p-4">
          <h4 className="text-sm font-semibold text-[var(--color-text)]">Stress years</h4>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full table-auto text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border-light)] text-[var(--color-text-light)]">
                  <th className="pb-2 pr-4 font-medium">Start year</th>
                  <th className="pb-2 pr-4 font-medium">Outcome</th>
                  <th className="pb-2 pr-4 font-medium">Final real</th>
                  <th className="pb-2 font-medium">Failure age</th>
                </tr>
              </thead>
              <tbody>
                {notableCohorts.map((cohort) => (
                  <tr key={cohort.start_year} className="border-b border-[var(--color-border-light)]/70 last:border-b-0">
                    <td className="py-2.5 pr-4 font-medium text-[var(--color-text)]">{cohort.start_year}</td>
                    <td className={`py-2.5 pr-4 font-medium ${cohort.success ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}`}>
                      {cohort.success ? "Held up" : "Failed"}
                    </td>
                    <td className="py-2.5 pr-4 font-medium text-[var(--color-text)]">{formatCurrency(cohort.final_value_real)}</td>
                    <td className="py-2.5 text-[var(--color-text-muted)]">{cohort.failure_age ?? "\u2014"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <p className="mt-4 text-xs text-[var(--color-text-light)]">
        Historical replay always disables mortality so cohort differences isolate market, inflation, and tax sequence effects.{includeMortality ? " Your Monte Carlo result above still includes mortality." : ""}
      </p>
    </section>
  );
}
