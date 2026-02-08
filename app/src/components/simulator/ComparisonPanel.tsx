import { useMemo } from "react";
import type {
  SimulationInput,
  StateComparisonResult,
  SSTimingComparisonResult,
  AllocationComparisonResult,
} from "../../lib/api";
import type { AnnuityComparisonResult } from "../../lib/simulatorUtils";
import { formatCurrency, formatPercent } from "../../lib/simulatorUtils";
import { US_STATES, NO_TAX_STATES } from "../../lib/constants";

// ============================================
// Annuity comparison
// ============================================

interface AnnuityComparisonProps {
  annuityResult: AnnuityComparisonResult;
  guaranteeYears: number;
}

export function AnnuityComparison({ annuityResult, guaranteeYears }: AnnuityComparisonProps) {
  return (
    <div className="summary-section annuity-comparison">
      <h3>Annuity Comparison</h3>
      <div className="comparison-grid">
        <div className="comparison-card">
          <div className="comparison-label">Annuity Guaranteed Total</div>
          <div className="comparison-value">
            {formatCurrency(annuityResult.annuity_total_guaranteed)}
          </div>
          <div className="comparison-desc">
            Over {guaranteeYears} year guarantee period
          </div>
        </div>
        <div className="comparison-card">
          <div className="comparison-label">Portfolio Median Total</div>
          <div className="comparison-value">
            {formatCurrency(annuityResult.simulation_median_total_income)}
          </div>
          <div className="comparison-desc">
            Median total income from portfolio
          </div>
        </div>
        <div className="comparison-card highlight">
          <div className="comparison-label">Portfolio Beats Annuity</div>
          <div
            className="comparison-value"
            style={{
              color:
                annuityResult.probability_simulation_beats_annuity >= 0.6
                  ? "#10b981"
                  : annuityResult.probability_simulation_beats_annuity >= 0.4
                    ? "#f59e0b"
                    : "#ef4444",
            }}
          >
            {formatPercent(annuityResult.probability_simulation_beats_annuity)}
          </div>
          <div className="comparison-desc">Probability</div>
        </div>
      </div>
      <div className="recommendation">
        <strong>Recommendation:</strong> {annuityResult.recommendation}
      </div>
    </div>
  );
}

// ============================================
// State comparison
// ============================================

interface StateComparisonProps {
  params: SimulationInput;
  stateComparisonResult: StateComparisonResult | null;
  isComparingStates: boolean;
  selectedCompareStates: string[];
  onCompareStates: (states?: string[]) => void;
  onToggleCompareState: (state: string) => void;
  onResetComparison: () => void;
}

