import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DrawdownChart, type ChartMarker } from "./DrawdownChart";

// Invariants these tests hold for both pages' charts:
// - On a phone the draw moves on a horizontal drag or a tap, never on a
//   vertical pan, and a cancelled or lost pointer ends the drag (uk-page-14,
//   us-page-5).
// - The slider's keys reach the top of the range, the balance itself
//   (uk-page-18a).
// - Every marker label sits inside the chart (us-page-6).
// - Under the pointer, inside a jump the API holds no row for, the tooltip
//   says what changes there and between which draws, never a figure the
//   engine may not give, and the chart marks no point on the curve there
//   (us-page-2, page2). Elsewhere it shows the figures at the draw.

interface Row {
  draw: number;
  money_to_spend: number;
  tax: number;
}

const row = (draw: number, money: number, tax = 0): Row => ({ draw, money_to_spend: money, tax });
const SWEEP = [row(0, 10_000), row(1_000, 11_000), row(2_000, 12_000), row(10_000, 19_000, 1_000)];
const LABELS = {
  reference: "If you kept every pound",
  tax: "Extra tax",
  lost: "Lost",
  axis: "Amount you draw",
  slider: "Amount to draw",
};

function renderChart(overrides: Partial<Parameters<typeof DrawdownChart<Row>>[0]> = {}) {
  const onDraw = vi.fn();
  render(
    <DrawdownChart<Row>
      sweep={SWEEP}
      draw={2_000}
      top={10_000}
      step={50}
      markers={[]}
      onDraw={onDraw}
      taxAbove={(r, none) => r.tax - none.tax}
      lostAt={() => 0}
      details={(r) => [`£${r.tax} tax`]}
      describeStep={(from, to) => `Tax rises by £${to.tax - from.tax} all at once.`}
      money={(value) => `£${Math.round(value).toLocaleString("en-GB")}`}
      compact={(value) => `£${value}`}
      labels={LABELS}
      {...overrides}
    />,
  );
  return onDraw;
}

/** jsdom lays nothing out: the plot spans x = 100 to 600. */
function surface(): Element {
  const element = screen.getByTestId("curve-surface");
  element.getBoundingClientRect = () =>
    ({ left: 100, width: 500, top: 0, right: 600, bottom: 300, height: 300 }) as DOMRect;
  return element;
}

const touch = { pointerId: 7, pointerType: "touch" };

