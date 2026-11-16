import type { DrawdownSlice } from "../../lib/api-uk-drawdown";
import { bandRange, describePound, splitPence } from "../../lib/uk-drawdown";
import { PoundSplitBar, PoundSplitLegend } from "./PoundSplitBar";

/** The draw amounts where each extra pound changes hands, lowest first. */
export function PoundLadder({
  bands,
  draw,
  balance,
}: {
  bands: DrawdownSlice[];
  draw: number;
  balance: number;
}) {
  const showLost = bands.some((band) => splitPence(band).lost > 0);
  const current = bands.findIndex(
    (band, index) =>
      draw >= band.draw_from && (draw < band.draw_to || index === bands.length - 1),
  );

  return (
    <section aria-labelledby="ladder-heading">
      <h2 id="ladder-heading" className="font-[var(--font-display)] text-2xl">
        Where each extra pound goes
      </h2>
      <div className="mt-3">
        <PoundSplitLegend showLost={showLost} />
      </div>
      <ol className="mt-4">
        {bands.map((band, index) => (
          <li
            key={band.draw_from}
            aria-current={index === current ? "true" : undefined}
            className={`grid gap-x-6 gap-y-2 border-t border-[var(--color-border)] py-3 sm:grid-cols-[9.5rem_minmax(0,1fr)] ${
              index === current ? "font-medium" : ""
            }`}
          >
            <div className="tabular-nums">
              <div>{bandRange(bands, index, balance)}</div>
              {index === current && (
                <div className="text-sm font-normal text-[var(--color-text-muted)]">
                  Your draw sits here
                </div>
              )}
            </div>
            <div>
              <PoundSplitBar split={splitPence(band)} />
              <p className="mt-1.5 text-[0.95rem]">{describePound(band)}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
