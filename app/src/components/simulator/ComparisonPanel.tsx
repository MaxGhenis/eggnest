"use client";

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

/* Shared styles */
const sectionCls = "rounded-[var(--radius-lg)] bg-[var(--color-bg-card)] p-6 shadow-[var(--shadow-sm)] border border-[var(--color-border-light)]";
const btnPrimary = "rounded-[var(--radius-md)] bg-gradient-golden px-5 py-2.5 text-sm font-semibold text-white shadow-[var(--shadow-sm)] transition-all hover:shadow-[var(--shadow-md)] hover:brightness-110 disabled:opacity-50";
const btnSecondary = "rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-5 py-2.5 text-sm font-medium text-[var(--color-text-muted)] transition-all hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text)]";

/* ============================================ */
/* Annuity comparison                           */
/* ============================================ */

interface AnnuityComparisonProps {
  annuityResult: AnnuityComparisonResult;
  guaranteeYears: number;
}

export function AnnuityComparison({ annuityResult, guaranteeYears }: AnnuityComparisonProps) {
  return (
    <div className={sectionCls}>
      <h3 className="text-lg font-semibold mb-4">Annuity Comparison</h3>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-[var(--radius-md)] bg-[var(--color-gray-50)] p-4">
          <div className="text-xs font-medium text-[var(--color-text-light)] uppercase tracking-wider">Annuity Guaranteed Total</div>
          <div className="mt-1 text-xl font-bold text-[var(--color-text)]">{formatCurrency(annuityResult.annuity_total_guaranteed)}</div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">Over {guaranteeYears} year guarantee period</div>
        </div>
        <div className="rounded-[var(--radius-md)] bg-[var(--color-gray-50)] p-4">
          <div className="text-xs font-medium text-[var(--color-text-light)] uppercase tracking-wider">Portfolio Median Total</div>
          <div className="mt-1 text-xl font-bold text-[var(--color-text)]">{formatCurrency(annuityResult.simulation_median_total_income)}</div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">Median total income from portfolio</div>
        </div>
        <div className="rounded-[var(--radius-md)] bg-[var(--color-primary-50)] p-4 border border-[var(--color-primary-200)]">
          <div className="text-xs font-medium text-[var(--color-text-light)] uppercase tracking-wider">Portfolio Beats Annuity</div>
          <div className="mt-1 text-xl font-bold" style={{
            color: annuityResult.probability_simulation_beats_annuity >= 0.6 ? "#10b981"
              : annuityResult.probability_simulation_beats_annuity >= 0.4 ? "#f59e0b" : "#ef4444"
          }}>
            {formatPercent(annuityResult.probability_simulation_beats_annuity)}
          </div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">Probability</div>
        </div>
      </div>
      <div className="mt-4 rounded-[var(--radius-md)] bg-[var(--color-bg-alt)] p-3 text-sm">
        <strong>Recommendation:</strong> {annuityResult.recommendation}
      </div>
    </div>
  );
}

