import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import recorded from "../../test/fixtures/us-drawdown-recorded.json";
import type {
  USDrawdownPerson,
  USDrawdownRun,
  USDrawdownYearInput,
} from "../../lib/api-us-drawdown";
import { runUSDrawdownYear } from "../../lib/api-us-drawdown";
import { dollars, outcomeAt } from "../../lib/us-drawdown";
import USDrawdownPage from "./page";

vi.mock("../../lib/api-us-drawdown", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api-us-drawdown")>()),
  runUSDrawdownYear: vi.fn(),
}));

const runMock = vi.mocked(runUSDrawdownYear);

type Scenario = keyof typeof recorded;

const inputsOf = (name: Scenario) => recorded[name].inputs as unknown as USDrawdownYearInput;

/** A real-engine run the recorder saved for one scenario. */
function runOf(name: Scenario): USDrawdownRun {
  const { envelope } = recorded[name];
  return {
    result: envelope.outputs.us_drawdown_year_result as unknown as USDrawdownRun["result"],
    caveats: envelope.caveats,
    citations: envelope.citations as USDrawdownRun["citations"],
    sources: envelope.sources as USDrawdownRun["sources"],
  };
}

/** JSON with every object's keys in order, so equal figures always read the same. */
function sortedJSON(value: unknown): string {
  return JSON.stringify(value, (_key, entry) =>
    entry && typeof entry === "object" && !Array.isArray(entry)
      ? Object.fromEntries(Object.entries(entry).sort(([a], [b]) => a.localeCompare(b)))
      : entry,
  );
}

const withoutDraw = (inputs: USDrawdownYearInput) => sortedJSON({ ...inputs, draw_amount: 0 });

/**
 * The run the recorder saved for the same household, whatever the draw. Other
 * figures get the example's run, so a test that changes them sees the page dim.
 */
function runFor(inputs: USDrawdownYearInput): USDrawdownRun {
  const match = (Object.keys(recorded) as Scenario[]).find(
    (name) => withoutDraw(inputsOf(name)) === withoutDraw(inputs),
  );
  return runOf(match ?? "example");
}

const HEADLINE =
  "Draw $30,000 from your traditional IRA or 401(k) in 2026 and you’ll have $51,474 to spend.";
const BANNER = /These figures describe an example person/;

async function openPage() {
  render(<USDrawdownPage />);
  await screen.findByText(HEADLINE, undefined, { timeout: 3_000 });
}

function lastInputs(): USDrawdownYearInput {
  return runMock.mock.calls[runMock.mock.calls.length - 1][0];
}

/** Waits past the debounce so any request the page would send has gone. */
function debounceSettles() {
  return act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 450));
  });
}

function edit(field: HTMLElement, value: number | string) {
  fireEvent.focus(field);
  fireEvent.change(field, { target: { value: String(value) } });
  fireEvent.blur(field);
}

const byLabel = (label: string) => screen.getByLabelText(label);

function enterIncome(group: string, person: USDrawdownPerson) {
  const scope = within(screen.getByRole("group", { name: group }));
  edit(scope.getByLabelText("Social Security"), person.social_security);
  edit(scope.getByLabelText("Pensions and annuities"), person.pension_income);
  edit(scope.getByLabelText("Government pensions"), person.government_pension_income);
  edit(scope.getByLabelText("Earnings"), person.earnings);
}

