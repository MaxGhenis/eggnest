"use client";

interface SimulationProgressProps {
  currentYear: number;
  totalYears: number;
}

export function SimulationProgress({ currentYear, totalYears }: SimulationProgressProps) {
  const percentage = totalYears > 0 ? Math.round((currentYear / totalYears) * 100) : 0;

  return (
    <div className="mx-auto max-w-md space-y-3 py-4">
      <div className="flex items-center justify-between text-sm">
        <span className="text-[var(--color-text-muted)]">
          Calculating taxes with PolicyEngine...
        </span>
        <span className="font-semibold text-[var(--color-primary)]">
          {percentage}%
        </span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-[var(--color-gray-200)]"
        role="progressbar"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full bg-gradient-golden progress-fill-transition"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="text-center text-xs text-[var(--color-text-light)]">
        Year {currentYear} of {totalYears}
      </div>
    </div>
  );
}
