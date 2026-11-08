import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import recorded from "../../test/fixtures/uk-drawdown-recorded.json";
import type { UKDrawdownRun, UKDrawdownYearInput } from "../../lib/api-uk-drawdown";
import { runUKDrawdownYear } from "../../lib/api-uk-drawdown";
import UKDrawdownPage from "./page";

vi.mock("../../lib/api-uk-drawdown", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api-uk-drawdown")>()),
  runUKDrawdownYear: vi.fn(),
}));

const runMock = vi.mocked(runUKDrawdownYear);

/** A real-engine run recorded for the page's example inputs. */
function exampleRun(): UKDrawdownRun {
  const { envelope } = recorded.example;
  return {
    result: envelope.outputs.uk_drawdown_year_result as unknown as UKDrawdownRun["result"],
    caveats: envelope.caveats,
    sources: envelope.sources,
  };
}

const HEADLINE =
  "Draw £2,500 from your pension pot in 2026/27 and you’ll have £12,376 to spend.";

async function openPage() {
  render(<UKDrawdownPage />);
  await screen.findByText(HEADLINE, undefined, { timeout: 3_000 });
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
      screen.getByText("Draw £3,000 from your pension pot in 2026/27 and you’ll have £12,376 to spend."),
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

    edit("State Pension", "12547.60");
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

  it("explains an under-age pension draw without calling the API", async () => {
    await openPage();
    runMock.mockClear();
    fireEvent.change(screen.getByLabelText("Date of birth"), { target: { value: "1975-01-01" } });
    expect(screen.getByRole("alert")).toHaveTextContent("You can’t draw from a pension pot before age 55.");
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

  it("offers a retry when the API fails", async () => {
    runMock.mockRejectedValueOnce(new Error("network down"));
    render(<UKDrawdownPage />);
    expect(await screen.findByRole("alert", undefined, { timeout: 3_000 })).toHaveTextContent(
      "We couldn’t work this out. Check your connection and try again.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(HEADLINE)).toBeInTheDocument();
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

  it("asks for a balance when the chosen source holds nothing", async () => {
    await openPage();
    fireEvent.click(screen.getByRole("radio", { name: "Cash" }));
    expect(
      await screen.findByText("Enter how much you have in your cash savings to see what you’d keep."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("slider")).not.toBeInTheDocument();
  });
});