/** Types a household into the form the way a reader would. */
function enter(inputs: USDrawdownYearInput) {
  const joint = inputs.spouse !== null;
  fireEvent.click(
    screen.getByRole("radio", { name: joint ? "Married, filing jointly" : "Single" }),
  );
  fireEvent.change(byLabel("State"), { target: { value: inputs.state } });
  edit(byLabel("Your birth year"), inputs.you.birth_year);
  enterIncome(
    joint ? "Your income in 2026, before you draw" : "Income in 2026, before you draw",
    inputs.you,
  );
  edit(byLabel("Taxable interest"), inputs.taxable_interest);
  edit(byLabel("Tax-exempt interest"), inputs.tax_exempt_interest);
  edit(byLabel("Dividends"), inputs.dividends);
  edit(
    byLabel(joint ? "Your traditional IRAs and 401(k)s" : "Traditional IRAs and 401(k)s"),
    inputs.you.traditional_balance,
  );
  edit(byLabel(joint ? "Your Roth IRAs" : "Roth IRAs"), inputs.you.roth_balance);
  edit(byLabel("Investments in taxable accounts"), inputs.taxable_balance);
  edit(byLabel("Cash and savings"), inputs.cash_savings);
  if (inputs.spouse) {
    edit(byLabel("Your spouse’s birth year"), inputs.spouse.birth_year);
    enterIncome("Your spouse’s income in 2026", inputs.spouse);
    edit(byLabel("Your spouse’s traditional IRAs and 401(k)s"), inputs.spouse.traditional_balance);
    edit(byLabel("Your spouse’s Roth IRAs"), inputs.spouse.roth_balance);
  }
  const sources = {
    traditional: "Traditional IRA or 401(k)",
    roth: "Roth IRA",
    taxable: "Investments",
    cash: "Cash",
  };
  fireEvent.click(screen.getByRole("radio", { name: sources[inputs.draw_source] }));
  edit(byLabel("Amount to draw in 2026"), inputs.draw_amount);
}

/** Enters a recorded household and waits for its run. */
async function openScenario(name: Scenario, headline: string) {
  await openPage();
  runMock.mockClear();
  enter(inputsOf(name));
  // The form sends exactly what the recorder sent, before any wording is checked.
  await waitFor(() => expect(runMock).toHaveBeenCalled());
  expect(lastInputs()).toEqual(inputsOf(name));
  await screen.findByText(headline);
}

function rowText(table: HTMLElement, name: string) {
  return within(table)
    .getByRole("rowheader", { name })
    .closest("tr")
    ?.textContent?.replace(name, "");
}

const ledger = () =>
  screen.getByRole("table", { name: "Your 2026 with no draw and with your chosen draw" });
const coverage = () => screen.getByRole("table", { name: "Health coverage" });

