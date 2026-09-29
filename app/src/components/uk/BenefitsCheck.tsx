"use client";

import { useState } from "react";
import type { UKPensionCreditScreen } from "../../lib/api-uk";
import { citationLabel, summarizePensionCredit } from "../../lib/uk-benefits";

/**
 * Guarantee credit (Pension Credit) screening across simulated paths,
 * computed from statute encodings via the Axiom rules engine. Rendered only
 * when the API returns a screen.
 */
export function BenefitsCheck({
  screen,
  maxAge,
}: {
  screen: UKPensionCreditScreen;
  maxAge: number;
}) {
  const [showSources, setShowSources] = useState(false);
  const summary = summarizePensionCredit(screen, maxAge);

  return (
    <section
      aria-label="Pension Credit check"
      className="rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-[var(--color-bg-card)] p-5 shadow-[var(--shadow-sm)]"
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-widest text-[var(--color-text-muted)]">
          Pension Credit check
        </h3>
        <span className="rounded-full border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] px-2 py-0.5 text-[0.65rem] font-semibold text-[var(--color-primary)]">
          Statute-cited · modeled
        </span>
      </div>
      <p
        className={`mt-2 text-sm leading-relaxed ${
          summary.tone === "indicated"
            ? "text-[var(--color-text)]"
            : "text-[var(--color-text-muted)]"
        }`}
      >
        {summary.headline}
      </p>
      {summary.detail && (
        <p className="mt-1 text-sm leading-relaxed text-[var(--color-text)]">
          {summary.detail}
        </p>
      )}
      {screen.citations.length > 0 && (
        <>
          <button
            type="button"
            aria-expanded={showSources}
            className="mt-2 text-xs font-semibold text-[var(--color-primary)] underline-offset-2 hover:underline"
            onClick={() => setShowSources((value) => !value)}
          >
            {showSources ? "Hide sources" : `Sources (${screen.citations.length})`}
          </button>
          {showSources && (
            <ul className="mt-2 space-y-1">
              {screen.citations.map((citation) => (
                <li key={citation.id} className="text-xs">
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[var(--color-text-muted)] underline decoration-[var(--color-border)] underline-offset-2 hover:text-[var(--color-primary)]"
                  >
                    {citationLabel(citation.id)}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      <p className="mt-2 text-[0.7rem] leading-snug text-[var(--color-text-light)]">
        Screening estimate from encoded law (State Pension Credit Act 2002 s.2;
        SI 2002/1792 regs 6 and 15), not a benefits decision. It counts State
        Pension, pension drawdown (tax-free part included) and earnings, less
        tax, plus income deemed from ISA and GIA savings over £10,000; their
        actual dividends and interest are not counted. Qualifying age follows
        the Pensions Act 1995 State Pension age rules, taking your birthday to
        be today. Not modeled: notional income from pension pots you have not
        drawn, savings credit, and housing costs.
      </p>
    </section>
  );
}
