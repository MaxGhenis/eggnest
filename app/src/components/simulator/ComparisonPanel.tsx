"use client";

import { useMemo, useState } from "react";
import type {
  SimulationInput,
  StateComparisonResult,
  StrategyComparisonResult,
  RothOptimizationResult,
  SSTimingComparisonResult,
  AllocationComparisonResult,
} from "../../lib/api";
import type { AnnuityComparisonResult } from "../../lib/simulatorUtils";
import { formatCurrency, formatPercent } from "../../lib/simulatorUtils";
import { US_STATES, NO_TAX_STATES } from "../../lib/constants";
import type { WithdrawalStrategy } from "../../hooks/usePortfolio";
import {
  buildRothOptimizationExportArtifact,
  downloadTextFile,
  makeRothOptimizationExportFilename,
  serializeRothOptimizationCsv,
} from "../../lib/rothExport";

/* Shared styles */
const sectionCls = "section-card";
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
      <h3 className="mb-4 text-lg font-semibold">Annuity vs portfolio</h3>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-[var(--radius-md)] bg-[var(--color-gray-50)] p-4">
          <div className="text-xs font-medium text-[var(--color-text-light)] uppercase tracking-wider">Annuity guaranteed total</div>
          <div className="mt-1 text-xl font-bold text-[var(--color-text)]">{formatCurrency(annuityResult.annuity_total_guaranteed)}</div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">Over {guaranteeYears} year guarantee period</div>
        </div>
        <div className="rounded-[var(--radius-md)] bg-[var(--color-gray-50)] p-4">
          <div className="text-xs font-medium text-[var(--color-text-light)] uppercase tracking-wider">Portfolio median total</div>
          <div className="mt-1 text-xl font-bold text-[var(--color-text)]">{formatCurrency(annuityResult.simulation_median_total_income)}</div>
          <div className="mt-1 text-xs text-[var(--color-text-muted)]">Median total income from portfolio</div>
        </div>
        <div className="rounded-[var(--radius-md)] bg-[var(--color-primary-50)] p-4 border border-[var(--color-primary-200)]">
          <div className="text-xs font-medium text-[var(--color-text-light)] uppercase tracking-wider">Portfolio beats annuity</div>
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
        <strong>Model reading:</strong> {annuityResult.summary}
      </div>
    </div>
  );
}

/* ============================================ */
/* Withdrawal strategy comparison               */
/* ============================================ */

interface WithdrawalStrategyComparisonProps {
  strategyComparisonResult: StrategyComparisonResult | null;
  isComparingStrategies: boolean;
  currentStrategy: WithdrawalStrategy;
  onCompare: () => void;
  onReset: () => void;
}

const STRATEGY_LABELS: Record<WithdrawalStrategy, string> = {
  taxable_first: "Taxable first",
  traditional_first: "Traditional first",
  roth_first: "Roth first",
  pro_rata: "Pro rata",
};

