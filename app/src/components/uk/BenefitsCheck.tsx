"use client";

import { useState } from "react";
import type { UKPensionCreditScreen } from "../../lib/api-uk";
import { formatGBP } from "../../lib/uk-outcome";

/**
 * Guarantee credit (Pension Credit) screening along the median path,
 * computed from statute encodings via the Axiom rules engine. Every number
 * links to the legislation that produced it.
 */
export function BenefitsCheck({ screen }: { screen: UKPensionCreditScreen }) {
  const [showSources, setShowSources] = useState(false);
  const indicated = screen.years_indicated > 0;
  const maxAmount = Math.max(0, ...screen.annual_amounts);
  const firstAge = screen.ages.find(
    (_, i) => (screen.annual_amounts[i] ?? 0) > 0,
  );

  return (
    <section className="rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-[var(--color-bg-card)] p-5 shadow-[var(--shadow-sm)]">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-widest text-[var(--color-text-muted)]">
          Benefits check
        </h3>
        <span className="rounded-full border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] px-2 py-0.5 text-[0.65rem] font-semibold text-[var(--color-primary)]">
          Statute-cited · modeled
        </span>
      </div>
      {indicated ? (
        <p className="mt-2 text-sm leading-relaxed text-[var(--color-text)]">
          On the median path, modeled income falls below the Pension Credit
          minimum guarantee ({formatGBP(screen.weekly_minimum_guarantee)}/week)
          in <strong>{screen.years_indicated}</strong> of {screen.ages.length}{" "}
          years{firstAge != null && <> (first at age {firstAge})</>}, with a
          guarantee credit of up to{" "}
          <strong>{formatGBP(maxAmount)}/year</strong>. Checking eligibility
          with the DWP could matter more than withdrawal strategy in those
          years.
        </p>
      ) : (
        <p className="mt-2 text-sm leading-relaxed text-[var(--color-text-muted)]">
          Median-path income stays above the Pension Credit minimum guarantee
          ({formatGBP(screen.weekly_minimum_guarantee)}/week) in every modeled
          year, so no guarantee credit is indicated.
        </p>
      )}
      <button
        type="button"
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
                {citation.id.replace("uk:", "").replace("#", " — ")}
              </a>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-[0.7rem] leading-snug text-[var(--color-text-light)]">
        Screening estimate from encoded law (State Pension Credit Act 2002
        s.2; SI 2002/1792 reg 6), not a benefits decision. Savings credit and
        housing additions are not modeled.
      </p>
    </section>
  );
}
