import type { SimulationResult } from "../lib/api";

interface ResultsSummaryProps {
  result: SimulationResult;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function ResultsSummary({ result }: ResultsSummaryProps) {
  const successColor =
    result.success_rate >= 0.9
      ? "#10b981"
      : result.success_rate >= 0.7
        ? "#f59e0b"
        : "#ef4444";

  return (
    <div className="results-summary">
      <div className="summary-grid">
        <div className="summary-card primary">
          <div className="card-label">Success Rate</div>
          <div className="card-value" style={{ color: successColor }}>
            {formatPercent(result.success_rate)}
          </div>
          <div className="card-description">
            Probability of not running out of money
          </div>
        </div>

        <div className="summary-card">
          <div className="card-label">Median Final Value</div>
          <div className="card-value">
            {formatCurrency(result.median_final_value)}
          </div>
          <div className="card-description">
            50th percentile portfolio value at end
          </div>
        </div>

        <div className="summary-card">
          <div className="card-label">Total Withdrawals</div>
          <div className="card-value">
            {formatCurrency(result.total_withdrawn_median)}
          </div>
          <div className="card-description">Median total withdrawn over period</div>
        </div>

        <div className="summary-card">
          <div className="card-label">Total Taxes</div>
          <div className="card-value">
            {formatCurrency(result.total_taxes_median)}
          </div>
          <div className="card-description">Estimated taxes paid</div>
        </div>
      </div>

      <div className="percentile-breakdown">
        <h4>Portfolio Value Distribution</h4>
        <div className="percentile-row">
          <span className="percentile-label">5th percentile (worst case)</span>
          <span className="percentile-value">
            {formatCurrency(result.percentiles.p5)}
          </span>
        </div>
        <div className="percentile-row">
          <span className="percentile-label">25th percentile</span>
          <span className="percentile-value">
            {formatCurrency(result.percentiles.p25)}
          </span>
        </div>
        <div className="percentile-row highlight">
          <span className="percentile-label">50th percentile (median)</span>
          <span className="percentile-value">
            {formatCurrency(result.percentiles.p50)}
          </span>
        </div>
        <div className="percentile-row">
          <span className="percentile-label">75th percentile</span>
          <span className="percentile-value">
            {formatCurrency(result.percentiles.p75)}
          </span>
        </div>
        <div className="percentile-row">
          <span className="percentile-label">95th percentile (best case)</span>
          <span className="percentile-value">
            {formatCurrency(result.percentiles.p95)}
          </span>
        </div>
      </div>

      {result.median_depletion_year && (
        <div className="depletion-warning">
          <span className="warning-icon">!</span>
          <span>
            In scenarios where the portfolio is depleted, the median depletion
            occurs at year {result.median_depletion_year.toFixed(1)}.
          </span>
        </div>
      )}
    </div>
  );
}