export function WithdrawalStrategyComparison({
  strategyComparisonResult,
  isComparingStrategies,
  currentStrategy,
  onCompare,
  onReset,
}: WithdrawalStrategyComparisonProps) {
  return (
    <div className={sectionCls}>
      <h3 className="text-lg font-semibold">How do withdrawal strategies compare?</h3>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        Compare tax-aware drawdown policies across Monte Carlo and exact
        historical cohorts using the same household assumptions. EggNest ranks
        modeled scenarios here; it does not provide advice.
      </p>

      {!strategyComparisonResult && (
        <button className={`mt-4 ${btnPrimary}`} onClick={onCompare} disabled={isComparingStrategies}>
          {isComparingStrategies ? "Comparing scenarios..." : "Compare strategy scenarios"}
        </button>
      )}

      {strategyComparisonResult && (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-4">
            <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-alt)] px-4 py-2 text-sm">
              <span className="text-[var(--color-text-muted)]">Lowest modeled taxes: </span>
              <span className="font-semibold text-[var(--color-text)]">{STRATEGY_LABELS[strategyComparisonResult.lowest_modeled_tax_strategy]}</span>
            </div>
            <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-alt)] px-4 py-2 text-sm">
              <span className="text-[var(--color-text-muted)]">Strongest historical resilience: </span>
              <span className="font-semibold text-[var(--color-text)]">{STRATEGY_LABELS[strategyComparisonResult.strongest_historical_strategy]}</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full table-auto-style">
              <thead>
                <tr>
                  <th>Strategy</th><th>MC success</th><th>Historical success</th><th>Median final (real)</th><th>Weakest cohort (real)</th><th>Median taxes</th>
                </tr>
              </thead>
              <tbody>
                {strategyComparisonResult.results.map((result) => (
                  <tr key={result.strategy}>
                    <td className="font-medium">
                      {STRATEGY_LABELS[result.strategy]}
                      {result.strategy === currentStrategy && <span className="ml-1 rounded bg-[var(--color-primary-100)] px-1.5 py-0.5 text-[0.6rem] font-bold text-[var(--color-primary)]">Current</span>}
                    </td>
                    <td>{formatPercent(result.monte_carlo.success_rate)}</td>
                    <td>{formatPercent(result.historical.success_rate)}</td>
                    <td>{formatCurrency(result.historical.median_final_value_real)}</td>
                    <td style={{ color: result.historical.worst_final_value_real <= 0 ? "#ef4444" : "inherit" }}>
                      {formatCurrency(result.historical.worst_final_value_real)}
                    </td>
                    <td>{formatCurrency(result.monte_carlo.total_taxes_median)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-sm text-[var(--color-text-muted)]">
            Compare the table directly across success, historical downside, and taxes under the current assumptions.
          </p>
          <button className={btnSecondary} onClick={onReset}>Hide results</button>
        </div>
      )}
    </div>
  );
}

/* ============================================ */
/* Roth conversion optimization                 */
/* ============================================ */

interface RothOptimizationComparisonProps {
  rothOptimizationResult: RothOptimizationResult | null;
  isOptimizingRoth: boolean;
  onOptimize: () => void;
  onReset: () => void;
  reportLink?: string | null;
}

const ROTH_POLICY_LABELS: Record<string, string> = {
  fixed_amount: "Fixed amount",
  fill_standard_deduction: "Fill standard deduction",
  fill_12_percent_bracket: "Fill 12% bracket",
  fill_22_percent_bracket: "Fill 22% bracket",
};

export function RothOptimizationComparison({
  rothOptimizationResult,
  isOptimizingRoth,
  onOptimize,
  onReset,
  reportLink,
}: RothOptimizationComparisonProps) {
  return (
    <div className={sectionCls}>
      <h3 className="text-lg font-semibold">How do Roth conversion paths compare?</h3>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        Search bounded Roth conversion windows and sizing rules on the current
        plan. EggNest ranks modeled scenarios here; it does not provide advice.
      </p>

      {!rothOptimizationResult && (
        <button className={`mt-4 ${btnPrimary}`} onClick={onOptimize} disabled={isOptimizingRoth}>
          {isOptimizingRoth ? "Searching Roth scenarios..." : "Search Roth conversion scenarios"}
        </button>
      )}

      {rothOptimizationResult && (
        <RothOptimizationReportView
          rothOptimizationResult={rothOptimizationResult}
          reportLink={reportLink}
          showOpenReportPage
          onReset={onReset}
        />
      )}
    </div>
  );
}

interface RothOptimizationReportViewProps {
  rothOptimizationResult: RothOptimizationResult;
  reportLink?: string | null;
  showOpenReportPage?: boolean;
  onReset?: () => void;
}

