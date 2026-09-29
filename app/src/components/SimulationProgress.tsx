"use client";

import type { YearProgressSummary } from "../lib/api";

interface SimulationProgressProps {
  currentYear: number;
  totalYears: number;
  progress?: number;
  message?: string | null;
  yearSummary?: YearProgressSummary | null;
}

const compactCurrency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function SimulationProgress({
  currentYear,
  totalYears,
  progress,
  message,
  yearSummary,
}: SimulationProgressProps) {
  const progressFraction = progress ?? (totalYears > 0 ? currentYear / totalYears : 0);
  const percentage = Math.round(Math.max(0, Math.min(1, progressFraction)) * 100);
  const displayYear = Number.isInteger(currentYear)
    ? currentYear
    : Math.min(totalYears, Math.floor(currentYear) + 1);

  return (
    <div className="mx-auto max-w-md space-y-4 py-4">
      <div className="text-center">
        <div className="mb-1 text-xs font-semibold uppercase tracking-widest text-[var(--color-text-light)]">
          Running simulation
        </div>
        <div className="text-sm text-[var(--color-text-muted)]">
          {message || "Calculating taxes with PolicyEngine..."}
        </div>
      </div>
      <div className="space-y-2">
        <div
          className="h-2.5 w-full overflow-hidden rounded-full bg-[var(--color-gray-200)]"
          role="progressbar"
          aria-valuenow={percentage}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full rounded-full bg-gradient-golden progress-fill-transition progress-bar-shimmer"
            style={{ width: `${percentage}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-[var(--color-text-light)]">
            Year {displayYear} of {totalYears}
          </span>
          <span className="font-bold tabular-nums text-[var(--color-primary)]">
            {percentage}%
          </span>
        </div>
      </div>
      {yearSummary && (
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-primary-50)] px-4 py-3 text-sm shadow-[var(--shadow-sm)]">
          <div className="mb-2 flex items-center justify-between gap-3">
            <span className="font-semibold text-[var(--color-text)]">
              Year {yearSummary.year} result
            </span>
            <span className="text-xs font-medium text-[var(--color-text-muted)]">
              Age {yearSummary.age}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">
                Median portfolio
              </div>
              <div className="font-bold tabular-nums text-[var(--color-primary)]">
                {compactCurrency.format(yearSummary.median_portfolio)}
              </div>
            </div>
            <div>
              <div className="text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">
                Middle range
              </div>
              <div className="font-bold tabular-nums text-[var(--color-text)]">
                {compactCurrency.format(yearSummary.p25_portfolio)} -{" "}
                {compactCurrency.format(yearSummary.p75_portfolio)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
