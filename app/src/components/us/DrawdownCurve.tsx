"use client";

import type { USDrawdownMarker, USDrawdownOutcome } from "../../lib/api-us-drawdown";
import { compactDollars, dollars, markerLabel, taxesOf } from "../../lib/us-drawdown";
import { DrawdownChart } from "../drawdown/DrawdownChart";

const LABELS = {
  reference: "If you kept every dollar",
  tax: "Extra tax",
  lost: "Benefits you lose",
  axis: "Amount you draw in 2026",
  slider: "Amount to draw",
};

/**
 * Money to spend at every draw. The horizontal axis doubles as the slider that
 * sets the draw, and dragging across the plot moves it too.
 */
export function DrawdownCurve({
  sweep,
  draw,
  top,
  step,
  markers,
  onDraw,
}: {
  sweep: USDrawdownOutcome[];
  draw: number;
  top: number;
  step: number;
  markers: USDrawdownMarker[];
  onDraw: (draw: number) => void;
}) {
  return (
    <DrawdownChart
      sweep={sweep}
      draw={draw}
      top={top}
      step={step}
      markers={markers.map((marker) => ({
        key: `${marker.kind}-${marker.program ?? ""}-${marker.draw}`,
        draw: marker.draw,
        label: markerLabel(marker),
      }))}
      onDraw={onDraw}
      taxAbove={(row, noDraw) => taxesOf(row) - taxesOf(noDraw)}
      lostAt={(row, noDraw) => noDraw.benefits - row.benefits}
      details={(row) => [
        `${dollars(taxesOf(row))} tax`,
        `${dollars(row.benefits)} benefits`,
        ...(Math.round(row.later_medicare_surcharge) > 0
          ? [`${dollars(row.later_medicare_surcharge)} more for Medicare in 2028`]
          : []),
      ]}
      money={dollars}
      compact={compactDollars}
      labels={LABELS}
    />
  );
}
