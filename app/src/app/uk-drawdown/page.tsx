"use client";

import { IconAlertTriangle, IconInfoCircle } from "@tabler/icons-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { DrawdownCurve } from "../../components/uk/DrawdownCurve";
import { DrawdownForm } from "../../components/uk/DrawdownForm";
import { PoundLadder } from "../../components/uk/PoundLadder";
import { PoundSplitBar, PoundSplitLegend } from "../../components/uk/PoundSplitBar";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import {
  runUKDrawdownYear,
  type DrawdownCitation,
  type DrawdownOutcome,
  type UKDrawdownRun,
  type UKDrawdownYearInput,
} from "../../lib/api-uk-drawdown";
import { citationLabel } from "../../lib/uk-benefits";
import {
  EXAMPLE_INPUTS,
  chartTop,
  comparedWithNoDraw,
  describeNextStep,
  drawStep,
  emptySourceMessage,
  headline,
  inputProblem,
  isExamplePerson,
  outcomeAt,
  pounds,
  poundsAndPence,
  sliceBetween,
  sourceBalance,
  splitPence,
  withDrawInBounds,
} from "../../lib/uk-drawdown";

const NEXT_STEP = 1_000;

function longDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function money(value: number): string {
  return Math.round(value) === 0 ? pounds(0) : `−${pounds(value)}`;
}