export function StateComparison({
  params,
  stateComparisonResult,
  isComparingStates,
  selectedCompareStates,
  onCompareStates,
  onToggleCompareState,
  onResetComparison,
}: StateComparisonProps) {
  const filteredStates = useMemo(
    () => US_STATES.filter(s => s !== params.state),
    [params.state]
  );

  return (
    <div className="summary-section state-comparison">
      <h3>Compare states</h3>
      <p className="section-desc">
        See how relocating could affect your taxes and outcomes.
      </p>

      {!stateComparisonResult && !isComparingStates && (
        <div className="state-picker">
          <div className="state-picker-row">
            <button
              className="btn-secondary"
              onClick={() => onCompareStates()}
              disabled={isComparingStates}
            >
              Compare to No-Income-Tax States
            </button>
          </div>

          <div className="state-picker-divider">or select specific states</div>

          <div className="state-chips">
            {filteredStates.map(state => (
              <button
                key={state}
                className={`state-chip ${selectedCompareStates.includes(state) ? 'selected' : ''} ${NO_TAX_STATES.includes(state) ? 'no-tax' : ''}`}
                onClick={() => onToggleCompareState(state)}
                disabled={!selectedCompareStates.includes(state) && selectedCompareStates.length >= 5}
              >
                {state}
              </button>
            ))}
          </div>

          {selectedCompareStates.length > 0 && (
            <button
              className="btn-primary"
              onClick={() => onCompareStates(selectedCompareStates)}
              disabled={isComparingStates}
            >
              Compare {selectedCompareStates.length} State{selectedCompareStates.length > 1 ? 's' : ''}
            </button>
          )}
        </div>
      )}

      {isComparingStates && (
        <div className="loading-indicator">
          <div className="spinner"></div>
          Comparing states...
        </div>
      )}

      {stateComparisonResult && (
        <div className="state-comparison-results">
          <table className="state-table">
            <thead>
              <tr>
                <th>State</th>
                <th>Total Taxes</th>
                <th>Tax Savings</th>
                <th>Success Rate</th>
              </tr>
            </thead>
            <tbody>
              {stateComparisonResult.results
                .sort((a, b) =>
                  stateComparisonResult.tax_savings_vs_base[b.state] -
                  stateComparisonResult.tax_savings_vs_base[a.state]
                )
                .map((r) => (
                <tr key={r.state} className={r.state === params.state ? "current-state" : ""}>
                  <td>
                    {r.state}
                    {r.state === params.state && " (current)"}
                  </td>
                  <td>{formatCurrency(r.total_taxes_median)}</td>
                  <td
                    style={{
                      color: stateComparisonResult.tax_savings_vs_base[r.state] > 0
                        ? "#10b981"
                        : stateComparisonResult.tax_savings_vs_base[r.state] < 0
                          ? "#ef4444"
                          : "inherit",
                      fontWeight: stateComparisonResult.tax_savings_vs_base[r.state] !== 0 ? 600 : 400,
                    }}
                  >
                    {stateComparisonResult.tax_savings_vs_base[r.state] > 0 && "+"}
                    {formatCurrency(stateComparisonResult.tax_savings_vs_base[r.state])}
                  </td>
                  <td>{formatPercent(r.success_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="tax-note">
            Tax savings show lifetime difference compared to {params.state}.
            Positive values mean you save money by relocating.
          </p>
          <button
            className="btn-secondary"
            onClick={onResetComparison}
            style={{ marginTop: '1rem' }}
          >
            Compare Different States
          </button>
        </div>
      )}
    </div>
  );
}

// ============================================
// SS timing comparison
// ============================================

interface SSTimingComparisonProps {
  ssTimingResult: SSTimingComparisonResult | null;
  isComparingSSTiming: boolean;
  birthYear: number;
  setBirthYear: (year: number) => void;
  piaMonthly: number;
  setPiaMonthly: (pia: number) => void;
  onCompare: () => void;
  onReset: () => void;
}

export function SSTimingComparison({
  ssTimingResult,
  isComparingSSTiming,
  birthYear,
  setBirthYear,
  piaMonthly,
  setPiaMonthly,
  onCompare,
  onReset,
}: SSTimingComparisonProps) {
  return (
    <div className="summary-section ss-timing">
      <h3>When should you claim Social Security?</h3>
      <p className="section-desc">
        Compare how different claiming ages affect your lifetime benefits and portfolio.
      </p>

      {!ssTimingResult && !isComparingSSTiming && (
        <div className="ss-timing-inputs">
          <div className="ss-timing-row">
            <div className="wizard-field">
              <label>Your Birth Year</label>
              <input
                type="number"
                value={birthYear}
                onChange={(e) => setBirthYear(Number(e.target.value))}
                min={1930}
                max={2000}
              />
              <div className="wizard-field-hint">
                Used to determine your Full Retirement Age
              </div>
            </div>
            <div className="wizard-field">
              <label>Estimated Benefit at FRA (PIA)</label>
              <div className="wizard-field-prefix">
                <span>$</span>
                <input
                  type="number"
                  value={piaMonthly}
                  onChange={(e) => setPiaMonthly(Number(e.target.value))}
                  min={0}
                  max={10000}
                  step={100}
                />
              </div>
              <div className="wizard-field-hint">
                Your benefit if you claim at full retirement age (check ssa.gov/myaccount)
              </div>
            </div>
          </div>
          <button
            className="btn-primary"
            onClick={onCompare}
            disabled={isComparingSSTiming || piaMonthly <= 0}
          >
            Compare Claiming Ages
          </button>
        </div>
      )}

      {isComparingSSTiming && (
        <div className="loading-indicator">
          <div className="spinner"></div>
          Comparing claiming ages (this takes a few minutes)...
        </div>
      )}

      {ssTimingResult && (
        <div className="ss-timing-results">
          <div className="ss-timing-summary">
            <div className="ss-timing-fra">
              <span className="label">Your Full Retirement Age:</span>
              <span className="value">
                {Math.floor(ssTimingResult.full_retirement_age)} years
                {ssTimingResult.full_retirement_age % 1 > 0 &&
                  ` ${Math.round((ssTimingResult.full_retirement_age % 1) * 12)} months`}
              </span>
            </div>
            <div className="ss-timing-optimal">
              <span className="label">Optimal for success rate:</span>
              <span className="value highlight">
                Claim at age {ssTimingResult.optimal_claiming_age}
              </span>
            </div>
            {ssTimingResult.optimal_for_longevity !== ssTimingResult.optimal_claiming_age && (
              <div className="ss-timing-optimal">
                <span className="label">Optimal if you live long:</span>
                <span className="value">
                  Claim at age {ssTimingResult.optimal_for_longevity}
                </span>
              </div>
            )}
          </div>

          <table className="ss-timing-table">
            <thead>
              <tr>
                <th>Claiming Age</th>
                <th>Monthly Benefit</th>
                <th>Adjustment</th>
                <th>Success Rate</th>
                <th>Lifetime SS Income</th>
                <th>Breakeven vs 62</th>
              </tr>
            </thead>
            <tbody>
              {ssTimingResult.results.map((r) => (
                <tr
                  key={r.claiming_age}
                  className={
                    r.claiming_age === ssTimingResult.optimal_claiming_age
                      ? "optimal"
                      : r.claiming_age === Math.round(ssTimingResult.full_retirement_age)
                        ? "fra"
                        : ""
                  }
                >
                  <td>
                    {r.claiming_age}
                    {r.claiming_age === Math.round(ssTimingResult.full_retirement_age) && (
                      <span className="fra-badge">FRA</span>
                    )}
                    {r.claiming_age === ssTimingResult.optimal_claiming_age && (
                      <span className="optimal-badge">Best</span>
                    )}
                  </td>
                  <td>${r.monthly_benefit.toLocaleString()}/mo</td>
                  <td
                    style={{
                      color:
                        r.adjustment_factor < 1
                          ? "#ef4444"
                          : r.adjustment_factor > 1
                            ? "#10b981"
                            : "inherit",
                    }}
                  >
                    {r.adjustment_factor < 1
                      ? `-${((1 - r.adjustment_factor) * 100).toFixed(0)}%`
                      : r.adjustment_factor > 1
                        ? `+${((r.adjustment_factor - 1) * 100).toFixed(0)}%`
                        : "\u2014"}
                  </td>
                  <td>{formatPercent(r.success_rate)}</td>
                  <td>{formatCurrency(r.total_ss_income_median)}</td>
                  <td>
                    {r.breakeven_vs_62
                      ? `Age ${r.breakeven_vs_62}`
                      : r.claiming_age === 62
                        ? "\u2014"
                        : "N/A"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="tax-note">
            Early claiming (before FRA) permanently reduces your benefit. Delayed claiming (after FRA, up to 70)
            permanently increases it by 8% per year. Breakeven shows when total cumulative benefits from waiting exceed claiming at 62.
          </p>

          <button
            className="btn-secondary"
            onClick={onReset}
            style={{ marginTop: "1rem" }}
          >
            Change Assumptions
          </button>
        </div>
      )}
    </div>
  );
}

// ============================================
// Allocation comparison
// ============================================

interface AllocationComparisonProps {
  allocationResult: AllocationComparisonResult | null;
  isComparingAllocations: boolean;
  onCompare: () => void;
  onReset: () => void;
}

export function AllocationComparison({
  allocationResult,
  isComparingAllocations,
  onCompare,
  onReset,
}: AllocationComparisonProps) {
  return (
    <div className="summary-section allocation-comparison">
      <h3>How does asset allocation affect your plan?</h3>
      <p className="section-description">
        Compare different stock/bond mixes to find the right balance of growth and safety for your situation.
      </p>

      {!allocationResult && (
        <button
          className="btn-primary"
          onClick={onCompare}
          disabled={isComparingAllocations}
        >
          {isComparingAllocations ? "Comparing..." : "Compare Allocations"}
        </button>
      )}

      {allocationResult && (
        <div className="allocation-results">
          <div className="allocation-summary">
            <div className="allocation-optimal">
              <span className="allocation-optimal-label">Optimal for Success</span>
              <span className="allocation-optimal-value">
                {Math.round(allocationResult.optimal_for_success * 100)}% Stocks
              </span>
            </div>
            {allocationResult.optimal_for_safety !== allocationResult.optimal_for_success && (
              <div className="allocation-optimal">
                <span className="allocation-optimal-label">Optimal for Safety</span>
                <span className="allocation-optimal-value">
                  {Math.round(allocationResult.optimal_for_safety * 100)}% Stocks
                </span>
              </div>
            )}
          </div>

          <table className="allocation-table">
            <thead>
              <tr>
                <th>Allocation</th>
                <th>Success Rate</th>
                <th>Median Final</th>
                <th>Worst Case (5th)</th>
                <th>Best Case (95th)</th>
                <th>Volatility</th>
              </tr>
            </thead>
            <tbody>
              {allocationResult.results.map((r) => (
                <tr
                  key={r.stock_allocation}
                  className={
                    r.stock_allocation === allocationResult.optimal_for_success
                      ? "optimal-row"
                      : ""
                  }
                >
                  <td>
                    {Math.round(r.stock_allocation * 100)}% / {Math.round(r.bond_allocation * 100)}%
                    {r.stock_allocation === allocationResult.optimal_for_success && (
                      <span className="optimal-badge">Best</span>
                    )}
                  </td>
                  <td
                    style={{
                      color:
                        r.success_rate >= 0.9
                          ? "#10b981"
                          : r.success_rate >= 0.8
                            ? "#84cc16"
                            : r.success_rate >= 0.7
                              ? "#eab308"
                              : "#ef4444",
                    }}
                  >
                    {formatPercent(r.success_rate)}
                  </td>
                  <td>{formatCurrency(r.median_final_value)}</td>
                  <td style={{ color: r.percentile_5_final_value <= 0 ? "#ef4444" : "inherit" }}>
                    {formatCurrency(r.percentile_5_final_value)}
                  </td>
                  <td>{formatCurrency(r.percentile_95_final_value)}</td>
                  <td>{(r.volatility * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="allocation-recommendation">
            {allocationResult.recommendation}
          </p>

          <p className="tax-note">
            Stocks historically offer higher returns but more volatility. Bonds provide stability but lower growth.
            A balanced allocation can reduce risk while maintaining reasonable growth potential.
          </p>

          <button
            className="btn-secondary"
            onClick={onReset}
            style={{ marginTop: "1rem" }}
          >
            Hide Results
          </button>
        </div>
      )}
    </div>
  );
}
