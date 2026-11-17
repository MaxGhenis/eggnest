import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import recorded from "../../test/fixtures/uk-drawdown-recorded.json";
import type {
  DrawdownBand,
  DrawdownOutcome,
  UKDrawdownRun,
  UKDrawdownYearInput,
} from "../../lib/api-uk-drawdown";
import { NetworkError, SimulationError } from "../../lib/api";
import { runUKDrawdownYear } from "../../lib/api-uk-drawdown";
import { pounds } from "../../lib/uk-drawdown";
import UKDrawdownPage from "./page";

vi.mock("../../lib/api-uk-drawdown", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api-uk-drawdown")>()),
  runUKDrawdownYear: vi.fn(),
}));

const runMock = vi.mocked(runUKDrawdownYear);

/** A real-engine run recorded for the page's example inputs, or another scenario. */
function exampleRun(name: keyof typeof recorded = "example"): UKDrawdownRun {
  const { envelope } = recorded[name];
  return {
    result: envelope.outputs.uk_drawdown_year_result as unknown as UKDrawdownRun["result"],
    caveats: envelope.caveats,
    sources: envelope.sources,
  };
}

/**
 * A stand-in for a run with a jump at the top of its sweep: the run with its
 * last interval marked as a jump, its rates read off that interval's rows.
 */
function withJumpAtTop(run: UKDrawdownRun): UKDrawdownRun {
  const { sweep, bands } = run.result;
  const [a, b] = sweep.slice(-2);
  const width = b.draw - a.draw;
  const tax = (row: DrawdownOutcome) => row.income_tax + row.employee_ni;
  const last = bands[bands.length - 1];
  const jump: DrawdownBand = {
    draw_from: a.draw,
    draw_to: b.draw,
    kept: (b.money_to_spend - a.money_to_spend) / width,
    to_tax: (tax(b) - tax(a)) / width,
    to_pension_credit: (a.pension_credit - b.pension_credit) / width,
    jump: true,
  };
  const before = last.draw_from < a.draw ? [{ ...last, draw_to: a.draw }] : [];
  return { ...run, result: { ...run.result, bands: [...bands.slice(0, -1), ...before, jump] } };
}

/** Each ledger line's amount in the chosen draw's column, a deduction below zero. */
function chosenColumn(table: HTMLElement): Map<string, number> {
  const column = new Map<string, number>();
  for (const row of table.querySelectorAll("tbody tr, tfoot tr")) {
    const label = row.querySelector("th")!.textContent!;
    const text = row.querySelectorAll("td")[1].textContent!;
    column.set(label, (text.startsWith("−") ? -1 : 1) * Number(text.replace(/[^0-9.]/g, "")));
  }
  return column;
}

/** The page's visible text, not the screen-reader announcement of the API's answer. */
const SHOWN = { ignore: "script, style, [role=status]" };

const HEADLINE =
  "Draw £2,500 from your pension pot in 2026/27 and you’ll have £12,376 to spend.";

async function openPage() {
  render(<UKDrawdownPage />);
  await screen.findByText(HEADLINE, SHOWN, { timeout: 3_000 });
}

function lastInputs(): UKDrawdownYearInput {
  return runMock.mock.calls[runMock.mock.calls.length - 1][0];
}

/** Waits past the debounce so any request the page would send has gone. */
function debounceSettles() {
  return act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 450));
  });
}

function edit(label: string, value: string) {
  const field = screen.getByLabelText(label);
  fireEvent.focus(field);
  fireEvent.change(field, { target: { value } });
  fireEvent.blur(field);
}