function YearLedger({
  income,
  chosen,
  none,
}: {
  income: number;
  chosen: DrawdownOutcome;
  none: DrawdownOutcome;
}) {
  const columns = chosen.draw > 0 ? [none, chosen] : [none];
  const rows: [string, (column: DrawdownOutcome) => string][] = [
    ["Income before you draw", () => pounds(income)],
    ["Money you draw", (column) => pounds(column.draw)],
    ["Pension Credit", (column) => pounds(column.pension_credit)],
    ["Income tax", (column) => money(column.income_tax)],
    ...(none.employee_ni || chosen.employee_ni
      ? ([["National Insurance", (column) => money(column.employee_ni)]] as [
          string,
          (column: DrawdownOutcome) => string,
        ][])
      : []),
  ];
  return (
    <table className="w-full border-collapse tabular-nums">
      <caption className="sr-only">Your tax year with no draw and with your chosen draw</caption>
      <thead>
        <tr className="text-right text-sm text-[var(--color-text-muted)]">
          <td />
          {columns.map((column) => (
            <th key={column.draw} scope="col" className="pb-1 pl-4 font-normal">
              {column.draw > 0 ? `Draw ${pounds(column.draw)}` : "Draw nothing"}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, value]) => (
          <tr key={label} className="border-t border-[var(--color-border)]">
            <th scope="row" className="py-1.5 pr-3 text-left font-normal">
              {label}
            </th>
            {columns.map((column) => (
              <td key={column.draw} className="pl-4 text-right">
                {value(column)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr className="border-t-2 border-[var(--color-text)] font-semibold">
          <th scope="row" className="py-2 pr-3 text-left">
            Money to spend
          </th>
          {columns.map((column) => (
            <td key={column.draw} className="pl-4 text-right">
              {pounds(column.money_to_spend)}
            </td>
          ))}
        </tr>
      </tfoot>
    </table>
  );
}

function PensionCreditWorking({ run }: { run: UKDrawdownRun }) {
  const working = run.result.pension_credit_working;
  if (working.status === "under_qualifying_age") {
    return (
      <p>
        You reach Pension Credit age on {longDate(working.qualifying_date)}, after this tax year, so
        you get no Pension Credit in {run.result.tax_year_label}.
      </p>
    );
  }
  const rows: [string, number][] = [
    ["State Pension", working.state_pension],
    ["Other pensions and annuities", working.other_pension_income],
    ["Earnings above £5 a week", working.earnings_counted],
    ["Regular withdrawals from your pot", working.regular_pot_income],
    ["Income DWP assumes your pot could also pay", working.notional_pot_income],
    ["Less tax on that income", -working.tax_deducted],
  ];
  const yieldUsed = run.result.assumptions.gilt_yield_percent_used;
  return (
    <>
      {working.eligible_weeks < 52 && (
        <p className="mb-3">
          You reach Pension Credit age on {longDate(working.qualifying_date)}, so we count{" "}
          {working.eligible_weeks} of the year’s 52 weeks.
        </p>
      )}
      <table className="w-full max-w-md border-collapse tabular-nums">
        <caption className="sr-only">Income Pension Credit counts each week</caption>
        <tbody>
          {rows
            .filter(([, value]) => value !== 0)
            .map(([label, value]) => (
              <tr key={label} className="border-t border-[var(--color-border)]">
                <th scope="row" className="py-1 pr-3 text-left font-normal">
                  {label}
                </th>
                <td className="text-right">
                  {value < 0 ? `−${poundsAndPence(-value)}` : poundsAndPence(value)}
                </td>
              </tr>
            ))}
          {(working.deemed_income_first_week > 0 || working.deemed_income_last_week > 0) && (
            <tr className="border-t border-[var(--color-border)]">
              <th scope="row" className="py-1 pr-3 text-left font-normal">
                Income DWP assumes from savings over £10,000, first and last week
              </th>
              <td className="text-right whitespace-nowrap">
                {poundsAndPence(working.deemed_income_first_week)},{" "}
                {poundsAndPence(working.deemed_income_last_week)}
              </td>
            </tr>
          )}
          <tr className="border-t border-[var(--color-border)]">
            <th scope="row" className="py-1 pr-3 text-left font-normal">
              Minimum guarantee, which Pension Credit tops you up to
            </th>
            <td className="text-right">
              {poundsAndPence(working.weekly_minimum_guarantee ?? 0)}
            </td>
          </tr>
          <tr className="border-t-2 border-[var(--color-text)] font-semibold">
            <th scope="row" className="py-1.5 pr-3 text-left">
              Pension Credit each week, on average
            </th>
            <td className="text-right">
              {poundsAndPence(run.result.pension_credit.amount / working.eligible_weeks)}
            </td>
          </tr>
        </tbody>
      </table>
      {run.result.pension_credit_working.annual_annuity_income > 0 && (
        <p className="mt-3">
          DWP assumes an untouched pot pays the annuity it could buy. For your pot that comes to{" "}
          {pounds(working.annual_annuity_income)} a year,{" "}
          {yieldUsed === null
            ? `from your provider’s figure of ${poundsAndPence(working.annuity_income_per_1000)} per £1,000.`
            : `from the Government Actuary’s table for age ${working.annuity_age} and a ${yieldUsed.toFixed(2)}% gilt yield.`}
        </p>
      )}
    </>
  );
}

function CitationList({ citations }: { citations: DrawdownCitation[] }) {
  return (
    <ul className="mt-1 space-y-1">
      {citations.map((citation) => (
        <li key={`${citation.id}${citation.url}`}>
          <a
            href={citation.url}
            target="_blank"
            rel="noreferrer"
            className="text-[var(--color-primary-dark)] underline underline-offset-2"
          >
            {citationLabel(citation.id)}
          </a>
        </li>
      ))}
    </ul>
  );
}

function TurningPoints({
  run,
  draw,
}: {
  run: UKDrawdownRun;
  draw: number;
}) {
  const amounts = [
    ...new Set([...run.result.bands.flatMap((band) => [band.draw_from, band.draw_to]), draw]),
  ].sort((a, b) => a - b);
  return (
    <details>
      <summary className="cursor-pointer font-medium">See the turning points as a table</summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full border-collapse text-right tabular-nums">
          <thead>
            <tr className="text-sm text-[var(--color-text-muted)]">
              <th scope="col" className="py-1 text-left font-normal">
                You draw
              </th>
              <th scope="col" className="font-normal">
                Money to spend
              </th>
              <th scope="col" className="font-normal">
                Income tax and NI
              </th>
              <th scope="col" className="font-normal">
                Pension Credit
              </th>
            </tr>
          </thead>
          <tbody>
            {amounts.map((amount) => {
              const row = outcomeAt(run.result.sweep, amount);
              return (
                <tr key={amount} className="border-t border-[var(--color-border)]">
                  <th scope="row" className="py-1 text-left font-normal">
                    {pounds(row.draw)}
                  </th>
                  <td>{pounds(row.money_to_spend)}</td>
                  <td>{pounds(row.income_tax + row.employee_ni)}</td>
                  <td>{pounds(row.pension_credit)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function Results({
  run,
  inputs,
  stale,
  onDraw,
}: {
  run: UKDrawdownRun;
  inputs: UKDrawdownYearInput;
  stale: boolean;
  onDraw: (draw: number) => void;
}) {
  const { result } = run;
  const balance = sourceBalance(inputs);
  const sweepTop = result.sweep[result.sweep.length - 1].draw;
  const top = chartTop(sweepTop, balance, inputs.draw_amount);
  const chosen = outcomeAt(result.sweep, inputs.draw_amount);
  const none = result.with_no_draw;
  const next = sliceBetween(
    result.sweep,
    inputs.draw_amount,
    Math.min(inputs.draw_amount + NEXT_STEP, balance),
  );
  const income =
    inputs.state_pension +
    inputs.other_pension_income +
    inputs.employment_income +
    inputs.savings_interest +
    inputs.dividend_income;
  const comparison = comparedWithNoDraw(chosen, none);
  const creditGone = none.pension_credit >= 1 && chosen.pension_credit < 1;
  const taxCitations = result.income_tax.citations;
  const creditCitations = result.pension_credit.citations;
  const engine = run.sources.find((source) => source.name === "Axiom rules engine");
  const rules = run.sources.find((source) => source.name === "rulespec-uk");

  return (
    <div className={`min-w-0 space-y-10 ${stale ? "opacity-60" : ""}`} aria-busy={stale}>
      <section aria-live="polite">
        <p className="font-[var(--font-display)] text-[clamp(1.85rem,1.3rem+1.9vw,2.85rem)] leading-[1.12]">
          {headline(inputs.draw_source, inputs.draw_amount, chosen.money_to_spend, result.tax_year_label)}
        </p>
        {comparison && <p className="mt-3 text-lg">{comparison}</p>}
        {creditGone && (
          <p className="mt-3 flex max-w-2xl items-start gap-2 text-[0.95rem]">
            <IconAlertTriangle
              aria-hidden="true"
              size={20}
              className="mt-0.5 shrink-0 text-[var(--color-warning-text)]"
            />
            You’d lose Pension Credit altogether at this draw. If you get Housing Benefit or Council
            Tax Reduction, those can fall too, and we leave them out.
          </p>
        )}
        <a
          href="#your-figures"
          className="mt-3 inline-block text-[var(--color-primary-dark)] underline underline-offset-2 lg:hidden"
        >
          Change your figures
        </a>
      </section>

      {balance > 0 ? (
        <div>
          <DrawdownCurve
            sweep={result.sweep}
            draw={Math.min(inputs.draw_amount, top)}
            top={top}
            step={drawStep(top)}
            markers={result.markers}
            onDraw={onDraw}
          />
          <TurningPoints run={run} draw={inputs.draw_amount} />
        </div>
      ) : (
        <p className="text-lg">{emptySourceMessage(inputs.draw_source)}</p>
      )}

      <section className="grid gap-8 md:grid-cols-2" aria-label="Your tax year">
        <div>
          <YearLedger income={income} chosen={chosen} none={none} />
          {balance > 0 && (
            <p className="mt-2 text-[0.95rem] text-[var(--color-text-muted)]">
              {pounds(balance - inputs.draw_amount)} stays in this pot after your draw, before any
              growth.
            </p>
          )}
        </div>
        {next && (
          <div>
            <h2 className="font-[var(--font-display)] text-2xl">
              Your next {pounds(next.draw_to - next.draw_from)}
            </h2>
            <div className="mt-3">
              <PoundSplitBar split={splitPence(next)} />
            </div>
            <div className="mt-2">
              <PoundSplitLegend showLost={splitPence(next).lost > 0} />
            </div>
            <p className="mt-2">{describeNextStep(next)}</p>
          </div>
        )}
      </section>

      {result.bands.length > 0 && (
        <PoundLadder bands={result.bands} draw={inputs.draw_amount} balance={balance} />
      )}

      <section aria-labelledby="working-heading">
        <h2 id="working-heading" className="font-[var(--font-display)] text-2xl">
          What DWP counts each week
        </h2>
        <div className="mt-3">
          <PensionCreditWorking run={run} />
        </div>
      </section>

      <section aria-labelledby="limits-heading">
        <h2 id="limits-heading" className="font-[var(--font-display)] text-2xl">
          What we leave out
        </h2>
        <ul className="mt-3 max-w-[70ch] list-disc space-y-2 pl-5">
          {run.caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="sources-heading">
        <h2 id="sources-heading" className="font-[var(--font-display)] text-2xl">
          Sources
        </h2>
        <p className="mt-3 max-w-[70ch]">
          The{" "}
          <a
            href={engine?.url ?? undefined}
            target="_blank"
            rel="noreferrer"
            className="text-[var(--color-primary-dark)] underline underline-offset-2"
          >
            Axiom rules engine
          </a>{" "}
          {engine?.version} calculates income tax, National Insurance and Pension Credit from{" "}
          <a
            href={rules?.url ?? undefined}
            target="_blank"
            rel="noreferrer"
            className="text-[var(--color-primary-dark)] underline underline-offset-2"
          >
            rulespec-uk
          </a>{" "}
          {rules?.version?.slice(0, 7)}.
        </p>
        <div className="mt-4 grid gap-6 text-[0.95rem] md:grid-cols-2">
          <div>
            <h3 className="font-medium">Income tax and National Insurance</h3>
            <CitationList citations={taxCitations} />
          </div>
          <div>
            <h3 className="font-medium">Pension Credit</h3>
            <CitationList citations={creditCitations} />
          </div>
        </div>
      </section>
    </div>
  );
}

export default function UKDrawdownPage() {
  const [form, setForm] = useState<UKDrawdownYearInput>(EXAMPLE_INPUTS);
  const [run, setRun] = useState<{ baseKey: string; data: UKDrawdownRun } | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const inputs = useMemo(() => withDrawInBounds(form), [form]);
  const problem = inputProblem(inputs);
  const key = JSON.stringify(inputs);
  const baseKey = JSON.stringify({ ...inputs, draw_amount: 0 });
  const debouncedKey = useDebouncedValue(key, 300);

  useEffect(() => {
    if (problem || debouncedKey !== key) return;
    const controller = new AbortController();
    const sent = JSON.parse(debouncedKey) as UKDrawdownYearInput;
    runUKDrawdownYear(sent, controller.signal)
      .then((data) => {
        setRun({ baseKey: JSON.stringify({ ...sent, draw_amount: 0 }), data });
        setFailure(null);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setFailure("We couldn’t work this out. Check your connection and try again.");
        }
      });
    return () => controller.abort();
  }, [debouncedKey, key, problem, attempt]);

  const update = (change: Partial<UKDrawdownYearInput>) =>
    setForm((current) => ({ ...current, ...change }));

  return (
    <div className="min-h-screen">
      <header className="header-glass sticky top-0 z-50 border-b border-[var(--color-border-light)]">
        <div className="mx-auto flex max-w-6xl items-center px-4 py-3 md:px-6">
          <Link href="/" className="flex items-center gap-2.5 transition-opacity hover:opacity-80">
            <Image src="/logo.svg" alt="EggNest" width={140} height={28} priority />
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 md:px-6 md:py-10">
        <h1 className="max-w-3xl font-[var(--font-display)] text-3xl md:text-4xl">
          What you keep when you draw from your savings
        </h1>
        <p className="mt-2 max-w-[62ch] text-lg text-[var(--color-text-muted)]">
          Pick how much to take from your pension pot, ISAs or other savings in the 2026/27 tax
          year, and see what you keep after income tax, National Insurance and any change in Pension
          Credit.
        </p>

        {isExamplePerson(inputs) && (
          <p className="mt-6 flex max-w-3xl items-start gap-2 rounded-[var(--radius-sm)] bg-[var(--color-warning-light)] px-4 py-3 text-[var(--color-warning-text)]">
            <IconInfoCircle aria-hidden="true" size={20} className="mt-0.5 shrink-0" />
            These figures describe an example person. Enter your own to see your year.
          </p>
        )}

        <div className="mt-8 grid gap-10 lg:grid-cols-[360px_minmax(0,1fr)]">
          <div className="order-2 lg:order-1">
            <DrawdownForm inputs={form} onChange={update} />
          </div>

          <div className="order-1 min-w-0 lg:order-2">
            {problem ? (
              <p role="alert" className="text-lg">
                {problem}
              </p>
            ) : failure ? (
              <div role="alert">
                <p className="text-lg">{failure}</p>
                <button
                  type="button"
                  className="mt-3 rounded-[var(--radius-sm)] bg-[var(--color-primary-dark)] px-4 py-2 font-medium text-white"
                  onClick={() => setAttempt((count) => count + 1)}
                >
                  Try again
                </button>
              </div>
            ) : run ? (
              <Results
                run={run.data}
                inputs={inputs}
                stale={run.baseKey !== baseKey}
                onDraw={(draw_amount) => update({ draw_amount })}
              />
            ) : (
              <p className="text-lg text-[var(--color-text-muted)]">Working out your year</p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
