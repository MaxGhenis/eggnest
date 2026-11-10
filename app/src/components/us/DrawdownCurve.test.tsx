import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { USDrawdownMarker, USDrawdownOutcome } from "../../lib/api-us-drawdown";
import { DrawdownCurve } from "./DrawdownCurve";

function row(draw: number, snap: number, tax = 0, surcharge = 0): USDrawdownOutcome {
  return {
    draw,
    taxable_draw: draw,
    federal_income_tax: tax,
    state_income_tax: 0,
    other_taxes: 0,
    benefits: snap,
    benefits_by_program: { snap },
    taxable_social_security: 0,
    medicare_income: 10_000 + draw,
    later_medicare_surcharge: surcharge,
    money_to_spend: 10_000 + draw + snap - tax,
  };
}

const SWEEP = [
  row(0, 2_000),
  row(1_000, 1_000),
  row(2_000, 0),
  row(5_000, 0, 150),
  row(10_000, 0, 900, 1_148.4),
];

// SNAP and Medicaid end at the same draw, so their keys must still differ.
const MARKERS: USDrawdownMarker[] = [
  { kind: "benefit_ends", draw: 2_000, program: "snap", amount: null },
  { kind: "coverage_ends", draw: 2_000, program: "medicaid", amount: null },
  { kind: "medicare_surcharge_step", draw: 8_000, program: null, amount: 1_148.4 },
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

afterEach(() => vi.restoreAllMocks());

describe("DrawdownCurve", () => {
  it("makes the axis a labelled slider with the draw in dollars", () => {
    const onDraw = renderCurve();
    const slider = screen.getByRole("slider", { name: "Amount to draw" });
    expect(slider).toHaveAttribute("aria-valuetext", "$2,000");
    expect(slider).toHaveAttribute("max", "10000");
    fireEvent.change(slider, { target: { value: "3500" } });
    expect(onDraw).toHaveBeenCalledWith(3_500);
  });

  it("names the series and every turning point, two at one draw included", () => {
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    renderCurve();
    for (const label of [
      "Money to spend",
      "If you kept every dollar",
      "Extra tax",
      "Benefits you lose",
      "SNAP ends",
      "Medicaid ends",
      "2028 Medicare premiums up $1,148",
      "Amount you draw in 2026",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(errors).not.toHaveBeenCalled();
  });

  it("drops the tax and benefit bands when nothing goes to either", () => {
    renderCurve({ sweep: [row(0, 0), row(5_000, 0)], top: 5_000, markers: [], draw: 0 });
    expect(screen.queryByText("Extra tax")).not.toBeInTheDocument();
    expect(screen.queryByText("Benefits you lose")).not.toBeInTheDocument();
  });

  it("describes the curve for screen readers", () => {
    renderCurve();
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Money to spend at each amount you draw, from $12,000 with no draw to $19,100 with a draw of $10,000.",
    );
  });

  it("shows tax, benefits and any later Medicare surcharge under the pointer", () => {
    renderCurve();
    const surface = sizedSurface();
    fireEvent.pointerMove(surface, { clientX: 150, pointerId: 1 });
    expect(screen.getByText("Draw $1,000")).toBeInTheDocument();
    expect(screen.getByText("$12,000 to spend")).toBeInTheDocument();
    expect(screen.getByText("$0 tax")).toBeInTheDocument();
    expect(screen.getByText("$1,000 benefits")).toBeInTheDocument();
    expect(screen.queryByText(/more for Medicare/)).not.toBeInTheDocument();

    fireEvent.pointerMove(surface, { clientX: 600, pointerId: 1 });
    expect(screen.getByText("$19,100 to spend")).toBeInTheDocument();
    expect(screen.getByText("$900 tax")).toBeInTheDocument();
    expect(screen.getByText("$1,148 more for Medicare in 2028")).toBeInTheDocument();
  });

  it("sets the draw where the pointer lands", () => {
    const onDraw = renderCurve();
    fireEvent.pointerDown(sizedSurface(), { clientX: 351, pointerId: 1 });
    expect(onDraw).toHaveBeenCalledWith(5_000);
  });
});