describe("UKDrawdownPage", () => {
  beforeEach(() => {
    runMock.mockReset();
    runMock.mockImplementation(async () => exampleRun());
  });

  it("calculates the example and says it is one", async () => {
    await openPage();
    expect(screen.getByText(/These figures describe an example person/)).toBeInTheDocument();
    expect(runMock).toHaveBeenCalledTimes(1);
    expect(
      screen.getByText("You’d have £800 more to spend than if you drew nothing, after losing £1,700 of Pension Credit."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Your next £1,000" })).toBeInTheDocument();
    expect(screen.getByText("Draw another £1,000 and you keep £484: you lose £516 of Pension Credit.")).toBeInTheDocument();
  });

  it("shows the year's accounts with no draw and the chosen draw", async () => {
    await openPage();
    const rowText = (name: string) => screen.getByRole("row", { name: new RegExp(`^${name}`) }).textContent;
    expect(rowText("Pension Credit £")).toContain("£2,216");
    expect(rowText("Pension Credit £")).toContain("£516");
    expect(rowText("Money to spend")).toContain("£11,576");
    expect(rowText("Money to spend")).toContain("£12,376");
  });

  it("works through what Pension Credit counts, ending on the weekly amount", async () => {
    await openPage();
    expect(screen.getByRole("row", { name: "Regular withdrawals from your pot £48.08" })).toBeInTheDocument();
    expect(
      screen.getByRole("row", { name: "Minimum guarantee, which Pension Credit tops you up to £238.00" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("row", { name: "Pension Credit each week, on average £9.92" })).toBeInTheDocument();
  });

  it("lists what it leaves out and links its sources", async () => {
    await openPage();
    expect(screen.getByText(/educational estimates/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Axiom rules engine" })).toHaveAttribute(
      "href",
      "https://github.com/TheAxiomFoundation/axiom-rules-engine",
    );
    expect(screen.getByRole("heading", { name: "Pension Credit", level: 3 })).toBeInTheDocument();
  });

  it("moves the result at once and asks the API only when the slider settles", async () => {
    await openPage();
    runMock.mockClear();
    const slider = screen.getByRole("slider", { name: "Amount to draw in the tax year" });

    fireEvent.change(slider, { target: { value: "1000" } });
    fireEvent.change(slider, { target: { value: "3000" } });

    // £3,000 sits on the sweep, so the preview needs no second request.
    expect(
      screen.getByText("Draw £3,000 from your pension pot in 2026/27 and you’ll have £12,376 to spend.", SHOWN),
    ).toBeInTheDocument();
    expect(runMock).not.toHaveBeenCalled();

    await waitFor(() => expect(runMock).toHaveBeenCalledTimes(1));
    expect(lastInputs().draw_amount).toBe(3_000);
  });

  it("keeps the example banner for a new draw and drops it for new figures", async () => {
    await openPage();
    fireEvent.change(screen.getByRole("slider", { name: "Amount to draw in the tax year" }), {
      target: { value: "1000" },
    });
    expect(screen.getByText(/These figures describe an example person/)).toBeInTheDocument();

    edit("State Pension, yearly rate", "12547.60");
    expect(screen.queryByText(/These figures describe an example person/)).not.toBeInTheDocument();
  });

  it("dims the old result while a changed figure recalculates", async () => {
    await openPage();
    edit("Other pensions and annuities", "5000");
    expect(document.querySelector("[aria-busy=true]")).not.toBeNull();
  });

  it("never draws more than the pot holds", async () => {
    await openPage();
    runMock.mockClear();
    edit("Amount to draw in 2026/27", "50000");
    await waitFor(() => expect(runMock).toHaveBeenCalled());
    expect(lastInputs().draw_amount).toBe(10_000);
  });

  it("says beside the draw field that the draw stops at the pot", async () => {
    // uk-page-02: the field kept £50,000 while the page worked out £10,000,
    // and raising the pot later revived the hidden figure.
    await openPage();
    edit("Amount to draw in 2026/27", "50000");
    const note = screen.getByText(
      "You can draw up to £10,000 from your pension pot, so we use £10,000.",
    );
    expect(
      screen.getByLabelText("Amount to draw in 2026/27").getAttribute("aria-describedby")?.split(" "),
    ).toContain(note.id);

    edit("Pension pots", "100000");
    expect(screen.queryByText(/You can draw up to/)).not.toBeInTheDocument();
    await waitFor(() => expect(lastInputs().draw_amount).toBe(50_000));
  });

  it("dims the result for a draw past the sweep's top until the API answers", async () => {
    // uk-page-03: a draw past the last row showed that row's figures under the
    // new draw's headline, undimmed. The API's sweep can stop short of a large
    // pot, as this one does at £180,000 of £400,000.
    const large = exampleRun("large_pot");
    const short = {
      ...large,
      result: { ...large.result, sweep: large.result.sweep.filter((row) => row.draw <= 180_000) },
    };
    await openPage();
    runMock.mockImplementation(async () => short);
    edit("Pension pots", "400000");
    await waitFor(() => expect(lastInputs().sipp_balance).toBe(400_000));
    await waitFor(() =>
      expect(
        screen.getByText(/^Draw £2,500 from your pension pot/, SHOWN).closest("[aria-busy]"),
      ).toHaveAttribute("aria-busy", "false"),
    );

    let answer: (run: UKDrawdownRun) => void = () => {};
    runMock.mockImplementation(() => new Promise((resolve) => (answer = resolve)));
    edit("Amount to draw in 2026/27", "300000");
    const headline = screen.getByText(/^Draw £300,000 from your pension pot/, SHOWN);
    expect(headline.closest("[aria-busy]")).toHaveAttribute("aria-busy", "true");

    await waitFor(() => expect(lastInputs().draw_amount).toBe(300_000));
    const at = large.result.sweep.find((row) => row.draw === 300_000)!;
    await act(async () => answer({ ...large, result: { ...large.result, at_chosen_draw: at } }));
    expect(
      screen.getByText(/^Draw £300,000 from your pension pot/, SHOWN).closest("[aria-busy]"),
    ).toHaveAttribute("aria-busy", "false");
  });

  it("adds up the year at a draw inside a jump at the sweep's top, and dims it", async () => {
    // page2: inside a jump on the sweep's last interval, a draw nearer the top
    // showed the top row's tax and money to spend beside the new draw, so the
    // ledger no longer added up. No recorded run has a jump at either end:
    // this stand-in marks the example's last interval, £9,950 to £10,000, as one.
    runMock.mockImplementation(async () => withJumpAtTop(exampleRun()));
    await openPage();
    runMock.mockImplementation(() => new Promise(() => {}));
    edit("Amount to draw in 2026/27", "9990");
    const table = screen.getByRole("table", {
      name: "Your tax year with no draw and with your chosen draw",
    });
    const column = chosenColumn(table);
    expect(column.get("Money you draw")).toBe(9_990);
    const { "Money to spend": spend, ...lines } = Object.fromEntries(column);
    const sum = Object.values(lines).reduce((total, value) => total + value, 0);
    // Each line rounds to the pound, so the sum can miss by a pound or two.
    expect(Math.abs(sum - spend)).toBeLessThanOrEqual(2);
    expect(table.closest("[aria-busy]")).toHaveAttribute("aria-busy", "true");
  });

  it("dims the weekly working until the API answers for the new draw", async () => {
    // uk-page-06: the working showed the old draw's weekly figures under the
    // new draw's headline.
    await openPage();
    runMock.mockClear();
    let answer: (run: UKDrawdownRun) => void = () => {};
    runMock.mockImplementation(() => new Promise((resolve) => (answer = resolve)));
    fireEvent.change(screen.getByRole("slider", { name: "Amount to draw in the tax year" }), {
      target: { value: "5000" },
    });
    const working = screen.getByRole("region", { name: "What DWP counts each week" });
    expect(working).toHaveAttribute("aria-busy", "true");

    await waitFor(() => expect(runMock).toHaveBeenCalledTimes(1));
    const run = exampleRun();
    const at = run.result.sweep.find((row) => row.draw === 5_000)!;
    await act(async () => answer({ ...run, result: { ...run.result, at_chosen_draw: at } }));
    expect(screen.getByRole("region", { name: "What DWP counts each week" })).toHaveAttribute(
      "aria-busy",
      "false",
    );
  });

  it("lists only the API's own rows as turning points", async () => {
    // uk-page-09: the table read rows off a straight line, which misses the
    // engine's figures most at a band's edge.
    await openPage();
    runMock.mockClear();
    let answer: (run: UKDrawdownRun) => void = () => {};
    runMock.mockImplementation(() => new Promise((resolve) => (answer = resolve)));
    edit("Amount to draw in 2026/27", "2345");
    const drawsListed = () =>
      [
        ...(screen
          .getByText("See the turning points as a table")
          .closest("details")
          ?.querySelectorAll("tbody th") ?? []),
      ].map((cell) => cell.textContent);
    const sweep = exampleRun().result.sweep;
    expect(drawsListed()).not.toContain("£2,345");
    for (const amount of drawsListed()) {
      expect(sweep.some((row) => pounds(row.draw) === amount)).toBe(true);
    }

    await waitFor(() => expect(runMock).toHaveBeenCalledTimes(1));
    const run = exampleRun();
    const at = { ...run.result.with_no_draw, draw: 2_345 };
    const withDraw = [...sweep.filter((row) => row.draw < 2_345), at, ...sweep.filter((row) => row.draw > 2_345)];
    await act(async () =>
      answer({ ...run, result: { ...run.result, sweep: withDraw, at_chosen_draw: at } }),
    );
    expect(drawsListed()).toContain("£2,345");
  });

  it("announces the API's answer once, not each figure on the way", async () => {
    // uk-page-15: every figure typed re-announced the headline.
    await openPage();
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(HEADLINE);
    runMock.mockClear();
    let answer: (run: UKDrawdownRun) => void = () => {};
    runMock.mockImplementation(() => new Promise((resolve) => (answer = resolve)));
    const slider = screen.getByRole("slider", { name: "Amount to draw in the tax year" });
    fireEvent.change(slider, { target: { value: "1000" } });
    fireEvent.change(slider, { target: { value: "3000" } });
    expect(status).toHaveTextContent(HEADLINE);

    await waitFor(() => expect(runMock).toHaveBeenCalledTimes(1));
    const run = exampleRun();
    const at = run.result.sweep.find((row) => row.draw === 3_000)!;
    await act(async () => answer({ ...run, result: { ...run.result, at_chosen_draw: at } }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Draw £3,000 from your pension pot in 2026/27 and you’ll have £12,376 to spend.",
    );
  });

  it("explains an under-age pension draw without calling the API", async () => {
    await openPage();
    runMock.mockClear();
    fireEvent.change(screen.getByLabelText("Date of birth"), { target: { value: "1975-01-01" } });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "You can’t draw from a pension pot before age 55, and you turn 55 after this tax year ends",
    );
    await debounceSettles();
    expect(runMock).not.toHaveBeenCalled();
  });

  it("sends only the corrected figures once a problem clears", async () => {
    await openPage();
    runMock.mockClear();
    const birth = screen.getByLabelText("Date of birth");
    fireEvent.change(birth, { target: { value: "1975-01-01" } });
    await debounceSettles();

    fireEvent.change(birth, { target: { value: "1962-01-01" } });
    await debounceSettles();

    expect(runMock.mock.calls.map(([inputs]) => inputs.birth_date)).toEqual(["1962-01-01"]);
  });

  it("offers a retry when the API can't be reached", async () => {
    runMock.mockRejectedValueOnce(new NetworkError("network down"));
    render(<UKDrawdownPage />);
    expect(await screen.findByRole("alert", undefined, { timeout: 3_000 })).toHaveTextContent(
      "We couldn’t reach the calculator. Check your connection and try again.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(HEADLINE, SHOWN)).toBeInTheDocument();
  });

  it("words a server error as one, not as a connection problem", async () => {
    runMock.mockRejectedValueOnce(new SimulationError("engine failed", 500));
    render(<UKDrawdownPage />);
    expect(await screen.findByRole("alert", undefined, { timeout: 3_000 })).toHaveTextContent(
      "The calculator couldn’t work out this year. Try again, or change a figure.",
    );
  });

  it("never sends tax-free cash first with a regular draw", async () => {
    await openPage();
    fireEvent.click(screen.getByRole("radio", { name: "One-off" }));
    fireEvent.click(screen.getByRole("radio", { name: "Tax-free cash first" }));
    await waitFor(() => expect(lastInputs().sipp_tax_free_cash_first).toBe(true));
    fireEvent.click(screen.getByRole("radio", { name: "Regular" }));
    await waitFor(() => expect(lastInputs().sipp_draw_pattern).toBe("regular"));
    expect(lastInputs().sipp_tax_free_cash_first).toBe(false);
  });

  it("ignores the result of a superseded request", async () => {
    await openPage();
    const aborted: boolean[] = [];
    runMock.mockImplementation(
      (_inputs, signal) =>
        new Promise((_resolve, reject) => {
          signal?.addEventListener("abort", () => {
            aborted.push(true);
            reject(new DOMException("Aborted", "AbortError"));
          });
        }),
    );
    edit("Earnings", "100");
    await waitFor(() => expect(runMock).toHaveBeenCalledTimes(2));
    edit("Earnings", "200");
    await waitFor(() => expect(aborted).toEqual([true]));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("offers no draw from a pot that can't pay out this tax year", async () => {
    await openPage();
    runMock.mockImplementation(async () => exampleRun("locked_pot"));
    edit("Amount to draw in 2026/27", "0");
    fireEvent.change(screen.getByLabelText("Date of birth"), { target: { value: "1980-01-10" } });
    expect(
      screen.getByText(/your pension pot can’t pay you a pension or lump sum in 2026\/27/),
    ).toBeInTheDocument();
    await waitFor(() => expect(lastInputs().birth_date).toBe("1980-01-10"));
    expect(await screen.findByText(/You turn 55 on 10 January 2035/)).toBeInTheDocument();
    expect(
      screen.getByText(/You reach Pension Credit age on 10 January 2048, after this tax year, so you get no Pension Credit in 2026\/27/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("slider")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Your next/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/Draw another/)).not.toBeInTheDocument();
  });

  it("says a Pension Credit age in the year's last days falls in the year", async () => {
    // The API counts the 52 weeks from 6 April 2026 that start on or after the
    // qualifying date; the last starts on 29 March 2027. A qualifying date
    // from 30 March to 5 April 2027 counts no week but is not after the year.
    await openPage();
    runMock.mockImplementation(async () => exampleRun("pension_credit_age_in_last_days"));
    fireEvent.change(screen.getByLabelText("Date of birth"), { target: { value: "1960-09-30" } });
    await waitFor(() => expect(lastInputs().birth_date).toBe("1960-09-30"));
    expect(
      await screen.findByText(
        /You reach Pension Credit age on 30 March 2027, in 2026\/27 but after the last of the 52 weeks we count starts on 29 March 2027/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/DWP may still pay you up to a week’s credit for 2026\/27/)).toBeInTheDocument();
    expect(screen.queryByText(/after this tax year, so you get no Pension Credit/)).not.toBeInTheDocument();
  });

  it("says DWP's count of weeks turns on the payday", async () => {
    await openPage();
    runMock.mockImplementation(async () => exampleRun("reaches_state_pension_age"));
    fireEvent.change(screen.getByLabelText("Date of birth"), { target: { value: "1960-07-15" } });
    await waitFor(() => expect(lastInputs().birth_date).toBe("1960-07-15"));
    expect(
      await screen.findByText(/so we count 20 of the year’s 52 weeks\. DWP pays from your first full benefit week, which turns on your payday, so its count can be a week more or less\./),
    ).toBeInTheDocument();
  });

  it("asks for a balance when the chosen source holds nothing", async () => {
    await openPage();
    fireEvent.click(screen.getByRole("radio", { name: "Cash" }));
    expect(
      await screen.findByText("Enter how much you have in your cash savings to see what you’d keep."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("slider")).not.toBeInTheDocument();
  });
});
