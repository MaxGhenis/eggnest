"use client";

import { Skeleton } from "./Skeleton";
import { SimulationProgress } from "./SimulationProgress";

interface ResultsSkeletonProps {
  currentYear: number;
  totalYears: number;
}

export function ResultsSkeleton({
  currentYear,
  totalYears,
}: ResultsSkeletonProps) {
  return (
    <div className="relative space-y-6">
      {/* Back button skeleton */}
      <Skeleton variant="rect" width={120} height={36} />

      {/* Success banner skeleton */}
      <Skeleton variant="rect" width="100%" height={80} />

      {/* Metrics grid skeleton */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Skeleton variant="rect" height={100} className="!bg-[var(--color-primary-50)]" />
        <Skeleton variant="rect" height={100} />
        <Skeleton variant="rect" height={100} />
        <Skeleton variant="rect" height={100} />
      </div>

      {/* Chart skeleton */}
      <div className="space-y-3">
        <Skeleton variant="text" width={200} />
        <Skeleton variant="rect" height={420} />
      </div>

      {/* Table skeleton */}
      <div className="space-y-3">
        <Skeleton variant="text" width={200} />
        <div className="space-y-2">
          <div className="flex gap-4">
            <Skeleton variant="text" width="30%" />
            <Skeleton variant="text" width="30%" />
            <Skeleton variant="text" width="30%" />
          </div>
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex gap-4">
              <Skeleton variant="text" width="30%" />
              <Skeleton variant="text" width="20%" />
              <Skeleton variant="text" width="40%" />
            </div>
          ))}
        </div>
      </div>

      {/* Tax summary skeleton */}
      <div className="space-y-3">
        <Skeleton variant="text" width={180} />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex justify-between">
              <Skeleton variant="text" width="40%" />
              <Skeleton variant="text" width="20%" />
            </div>
          ))}
        </div>
      </div>

      {/* What-if skeleton */}
      <div className="space-y-3">
        <Skeleton variant="text" width={160} />
        <Skeleton variant="text" width={280} />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} variant="rect" height={72} />
          ))}
        </div>
      </div>

      {/* Progress overlay */}
      <div className="absolute inset-0 flex items-center justify-center rounded-[var(--radius-lg)] bg-white/85 backdrop-blur-md">
        <div className="w-full max-w-sm rounded-[var(--radius-xl)] border border-[var(--color-border-light)] bg-white p-6 shadow-[var(--shadow-lg)] animate-pulse-glow">
          <SimulationProgress
            currentYear={currentYear}
            totalYears={totalYears}
          />
        </div>
      </div>
    </div>
  );
}
