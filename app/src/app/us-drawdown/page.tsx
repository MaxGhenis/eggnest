"use client";

import { IconAlertTriangle, IconInfoCircle } from "@tabler/icons-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { DollarLadder } from "../../components/us/DollarLadder";
import { DollarSplitBar, DollarSplitLegend } from "../../components/us/DollarSplitBar";
import { DrawdownCurve } from "../../components/us/DrawdownCurve";
import { DrawdownForm } from "../../components/us/DrawdownForm";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import {
  runUSDrawdownYear,
  type USCitation,
  type USCoverage,
  type USDrawdownMarker,
  type USDrawdownOutcome,
  type USDrawdownRun,
  type USDrawdownYearInput,
} from "../../lib/api-us-drawdown";
import { joined } from "../../lib/drawdown";
import {
  COVERAGE_NAMES,
  COVERAGE_SUBJECTS,
  EXAMPLE_FORM,
  cashIncome,
  chartTop,
  comparedWithNoDraw,
  coverageAt,
  coverageLost,
  describeCoverageEnds,
  describeMedicare,
  describeNextStep,
  describeRequiredMinimum,
  describeShortfall,
  dollars,
  drawStep,
  emptySourceMessage,
  headline,
  inputProblem,
  inputsFrom,
  isExamplePerson,
  outcomeAt,
  programName,
  requiredMinimumAt,
  sliceBetween,
  sourceBalance,
  sourceName,
  splitCents,
  taxesOf,
  type USDrawdownForm,
} from "../../lib/us-drawdown";

const NEXT_STEP = 1_000;
const LINK_CLASS = "text-[var(--color-primary-dark)] underline underline-offset-2";

/** A tax as the ledger subtracts it. */
function minus(value: number): string {
  if (Math.round(value) === 0) return dollars(0);
  return value > 0 ? `−${dollars(value)}` : dollars(-value);
}

type LedgerRow = [string, (column: USDrawdownOutcome) => string];

function columnHeading(draw: number): string {
  return draw > 0 ? `Draw ${dollars(draw)}` : "Draw nothing";
}

function YearLedger({
  income,
  chosen,
  none,
}: {
  income: number;
  chosen: USDrawdownOutcome;
  none: USDrawdownOutcome;
}) {
  const columns = chosen.draw > 0 ? [none, chosen] : [none];
  const programs = Object.keys(none.benefits_by_program).filter((program) =>
    columns.some((column) => Math.round(column.benefits_by_program[program] ?? 0) !== 0),
  );
  const rows: LedgerRow[] = [
    ["Income before you draw", () => dollars(income)],
    ["Money you draw", (column) => dollars(column.draw)],
    ...programs.map((program): LedgerRow => [
      programName(program).label,
      (column) => dollars(column.benefits_by_program[program] ?? 0),
    ]),
    ["Federal income tax", (column) => minus(column.federal_income_tax)],
    ["State income tax", (column) => minus(column.state_income_tax)],
    ...(columns.some((column) => Math.round(column.other_taxes) !== 0)
      ? [["Other taxes", (column: USDrawdownOutcome) => minus(column.other_taxes)] as LedgerRow]
      : []),
  ];
  return (
    <table className="w-full border-collapse tabular-nums">
      <caption className="sr-only">Your 2026 with no draw and with your chosen draw</caption>
      <thead>
        <tr className="text-right text-sm text-[var(--color-text-muted)]">
          <td />
          {columns.map((column) => (
            <th key={column.draw} scope="col" className="pb-1 pl-4 font-normal">
              {columnHeading(column.draw)}
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
              {dollars(column.money_to_spend)}
            </td>
          ))}
        </tr>
      </tfoot>
    </table>
  );
}