export function RothOptimizationReportView({
  rothOptimizationResult,
  reportLink,
  showOpenReportPage = false,
  onReset,
}: RothOptimizationReportViewProps) {
  const ledgerScenario = rothOptimizationResult.results.find(
    (item) =>
      item.monte_carlo.year_breakdown.some(
        (row) =>
          Math.abs(row.roth_conversion ?? 0) > 1e-9 ||
          Math.abs(row.medicare_premium_delta_vs_baseline ?? 0) > 1e-9 ||
          (row.medicare_part_b_irmaa_bracket ?? "none") !== "none" ||
          (row.medicare_part_d_irmaa_bracket ?? "none") !== "none"
      )
  ) ?? null;
  const [reportLinkCopied, setReportLinkCopied] = useState(false);

  const ledgerRows = (ledgerScenario?.monte_carlo.year_breakdown ?? []).filter(
    (row) =>
      Math.abs(row.roth_conversion ?? 0) > 1e-9 ||
      Math.abs(row.medicare_premium_delta_vs_baseline ?? 0) > 1e-9 ||
      (row.medicare_part_b_irmaa_bracket ?? "none") !== "none" ||
      (row.medicare_part_d_irmaa_bracket ?? "none") !== "none"
  );

  const handleDownloadJson = () => {
    if (!rothOptimizationResult) return;
    const generatedAt = new Date().toISOString();
    downloadTextFile(
      makeRothOptimizationExportFilename("json", generatedAt),
      JSON.stringify(
        buildRothOptimizationExportArtifact(rothOptimizationResult, generatedAt),
        null,
        2
      ),
      "application/json"
    );
  };

  const handleDownloadCsv = () => {
    if (!rothOptimizationResult) return;
    const generatedAt = new Date().toISOString();
    downloadTextFile(
      makeRothOptimizationExportFilename("csv", generatedAt),
      serializeRothOptimizationCsv(rothOptimizationResult),
      "text/csv;charset=utf-8"
    );
  };

  const handleCopyReportLink = async () => {
    if (!reportLink) return;
    try {
      await navigator.clipboard.writeText(reportLink);
      setReportLinkCopied(true);
      window.setTimeout(() => setReportLinkCopied(false), 2000);
    } catch (error) {
      console.error("Failed to copy Roth report link:", error);
    }
  };

  return (
    <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-4">
            <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-alt)] px-4 py-2 text-sm">
              <span className="text-[var(--color-text-muted)]">Lowest modeled taxes: </span>
              <span className="font-semibold text-[var(--color-text)]">{rothOptimizationResult.lowest_modeled_tax_scenario_label}</span>
            </div>
            <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-alt)] px-4 py-2 text-sm">
              <span className="text-[var(--color-text-muted)]">Lowest Medicare premiums: </span>
              <span className="font-semibold text-[var(--color-text)]">{rothOptimizationResult.lowest_medicare_premium_scenario_label}</span>
            </div>
            <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-alt)] px-4 py-2 text-sm">
              <span className="text-[var(--color-text-muted)]">Highest real ending wealth: </span>
              <span className="font-semibold text-[var(--color-text)]">{rothOptimizationResult.highest_real_ending_wealth_scenario_label}</span>
            </div>
          </div>

          <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-alt)] px-4 py-3 text-sm text-[var(--color-text-muted)]">
            <span className="font-semibold text-[var(--color-text)]">Search space:</span>{" "}
            {rothOptimizationResult.candidate_count} candidates across start ages{" "}
            {rothOptimizationResult.candidate_start_ages.join(", ")} and window lengths{" "}
            {rothOptimizationResult.window_lengths.join(", ")} years.
            {rothOptimizationResult.baseline_scenario_label && (
              <>
                {" "}
                Deltas are relative to{" "}
                <span className="font-semibold text-[var(--color-text)]">
                  {rothOptimizationResult.baseline_scenario_label}
                </span>
                .
              </>
            )}
          </div>

          {rothOptimizationResult.metadata && (
            <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-alt)] px-4 py-3 text-sm text-[var(--color-text-muted)]">
              <span className="font-semibold text-[var(--color-text)]">Method:</span>{" "}
              {rothOptimizationResult.metadata.method_version} on engine{" "}
              {rothOptimizationResult.metadata.engine_version}
              {rothOptimizationResult.metadata.random_seed !== null && (
                <>
                  {" "}
                  with seed{" "}
                  <span className="font-semibold text-[var(--color-text)]">
                    {rothOptimizationResult.metadata.random_seed}
                  </span>
                </>
              )}
              .{" "}
              {rothOptimizationResult.metadata.assumptions_summary}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {reportLink && showOpenReportPage && (
              <a className={btnSecondary} href={reportLink}>
                Open report page
              </a>
            )}
            {reportLink && (
              <button className={btnSecondary} onClick={handleCopyReportLink}>
                {reportLinkCopied ? "Report link copied!" : "Copy report link"}
              </button>
            )}
            <button className={btnSecondary} onClick={handleDownloadJson}>
              Download JSON report
            </button>
            <button className={btnSecondary} onClick={handleDownloadCsv}>
              Download CSV table
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full table-auto-style">
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>Policy</th>
                  <th>MC success</th>
                  <th>Historical success</th>
                  <th>Real Δ</th>
                  <th>Tax Δ</th>
                  <th>Medicare Δ</th>
                  <th>Median converted</th>
                </tr>
              </thead>
              <tbody>
                {rothOptimizationResult.results.map((item) => (
                  <tr key={item.scenario_label}>
                    <td className="font-medium">
                      {item.scenario_label}
                    </td>
                    <td>{ROTH_POLICY_LABELS[item.conversion_policy] ?? item.conversion_policy}</td>
                    <td>{formatPercent(item.monte_carlo.success_rate)}</td>
                    <td>{formatPercent(item.historical.success_rate)}</td>
                    <td>{formatCurrency(item.delta_vs_baseline.monte_carlo_median_final_value_real_delta)}</td>
                    <td>{formatCurrency(item.delta_vs_baseline.monte_carlo_total_taxes_median_delta)}</td>
                    <td>{formatCurrency(item.delta_vs_baseline.monte_carlo_total_medicare_premiums_median_delta)}</td>
                    <td>{formatCurrency(item.monte_carlo.total_roth_conversions_median)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {ledgerScenario && ledgerRows.length > 0 && (
            <div className="space-y-3">
              <div className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-alt)] px-4 py-3 text-sm text-[var(--color-text-muted)]">
                <span className="font-semibold text-[var(--color-text)]">Example cliff ledger:</span>{" "}
                {ledgerScenario.scenario_label}. Medicare deltas are relative to{" "}
                {rothOptimizationResult.baseline_scenario_label ?? "the baseline"}.
              </div>
              <div className="overflow-x-auto">
                <table className="w-full table-auto-style">
                  <thead>
                    <tr>
                      <th>Age</th>
                      <th>Convert</th>
                      <th>Bracket room used</th>
                      <th>Marginal</th>
                      <th>Part B band</th>
                      <th>Part D surcharge</th>
                      <th>Medicare Δ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ledgerRows.map((row) => (
                      <tr key={`${row.age}-${row.year_index}`}>
                        <td>{row.age}</td>
                        <td>{formatCurrency(row.roth_conversion ?? 0)}</td>
                        <td>{formatCurrency(row.federal_bracket_headroom_used ?? 0)}</td>
                        <td>{formatPercent(row.federal_marginal_rate_on_last_conversion_dollar ?? 0)}</td>
                        <td>{row.medicare_part_b_irmaa_bracket ?? "none"}</td>
                        <td>{formatCurrency(row.medicare_part_d_premium_surcharge ?? 0)}</td>
                        <td>{formatCurrency(row.medicare_premium_delta_vs_baseline ?? 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <p className="text-sm text-[var(--color-text-muted)]">
            Compare the scenarios directly across success, tax drag, Medicare drag, and conversion size under the current assumptions.
          </p>
          {onReset && <button className={btnSecondary} onClick={onReset}>Hide results</button>}
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
            Compare to no-income-tax states
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
                  <th>State</th><th>Total taxes</th><th>Tax savings</th><th>Success rate</th>
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
          <button className={btnSecondary} onClick={onResetComparison}>Compare different states</button>
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
      <h3 className="text-lg font-semibold">How do Social Security claiming ages compare?</h3>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">Compare how different claiming ages change modeled lifetime benefits and portfolio outcomes.</p>

      {!ssTimingResult && !isComparingSSTiming && (
        <div className="mt-4 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className={fieldCls}>
              <label className={labelCls}>Your birth year</label>
              <input type="number" value={birthYear} onChange={(e) => setBirthYear(Number(e.target.value))}
                min={1930} max={2000} className={inputCls} />
              <div className="text-xs text-[var(--color-text-light)]">Used to determine your full retirement age</div>
            </div>
            <div className={fieldCls}>
              <label className={labelCls}>Estimated benefit at FRA (PIA)</label>
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
            Compare claiming scenarios
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
              <span className="text-[var(--color-text-muted)]">Full retirement age: </span>
              <span className="font-semibold">{Math.floor(ssTimingResult.full_retirement_age)} years
                {ssTimingResult.full_retirement_age % 1 > 0 && ` ${Math.round((ssTimingResult.full_retirement_age % 1) * 12)} months`}
              </span>
            </div>
            <div className="rounded-[var(--radius-md)] bg-[var(--color-success-light)] px-4 py-2 text-sm">
              <span className="text-[var(--color-text-muted)]">Highest modeled success: </span>
              <span className="font-semibold text-[var(--color-success)]">Age {ssTimingResult.highest_success_claiming_age}</span>
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
                    className={r.claiming_age === ssTimingResult.highest_success_claiming_age ? "!bg-[var(--color-success-light)]" : r.claiming_age === Math.round(ssTimingResult.full_retirement_age) ? "!bg-[var(--color-primary-50)]" : ""}>
                    <td className="font-medium">
                      {r.claiming_age}
                      {r.claiming_age === Math.round(ssTimingResult.full_retirement_age) && <span className="ml-1 rounded bg-[var(--color-primary-100)] px-1.5 py-0.5 text-[0.6rem] font-bold text-[var(--color-primary)]">FRA</span>}
                      {r.claiming_age === ssTimingResult.highest_success_claiming_age && <span className="ml-1 rounded bg-[var(--color-success)] px-1.5 py-0.5 text-[0.6rem] font-bold text-white">Top score</span>}
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
          <button className={btnSecondary} onClick={onReset}>Change assumptions</button>
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
      <h3 className="text-lg font-semibold">How do asset allocations compare?</h3>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">Compare different stock/bond mixes for the right balance of growth and safety.</p>

      {!allocationResult && (
        <button className={`mt-4 ${btnPrimary}`} onClick={onCompare} disabled={isComparingAllocations}>
          {isComparingAllocations ? "Comparing..." : "Compare allocation scenarios"}
        </button>
      )}

      {allocationResult && (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-4">
            <div className="rounded-[var(--radius-md)] bg-[var(--color-success-light)] px-4 py-2 text-sm">
              <span className="text-[var(--color-text-muted)]">Highest modeled success: </span>
              <span className="font-semibold text-[var(--color-success)]">{Math.round(allocationResult.highest_success_allocation * 100)}% Stocks</span>
            </div>
            {allocationResult.highest_safety_allocation !== allocationResult.highest_success_allocation && (
              <div className="rounded-[var(--radius-md)] bg-[var(--color-primary-50)] px-4 py-2 text-sm">
                <span className="text-[var(--color-text-muted)]">Highest modeled safety: </span>
                <span className="font-semibold text-[var(--color-primary)]">{Math.round(allocationResult.highest_safety_allocation * 100)}% Stocks</span>
              </div>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full table-auto-style">
              <thead>
                <tr><th>Allocation</th><th>Success</th><th>Median final</th><th>Lower tail (5th)</th><th>Upper tail (95th)</th><th>Volatility</th></tr>
              </thead>
              <tbody>
                {allocationResult.results.map((r) => (
                  <tr key={r.stock_allocation} className={r.stock_allocation === allocationResult.highest_success_allocation ? "!bg-[var(--color-success-light)]" : ""}>
                    <td className="font-medium">
                      {Math.round(r.stock_allocation * 100)}% / {Math.round(r.bond_allocation * 100)}%
                      {r.stock_allocation === allocationResult.highest_success_allocation && <span className="ml-1 rounded bg-[var(--color-success)] px-1.5 py-0.5 text-[0.6rem] font-bold text-white">Top score</span>}
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
          <p className="text-sm text-[var(--color-text-muted)]">
            <span className="font-semibold text-[var(--color-text)]">Model reading:</span>{" "}
            {allocationResult.summary}
          </p>
          <button className={btnSecondary} onClick={onReset}>Hide results</button>
        </div>
      )}
    </div>
  );
}
