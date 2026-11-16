import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { DrawdownMarker, DrawdownOutcome } from "../../lib/api-uk-drawdown";
import { DrawdownCurve } from "./DrawdownCurve";

function row(draw: number, pension_credit: number, income_tax = 0): DrawdownOutcome {
  return {
    draw,
    taxable_draw: draw * 0.75,
    income_tax,
    employee_ni: 0,
    pension_credit,
    money_to_spend: 10_000 + draw + pension_credit - income_tax,
  };
}

const SWEEP = [row(0, 2_000), row(1_000, 1_000), row(2_000, 0), row(5_000, 0, 150), row(10_000, 0, 900)];
const MARKERS: DrawdownMarker[] = [
  { kind: "pot_income_covered", draw: 500 },
  { kind: "guarantee_credit_ends", draw: 2_000 },
];

function renderCurve(overrides: Partial<Parameters<typeof DrawdownCurve>[0]> = {}) {
  const onDraw = vi.fn();
  render(
    <DrawdownCurve
      sweep={SWEEP}
      draw={2_000}
      top={10_000}
      step={50}
      markers={MARKERS}
      onDraw={onDraw}
      {...overrides}
    />,
  );
  return onDraw;
}

/** jsdom lays nothing out, so give the plot a size to point at. */
function sizedSurface(): Element {
  const surface = screen.getByTestId("curve-surface");
  surface.getBoundingClientRect = () =>
    ({ left: 100, width: 500, top: 0, right: 600, bottom: 300, height: 300 }) as DOMRect;
  return surface;
}

describe("DrawdownCurve", () => {
  it("makes the axis a labelled slider with the draw in words", () => {
    const onDraw = renderCurve();
    const slider = screen.getByRole("slider", { name: "Amount to draw in the tax year" });
    expect(slider).toHaveAttribute("aria-valuetext", "£2,000");
    expect(slider).toHaveAttribute("max", "10000");
    expect(slider).toHaveAttribute("step", "50");
    fireEvent.change(slider, { target: { value: "3500" } });
    expect(onDraw).toHaveBeenCalledWith(3_500);
  });

  it("names the series in the legend and the turning points on the plot", () => {
    renderCurve();
    for (const label of [
      "Money to spend",
      "If you kept every pound",
      "Extra income tax",
      "Pension Credit lost",
      "Pension Credit starts to fall",
      "Pension Credit ends",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("drops what doesn't apply", () => {
    renderCurve({ sweep: [row(0, 0), row(5_000, 0)], top: 5_000, markers: [], draw: 0 });
    expect(screen.queryByText("Pension Credit lost")).not.toBeInTheDocument();
    expect(screen.queryByText("Extra income tax")).not.toBeInTheDocument();
    expect(screen.queryByText("Pension Credit ends")).not.toBeInTheDocument();
  });

  it("hides turning points beyond the view", () => {
    renderCurve({ top: 1_500, draw: 100 });
    expect(screen.getByText("Pension Credit starts to fall")).toBeInTheDocument();
    expect(screen.queryByText("Pension Credit ends")).not.toBeInTheDocument();
  });

  it("describes the curve for screen readers", () => {
    renderCurve();
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Money to spend by amount drawn, from £12,000 with no draw to £19,100 with a draw of £10,000.",
    );
  });

  it("sets the draw where the pointer lands, to the nearest step", () => {
    const onDraw = renderCurve();
    fireEvent.pointerDown(sizedSurface(), { clientX: 351, pointerId: 1 });
    expect(onDraw).toHaveBeenCalledWith(5_000);
  });

  it("follows a drag and stops when released", () => {
    const onDraw = renderCurve();
    const surface = sizedSurface();
    fireEvent.pointerDown(surface, { clientX: 100, pointerId: 1 });
    fireEvent.pointerMove(surface, { clientX: 225, pointerId: 1 });
    expect(onDraw).toHaveBeenLastCalledWith(2_500);
    fireEvent.pointerUp(surface, { pointerId: 1 });
    onDraw.mockClear();
    fireEvent.pointerMove(surface, { clientX: 400, pointerId: 1 });
    expect(onDraw).not.toHaveBeenCalled();
  });

  it("keeps the draw inside the view at the edges", () => {
    const onDraw = renderCurve({ top: 9_980 });
    const surface = sizedSurface();
    fireEvent.pointerDown(surface, { clientX: 900, pointerId: 1 });
    expect(onDraw).toHaveBeenLastCalledWith(9_980);
    fireEvent.pointerMove(surface, { clientX: 0, pointerId: 1 });
    expect(onDraw).toHaveBeenLastCalledWith(0);
  });

  it("shows the figures under the pointer and clears them on leaving", () => {
    renderCurve();
    const surface = sizedSurface();
    // Hovering over £1,000 lands exactly on a sweep row.
    fireEvent.pointerMove(surface, { clientX: 150, pointerId: 1 });
    expect(screen.getByText("Draw £1,000")).toBeInTheDocument();
    expect(screen.getByText("£12,000 to spend")).toBeInTheDocument();
    expect(screen.getByText("£1,000 Pension Credit")).toBeInTheDocument();
    fireEvent.pointerLeave(surface, { pointerId: 1 });
    expect(screen.queryByText("Draw £1,000")).not.toBeInTheDocument();
  });
});
