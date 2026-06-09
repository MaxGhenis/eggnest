"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import Image from "next/image";
import Link from "next/link";
import {
  runUKSimulation,
  type UKSimulationInput,
  type UKSimulationResult,
} from "../../lib/api-uk";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { colors, chartColors } from "../../lib/design-tokens";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const DEFAULT_INPUT: UKSimulationInput = {
  current_age: 65,
  max_age: 90,
  gender: "male",
  region: "London",
  isa_balance: 150000,
  sipp_balance: 300000,
  gia_balance: 50000,
  annual_spending: 30000,
  spending_mode: "real",
  state_pension_annual: 11502,
  state_pension_start_age: 67,
  employment_income: 0,
  retirement_age: 67,
  return_source: "historical_block_bootstrap",
  equity_weight: 0.6,
  expected_return: 0.055,
  return_volatility: 0.15,
  dividend_yield: 0.025,
  inflation_rate: 0.025,
  earnings_model: "flat",
  earnings_persistent_sigma: 0.10,
  earnings_transitory_sigma: 0.20,
  earnings_persistence: 0.97,
  earnings_profile_peak_growth: 0.40,
  savings_rate: 0.08,
  sipp_contribution_share: 1.0,
  n_simulations: 800,
  include_mortality: true,
};

const EARNINGS_MODEL_OPTIONS: {
  value: NonNullable<UKSimulationInput["earnings_model"]>;
  label: string;
  detail: string;
}[] = [
  { value: "flat", label: "Flat", detail: "Constant until retirement" },
  { value: "deterministic", label: "Age-wage hump", detail: "UK profile, peaks ~52" },
  { value: "stochastic", label: "Stochastic", detail: "Hump + permanent + transitory shocks (UK calibration)" },
];

const RETURN_SOURCE_OPTIONS: {
  value: NonNullable<UKSimulationInput["return_source"]>;
  label: string;
  detail: string;
}[] = [
  {
    value: "historical_block_bootstrap",
    label: "UK history · blocks",
    detail: "Real 5-year windows resampled",
  },
  {
    value: "historical_sequential",
    label: "UK history · sequences",
    detail: "'What if I retired in 1974?'",
  },
  {
    value: "historical_bootstrap",
    label: "UK history · shuffled",
    detail: "Random historical years",
  },
  {
    value: "gaussian",
    label: "Synthetic (Gaussian)",
    detail: "Fixed mean + volatility",
  },
];

const RETURN_SOURCE_LABEL: Record<
  NonNullable<UKSimulationInput["return_source"]>,
  string
> = Object.fromEntries(
  RETURN_SOURCE_OPTIONS.map((o) => [o.value, o.label]),
) as Record<NonNullable<UKSimulationInput["return_source"]>, string>;

const UK_REGIONS = [
  "London",
  "South East",
  "South West",
  "East of England",
  "East Midlands",
  "West Midlands",
  "Yorkshire and the Humber",
  "North East",
  "North West",
  "Scotland",
  "Wales",
  "Northern Ireland",
];

interface ScenarioProbe {
  label: string;
  delta: Partial<UKSimulationInput>;
}