describe("DrawdownChart pointer", () => {
  it("leaves the draw alone when a thumb lands to scroll the page", () => {
    // us-page-5: pointerdown set the draw before the browser took the pan and
    // sent pointercancel, and the drag then outlived the cancel.
    const onDraw = renderChart();
    const plot = surface();
    fireEvent.pointerDown(plot, { ...touch, clientX: 200, clientY: 100 });
    fireEvent.pointerCancel(plot, touch);
    expect(onDraw).not.toHaveBeenCalled();
    fireEvent.pointerMove(plot, { pointerId: 1, pointerType: "mouse", clientX: 400, buttons: 0 });
    expect(onDraw).not.toHaveBeenCalled();
  });

  it("ignores a vertical pan, even one the browser never cancels", () => {
    const onDraw = renderChart();
    const plot = surface();
    fireEvent.pointerDown(plot, { ...touch, clientX: 200, clientY: 100 });
    fireEvent.pointerMove(plot, { ...touch, clientX: 203, clientY: 140 });
    fireEvent.pointerMove(plot, { ...touch, clientX: 260, clientY: 150 });
    fireEvent.pointerUp(plot, { ...touch, clientX: 260, clientY: 150 });
    expect(onDraw).not.toHaveBeenCalled();
  });

  it("follows a horizontal drag on a touch screen", () => {
    const onDraw = renderChart();
    const plot = surface();
    fireEvent.pointerDown(plot, { ...touch, clientX: 200, clientY: 100 });
    fireEvent.pointerMove(plot, { ...touch, clientX: 204, clientY: 101 });
    expect(onDraw).not.toHaveBeenCalled();
    fireEvent.pointerMove(plot, { ...touch, clientX: 225, clientY: 102 });
    expect(onDraw).toHaveBeenLastCalledWith(2_500);
    fireEvent.pointerMove(plot, { ...touch, clientX: 350, clientY: 120 });
    expect(onDraw).toHaveBeenLastCalledWith(5_000);
    fireEvent.pointerUp(plot, { ...touch, clientX: 350, clientY: 120 });
    onDraw.mockClear();
    fireEvent.pointerMove(plot, { ...touch, clientX: 500, clientY: 120 });
    expect(onDraw).not.toHaveBeenCalled();
  });

  it("sets the draw where a tap lands", () => {
    const onDraw = renderChart();
    const plot = surface();
    fireEvent.pointerDown(plot, { ...touch, clientX: 351, clientY: 100 });
    expect(onDraw).not.toHaveBeenCalled();
    fireEvent.pointerUp(plot, { ...touch, clientX: 351, clientY: 103 });
    expect(onDraw).toHaveBeenCalledTimes(1);
    expect(onDraw).toHaveBeenCalledWith(5_000);
  });

  it("ends a drag when the pointer is lost or a mouse button is up", () => {
    const onDraw = renderChart();
    const plot = surface();
    fireEvent.pointerDown(plot, { pointerId: 1, pointerType: "mouse", clientX: 100, buttons: 1 });
    expect(onDraw).toHaveBeenLastCalledWith(0);
    fireEvent(plot, new PointerEvent("lostpointercapture", { pointerId: 1, bubbles: true }));
    onDraw.mockClear();
    fireEvent.pointerMove(plot, { pointerId: 1, pointerType: "mouse", clientX: 400, buttons: 1 });
    expect(onDraw).not.toHaveBeenCalled();

    fireEvent.pointerDown(plot, { pointerId: 2, pointerType: "mouse", clientX: 100, buttons: 1 });
    onDraw.mockClear();
    fireEvent.pointerMove(plot, { pointerId: 2, pointerType: "mouse", clientX: 400, buttons: 0 });
    expect(onDraw).not.toHaveBeenCalled();
  });
});

describe("DrawdownChart slider", () => {
  it("reaches the balance from the keyboard", () => {
    // uk-page-18a: a pot of £10,025 on £50 steps stopped the keys at £10,000.
    const onDraw = renderChart({ top: 10_025, draw: 10_000 });
    const slider = screen.getByRole("slider", { name: "Amount to draw" });
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    expect(onDraw).toHaveBeenLastCalledWith(10_025);
    fireEvent.keyDown(slider, { key: "End" });
    expect(onDraw).toHaveBeenLastCalledWith(10_025);
    fireEvent.keyDown(slider, { key: "ArrowLeft" });
    expect(onDraw).toHaveBeenLastCalledWith(9_950);
  });
});

describe("DrawdownChart markers", () => {
  const original = globalThis.ResizeObserver;
  afterEach(() => {
    globalThis.ResizeObserver = original;
    vi.restoreAllMocks();
  });

  it("keeps a long label inside a phone-width chart", () => {
    // us-page-6: the 62% rule put this label 27 to 42 px past a 288 px chart.
    globalThis.ResizeObserver = class {
      observe() {}
      disconnect() {}
      unobserve() {}
    } as unknown as typeof ResizeObserver;
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      width: 288,
    } as DOMRect);
    const markers: ChartMarker[] = [
      { key: "msp", draw: 3_700, label: "Medicare Savings Program ends" },
      { key: "acp", draw: 9_000, label: "Affordable Connectivity Program ends" },
    ];
    renderChart({ markers });
    const svg = document.querySelector("svg")!;
    expect(svg.getAttribute("width")).toBe("288");
    for (const marker of markers) {
      const text = screen.getByText(marker.label) as unknown as SVGTextElement;
      const x = Number(text.getAttribute("x"));
      const width = marker.label.length * 6.6;
      const left = text.getAttribute("text-anchor") === "end" ? x - width : x;
      expect(left).toBeGreaterThanOrEqual(0);
      expect(left + width).toBeLessThanOrEqual(288);
    }
  });

  it("uses the label's measured length once the browser lays it out", () => {
    // A resize observer reports on its first look, after layout.
    globalThis.ResizeObserver = class {
      constructor(private readonly report: (entries: unknown[]) => void) {}
      observe() {
        this.report([{ contentRect: { width: 640 } }]);
      }
      disconnect() {}
      unobserve() {}
    } as unknown as typeof ResizeObserver;
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      width: 640,
    } as DOMRect);
    const measure = vi.fn(() => 300);
    (SVGElement.prototype as unknown as { getComputedTextLength: () => number }).getComputedTextLength =
      measure;
    try {
      renderChart({ markers: [{ key: "a", draw: 9_000, label: "Short" }] });
      const text = screen.getByText("Short");
      // 300 px fits only left of a line near the right end of a 640 px chart.
      expect(text.getAttribute("text-anchor")).toBe("end");
      expect(measure).toHaveBeenCalled();
    } finally {
      delete (SVGElement.prototype as unknown as { getComputedTextLength?: () => number })
        .getComputedTextLength;
    }
  });
});

