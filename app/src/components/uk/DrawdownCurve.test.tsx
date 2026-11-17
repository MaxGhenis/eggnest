import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { DrawdownBand, DrawdownMarker, DrawdownOutcome } from "../../lib/api-uk-drawdown";
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
      "Money to spend at each amount you draw, from £12,000 with no draw to £19,100 with a draw of £10,000.",
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

  it("says where a jump falls under the pointer, not a figure", () => {
    // page2: the API places the UK's income tax jumps to the penny, so no
    // pointer lands inside one; this stand-in band places a £101 jump only
    // within £770 to £775, as a wider band would.
    const band = (draw_from: number, draw_to: number, to_tax: number, jump = false): DrawdownBand => ({
      draw_from,
      draw_to,
      kept: 1 - to_tax,
      to_tax,
      to_pension_credit: 0,
      jump,
    });
    renderCurve({
      sweep: [row(0, 0), row(770, 0, 154), row(775, 0, 255), row(1_770, 0, 455)],
      bands: [band(0, 770, 0.2), band(770, 775, 20.2, true), band(775, 1_770, 0.2)],
      top: 1_770,
      step: 1,
      markers: [],
      draw: 0,
    });
    const surface = sizedSurface();
    // 773 of 1,770 across the plot's 500 px.
    fireEvent.pointerMove(surface, { clientX: 100 + (500 * 773) / 1_770, pointerId: 1 });
    expect(screen.getByText("Draw £773")).toBeInTheDocument();
    expect(screen.getByText("Between £770 and £775")).toBeInTheDocument();
    expect(screen.getByText("Your tax rises by £101 all at once.")).toBeInTheDocument();
    expect(screen.queryByText(/^£[\d,]+ to spend$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^£[\d,]+ Pension Credit$/)).not.toBeInTheDocument();
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