function CoverageTable({
  withNoDraw,
  atDraw,
  draw,
  markers,
}: {
  withNoDraw: Record<USCoverage, boolean>;
  atDraw: Record<USCoverage, boolean>;
  draw: number;
  markers: USDrawdownMarker[];
}) {
  const names = (Object.keys(withNoDraw) as USCoverage[]).filter(
    (name) => withNoDraw[name] || atDraw[name],
  );
  if (!names.length) return null;
  const columns: [number, Record<USCoverage, boolean>][] =
    draw > 0
      ? [
          [0, withNoDraw],
          [draw, atDraw],
        ]
      : [[0, withNoDraw]];
  const ends = describeCoverageEnds(markers);
  return (
    <>
      <table className="mt-5 w-full border-collapse">
        <caption className="mb-1 text-left font-medium">Health coverage</caption>
        <thead>
          <tr className="text-right text-sm text-[var(--color-text-muted)]">
            <td />
            {columns.map(([amount]) => (
              <th key={amount} scope="col" className="pb-1 pl-4 font-normal">
                {columnHeading(amount)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {names.map((name) => (
            <tr key={name} className="border-t border-[var(--color-border)]">
              <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                {COVERAGE_NAMES[name]}
              </th>
              {columns.map(([amount, coverage]) => (
                <td key={amount} className="pl-4 text-right">
                  {coverage[name] ? "Yes" : "No"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {ends && <p className="mt-2 text-[0.95rem] text-[var(--color-text-muted)]">{ends}</p>}
    </>
  );
}

function Warning({ children }: { children: ReactNode }) {
  return (
    <p className="mt-3 flex max-w-2xl items-start gap-2 text-[0.95rem]">
      <IconAlertTriangle
        aria-hidden="true"
        size={20}
        className="mt-0.5 shrink-0 text-[var(--color-warning-text)]"
      />
      <span>{children}</span>
    </p>
  );
}

function CitationList({ citations }: { citations: USCitation[] }) {
  return (
    <ul className="mt-1 space-y-1">
      {citations.map((citation) => (
        <li key={`${citation.id}${citation.url}`}>
          <a href={citation.url} target="_blank" rel="noreferrer" className={LINK_CLASS}>
            {citation.source}: {citation.title}
          </a>
        </li>
      ))}
    </ul>
  );
}

function TurningPoints({ run, draw }: { run: USDrawdownRun; draw: number }) {
  const { sweep, bands } = run.result;
  const amounts = [
    ...new Set([...bands.flatMap((band) => [band.draw_from, band.draw_to]), draw]),
  ].sort((a, b) => a - b);
  const rows = amounts.map((amount) => outcomeAt(sweep, amount));
  const showMedicare = rows.some((row) => Math.round(row.later_medicare_surcharge) > 0);
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
                Tax
              </th>
              <th scope="col" className="font-normal">
                Benefits
              </th>
              {showMedicare && (
                <th scope="col" className="font-normal">
                  More for Medicare in 2028
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.draw} className="border-t border-[var(--color-border)]">
                <th scope="row" className="py-1 text-left font-normal">
                  {dollars(row.draw)}
                </th>
                <td>{dollars(row.money_to_spend)}</td>
                <td>{dollars(taxesOf(row))}</td>
                <td>{dollars(row.benefits)}</td>
                {showMedicare && <td>{dollars(row.later_medicare_surcharge)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function Sources({ run }: { run: USDrawdownRun }) {
  const { result } = run;
  const engine = run.sources.find((source) => source.name === "PolicyEngine US");
  const core = run.sources.find((source) => source.name === "PolicyEngine Core");
  const table = run.sources.find((source) => source.name === "IRS Uniform Lifetime Table");
  const groups: [string, USCitation[]][] = [
    ["Federal income tax", result.federal_income_tax.citations],
    ["State income tax", result.state_income_tax.citations],
    ["Other taxes", result.other_taxes.citations],
    ["Benefits", result.benefits.citations],
  ];
  const listed = new Set(groups.flatMap(([, citations]) => citations.map((c) => c.id)));
  const rest = run.citations.filter((citation) => !listed.has(citation.id));
  const medicare = rest.filter((citation) => citation.id.startsWith("us:statutes/42/"));
  const minimums = rest.filter((citation) => !citation.id.startsWith("us:statutes/42/"));
  groups.push(["Medicare premiums", medicare], ["Required minimum distributions", minimums]);

  return (
    <section aria-labelledby="sources-heading">
      <h2 id="sources-heading" className="font-[var(--font-display)] text-2xl">
        Sources
      </h2>
      <p className="mt-3 max-w-[70ch]">
        <a href={engine?.url ?? undefined} target="_blank" rel="noreferrer" className={LINK_CLASS}>
          PolicyEngine-US
        </a>{" "}
        {engine?.version} calculates federal and state income taxes, benefits, Medicaid and Medicare
        Savings Program eligibility, and Medicare’s income-related premiums. It runs on{" "}
        <a href={core?.url ?? undefined} target="_blank" rel="noreferrer" className={LINK_CLASS}>
          PolicyEngine Core
        </a>{" "}
        {core?.version}. We figure required minimum distributions from the{" "}
        <a href={table?.url ?? undefined} target="_blank" rel="noreferrer" className={LINK_CLASS}>
          IRS Uniform Lifetime Table
        </a>
        .
      </p>
      <div className="mt-4 grid gap-6 text-[0.95rem] md:grid-cols-2">
        {groups
          .filter(([, citations]) => citations.length > 0)
          .map(([title, citations]) => (
            <div key={title}>
              <h3 className="font-medium">{title}</h3>
              <CitationList citations={citations} />
            </div>
          ))}
      </div>
    </section>
  );
}

function Results({
  run,
  inputs,
  stale,
  onDraw,
}: {
  run: USDrawdownRun;
  inputs: USDrawdownYearInput;
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
  const showNext = next !== null && next.draw_to - next.draw_from >= 1;
  const comparison = comparedWithNoDraw(chosen, none);
  const coverage = coverageAt(result.coverage_with_no_draw, result.markers, inputs.draw_amount);
  const lost = coverageLost(result.coverage_with_no_draw, coverage);
  const minimums = result.required_minimums.map((minimum) => ({
    minimum,
    atDraw: requiredMinimumAt(minimum, inputs),
  }));
  const shortfalls = minimums.filter(({ atDraw }) => Math.round(atDraw.shortfall) > 0);

  return (
    <div className={`min-w-0 space-y-10 ${stale ? "opacity-60" : ""}`} aria-busy={stale}>
      <section aria-live="polite">
        <p className="font-[var(--font-display)] text-[clamp(1.85rem,1.3rem+1.9vw,2.85rem)] leading-[1.12]">
          {headline(
            inputs.draw_source,
            inputs.draw_owner,
            inputs.draw_amount,
            chosen.money_to_spend,
          )}
        </p>
        {comparison && <p className="mt-3 text-lg">{comparison}</p>}
        {lost.length > 0 && (
          <Warning>
            You’d lose {joined(lost.map((name) => COVERAGE_SUBJECTS[name]))} at this draw. We mark
            where coverage ends but leave its value out of money to spend
            {lost.includes("msp")
              ? "; without a Medicare Savings Program you’d pay your own Part B premium."
              : "."}
          </Warning>
        )}
        {shortfalls.map(({ minimum, atDraw }) => (
          <Warning key={minimum.person}>{describeShortfall(minimum, atDraw)}</Warning>
        ))}
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
        <p className="text-lg">{emptySourceMessage(inputs.draw_source, inputs.draw_owner)}</p>
      )}

      <section className="grid gap-8 md:grid-cols-2" aria-label="Your 2026">
        <div>
          <YearLedger income={cashIncome(inputs)} chosen={chosen} none={none} />
          {balance > 0 && (
            <p className="mt-2 text-[0.95rem] text-[var(--color-text-muted)]">
              {dollars(balance - inputs.draw_amount)} stays in{" "}
              {sourceName(inputs.draw_source, inputs.draw_owner)} after your draw, before any
              growth.
            </p>
          )}
          <CoverageTable
            withNoDraw={result.coverage_with_no_draw}
            atDraw={coverage}
            draw={inputs.draw_amount}
            markers={result.markers}
          />
        </div>
        {showNext && next && (
          <div>
            <h2 className="font-[var(--font-display)] text-2xl">
              Your next {dollars(next.draw_to - next.draw_from)}
            </h2>
            <div className="mt-3">
              <DollarSplitBar split={splitCents(next)} />
            </div>
            <div className="mt-2">
              <DollarSplitLegend showLost={splitCents(next).lost > 0} />
            </div>
            <p className="mt-2">
              {describeNextStep(
                next,
                outcomeAt(result.sweep, next.draw_from),
                outcomeAt(result.sweep, next.draw_to),
              )}
            </p>
          </div>
        )}
      </section>

      {result.bands.length > 0 && (
        <DollarLadder
          bands={result.bands}
          sweep={result.sweep}
          draw={inputs.draw_amount}
          balance={balance}
        />
      )}

      <section aria-labelledby="medicare-heading">
        <h2 id="medicare-heading" className="font-[var(--font-display)] text-2xl">
          Medicare premiums in {result.medicare_surcharge.premium_year}
        </h2>
        <div className="mt-3 max-w-[70ch] space-y-2">
          {describeMedicare(chosen, result.medicare_surcharge, result.markers).map((sentence) => (
            <p key={sentence}>{sentence}</p>
          ))}
        </div>
      </section>

      {minimums.length > 0 && (
        <section aria-labelledby="minimum-heading">
          <h2 id="minimum-heading" className="font-[var(--font-display)] text-2xl">
            {minimums.length > 1
              ? "Required minimum distributions"
              : "Required minimum distribution"}
          </h2>
          {minimums.map(({ minimum, atDraw }) => (
            <div key={minimum.person} className="mt-3 max-w-[70ch] space-y-2">
              {describeRequiredMinimum(minimum, atDraw, inputs).map((sentence) => (
                <p key={sentence}>{sentence}</p>
              ))}
            </div>
          ))}
        </section>
      )}

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

      <Sources run={run} />
    </div>
  );
}

export default function USDrawdownPage() {
  const [form, setForm] = useState<USDrawdownForm>(EXAMPLE_FORM);
  const [run, setRun] = useState<{
    baseKey: string;
    data: USDrawdownRun;
  } | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const inputs = useMemo(() => inputsFrom(form), [form]);
  const problem = inputProblem(inputs);
  const key = JSON.stringify(inputs);
  const baseKey = JSON.stringify({ ...inputs, draw_amount: 0 });
  const debouncedKey = useDebouncedValue(key, 300);

  useEffect(() => {
    if (problem || debouncedKey !== key) return;
    const controller = new AbortController();
    const sent = JSON.parse(debouncedKey) as USDrawdownYearInput;
    runUSDrawdownYear(sent, controller.signal)
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

  const update = (change: Partial<USDrawdownForm>) =>
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
          Pick how much to take from a traditional IRA or 401(k), a Roth IRA, investments or cash in
          2026. See what you keep after federal and state income tax and any benefits you lose, and
          what it adds to your Medicare premiums in 2028.
        </p>

        {isExamplePerson(inputs) && (
          <p className="mt-6 flex max-w-3xl items-start gap-2 rounded-[var(--radius-sm)] bg-[var(--color-warning-light)] px-4 py-3 text-[var(--color-warning-text)]">
            <IconInfoCircle aria-hidden="true" size={20} className="mt-0.5 shrink-0" />
            These figures describe an example person. Enter your own to see your year.
          </p>
        )}

        <div className="mt-8 grid gap-10 lg:grid-cols-[360px_minmax(0,1fr)]">
          <div className="order-2 lg:order-1">
            <DrawdownForm form={form} onChange={update} />
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