/* ============================================ */
/* State comparison                             */
/* ============================================ */

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
  params, stateComparisonResult, isComparingStates, selectedCompareStates,
  onCompareStates, onToggleCompareState, onResetComparison,
}: StateComparisonProps) {
  const filteredStates = useMemo(() => US_STATES.filter(s => s !== params.state), [params.state]);

  return (
    <div className={sectionCls}>
      <h3 className="text-lg font-semibold">Compare states</h3>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">See how relocating could affect your taxes and outcomes.</p>

      {!stateComparisonResult && !isComparingStates && (
        <div className="mt-4 space-y-4">
          <button className={btnSecondary} onClick={() => onCompareStates()} disabled={isComparingStates}>
            Compare to No-Income-Tax States
          </button>
          <div className="text-center text-xs text-[var(--color-text-light)]">or select specific states</div>
          <div className="flex flex-wrap gap-1.5">
            {filteredStates.map(state => (
              <button key={state}
                className={`rounded-full px-2.5 py-1 text-xs font-medium transition-all ${
                  selectedCompareStates.includes(state)
                    ? "bg-[var(--color-primary)] text-white"
                    : NO_TAX_STATES.includes(state)
                      ? "bg-[var(--color-success-light)] text-[var(--color-success)] hover:bg-[var(--color-success)] hover:text-white"
                      : "bg-[var(--color-gray-100)] text-[var(--color-text-muted)] hover:bg-[var(--color-gray-200)]"
                }`}
                onClick={() => onToggleCompareState(state)}
                disabled={!selectedCompareStates.includes(state) && selectedCompareStates.length >= 5}>
                {state}
              </button>
            ))}
          </div>
          {selectedCompareStates.length > 0 && (
            <button className={btnPrimary} onClick={() => onCompareStates(selectedCompareStates)} disabled={isComparingStates}>
              Compare {selectedCompareStates.length} State{selectedCompareStates.length > 1 ? "s" : ""}
            </button>
          )}
        </div>
      )}

      {isComparingStates && (
        <div className="mt-4 flex items-center gap-3 text-sm text-[var(--color-text-muted)]">
          <div className="h-5 w-5 animate-spin-slow rounded-full border-2 border-[var(--color-primary-200)] border-t-[var(--color-primary)]" />
          Comparing states...
        </div>
      )}

      {stateComparisonResult && (
        <div className="mt-4 space-y-4">
          <div className="overflow-x-auto">
            <table className="w-full table-auto-style">
              <thead>
                <tr>
                  <th>State</th><th>Total Taxes</th><th>Tax Savings</th><th>Success Rate</th>
                </tr>
              </thead>
              <tbody>
                {stateComparisonResult.results
                  .sort((a, b) => stateComparisonResult.tax_savings_vs_base[b.state] - stateComparisonResult.tax_savings_vs_base[a.state])
                  .map((r) => (
                  <tr key={r.state} className={r.state === params.state ? "!bg-[var(--color-primary-50)]" : ""}>
                    <td className="font-medium">{r.state}{r.state === params.state && " (current)"}</td>
                    <td>{formatCurrency(r.total_taxes_median)}</td>
                    <td style={{
                      color: stateComparisonResult.tax_savings_vs_base[r.state] > 0 ? "#10b981"
                        : stateComparisonResult.tax_savings_vs_base[r.state] < 0 ? "#ef4444" : "inherit",
                      fontWeight: stateComparisonResult.tax_savings_vs_base[r.state] !== 0 ? 600 : 400,
                    }}>
                      {stateComparisonResult.tax_savings_vs_base[r.state] > 0 && "+"}{formatCurrency(stateComparisonResult.tax_savings_vs_base[r.state])}
                    </td>
                    <td>{formatPercent(r.success_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-[var(--color-text-muted)]">
            Tax savings show lifetime difference compared to {params.state}. Positive values mean you save money by relocating.
          </p>
          <button className={btnSecondary} onClick={onResetComparison}>Compare Different States</button>
        </div>
      )}
    </div>
  );
}

/* ============================================ */
/* SS timing comparison                         */
/* ============================================ */

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
  ssTimingResult, isComparingSSTiming, birthYear, setBirthYear, piaMonthly, setPiaMonthly, onCompare, onReset,
}: SSTimingComparisonProps) {
  const fieldCls = "space-y-1.5";
  const labelCls = "block text-sm font-medium text-[var(--color-text-muted)]";
  const inputCls = "w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm transition-colors focus:border-[var(--color-primary)] focus:outline-none";

  return (
    <div className={sectionCls}>
      <h3 className="text-lg font-semibold">When should you claim Social Security?</h3>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">Compare how different claiming ages affect your lifetime benefits and portfolio.</p>

      {!ssTimingResult && !isComparingSSTiming && (
        <div className="mt-4 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className={fieldCls}>
              <label className={labelCls}>Your Birth Year</label>
              <input type="number" value={birthYear} onChange={(e) => setBirthYear(Number(e.target.value))}
                min={1930} max={2000} className={inputCls} />
              <div className="text-xs text-[var(--color-text-light)]">Used to determine your Full Retirement Age</div>
            </div>
            <div className={fieldCls}>
              <label className={labelCls}>Estimated Benefit at FRA (PIA)</label>
              <div className="flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white focus-within:border-[var(--color-primary)]">
                <span className="pl-3 text-sm text-[var(--color-text-light)]">$</span>
                <input type="number" value={piaMonthly} onChange={(e) => setPiaMonthly(Number(e.target.value))}
                  min={0} max={10000} step={100}
                  className="w-full border-none bg-transparent px-2 py-2.5 text-sm focus:outline-none" />
              </div>
              <div className="text-xs text-[var(--color-text-light)]">Check ssa.gov/myaccount</div>
            </div>
          </div>
          <button className={btnPrimary} onClick={onCompare} disabled={isComparingSSTiming || piaMonthly <= 0}>
            Compare Claiming Ages
          </button>
        </div>
      )}

      {isComparingSSTiming && (
        <div className="mt-4 flex items-center gap-3 text-sm text-[var(--color-text-muted)]">
          <div className="h-5 w-5 animate-spin-slow rounded-full border-2 border-[var(--color-primary-200)] border-t-[var(--color-primary)]" />
          Comparing claiming ages (this takes a few minutes)...
        </div>
      )}

      {ssTimingResult && (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-4">
            <div className="rounded-[var(--radius-md)] bg-[var(--color-gray-50)] px-4 py-2 text-sm">
              <span className="text-[var(--color-text-muted)]">Full Retirement Age: </span>
              <span className="font-semibold">{Math.floor(ssTimingResult.full_retirement_age)} years
                {ssTimingResult.full_retirement_age % 1 > 0 && ` ${Math.round((ssTimingResult.full_retirement_age % 1) * 12)} months`}
              </span>
            </div>
            <div className="rounded-[var(--radius-md)] bg-[var(--color-success-light)] px-4 py-2 text-sm">
              <span className="text-[var(--color-text-muted)]">Optimal: </span>
              <span className="font-semibold text-[var(--color-success)]">Claim at age {ssTimingResult.optimal_claiming_age}</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full table-auto-style">
              <thead>
                <tr><th>Age</th><th>Monthly</th><th>Adj</th><th>Success</th><th>Lifetime SS</th><th>Break-even vs 62</th></tr>
              </thead>
              <tbody>
                {ssTimingResult.results.map((r) => (
                  <tr key={r.claiming_age}
                    className={r.claiming_age === ssTimingResult.optimal_claiming_age ? "!bg-[var(--color-success-light)]" : r.claiming_age === Math.round(ssTimingResult.full_retirement_age) ? "!bg-[var(--color-primary-50)]" : ""}>
                    <td className="font-medium">
                      {r.claiming_age}
                      {r.claiming_age === Math.round(ssTimingResult.full_retirement_age) && <span className="ml-1 rounded bg-[var(--color-primary-100)] px-1.5 py-0.5 text-[0.6rem] font-bold text-[var(--color-primary)]">FRA</span>}
                      {r.claiming_age === ssTimingResult.optimal_claiming_age && <span className="ml-1 rounded bg-[var(--color-success)] px-1.5 py-0.5 text-[0.6rem] font-bold text-white">Best</span>}
                    </td>
                    <td>${r.monthly_benefit.toLocaleString()}/mo</td>
                    <td style={{ color: r.adjustment_factor < 1 ? "#ef4444" : r.adjustment_factor > 1 ? "#10b981" : "inherit" }}>
                      {r.adjustment_factor < 1 ? `-${((1 - r.adjustment_factor) * 100).toFixed(0)}%` : r.adjustment_factor > 1 ? `+${((r.adjustment_factor - 1) * 100).toFixed(0)}%` : "\u2014"}
                    </td>
                    <td>{formatPercent(r.success_rate)}</td>
                    <td>{formatCurrency(r.total_ss_income_median)}</td>
                    <td>{r.breakeven_vs_62 ? `Age ${r.breakeven_vs_62}` : r.claiming_age === 62 ? "\u2014" : "N/A"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-[var(--color-text-muted)]">
            Early claiming permanently reduces your benefit. Delayed claiming (after FRA, up to 70) permanently increases it by 8% per year.
          </p>
          <button className={btnSecondary} onClick={onReset}>Change Assumptions</button>
        </div>
      )}
    </div>
  );
}

/* ============================================ */
/* Allocation comparison                        */
/* ============================================ */

interface AllocationComparisonProps {
  allocationResult: AllocationComparisonResult | null;
  isComparingAllocations: boolean;
  onCompare: () => void;
  onReset: () => void;
}

export function AllocationComparison({
  allocationResult, isComparingAllocations, onCompare, onReset,
}: AllocationComparisonProps) {
  return (
    <div className={sectionCls}>
      <h3 className="text-lg font-semibold">How does asset allocation affect your plan?</h3>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">Compare different stock/bond mixes for the right balance of growth and safety.</p>

      {!allocationResult && (
        <button className={`mt-4 ${btnPrimary}`} onClick={onCompare} disabled={isComparingAllocations}>
          {isComparingAllocations ? "Comparing..." : "Compare Allocations"}
        </button>
      )}

      {allocationResult && (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-4">
            <div className="rounded-[var(--radius-md)] bg-[var(--color-success-light)] px-4 py-2 text-sm">
              <span className="text-[var(--color-text-muted)]">Optimal for Success: </span>
              <span className="font-semibold text-[var(--color-success)]">{Math.round(allocationResult.optimal_for_success * 100)}% Stocks</span>
            </div>
            {allocationResult.optimal_for_safety !== allocationResult.optimal_for_success && (
              <div className="rounded-[var(--radius-md)] bg-[var(--color-primary-50)] px-4 py-2 text-sm">
                <span className="text-[var(--color-text-muted)]">Optimal for Safety: </span>
                <span className="font-semibold text-[var(--color-primary)]">{Math.round(allocationResult.optimal_for_safety * 100)}% Stocks</span>
              </div>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full table-auto-style">
              <thead>
                <tr><th>Allocation</th><th>Success</th><th>Median Final</th><th>Worst (5th)</th><th>Best (95th)</th><th>Volatility</th></tr>
              </thead>
              <tbody>
                {allocationResult.results.map((r) => (
                  <tr key={r.stock_allocation} className={r.stock_allocation === allocationResult.optimal_for_success ? "!bg-[var(--color-success-light)]" : ""}>
                    <td className="font-medium">
                      {Math.round(r.stock_allocation * 100)}% / {Math.round(r.bond_allocation * 100)}%
                      {r.stock_allocation === allocationResult.optimal_for_success && <span className="ml-1 rounded bg-[var(--color-success)] px-1.5 py-0.5 text-[0.6rem] font-bold text-white">Best</span>}
                    </td>
                    <td style={{
                      color: r.success_rate >= 0.9 ? "#10b981" : r.success_rate >= 0.8 ? "#84cc16" : r.success_rate >= 0.7 ? "#eab308" : "#ef4444"
                    }}>{formatPercent(r.success_rate)}</td>
                    <td>{formatCurrency(r.median_final_value)}</td>
                    <td style={{ color: r.percentile_5_final_value <= 0 ? "#ef4444" : "inherit" }}>{formatCurrency(r.percentile_5_final_value)}</td>
                    <td>{formatCurrency(r.percentile_95_final_value)}</td>
                    <td>{(r.volatility * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-sm text-[var(--color-text-muted)]">{allocationResult.recommendation}</p>
          <button className={btnSecondary} onClick={onReset}>Hide Results</button>
        </div>
      )}
    </div>
  );
}