describe("DrawdownChart tooltip", () => {
  it("says where a located jump falls, not a figure the engine may not give", () => {
    // us-page-2, page2: at $7,300, inside the SNAP jump the API places only
    // between $7,291.67 and $7,302.08, the tooltip read £31,370 to spend where
    // the engine gives £31,586.
    const sweep = [
      row(0, 24_000),
      row(7_291.67, 31_577.67),
      row(7_302.08, 31_372.08, 216),
      row(10_000, 34_070, 216),
    ];
    renderChart({
      sweep,
      top: 10_000,
      bands: [
        { draw_from: 0, draw_to: 7_291.67, jump: false },
        { draw_from: 7_291.67, draw_to: 7_302.08, jump: true },
        { draw_from: 7_302.08, draw_to: 10_000, jump: false },
      ],
      step: 1,
    });
    const plot = surface();
    fireEvent.pointerMove(plot, { pointerId: 1, pointerType: "mouse", clientX: 465, buttons: 0 });
    expect(screen.getByText("Draw £7,300")).toBeInTheDocument();
    expect(screen.getByText("Between £7,292 and £7,302")).toBeInTheDocument();
    expect(screen.getByText("Tax rises by £216 all at once.")).toBeInTheDocument();
    expect(screen.queryByText(/^£[\d,]+ to spend$/)).not.toBeInTheDocument();
    expect(screen.queryByText("£0 tax")).not.toBeInTheDocument();
    expect(screen.queryByTestId("hover-point")).not.toBeInTheDocument();

    // Outside the jump, the figures at the draw.
    fireEvent.pointerMove(plot, { pointerId: 1, pointerType: "mouse", clientX: 500, buttons: 0 });
    expect(screen.getByText("Draw £8,000")).toBeInTheDocument();
    expect(screen.getByText("£32,070 to spend")).toBeInTheDocument();
    expect(screen.getByText("£216 tax")).toBeInTheDocument();
    expect(screen.queryByText("Between £7,292 and £7,302")).not.toBeInTheDocument();
    expect(screen.getByTestId("hover-point")).toBeInTheDocument();
  });

  it("shows the API's own row at a band's end", () => {
    const sweep = [row(0, 24_000), row(7_300, 31_300), row(7_310, 31_094, 216), row(10_000, 33_784, 216)];
    renderChart({
      sweep,
      top: 10_000,
      bands: [
        { draw_from: 0, draw_to: 7_300, jump: false },
        { draw_from: 7_300, draw_to: 7_310, jump: true },
        { draw_from: 7_310, draw_to: 10_000, jump: false },
      ],
      step: 1,
    });
    fireEvent.pointerMove(surface(), { pointerId: 1, pointerType: "mouse", clientX: 465, buttons: 0 });
    expect(screen.getByText("£31,300 to spend")).toBeInTheDocument();
    expect(screen.queryByText(/^Between/)).not.toBeInTheDocument();
  });
});
