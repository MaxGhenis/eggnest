"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  analyzeCompensationPackages,
  type CompensationAnalysisResult,
} from "../../lib/api";
import {
  buildEmployerAnalysisInputForPresets,
  employerRolePresets,
  employerStateOptions,
  formatCurrency,
} from "../../lib/employer";

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function EmployerPage() {
  const [selectedRoleId, setSelectedRoleId] = useState(employerRolePresets[0].id);
  const [selectedState, setSelectedState] = useState<(typeof employerStateOptions)[number]>("CA");
  const [analysisByBenchmarkId, setAnalysisByBenchmarkId] = useState<
    Record<string, CompensationAnalysisResult>
  >({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedRole =
    employerRolePresets.find((role) => role.id === selectedRoleId) ??
    employerRolePresets[0];
  const analysis = analysisByBenchmarkId[selectedRole.benchmarkId] ?? null;
  const topSummaryCards = [
    [
      "Market position",
      isLoading
        ? "Calculating..."
        : analysis?.market_position.guaranteed_percentile_label ?? selectedRole.targetPercentile,
    ],
    [
      "Loaded employer cost",
      isLoading
        ? "Calculating..."
        : analysis
          ? formatCurrency(analysis.employer_cost.total_cost)
          : "—",
    ],
    [
      "Employee net resources",
      isLoading
        ? "Calculating..."
        : analysis
          ? formatCurrency(analysis.employee_value.net_resources_total)
          : "—",
    ],
  ] as const;

  useEffect(() => {
    const controller = new AbortController();

    async function run() {
      setIsLoading(true);
      setError(null);
      try {
        const results = await analyzeCompensationPackages(
          buildEmployerAnalysisInputForPresets(selectedState),
          controller.signal
        );
        const next = Object.fromEntries(
          results.map((result) => [result.package.benchmark_id, result])
        );
        setAnalysisByBenchmarkId(next);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Unable to analyze package");
          setAnalysisByBenchmarkId({});
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void run();

    return () => controller.abort();
  }, [selectedState]);

  return (
    <main className="min-h-screen overflow-x-hidden bg-gradient-page">
      <nav className="sticky top-0 z-50 flex items-center justify-between border-b border-[var(--color-border-light)] bg-white/95 px-5 py-3 backdrop-blur-md md:px-10">
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/logo.svg"
            alt="EggNest"
            width={160}
            height={32}
            className="block"
            priority
          />
          <span className="hidden rounded-full border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] px-3 py-1 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)] sm:inline-flex">
            Employer
          </span>
        </Link>
        <div className="flex items-center gap-3 md:gap-6">
          <Link href="/simulator" className="hidden text-sm font-medium text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)] sm:block">
            Simulator
          </Link>
          <Link href="/thesis" className="hidden text-sm font-medium text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)] sm:block">
            Thesis
          </Link>
          <Link href="/simulator" className="rounded-full border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] px-4 py-2 text-sm font-semibold text-[var(--color-primary)] transition-all hover:bg-[var(--color-primary)] hover:text-white">
            Open simulator
          </Link>
        </div>
      </nav>

      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute -right-[10%] -top-[20%] h-[600px] w-[600px] rounded-full bg-[radial-gradient(circle,_var(--color-gold-pale)_0%,_transparent_70%)] opacity-60" />
        <div className="pointer-events-none absolute -bottom-[30%] -left-[15%] h-[800px] w-[800px] rounded-full bg-[radial-gradient(circle,_var(--color-primary-100)_0%,_transparent_70%)] opacity-40" />

        <div className="relative z-10 mx-auto grid max-w-7xl gap-10 px-6 pb-16 pt-16 md:px-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:pt-20">
          <div className="max-w-2xl">
            <div className="mb-4 inline-flex rounded-full border border-[var(--color-primary-200)] bg-white px-4 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-primary)] shadow-[var(--shadow-sm)]">
              EggNest Employer
            </div>
            <h1 className="text-[clamp(2.7rem,6vw,4.8rem)] font-medium leading-[1.02] text-[var(--color-text)]" style={{ letterSpacing: "-0.04em" }}>
              Model compensation as
              <br />
              a system, not a guess.
            </h1>
            <p className="mt-6 max-w-xl text-xl leading-relaxed text-[var(--color-text-muted)]">
              EggNest Employer is a compensation scenario calculator for hiring,
              finance, and people teams. Model loaded employer cost, market
              position, and employee after-tax value under explicit assumptions.
            </p>
            <p className="mt-4 max-w-xl text-sm leading-relaxed text-[var(--color-text-light)]">
              Outputs on this page are modeled comparisons only, not
              compensation advice or a directive to choose any specific package.
              The examples below are illustrative sample roles, not one
              organization&apos;s internal compensation plan.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link href="#package-tool" className="inline-flex items-center gap-2 rounded-full bg-gradient-golden px-8 py-4 text-base font-semibold text-white shadow-[var(--shadow-md),0_4px_20px_var(--color-primary-glow)] transition-all hover:-translate-y-0.5 hover:shadow-[var(--shadow-lg),0_8px_30px_rgba(234,88,12,0.3)]">
                Open employer calculator
              </Link>
              <Link href="/simulator" className="inline-flex items-center gap-2 rounded-full border-[1.5px] border-[var(--color-border)] bg-white px-8 py-4 text-base font-semibold text-[var(--color-text)] shadow-[var(--shadow-sm)] transition-all hover:border-[var(--color-primary-200)] hover:bg-[var(--color-primary-50)]">
                View simulator
              </Link>
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-[var(--radius-xl)] border border-[var(--color-border-light)] bg-white/90 p-6 shadow-[var(--shadow-xl),var(--shadow-glow)]">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
                Separate surface
              </div>
              <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text)]">
                Employer-facing by design
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-text-muted)]">
                This surface is built for package design, market benchmarking,
                and employer cost analysis. The Simulator remains a separate
                household-facing surface on the same tax-aware engine.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
              {topSummaryCards.map(([label, value]) => (
              <div key={label} className="rounded-[var(--radius-xl)] border border-[var(--color-border-light)] bg-white p-6 shadow-[var(--shadow-xl),var(--shadow-glow)]">
                <div className="text-xs font-semibold uppercase tracking-widest text-[var(--color-text-light)]">{label}</div>
                <div className="mt-2 text-2xl font-semibold text-[var(--color-text)]">{value}</div>
              </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 pb-6 md:px-10">
        <div className="grid gap-5 lg:grid-cols-[1fr_1fr_0.9fr]">
          {[
            {
              title: "Employer surface",
              body: "Use this product surface to price roles, pressure-test benefit design, and compare what the package costs the company versus what it means after tax to the worker.",
            },
            {
              title: "Simulator",
              body: "The Simulator stays focused on household scenarios, retirement, life events, and after-tax modeling for individuals or families.",
            },
            {
              title: "Shared model layer",
              body: "Both surfaces use the same state and federal tax engine, so the employer view and household view stay internally consistent.",
            },
          ].map((item) => (
            <div key={item.title} className="rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-white px-5 py-6 shadow-[var(--shadow-sm)]">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
                {item.title}
              </div>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-text-muted)]">
                {item.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section id="package-tool" className="mx-auto max-w-7xl px-6 py-20 md:px-10">
        <div className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-5">
            <div className="section-card">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-semibold text-[var(--color-text)]">Sample package library</h2>
                  <p className="mt-1 text-sm text-[var(--color-text-muted)]">Choose an illustrative role family and compare the modeled package through employer cost, market position, and employee value.</p>
                </div>
                <div className="rounded-full bg-[var(--color-primary-50)] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-primary)]">
                  {selectedRole.function}
                </div>
              </div>

              <div className="mt-6 grid gap-3">
                {employerRolePresets.map((role) => {
                  const active = role.id === selectedRoleId;
                  return (
                    <button
                      key={role.id}
                      type="button"
                      onClick={() => setSelectedRoleId(role.id)}
                      className={`flex items-start justify-between rounded-[var(--radius-md)] border px-4 py-4 text-left transition-all ${active ? "border-[var(--color-primary)] bg-[var(--color-primary-50)] shadow-[0_0_0_1px_var(--color-primary)]" : "border-[var(--color-border)] bg-white hover:border-[var(--color-primary-200)] hover:shadow-[var(--shadow-sm)]"}`}
                    >
                      <div>
                        <div className="font-semibold text-[var(--color-text)]">{role.title}</div>
                        <div className="mt-1 text-sm text-[var(--color-text-muted)]">{role.packageLens}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-semibold text-[var(--color-primary)]">
                          {analysisByBenchmarkId[role.benchmarkId]?.market_position.guaranteed_percentile_label ?? role.targetPercentile}
                        </div>
                        <div className="mt-1 text-sm text-[var(--color-text-muted)]">{formatCurrency(role.cashSalary)}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid gap-5 md:grid-cols-3">
              {[
                {
                  title: "Package design",
                  body: "Set the salary ladder, retirement policy, and bonus assumptions before you hire.",
                },
                {
                  title: "Market position",
                  body: "See where the role lands against the outside option instead of guessing from title alone.",
                },
                {
                  title: "Worker value",
                  body: "Estimate what the offer means after taxes using the same PolicyEngine-driven household math.",
                },
              ].map((card) => (
                <div key={card.title} className="metric-card">
                  <div className="text-sm font-semibold text-[var(--color-text)]">{card.title}</div>
                  <div className="mt-2 text-sm leading-relaxed text-[var(--color-text-muted)]">{card.body}</div>
                </div>
              ))}
            </div>
          </div>

          <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
            <div className="section-card">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-widest text-[var(--color-text-light)]">Selected role</div>
                  <h3 className="mt-1 text-2xl font-semibold text-[var(--color-text)]">{selectedRole.title}</h3>
                </div>
                <div className="rounded-full bg-[var(--color-primary-50)] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-primary)]">
                  {analysis?.market_position.guaranteed_percentile_label ?? selectedRole.targetPercentile}
                </div>
              </div>

              <p className="mt-4 text-sm leading-relaxed text-[var(--color-text-muted)]">
                {selectedRole.marketLens}
              </p>

              {analysis && (
                <div className="mt-4 rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-bg-alt)] px-4 py-3 text-sm text-[var(--color-text-muted)]">
                  <div className="font-medium text-[var(--color-text)]">{analysis.benchmark.label}</div>
                  <div className="mt-1">{analysis.benchmark.source}</div>
                </div>
              )}

              <div className="mt-6 space-y-4">
                {[
                  ["Cash salary", formatCurrency(selectedRole.cashSalary)],
                  [
                    "Employer loaded cost",
                    analysis ? formatCurrency(analysis.employer_cost.total_cost) : "—",
                  ],
                  [
                    "Employer retirement",
                    analysis ? formatCurrency(analysis.employer_cost.employer_retirement) : "—",
                  ],
                  [
                    "Payroll taxes",
                    analysis ? formatCurrency(analysis.employer_cost.employer_payroll_taxes) : "—",
                  ],
                  [
                    "Market upside",
                    analysis?.market_position.upside_percentile_label ?? "—",
                  ],
                ].map(([label, value]) => (
                  <div key={label} className="flex items-center justify-between rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-white px-4 py-3">
                    <span className="text-sm text-[var(--color-text-muted)]">{label}</span>
                    <span className="text-sm font-semibold text-[var(--color-text)]">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="section-card">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-widest text-[var(--color-text-light)]">Employee-side view</div>
                  <h3 className="mt-1 text-xl font-semibold text-[var(--color-text)]">Modeled after-tax value</h3>
                </div>
                <select
                  value={selectedState}
                  onChange={(e) => setSelectedState(e.target.value as (typeof employerStateOptions)[number])}
                  className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none"
                >
                  {employerStateOptions.map((state) => (
                    <option key={state} value={state}>
                      {state}
                    </option>
                  ))}
                </select>
              </div>

              <p className="mt-3 text-sm leading-relaxed text-[var(--color-text-muted)]">
                Estimated for a single-worker household in {selectedState}. This
                uses the same tax engine as the Simulator, but on an
                illustrative compensation package rather than a life-event
                scenario.
              </p>

              {error && (
                <div className="mt-4 rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-light)] px-4 py-3 text-sm text-[var(--color-danger)]">
                  {error}
                </div>
              )}

              <div className="mt-5 grid grid-cols-2 gap-3">
                {[
                  {
                    label: "Net resources",
                    value: analysis ? formatCurrency(analysis.employee_value.net_resources_total) : "—",
                    highlight: true,
                  },
                  {
                    label: "Cash after tax",
                    value: analysis ? formatCurrency(analysis.employee_value.cash_after_tax) : "—",
                  },
                  {
                    label: "Total taxes",
                    value: analysis ? formatCurrency(analysis.employee_value.total_taxes) : "—",
                  },
                  {
                    label: "Effective rate",
                    value: analysis ? formatPercent(analysis.employee_value.effective_tax_rate) : "—",
                  },
                ].map(({ label, value, highlight }) => (
                  <div key={label} className={`metric-card ${highlight ? "metric-card-primary bg-[var(--color-primary-50)]" : ""}`}>
                    <div className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--color-text-light)]">{label}</div>
                    <div className={`mt-1 text-lg font-bold tabular-nums ${highlight ? "text-[var(--color-primary)]" : "text-[var(--color-text)]"}`}>
                      {isLoading ? "Calculating..." : value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </section>

      <section className="bg-[var(--color-bg-alt)] px-6 py-20 md:px-10">
        <div className="mx-auto grid max-w-7xl gap-5 md:grid-cols-3">
          {[
            {
              title: "Hiring teams",
              body: "Use the calculator to frame role design, compensation bands, and package tradeoffs before the offer goes out.",
            },
            {
              title: "Comp and finance",
              body: "Keep employer loaded cost, retirement policy, and tax treatment in the same working model instead of separate spreadsheets.",
            },
            {
              title: "Candidate conversations",
              body: "Use the separate Simulator when you want an employee-facing after-tax view without collapsing the employer workflow into advice.",
            },
          ].map((card) => (
            <div key={card.title} className="section-card">
              <h3 className="text-lg font-semibold text-[var(--color-text)]">{card.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--color-text-muted)]">{card.body}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
