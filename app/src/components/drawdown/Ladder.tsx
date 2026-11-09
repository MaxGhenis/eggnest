import type { ReactNode } from "react";

/** The draw amounts where each extra unit of draw changes hands, lowest first. */
export function Ladder<Band extends { draw_from: number; draw_to: number }>({
  heading,
  legend,
  bands,
  draw,
  range,
  row,
}: {
  heading: string;
  legend: ReactNode;
  bands: readonly Band[];
  draw: number;
  range: (index: number) => string;
  row: (band: Band) => ReactNode;
}) {
  const current = bands.findIndex(
    (band, index) =>
      draw >= band.draw_from && (draw < band.draw_to || index === bands.length - 1),
  );

  return (
    <section aria-labelledby="ladder-heading">
      <h2 id="ladder-heading" className="font-[var(--font-display)] text-2xl">
        {heading}
      </h2>
      <div className="mt-3">{legend}</div>
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
              <div>{range(index)}</div>
              {index === current && (
                <div className="text-sm font-normal text-[var(--color-text-muted)]">
                  Your draw sits here
                </div>
              )}
            </div>
            <div>{row(band)}</div>
          </li>
        ))}
      </ol>
    </section>
  );
}