describe("USDrawdownPage", () => {
  beforeEach(() => {
    runMock.mockReset();
    runMock.mockImplementation(async (inputs) => runFor(inputs));
  });

  it("calculates the example and says it is one", async () => {
    await openPage();
    expect(runMock).toHaveBeenCalledTimes(1);
    expect(lastInputs()).toEqual(inputsOf("example"));
    expect(screen.getByText(BANNER)).toBeInTheDocument();
    expect(
      screen.getByText(
        "You’d have $27,184 more to spend than if you drew nothing, after losing $291 of SNAP and paying $2,525 more in tax.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Your next $1,000" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Draw another $1,000 and you keep $737: you pay $263 in tax. It also makes $850 more of your Social Security taxable.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the year with no draw and with the chosen draw, program by program", async () => {
    await openPage();
    const table = ledger();
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((cell) => cell.textContent),
    ).toEqual(["Draw nothing", "Draw $30,000"]);
    expect(rowText(table, "Income before you draw")).toBe("$24,000$24,000");
    expect(rowText(table, "Money you draw")).toBe("$0$30,000");
    expect(rowText(table, "SNAP")).toBe("$291$0");
    expect(rowText(table, "Federal income tax")).toBe("$0−$1,810");
    expect(rowText(table, "State income tax")).toBe("$0−$688");
    expect(rowText(table, "Other taxes")).toBe("−$1−$28");
    expect(rowText(table, "Money to spend")).toBe("$24,290$51,474");
    expect(
      screen.getByText(
        "$220,000 stays in your traditional IRA or 401(k) after your draw, before any growth.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Health coverage" })).not.toBeInTheDocument();
  });

  it("explains Medicare premiums and the required minimum", async () => {
    await openPage();
    expect(screen.getByRole("heading", { name: "Medicare premiums in 2028" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Your 2028 premiums rise once it reaches $109,001, which a draw of about $88,601 would do, adding $1,148 a year.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Required minimum distribution" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "You must take at least $9,804 from traditional IRAs and 401(k)s in 2026. We divide your $250,000 balance at the end of 2025 by 25.5, the IRS Uniform Lifetime Table’s factor for age 74.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("This draw covers it.")).toBeInTheDocument();
  });

  it("lists what it leaves out and links its sources", async () => {
    await openPage();
    expect(
      screen.getByText(
        "We count savings at their balances on January 1, 2026, for the whole year, so spending them down doesn’t change what you qualify for here.",
      ),
    ).toBeInTheDocument();
    const engine = runOf("example").sources.find((source) => source.name === "PolicyEngine US");
    expect(screen.getByRole("link", { name: "PolicyEngine-US" })).toHaveAttribute(
      "href",
      engine?.url ?? "",
    );
    expect(
      screen.getByText(new RegExp(`${engine?.version} calculates federal and state`)),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "IRS Uniform Lifetime Table" })).toBeInTheDocument();
    for (const name of ["Federal income tax", "Benefits", "Medicare premiums"]) {
      expect(screen.getByRole("heading", { name, level: 3 })).toBeInTheDocument();
    }
  });

  it("moves the result at once and asks the API only when the slider settles", async () => {
    await openPage();
    runMock.mockClear();
    const slider = screen.getByRole("slider", { name: "Amount to draw" });

    fireEvent.change(slider, { target: { value: "1000" } });
    fireEvent.change(slider, { target: { value: "8000" } });

    // $8,000 sits on the sweep, so the preview needs no new request.
    const atDraw = outcomeAt(runOf("example").result.sweep, 8_000);
    expect(
      screen.getByText(
        `Draw $8,000 from your traditional IRA or 401(k) in 2026 and you’ll have ${dollars(atDraw.money_to_spend)} to spend.`,
      ),
    ).toBeInTheDocument();
    expect(runMock).not.toHaveBeenCalled();

    await waitFor(() => expect(runMock).toHaveBeenCalledTimes(1));
    expect(lastInputs().draw_amount).toBe(8_000);
  });

  it("keeps the example banner for a new draw and drops it for new figures", async () => {
    await openPage();
    fireEvent.change(screen.getByRole("slider", { name: "Amount to draw" }), {
      target: { value: "1000" },
    });
    fireEvent.click(screen.getByRole("radio", { name: "Cash" }));
    expect(screen.getByText(BANNER)).toBeInTheDocument();

    edit(byLabel("Social Security"), 25_000);
    expect(screen.queryByText(BANNER)).not.toBeInTheDocument();
  });

  it("dims the old result while a changed figure recalculates", async () => {
    await openPage();
    edit(byLabel("Pensions and annuities"), 5_000);
    expect(document.querySelector("[aria-busy=true]")).not.toBeNull();
  });

  it("never draws more than the account holds", async () => {
    await openPage();
    runMock.mockClear();
    edit(byLabel("Amount to draw in 2026"), 400_000);
    await waitFor(() => expect(runMock).toHaveBeenCalled());
    expect(lastInputs().draw_amount).toBe(250_000);
  });

  it("asks for a birth year it covers without calling the API", async () => {
    await openPage();
    runMock.mockClear();
    edit(byLabel("Your birth year"), 1965);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Enter your birth year, from 1906 to 1961. We cover people 65 or older by the end of 2026.",
    );
    await debounceSettles();
    expect(runMock).not.toHaveBeenCalled();

    edit(byLabel("Your birth year"), 1952);
    await waitFor(() => expect(runMock).toHaveBeenCalledTimes(1));
    expect(lastInputs().you.birth_year).toBe(1952);
  });

  it("offers a retry when the API fails", async () => {
    runMock.mockRejectedValueOnce(new Error("network down"));
    render(<USDrawdownPage />);
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
    edit(byLabel("Earnings"), 100);
    await waitFor(() => expect(runMock).toHaveBeenCalledTimes(2));
    edit(byLabel("Earnings"), 200);
    await waitFor(() => expect(aborted).toEqual([true]));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("asks for a balance when the chosen account holds nothing", async () => {
    await openPage();
    fireEvent.click(screen.getByRole("radio", { name: "Roth IRA" }));
    expect(
      await screen.findByText("Enter how much you have in your Roth IRA to see what you’d keep."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("slider")).not.toBeInTheDocument();
  });

  it("links a phone reader from the result back to the form", async () => {
    await openPage();
    expect(screen.getByRole("link", { name: "Change your figures" })).toHaveAttribute(
      "href",
      "#your-figures",
    );
  });

  it("shows where a low-income household loses SNAP, CSFP food boxes and health coverage", async () => {
    await openScenario(
      "low_income",
      "Draw $3,000 from your traditional IRA or 401(k) in 2026 and you’ll have $16,019 to spend.",
    );
    expect(
      screen.getByText(
        "You’d have $1,653 more to spend than if you drew nothing, after losing $1,347 of SNAP.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Draw another $1,000 and you keep $922: you lose $78 of SNAP."),
    ).toBeInTheDocument();
    expect(rowText(ledger(), "SNAP")).toBe("$1,716$369");
    expect(rowText(ledger(), "CSFP food boxes")).toBe("$651$651");
    expect(rowText(coverage(), "Medicaid")).toBe("YesYes");
    expect(rowText(coverage(), "Medicare Savings Program")).toBe("YesYes");
    expect(
      screen.getByText(
        "Help from a Medicare Savings Program ends at a draw of about $7,394 and Medicaid at about $12,785.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("At about $11,942")).toBeInTheDocument();
    expect(screen.getByText("CSFP food boxes end, taking $651 all at once.")).toBeInTheDocument();
    expect(screen.queryByText(/You’d lose/)).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("slider", { name: "Amount to draw" }), {
      target: { value: "8000" },
    });
    expect(rowText(coverage(), "Medicare Savings Program")).toBe("YesNo");
    expect(
      screen.getByText(
        "You’d lose help from a Medicare Savings Program at this draw. We mark where coverage ends but leave its value out of money to spend; without a Medicare Savings Program you’d pay your own Part B premium.",
      ),
    ).toBeInTheDocument();
  });

  it("warns that a Roth draw leaves the required minimum unmet", async () => {
    await openScenario(
      "roth",
      "Draw $20,000 from your Roth IRA in 2026 and you’ll have $43,999 to spend.",
    );
    expect(
      screen.getByText(
        "You’d fall $9,804 short of your required minimum and owe an excise tax of $2,451, which we leave out of money to spend.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Withdrawing nothing falls $9,804 short, so you’d owe an excise tax of $2,451 (25% of the shortfall). We leave it out of money to spend.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Draw another $1,000 and you keep all of it.")).toBeInTheDocument();
    expect(screen.queryByText(BANNER)).not.toBeInTheDocument();
  });

  it("shows a couple's Medicare surcharge between the two of them", async () => {
    await openScenario(
      "couple",
      "Draw $150,000 from your traditional IRA or 401(k) in 2026 and you’ll have $205,884 to spend.",
    );
    expect(
      screen.getByText(
        "That reaches Medicare’s $218,001 income line, so your 2028 Part B and Part D premiums rise by $2,297 for the year between the two of you.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/, after paying \$29,116 more in tax\.$/)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Yours" })).toBeChecked();
    expect(screen.queryByRole("heading", { name: /Required minimum/ })).not.toBeInTheDocument();
  });
});