function formatGBP(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `£${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `£${(value / 1_000).toFixed(0)}k`;
  return `£${Math.round(value)}`;
}
function formatPct(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}
function formatPct1(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

interface SimState {
  forInput: UKSimulationInput | null;
  result: UKSimulationResult | null;
  error: string | null;
}

export default function UKSimulatorPage() {
  const [input, setInput] = useState<UKSimulationInput>(DEFAULT_INPUT);
  const [sim, setSim] = useState<SimState>({ forInput: null, result: null, error: null });

  const debouncedInput = useDebouncedValue(input, 250);

  useEffect(() => {
    const controller = new AbortController();
    runUKSimulation(debouncedInput, controller.signal)
      .then((r) => {
        if (!controller.signal.aborted) {
          setSim({ forInput: debouncedInput, result: r, error: null });
        }
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        setSim({
          forInput: debouncedInput,
          result: null,
          error: e instanceof Error ? e.message : "Simulation failed",
        });
      });
    return () => controller.abort();
  }, [debouncedInput]);

  // Fetching = a request is in flight for the debounced input; the result
  // identity check works because completion stores that exact reference.
  // The status pill shows for fetching or pending debounce, but the heavy
  // blur only applies while fetching so typing doesn't flicker per keystroke.
  const isFetching = sim.forInput !== debouncedInput;
  const isRunning = isFetching || input !== debouncedInput;
  const result = sim.result;
  const error = sim.error;

  const updateField = <K extends keyof UKSimulationInput>(key: K, value: UKSimulationInput[K]) => {
    setInput((prev) => ({ ...prev, [key]: value }));
  };

  const applyProbe = (delta: Partial<UKSimulationInput>) => {
    setInput((prev) => ({ ...prev, ...delta }));
  };

  const totalPortfolio = input.isa_balance + input.sipp_balance + input.gia_balance;
  const withdrawalRate = totalPortfolio > 0 ? (input.annual_spending / totalPortfolio) * 100 : 0;

  const probes: ScenarioProbe[] = useMemo(
    () => [
      {
        label: "Spend 10% less",
        delta: { annual_spending: Math.round(input.annual_spending * 0.9) },
      },
      {
        label: "Spend 10% more",
        delta: { annual_spending: Math.round(input.annual_spending * 1.1) },
      },
      {
        label: "Delay State Pension to 70",
        delta: { state_pension_start_age: 70 },
      },
      {
        label: "Retire 2 years later",
        delta: { current_age: input.current_age + 2 },
      },
    ],
    [input.annual_spending, input.current_age],
  );

  return (
    <div className="min-h-screen">
      <header className="header-glass sticky top-0 z-50 border-b border-[var(--color-border-light)]">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 md:px-6">
          <Link href="/" className="flex items-center gap-2.5 transition-opacity hover:opacity-80">
            <Image src="/logo.svg" alt="EggNest" width={140} height={28} priority />
          </Link>
          <span className="hidden text-xs font-semibold uppercase tracking-widest text-[var(--color-text-muted)] sm:block">
            UK simulator · live
          </span>
          <Link
            href="/simulator"
            className="rounded-full border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] px-4 py-1.5 text-xs font-semibold text-[var(--color-primary)] transition-all hover:bg-[var(--color-primary)] hover:text-white hover:border-[var(--color-primary)]"
          >
            US simulator
          </Link>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-6 px-4 py-8 md:grid-cols-[360px_minmax(0,1fr)] md:gap-8 md:px-6 md:py-10">
        {/* Results column — appears first on mobile so the answer is visible immediately */}
        <div className="order-1 space-y-6 md:order-2">
          <div className="relative space-y-6">
            {isRunning && result && (
              <div className="pointer-events-none absolute inset-x-0 top-14 z-20 flex justify-center">
                <div className="flex items-center gap-2 rounded-full border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] px-3 py-1 text-[0.7rem] font-semibold text-[var(--color-primary)] shadow-[var(--shadow-sm)]">
                  <svg
                    className="h-3 w-3 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.3" />
                    <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                  </svg>
                  Recalculating…
                </div>
              </div>
            )}
            <div
              className={`space-y-6 transition-all duration-300 ${
                isFetching && result ? "opacity-40 blur-[1px]" : ""
              }`}
            >
              <HeroAnswer
                input={input}
                result={result}
                isRunning={isRunning}
                error={error}
                totalPortfolio={totalPortfolio}
              />
              <PercentileFanChart
                title="Portfolio value over time"
                description="Median + 25/75 + 5/95 percentiles"
                paths={result?.percentile_paths}
                startAge={input.current_age + 1}
                yTitle="Portfolio (£)"
                height={380}
                cohorts={result?.percentile_path_start_years}
                withZeroLine
              />
              <PercentileFanChart
                title="HMRC tax by year"
                description="Median + 25/75 + 5/95 percentiles"
                paths={result?.tax_percentile_paths}
                startAge={input.current_age + 1}
                yTitle="Annual tax (£)"
                height={300}
              />
              {input.current_age < (input.retirement_age ?? 67) && (
                <PercentileFanChart
                  title="Earnings while working"
                  description="Median + 25/75 + 5/95 percentiles"
                  paths={result?.earnings_percentile_paths}
                  startAge={input.current_age + 1}
                  yTitle="Gross earnings (£)"
                  height={260}
                  maxAge={input.retirement_age ?? 67}
                />
              )}
            </div>
          </div>
          <ScenarioProbes probes={probes} onApply={applyProbe} />
        </div>

        {/* Inputs column — left on desktop, below results on mobile */}
        <div className="order-2 space-y-5 md:order-1 md:sticky md:top-20 md:self-start">
          <InputsPanel
            input={input}
            updateField={updateField}
            totalPortfolio={totalPortfolio}
            withdrawalRate={withdrawalRate}
          />
        </div>
      </main>
    </div>
  );
}

/* ============================================================ */
/* Inputs                                                       */
/* ============================================================ */

function InputsPanel({
  input,
  updateField,
  totalPortfolio,
  withdrawalRate,
}: {
  input: UKSimulationInput;
  updateField: <K extends keyof UKSimulationInput>(key: K, value: UKSimulationInput[K]) => void;
  totalPortfolio: number;
  withdrawalRate: number;
}) {
  const employmentIncome = input.employment_income ?? 0;
  return (
    <div className="space-y-5">
      <Section title="You">
        <RangeField
          label="Current age"
          value={input.current_age}
          onChange={(v) => updateField("current_age", v)}
          min={18}
          max={100}
          format={(v) => String(v)}
        />
        <RangeField
          label="Plan to age"
          value={input.max_age}
          onChange={(v) => updateField("max_age", v)}
          min={25}
          max={120}
          invalidBelow={input.current_age + 1}
          format={(v) => String(v)}
        />
        <PairedFields>
          <Field label="Gender">
            <select
              value={input.gender}
              onChange={(e) => updateField("gender", e.target.value as "male" | "female")}
              className={selectCls}
            >
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </Field>
          <Field label="Region">
            <select
              value={input.region}
              onChange={(e) => updateField("region", e.target.value)}
              className={selectCls}
            >
              {UK_REGIONS.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </Field>
        </PairedFields>
      </Section>

      <Section title="Accounts">
        <LogRangeField
          label="ISA"
          hint="Stocks & shares + cash ISAs"
          value={input.isa_balance}
          onChange={(v) => updateField("isa_balance", v)}
          min={0}
          max={2_000_000}
          format={formatGBP}
        />
        <LogRangeField
          label="SIPP / workplace pension"
          hint="DC pension pot"
          value={input.sipp_balance}
          onChange={(v) => updateField("sipp_balance", v)}
          min={0}
          max={2_000_000}
          format={formatGBP}
        />
        <LogRangeField
          label="General investment account"
          hint="Taxable outside wrappers"
          value={input.gia_balance}
          onChange={(v) => updateField("gia_balance", v)}
          min={0}
          max={2_000_000}
          format={formatGBP}
        />
        {totalPortfolio > 0 && (
          <div className="mt-1 flex items-center justify-between rounded-[var(--radius-sm)] bg-[var(--color-bg-alt)] px-3 py-2 text-xs">
            <span className="text-[var(--color-text-muted)]">Total portfolio</span>
            <span className="font-semibold tabular-nums text-[var(--color-text)]">
              {formatGBP(totalPortfolio)}
            </span>
          </div>
        )}
      </Section>

      <Section title="Return model">
        <OptionToggle
          options={RETURN_SOURCE_OPTIONS}
          value={input.return_source ?? "historical_block_bootstrap"}
          onChange={(v) => updateField("return_source", v)}
        />
        {(input.return_source ?? "historical_block_bootstrap") !== "gaussian" ? (
          <RangeField
            label="Equities vs. gilts"
            hint="Portfolio weight on UK equities (rest is UK gilts)"
            value={Math.round((input.equity_weight ?? 0.6) * 100)}
            onChange={(v) => updateField("equity_weight", v / 100)}
            min={0}
            max={100}
            format={(v) => `${v}% equities`}
          />
        ) : (
          <>
            <RangeField
              label="Expected return"
              value={Math.round((input.expected_return ?? 0.055) * 1000) / 10}
              onChange={(v) => updateField("expected_return", v / 100)}
              min={0}
              max={12}
              step={0.1}
              format={(v) => `${v.toFixed(1)}%`}
            />
            <RangeField
              label="Return volatility"
              value={Math.round((input.return_volatility ?? 0.15) * 1000) / 10}
              onChange={(v) => updateField("return_volatility", v / 100)}
              min={0}
              max={30}
              step={0.1}
              format={(v) => `${v.toFixed(1)}%`}
            />
            <RangeField
              label="Inflation (annual)"
              value={Math.round((input.inflation_rate ?? 0.025) * 1000) / 10}
              onChange={(v) => updateField("inflation_rate", v / 100)}
              min={0}
              max={10}
              step={0.1}
              format={(v) => `${v.toFixed(1)}%`}
            />
          </>
        )}
      </Section>

      <Section title="Spending & income">
        <RangeField
          label="Annual spending"
          hint={`≈ ${formatGBP(input.annual_spending / 12)}/mo`}
          value={input.annual_spending}
          onChange={(v) => updateField("annual_spending", v)}
          min={0}
          max={200_000}
          step={1_000}
          format={formatGBP}
        />
        {totalPortfolio > 0 && input.annual_spending > 0 && (
          <div className="-mt-2 text-xs text-[var(--color-text-light)]">
            Initial withdrawal rate:{" "}
            <span
              className={`font-semibold ${withdrawalRate > 4.5 ? "text-[var(--color-warning)]" : "text-[var(--color-success)]"}`}
            >
              {withdrawalRate.toFixed(1)}%
            </span>
          </div>
        )}
        <RangeField
          label="State Pension (annual)"
          hint="Full new = £11,502"
          value={input.state_pension_annual ?? 0}
          onChange={(v) => updateField("state_pension_annual", v)}
          min={0}
          max={15_000}
          step={100}
          format={formatGBP}
        />
        <RangeField
          label="State Pension claim age"
          value={input.state_pension_start_age ?? 67}
          onChange={(v) => updateField("state_pension_start_age", v)}
          min={55}
          max={75}
          format={(v) => String(v)}
        />
      </Section>

      {input.current_age < (input.retirement_age ?? 67) && (
        <Section title="Working years">
          <LogRangeField
            label="Starting gross earnings"
            hint="Taxable employment income in year 0"
            value={employmentIncome}
            onChange={(v) => updateField("employment_income", v)}
            min={0}
            max={500_000}
            format={formatGBP}
          />
          <RangeField
            label="Retirement age"
            value={input.retirement_age ?? 67}
            onChange={(v) => updateField("retirement_age", v)}
            min={input.current_age + 1}
            max={80}
            format={(v) => String(v)}
          />
          <OptionToggle
            label="Earnings model"
            columns={3}
            options={EARNINGS_MODEL_OPTIONS}
            value={input.earnings_model ?? "flat"}
            onChange={(v) => updateField("earnings_model", v)}
          />
          <RangeField
            label="Savings rate"
            hint="Fraction of gross earnings saved each year (auto-enrolment = 8%)"
            value={Math.round((input.savings_rate ?? 0.08) * 100)}
            onChange={(v) => updateField("savings_rate", v / 100)}
            min={0}
            max={60}
            step={1}
            format={(v) => `${v}%`}
          />
          <RangeField
            label="Savings split"
            hint="How much of savings goes to SIPP vs ISA"
            value={Math.round((input.sipp_contribution_share ?? 1.0) * 100)}
            onChange={(v) => updateField("sipp_contribution_share", v / 100)}
            min={0}
            max={100}
            step={5}
            format={(v) => `${v}% SIPP / ${100 - v}% ISA`}
          />
        </Section>
      )}
    </div>
  );
}

/* ============================================================ */
/* Results                                                      */
/* ============================================================ */

function HeroAnswer({
  input,
  result,
  isRunning,
  error,
  totalPortfolio,
}: {
  input: UKSimulationInput;
  result: UKSimulationResult | null;
  isRunning: boolean;
  error: string | null;
  totalPortfolio: number;
}) {
  const spendingYear20 = useMemo(() => {
    // What the spending target looks like in nominal £ 20 years from now
    if (input.spending_mode !== "real") return null;
    return input.annual_spending * Math.pow(1 + (input.inflation_rate ?? 0.025), 20);
  }, [input.annual_spending, input.inflation_rate, input.spending_mode]);

  return (
    <div className="relative rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-white p-6 shadow-[var(--shadow-sm)] md:p-8">
      <div className="flex items-center justify-between">
        <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">
          Outcome
        </div>
        <LiveIndicator isRunning={isRunning} />
      </div>

      {error && !result ? (
        <div className="mt-4 rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-light)] p-4 text-sm text-[var(--color-danger)]">
          {error}
        </div>
      ) : !result ? (
        <SkeletonHero />
      ) : (
        <>
          <div className="mt-3 grid gap-6 md:grid-cols-[auto_1fr] md:items-center">
            <div>
              <div className="bg-gradient-golden bg-clip-text text-5xl font-bold tabular-nums text-transparent md:text-6xl">
                {formatPct(result.success_rate)}
              </div>
              <div className="mt-1 max-w-xs text-sm leading-snug text-[var(--color-text-muted)]">
                {input.include_mortality ?? true
                  ? `of simulated paths avoid depletion before death or age ${input.max_age}`
                  : `of simulated paths last through age ${input.max_age}`}
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 sm:border-l sm:border-[var(--color-border-light)] sm:pl-6 lg:grid-cols-5">
              <HeroMetric
                label="Median ending (real)"
                value={formatGBP(result.median_final_value_real)}
                detail={`Today's £ at age ${input.max_age}`}
              />
              <HeroMetric
                label="10-year depletion risk"
                value={formatPct1(result.prob_10_year_failure)}
                detail="Running out within a decade"
              />
              <HeroMetric
                label={`Strict age ${input.max_age}`}
                value={formatPct(result.strict_horizon_success_rate)}
                detail="Ignores mortality"
              />
              <HeroMetric
                label="Year-1 withdrawal rate"
                value={`${result.initial_withdrawal_rate.toFixed(1)}%`}
                detail="Off the starting portfolio"
              />
              <HeroMetric
                label="Lifetime tax (median)"
                value={formatGBP(result.year_breakdown.reduce((s, b) => s + b.total_tax, 0))}
                detail="HMRC income tax + NI + dividend tax"
              />
            </div>
          </div>
          <p className="mt-6 border-t border-[var(--color-border-light)] pt-4 text-xs leading-relaxed text-[var(--color-text-light)]">
            {formatGBP(totalPortfolio)} at age {input.current_age} · spending {formatGBP(input.annual_spending)}/yr
            {input.spending_mode === "real" ? " (today's £)" : " (flat nominal)"} · {input.region}
            {spendingYear20 != null && input.return_source === "gaussian" ? (
              <> · ≈ {formatGBP(spendingYear20)}/yr at {(input.inflation_rate ?? 0.025) * 100}% inflation in year 20</>
            ) : null}{" "}
            · returns:{" "}
            {RETURN_SOURCE_LABEL[input.return_source ?? "historical_block_bootstrap"]}
            {input.return_source !== "gaussian" ? (
              <> · {Math.round((input.equity_weight ?? 0.6) * 100)}% equities / {100 - Math.round((input.equity_weight ?? 0.6) * 100)}% gilts</>
            ) : null}{" "}
            · HMRC tax via PolicyEngine UK (Rust)
          </p>
        </>
      )}
    </div>
  );
}

