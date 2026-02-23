"use client";

interface SimulationProgressProps {
  currentYear: number;
  totalYears: number;
}

export function SimulationProgress({ currentYear, totalYears }: SimulationProgressProps) {
  const percentage = totalYears > 0 ? Math.round((currentYear / totalYears) * 100) : 0;

  return (
    <div className="mx-auto max-w-md space-y-4 py-4">
      <div className="text-center">
        <div className="mb-1 text-xs font-semibold uppercase tracking-widest text-[var(--color-text-light)]">
          Running simulation
        </div>
        <div className="text-sm text-[var(--color-text-muted)]">
          Calculating taxes with PolicyEngine...
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
            Year {currentYear} of {totalYears}
          </span>
          <span className="font-bold tabular-nums text-[var(--color-primary)]">
            {percentage}%
          </span>
        </div>
      </div>
    </div>
  );
}
