import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DrawdownBand, DrawdownOutcome } from "../../lib/api-uk-drawdown";
import { PoundLadder } from "./PoundLadder";
import { PoundSplitBar, PoundSplitLegend } from "./PoundSplitBar";

function band(
  draw_from: number,
  draw_to: number,
  to_tax = 0,
  to_pension_credit = 0,
  jump = false,
): DrawdownBand {
  return {
    draw_from,
    draw_to,
    kept: 1 - to_tax - to_pension_credit,
    to_tax,
    to_pension_credit,
    jump,
  };
}

function outcome(draw: number, income_tax: number, pension_credit = 0): DrawdownOutcome {
  return {
    draw,
    taxable_draw: draw * 0.75,
    income_tax,
    employee_ni: 0,
    pension_credit,
    money_to_spend: 9_360 + draw + pension_credit - income_tax,
  };
}

const BANDS = [band(0, 800), band(800, 3_016, 0, 1), band(3_016, 4_280), band(4_280, 10_000, 0.15)];
const SWEEP = [
  outcome(0, 0, 2_216),
  outcome(800, 0, 2_216),
  outcome(3_016, 0),
  outcome(4_280, 0),
  outcome(10_000, 858),
];

function rows() {
  return screen.getAllByRole("listitem").filter((item) => item.closest("ol"));
}

describe("PoundLadder", () => {
  it("lists each range with what happens to the next pound", () => {
    render(<PoundLadder bands={BANDS} sweep={SWEEP} draw={2_500} balance={10_000} />);
    const rows = screen.getAllByRole("listitem").filter((item) => item.closest("ol"));
    expect(rows).toHaveLength(4);
    expect(within(rows[0]).getByText("Up to £800")).toBeInTheDocument();
    expect(within(rows[1]).getByText("£800 to £3,016")).toBeInTheDocument();
    expect(within(rows[1]).getByText("You keep nothing: you lose 100p of Pension Credit.")).toBeInTheDocument();
    expect(within(rows[3]).getByText("You keep 85p and pay 15p in tax.")).toBeInTheDocument();
  });

  it("shows a jump the API marks as a step, not as a split pound", () => {
    // R3: the Personal Savings Allowance falls from £1,000 to £500 at £770.00
    // (ITA 2007 s.12B), and income tax rises by £100 in that penny.
    const sweep = [outcome(0, 0), outcome(770, 154), outcome(770.01, 254), outcome(1_770, 454)];
    const bands = [band(0, 770, 0.2), band(770, 770.01, 10_000, 0, true), band(770.01, 1_770, 0.2)];
    render(<PoundLadder bands={bands} sweep={sweep} draw={500} balance={1_770} />);
    const items = rows();
    expect(items).toHaveLength(3);
    expect(within(items[1]).getByText("At £770")).toBeInTheDocument();
    expect(within(items[1]).getByText("Your tax rises by £100 all at once.")).toBeInTheDocument();
    expect(within(items[1]).queryByRole("img")).not.toBeInTheDocument();
    expect(within(items[0]).getByText("You keep 80p and pay 20p in tax.")).toBeInTheDocument();
  });

  it("marks the band the draw sits in", () => {
    render(<PoundLadder bands={BANDS} sweep={SWEEP} draw={2_500} balance={10_000} />);
    const current = screen.getByText("Your draw sits here").closest("li");
    expect(current).toHaveAttribute("aria-current", "true");
    expect(within(current as HTMLElement).getByText("£800 to £3,016")).toBeInTheDocument();
  });

  it("marks the last band at the very top of the pot", () => {
    render(<PoundLadder bands={BANDS} sweep={SWEEP} draw={10_000} balance={10_000} />);
    const current = screen.getByText("Your draw sits here").closest("li");
    expect(within(current as HTMLElement).getByText("£4,280 to £10,000")).toBeInTheDocument();
  });

  it("leaves Pension Credit out of the legend when none is lost", () => {
    render(<PoundLadder bands={[band(0, 10_000, 0.15)]} sweep={[outcome(0, 0), outcome(10_000, 1_500)]} draw={0} balance={10_000} />);
    expect(screen.queryByText("Pension Credit lost")).not.toBeInTheDocument();
  });
});

describe("PoundSplitBar", () => {
  it("names the split for screen readers and draws only what applies", () => {
    render(<PoundSplitBar split={{ kept: 48, tax: 0, lost: 52 }} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("48p you keep, 52p Pension Credit lost");
    expect(screen.getByText("48p")).toHaveStyle({ width: "48%" });
    expect(screen.getByText("52p")).toHaveStyle({ width: "52%" });
  });

  it("scales a pound that also gains Pension Credit to fill the bar", () => {
    render(<PoundSplitBar split={{ kept: 108, tax: 0, lost: -8 }} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("108p you keep");
    expect(screen.getByText("108p")).toHaveStyle({ width: "100%" });
  });

  it("drops the printed pence when a segment is too narrow to hold it", () => {
    render(<PoundSplitBar split={{ kept: 95, tax: 5, lost: 0 }} />);
    expect(screen.getByText("95p")).toBeInTheDocument();
    expect(screen.queryByText("5p")).not.toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName("95p you keep, 5p income tax");
  });
});

describe("PoundSplitLegend", () => {
  it("adds Pension Credit only when asked", () => {
    const { rerender } = render(<PoundSplitLegend showLost={false} />);
    expect(screen.queryByText("Pension Credit lost")).not.toBeInTheDocument();
    rerender(<PoundSplitLegend showLost />);
    expect(screen.getByText("Pension Credit lost")).toBeInTheDocument();
  });
});