function LiveIndicator({ isRunning }: { isRunning: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          isRunning
            ? "animate-pulse bg-[var(--color-primary)]"
            : "bg-[var(--color-success)]"
        }`}
        aria-hidden="true"
      />
      <span className="text-[0.6rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">
        {isRunning ? "Updating" : "Live"}
      </span>
    </div>
  );
}

function SkeletonHero() {
  return (
    <div className="mt-3 grid gap-6 md:grid-cols-[auto_1fr] md:items-center">
      <div>
        <div className="h-14 w-40 animate-pulse rounded bg-[var(--color-gray-100)]" />
        <div className="mt-2 h-4 w-56 animate-pulse rounded bg-[var(--color-gray-100)]" />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="space-y-1.5">
            <div className="h-3 w-24 animate-pulse rounded bg-[var(--color-gray-100)]" />
            <div className="h-5 w-20 animate-pulse rounded bg-[var(--color-gray-100)]" />
            <div className="h-3 w-28 animate-pulse rounded bg-[var(--color-gray-100)]" />
          </div>
        ))}
      </div>
    </div>
  );
}

type PercentileKey = "p5" | "p25" | "p50" | "p75" | "p95";

/** Build the five-trace Plotly fan chart shared by Portfolio / Tax / Earnings. */
function buildPercentileFan(
  paths: Record<string, number[]>,
  ages: number[],
  sliceRange?: [number, number],
  cohorts?: Record<string, number> | null,
): Plotly.Data[] {
  const [s, e] = sliceRange ?? [0, ages.length];
  const x = ages.slice(s, e);
  const y = (k: PercentileKey) => paths[k].slice(s, e);
  const suffix = (k: PercentileKey) =>
    cohorts?.[k] != null ? ` — ${cohorts[k]} cohort` : "";
  return [
    { x, y: y("p95"), type: "scatter", mode: "lines",
      line: { color: "rgba(217,119,6,0.4)", width: 1, dash: "dot" },
      name: `95th${suffix("p95")}`, hoverinfo: "skip" },
    { x, y: y("p5"), type: "scatter", mode: "lines", fill: "tonexty",
      fillcolor: "rgba(217,119,6,0.08)",
      line: { color: "rgba(217,119,6,0.4)", width: 1, dash: "dot" },
      name: `5th${suffix("p5")}`, hoverinfo: "skip" },
    { x, y: y("p75"), type: "scatter", mode: "lines",
      line: { color: "rgba(217,119,6,0.6)", width: 1.5 },
      name: `75th${suffix("p75")}`, hoverinfo: "skip" },
    { x, y: y("p25"), type: "scatter", mode: "lines", fill: "tonexty",
      fillcolor: "rgba(217,119,6,0.15)",
      line: { color: "rgba(217,119,6,0.6)", width: 1.5 },
      name: `25th${suffix("p25")}`, hoverinfo: "skip" },
    { x, y: y("p50"), type: "scatter", mode: "lines",
      line: { color: chartColors.primary, width: 3 },
      name: `Median${suffix("p50")}` },
  ];
}

function buildFanLayout(yTitle: string, height: number, withZeroLine = false) {
  return {
    autosize: true,
    height,
    margin: { l: 70, r: 20, t: 30, b: 50 },
    font: { family: "DM Sans, system-ui, sans-serif", size: 12 },
    xaxis: { title: { text: "Age" }, gridcolor: colors.gray200, showgrid: true, zeroline: false },
    yaxis: {
      title: { text: yTitle },
      gridcolor: colors.gray200,
      tickprefix: "£",
      tickformat: "~s",
      rangemode: "tozero" as const,
      showgrid: true,
    },
    legend: {
      x: 0.5,
      y: 1.12,
      xanchor: "center" as const,
      orientation: "h" as const,
      bgcolor: "rgba(255,255,255,0.85)",
    },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    shapes: withZeroLine
      ? [{ type: "line" as const, xref: "paper" as const,
          x0: 0, x1: 1, y0: 0, y1: 0,
          line: { color: colors.gray300, width: 1 } }]
      : [],
  };
}

function PercentileFanChart({
  title,
  description,
  paths,
  startAge,
  yTitle,
  height,
  cohorts,
  /** Restrict the visible x-range by age. Used for earnings (drop retirement years). */
  maxAge,
  withZeroLine = false,
}: {
  title: string;
  description: string;
  paths: Record<string, number[]> | null | undefined;
  startAge: number;
  yTitle: string;
  height: number;
  cohorts?: Record<string, number> | null;
  maxAge?: number;
  withZeroLine?: boolean;
}) {
  const chartData = useMemo(() => {
    if (!paths) return [];
    const ages = paths.p50.map((_, i) => startAge + i);
    let range: [number, number] | undefined;
    if (maxAge !== undefined) {
      const cut = ages.findIndex((a) => a >= maxAge);
      const endIdx = cut === -1 ? ages.length : cut;
      range = [0, Math.max(endIdx, 1)];
    }
    return buildPercentileFan(paths, ages, range, cohorts);
  }, [paths, startAge, cohorts, maxAge]);

  const layout = useMemo(
    () => buildFanLayout(yTitle, height, withZeroLine),
    [yTitle, height, withZeroLine],
  );

  return (
    <div className="section-card">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-lg font-semibold">{title}</h3>
        <span className="text-xs text-[var(--color-text-light)]">{description}</span>
      </div>
      {paths ? (
        <div className="plotly-chart-wrapper -mx-2">
          <Plot data={chartData} layout={layout} config={{ responsive: true, displayModeBar: false }} style={{ width: "100%" }} />
        </div>
      ) : (
        <div className="animate-pulse rounded-[var(--radius-md)] bg-[var(--color-gray-100)]" style={{ height }} />
      )}
    </div>
  );
}

function ScenarioProbes({
  probes,
  onApply,
}: {
  probes: ScenarioProbe[];
  onApply: (delta: Partial<UKSimulationInput>) => void;
}) {
  return (
    <div className="section-card">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-light)]">
        Quick probes
      </h3>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        One-click tweaks. Results update live.
      </p>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {probes.map((p) => (
          <button
            key={p.label}
            onClick={() => onApply(p.delta)}
            className="rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-card)] px-3 py-2.5 text-left text-sm font-medium text-[var(--color-text)] transition-all hover:border-[var(--color-primary-200)] hover:shadow-[var(--shadow-sm)]"
          >
            {p.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ============================================================ */
/* Primitives                                                   */
/* ============================================================ */

const selectCls =
  "w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none";

interface ToggleOption<T extends string> {
  value: T;
  label: string;
  detail: string;
}

function OptionToggle<T extends string>({
  label,
  options,
  value,
  onChange,
  columns = 2,
}: {
  /** Small caption above the grid. Omit for legacy no-label layout. */
  label?: string;
  options: ReadonlyArray<ToggleOption<T>>;
  value: T;
  onChange: (v: T) => void;
  columns?: 2 | 3;
}) {
  const current = options.find((o) => o.value === value);
  const gridCls = columns === 3 ? "grid-cols-3" : "grid-cols-2";
  return (
    <div className="space-y-2">
      {label && (
        <label className="text-xs font-medium text-[var(--color-text-muted)]">{label}</label>
      )}
      <div className={`grid ${gridCls} gap-1.5`}>
        {options.map((o) => {
          const active = o.value === value;
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => onChange(o.value)}
              className={`rounded-[var(--radius-sm)] border px-2.5 py-1.5 text-left text-[0.72rem] font-medium leading-tight transition-colors ${
                active
                  ? "border-[var(--color-primary)] bg-[var(--color-primary-50)] text-[var(--color-primary)]"
                  : "border-[var(--color-border-light)] bg-white text-[var(--color-text-muted)] hover:border-[var(--color-border)]"
              }`}
            >
              {o.label}
            </button>
          );
        })}
      </div>
      {current && (
        <p className="text-[0.7rem] leading-snug text-[var(--color-text-light)]">
          {current.detail}
        </p>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-white p-4 shadow-[var(--shadow-sm)]">
      <h3 className="mb-3 text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">
        {title}
      </h3>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function PairedFields({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-2">{children}</div>;
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="block text-xs font-medium text-[var(--color-text-muted)]">{label}</label>
      {children}
      {hint && <div className="text-[0.7rem] text-[var(--color-text-light)]">{hint}</div>}
    </div>
  );
}

function HeroMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div>
      <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">
        {label}
      </div>
      <div className="mt-1 text-xl font-semibold tabular-nums text-[var(--color-text)]">{value}</div>
      <div className="mt-0.5 text-xs text-[var(--color-text-muted)]">{detail}</div>
    </div>
  );
}

/**
 * Linear slider + inline editable value. The value is displayed in bold next to the
 * label and is typeable via the small input; dragging the range below changes the
 * same value.
 */
function RangeField({
  label,
  hint,
  value,
  onChange,
  min,
  max,
  step = 1,
  format,
  invalidBelow,
}: {
  label: string;
  hint?: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  format: (v: number) => string;
  /** Values strictly less than this are visually grayed on the track. */
  invalidBelow?: number;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const invalidPct =
    invalidBelow != null && invalidBelow > min
      ? ((Math.min(invalidBelow, max) - min) / (max - min)) * 100
      : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2">
        <label className="text-xs font-medium text-[var(--color-text-muted)]">{label}</label>
        {isEditing ? (
          <input
            type="number"
            autoFocus
            value={value}
            onChange={(e) => {
              // A cleared field parses to NaN; keep the last valid value
              // instead of sending NaN to the API.
              const next = Number(e.target.value);
              if (!Number.isNaN(next)) onChange(Math.max(min, Math.min(max, next)));
            }}
            onBlur={() => setIsEditing(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === "Escape") setIsEditing(false);
            }}
            min={min}
            max={max}
            step={step}
            className="w-28 rounded-[var(--radius-sm)] border border-[var(--color-primary)] bg-white px-2 py-0.5 text-right text-sm tabular-nums focus:outline-none"
          />
        ) : (
          <button
            type="button"
            onClick={() => setIsEditing(true)}
            className="rounded px-1 text-right text-sm font-semibold tabular-nums text-[var(--color-text)] transition-colors hover:bg-[var(--color-bg-alt)]"
          >
            {format(value)}
          </button>
        )}
      </div>
      <div className="relative flex h-5 items-center">
        {invalidPct > 0 && (
          <div
            className="pointer-events-none absolute top-1/2 left-0 h-1.5 -translate-y-1/2 rounded bg-[var(--color-gray-300)] opacity-80"
            style={{ width: `${invalidPct}%` }}
            aria-hidden="true"
          />
        )}
        <input
          type="range"
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={(e) => onChange(Number(e.target.value))}
          className="relative w-full accent-[var(--color-primary)]"
        />
      </div>
      {hint && <div className="text-[0.7rem] text-[var(--color-text-light)]">{hint}</div>}
    </div>
  );
}

/**
 * Log-scale slider for values that span orders of magnitude (e.g. account
 * balances from £0 to £2M). Uses a 0–1000 position on the slider and maps
 * exponentially to the real value range so small-balance users get sensible
 * resolution near the low end.
 */
function LogRangeField({
  label,
  hint,
  value,
  onChange,
  min,
  max,
  format,
}: {
  label: string;
  hint?: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  format: (v: number) => string;
}) {
  const [isEditing, setIsEditing] = useState(false);
  // Log mapping — anchor at £1k so log(0) doesn't explode.
  const ANCHOR = 1_000;
  const logMin = Math.log(ANCHOR);
  const logMax = Math.log(Math.max(ANCHOR + 1, max));
  const positionFromValue = (v: number) => {
    if (v <= 0) return 0;
    const clamped = Math.max(ANCHOR, Math.min(max, v));
    return ((Math.log(clamped) - logMin) / (logMax - logMin)) * 1000;
  };
  const valueFromPosition = (p: number) => {
    if (p <= 0) return 0;
    const raw = Math.exp(logMin + (p / 1000) * (logMax - logMin));
    // Round to nice step based on magnitude.
    if (raw < 10_000) return Math.round(raw / 500) * 500;
    if (raw < 100_000) return Math.round(raw / 1_000) * 1_000;
    if (raw < 1_000_000) return Math.round(raw / 5_000) * 5_000;
    return Math.round(raw / 10_000) * 10_000;
  };
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2">
        <label className="text-xs font-medium text-[var(--color-text-muted)]">{label}</label>
        {isEditing ? (
          <input
            type="number"
            autoFocus
            value={value}
            onChange={(e) => {
              // Math.min/max propagate NaN from a partially-typed value, so
              // guard before clamping.
              const next = Number(e.target.value);
              if (!Number.isNaN(next)) onChange(Math.max(min, Math.min(max, next)));
            }}
            onBlur={() => setIsEditing(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === "Escape") setIsEditing(false);
            }}
            min={min}
            max={max}
            step={1000}
            className="w-28 rounded-[var(--radius-sm)] border border-[var(--color-primary)] bg-white px-2 py-0.5 text-right text-sm tabular-nums focus:outline-none"
          />
        ) : (
          <button
            type="button"
            onClick={() => setIsEditing(true)}
            className="rounded px-1 text-right text-sm font-semibold tabular-nums text-[var(--color-text)] transition-colors hover:bg-[var(--color-bg-alt)]"
          >
            {format(value)}
          </button>
        )}
      </div>
      <input
        type="range"
        value={positionFromValue(value)}
        min={0}
        max={1000}
        step={1}
        onChange={(e) => onChange(valueFromPosition(Number(e.target.value)))}
        className="w-full accent-[var(--color-primary)]"
      />
      {hint && <div className="text-[0.7rem] text-[var(--color-text-light)]">{hint}</div>}
    </div>
  );
}
