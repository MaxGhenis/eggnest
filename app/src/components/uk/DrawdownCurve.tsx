"use client";

import type { DrawdownMarker, DrawdownOutcome } from "../../lib/api-uk-drawdown";
import { compactPounds, pounds } from "../../lib/uk-drawdown";
import { DrawdownChart } from "../drawdown/DrawdownChart";

const MARKER_LABELS: Record<DrawdownMarker["kind"], string> = {
  pot_income_covered: "Pension Credit starts to fall",
  guarantee_credit_ends: "Pension Credit ends",
};

const LABELS = {
  reference: "If you kept every pound",
  tax: "Extra income tax",
  lost: "Pension Credit lost",
  axis: "Amount you draw in the tax year",
  slider: "Amount to draw in the tax year",
};

const taxOf = (row: DrawdownOutcome) => row.income_tax + row.employee_ni;

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
  sweep: DrawdownOutcome[];
  draw: number;
  top: number;
  step: number;
  markers: DrawdownMarker[];
  onDraw: (draw: number) => void;
}) {
  return (
    <DrawdownChart
      sweep={sweep}
      draw={draw}
      top={top}
      step={step}
      markers={markers.map((marker) => ({
        key: marker.kind,
        draw: marker.draw,
        label: MARKER_LABELS[marker.kind],
      }))}
      onDraw={onDraw}
      taxAbove={(row, noDraw) => taxOf(row) - taxOf(noDraw)}
      lostAt={(row, noDraw) => noDraw.pension_credit - row.pension_credit}
      details={(row) => [`${pounds(taxOf(row))} tax`, `${pounds(row.pension_credit)} Pension Credit`]}
      money={pounds}
      compact={compactPounds}
      labels={LABELS}
    />
  );
}
