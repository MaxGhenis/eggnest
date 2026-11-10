import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { USDrawdownOutcome, USDrawdownSlice } from "../../lib/api-us-drawdown";
import { DollarLadder } from "./DollarLadder";
import { DollarSplitBar, DollarSplitLegend } from "./DollarSplitBar";

function outcome(draw: number, snap: number, tax = 0): USDrawdownOutcome {
  return {
    draw,
    taxable_draw: draw,
    federal_income_tax: tax,
    state_income_tax: 0,
    other_taxes: 0,
    benefits: snap,
    benefits_by_program: { snap },
    taxable_social_security: 0,
    medicare_income: draw,
    later_medicare_surcharge: 0,
    money_to_spend: 20_000 + draw + snap - tax,
  };
}

function band(draw_from: number, draw_to: number, to_tax = 0, to_benefits = 0): USDrawdownSlice {
  return {
    draw_from,
    draw_to,
    kept: 1 - to_tax - to_benefits,
    to_tax,
    to_benefits,
    social_security_taxed: 0,
  };
}

// SNAP falls by $216 at $5,010, phases out by $6,000, then tax takes 12¢.
const SWEEP = [
  outcome(0, 291),
  outcome(5_000, 291),
  outcome(5_010, 75),
  outcome(6_000, 0),
  outcome(20_000, 0, 1_680),
];
const BANDS = [
  band(0, 5_000),
  band(5_000, 5_010, 0, 21.6),
  band(5_010, 6_000, 0, 75 / 990),
  band(6_000, 20_000, 0.12),
];

function rows() {
  return screen.getAllByRole("listitem").filter((item) => item.closest("ol"));
}

describe("DollarLadder", () => {
  it("lists each range with what happens to the next dollar, and each jump on its own", () => {
    render(<DollarLadder bands={BANDS} sweep={SWEEP} draw={5_500} balance={20_000} />);
    expect(
      screen.getByRole("heading", { name: "Where each extra dollar goes" }),
    ).toBeInTheDocument();
    const [first, jump, phaseOut, taxed] = rows();
    expect(rows()).toHaveLength(4);
    expect(within(first).getByText("Up to $5,000")).toBeInTheDocument();
    expect(within(first).getByText("You keep the whole dollar.")).toBeInTheDocument();
    expect(within(jump).getByText("At about $5,010")).toBeInTheDocument();
    expect(within(jump).getByText("SNAP falls by $216 all at once.")).toBeInTheDocument();
    expect(within(phaseOut).getByText("$5,010 to $6,000")).toBeInTheDocument();
    expect(within(phaseOut).getByText("You keep 92¢ and lose 8¢ of SNAP.")).toBeInTheDocument();
    expect(within(taxed).getByText("$6,000 to $20,000")).toBeInTheDocument();
    expect(within(taxed).getByText("You keep 88¢ and pay 12¢ in tax.")).toBeInTheDocument();
  });

  it("draws a split bar for each range but not for a jump", () => {
    render(<DollarLadder bands={BANDS} sweep={SWEEP} draw={0} balance={20_000} />);
    const [first, jump] = rows();
    expect(within(first).getByRole("img")).toHaveAccessibleName("100¢ you keep");
    expect(within(jump).queryByRole("img")).not.toBeInTheDocument();
  });

  it("marks the range the draw sits in", () => {
    render(<DollarLadder bands={BANDS} sweep={SWEEP} draw={5_500} balance={20_000} />);
    const current = screen.getByText("Your draw sits here").closest("li");
    expect(current).toHaveAttribute("aria-current", "true");
    expect(within(current as HTMLElement).getByText("$5,010 to $6,000")).toBeInTheDocument();
  });

  it("says where the sweep stops short of a large balance", () => {
    render(<DollarLadder bands={BANDS} sweep={SWEEP} draw={0} balance={2_000_000} />);
    expect(within(rows()[3]).getByText("Above $6,000")).toBeInTheDocument();
  });

  it("names benefits lost in the legend only when a range loses them", () => {
    const { unmount } = render(
      <DollarLadder bands={BANDS} sweep={SWEEP} draw={0} balance={20_000} />,
    );
    expect(screen.getByText("Benefits you lose")).toBeInTheDocument();
    unmount();

    // A jump alone draws no bar, so the legend has nothing to explain.
    const sweep = [
      outcome(0, 291),
      outcome(5_000, 291),
      outcome(5_010, 0),
      outcome(20_000, 0, 1_798.8),
    ];
    const bands = [band(0, 5_000), band(5_000, 5_010, 0, 29.1), band(5_010, 20_000, 0.12)];
    render(<DollarLadder bands={bands} sweep={sweep} draw={0} balance={20_000} />);
    expect(screen.getByText("SNAP ends, taking $291 all at once.")).toBeInTheDocument();
    expect(screen.queryByText("Benefits you lose")).not.toBeInTheDocument();
  });
});

describe("DollarSplitBar", () => {
  it("names the split for screen readers and sizes each part", () => {
    render(<DollarSplitBar split={{ kept: 55, tax: 0, lost: 45 }} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("55¢ you keep, 45¢ you lose in benefits");
    expect(screen.getByText("55¢")).toHaveStyle({ width: "55%" });
    expect(screen.getByText("45¢")).toHaveStyle({ width: "45%" });
  });

  it("scales a dollar that also gains benefits to fill the bar", () => {
    render(<DollarSplitBar split={{ kept: 108, tax: 0, lost: -8 }} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("108¢ you keep");
    expect(screen.getByText("108¢")).toHaveStyle({ width: "100%" });
  });

  it("drops the printed cents when a part is too narrow to hold them", () => {
    render(<DollarSplitBar split={{ kept: 95, tax: 5, lost: 0 }} />);
    expect(screen.queryByText("5¢")).not.toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName("95¢ you keep, 5¢ you pay in tax");
  });
});

describe("DollarSplitLegend", () => {
  it("adds benefits lost only when asked", () => {
    const { rerender } = render(<DollarSplitLegend showLost={false} />);
    expect(screen.getByText("You keep")).toBeInTheDocument();
    expect(screen.getByText("Tax")).toBeInTheDocument();
    expect(screen.queryByText("Benefits you lose")).not.toBeInTheDocument();
    rerender(<DollarSplitLegend showLost />);
    expect(screen.getByText("Benefits you lose")).toBeInTheDocument();
  });
});
