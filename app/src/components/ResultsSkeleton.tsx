import { Skeleton } from "./Skeleton";
import { SimulationProgress } from "./SimulationProgress";
import "../styles/Skeleton.css";

interface ResultsSkeletonProps {
  currentYear: number;
  totalYears: number;
}

/**
 * Skeleton loading state for the simulation results view.
 * Matches the layout of the actual results to provide visual continuity.
 */
export function ResultsSkeleton({
  currentYear,
  totalYears,
}: ResultsSkeletonProps) {
  return (
    <div className="skeleton-results">
      {/* Back button skeleton */}
      <Skeleton variant="rect" className="skeleton-back-btn" />

      {/* Success interpretation banner skeleton */}
      <Skeleton variant="rect" className="skeleton-interpretation" />

      {/* Metrics grid skeleton */}
      <div className="skeleton-metrics-grid">
        <Skeleton variant="rect" className="skeleton-metric-card primary" />
        <Skeleton variant="rect" className="skeleton-metric-card" />
        <Skeleton variant="rect" className="skeleton-metric-card" />
        <Skeleton variant="rect" className="skeleton-metric-card" />
      </div>

      {/* Chart skeleton */}
      <div className="skeleton-chart">
        <Skeleton variant="text" className="skeleton-chart-title" />
        <Skeleton variant="rect" className="skeleton-chart-area" />
      </div>

      {/* Outcome distribution table skeleton */}
      <div className="skeleton-summary">
        <Skeleton variant="text" className="skeleton-summary-title" />
        <div className="skeleton-table">
          <div className="skeleton-table-header">
            <Skeleton variant="text" className="skeleton-table-header-cell" />
            <Skeleton variant="text" className="skeleton-table-header-cell" />
            <Skeleton variant="text" className="skeleton-table-header-cell" />
          </div>
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton-table-row">
              <Skeleton variant="text" className="skeleton-table-cell medium" />
              <Skeleton variant="text" className="skeleton-table-cell short" />
              <Skeleton variant="text" className="skeleton-table-cell" />
            </div>
          ))}
        </div>
      </div>

      {/* Tax summary skeleton */}
      <div className="skeleton-summary">
        <Skeleton variant="text" className="skeleton-summary-title" />
        <div className="skeleton-tax-info">
          <div className="skeleton-tax-row">
            <Skeleton variant="text" className="skeleton-tax-label" />
            <Skeleton variant="text" className="skeleton-tax-value" />
          </div>
          <div className="skeleton-tax-row">
            <Skeleton variant="text" className="skeleton-tax-label" />
            <Skeleton variant="text" className="skeleton-tax-value" />
          </div>
          <div className="skeleton-tax-row">
            <Skeleton variant="text" className="skeleton-tax-label" />
            <Skeleton variant="text" className="skeleton-tax-value" />
          </div>
        </div>
        <div className="skeleton-tax-note">
          <Skeleton variant="text" className="skeleton-tax-note-line" />
          <Skeleton variant="text" className="skeleton-tax-note-line" />
        </div>
      </div>

      {/* What-if scenarios skeleton */}
      <div className="skeleton-what-if">
        <Skeleton variant="text" className="skeleton-what-if-title" />
        <Skeleton variant="text" className="skeleton-what-if-desc" />
        <div className="skeleton-what-if-buttons">
          <Skeleton variant="rect" className="skeleton-what-if-btn" />
          <Skeleton variant="rect" className="skeleton-what-if-btn" />
          <Skeleton variant="rect" className="skeleton-what-if-btn" />
          <Skeleton variant="rect" className="skeleton-what-if-btn" />
        </div>
      </div>

      {/* Progress overlay */}
      <div className="skeleton-progress-overlay">
        <SimulationProgress
          currentYear={currentYear}
          totalYears={totalYears}
        />
      </div>
    </div>
  );
}
