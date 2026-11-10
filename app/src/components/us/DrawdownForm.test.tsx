import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EXAMPLE_FORM, NEW_SPOUSE, type USDrawdownForm } from "../../lib/us-drawdown";
import { DrawdownForm } from "./DrawdownForm";

function renderForm(overrides: Partial<USDrawdownForm> = {}) {
  const onChange = vi.fn();
  const form = { ...EXAMPLE_FORM, ...overrides };
  render(<DrawdownForm form={form} onChange={onChange} />);
  return { onChange, form };
}

function type(field: HTMLElement, value: string) {
  fireEvent.focus(field);
  fireEvent.change(field, { target: { value } });
}

const JOINT = { filing_status: "married_filing_jointly" } as const;

describe("DrawdownForm", () => {
  it("offers the four places to draw from, by name", () => {
    const { onChange } = renderForm();
    expect(screen.getByRole("radio", { name: "Traditional IRA or 401(k)" })).toBeChecked();
    for (const name of ["Roth IRA", "Investments", "Cash"]) {
      expect(screen.getByRole("radio", { name })).not.toBeChecked();
    }
    fireEvent.click(screen.getByRole("radio", { name: "Roth IRA" }));
    expect(onChange).toHaveBeenCalledWith({ draw_source: "roth" });
  });

  it("asks whose account only for a couple drawing from an IRA", () => {
    renderForm();
    expect(screen.queryByRole("group", { name: "Whose account" })).not.toBeInTheDocument();
    const { onChange } = renderForm(JOINT);
    fireEvent.click(screen.getByRole("radio", { name: "Your spouse’s" }));
    expect(onChange).toHaveBeenCalledWith({ draw_owner: "spouse" });
  });

  it("skips whose account for investments and cash, which the couple holds together", () => {
    renderForm({ ...JOINT, draw_source: "cash" });
    expect(screen.queryByRole("group", { name: "Whose account" })).not.toBeInTheDocument();
  });

  it("asks for the gain on a sale only for investments, and sends it as a share", () => {
    renderForm();
    expect(screen.queryByLabelText("Gain as a share of each sale")).not.toBeInTheDocument();
    const { onChange } = renderForm({ draw_source: "taxable" });
    const field = screen.getByLabelText("Gain as a share of each sale") as HTMLInputElement;
    expect(field.value).toBe("50");
    type(field, "75");
    expect(onChange).toHaveBeenLastCalledWith({ taxable_gain_share: 0.75 });
    type(field, "75%");
    expect(onChange).toHaveBeenLastCalledWith({ taxable_gain_share: 0.75 });
    type(field, "150");
    expect(onChange).toHaveBeenLastCalledWith({ taxable_gain_share: 1 });
  });

  it("lists the 50 states and DC and sends the state's code", () => {
    const { onChange } = renderForm();
    const state = screen.getByLabelText("State") as HTMLSelectElement;
    expect(within(state).getAllByRole("option")).toHaveLength(51);
    expect(state.value).toBe("NC");
    expect(within(state).getByRole("option", { name: "North Carolina" })).toHaveProperty(
      "selected",
      true,
    );
    fireEvent.change(state, { target: { value: "TX" } });
    expect(onChange).toHaveBeenCalledWith({ state: "TX" });
  });

  it("reads a birth year as digits only", () => {
    const { onChange, form } = renderForm();
    const field = screen.getByLabelText("Your birth year");
    expect(field).toHaveAttribute("maxLength", "4");
    fireEvent.change(field, { target: { value: "19a5" } });
    expect(onChange).toHaveBeenLastCalledWith({ you: { ...form.you, birth_year: 195 } });
    fireEvent.change(field, { target: { value: "" } });
    expect(onChange).toHaveBeenLastCalledWith({ you: { ...form.you, birth_year: 0 } });
  });

  it("asks for a spouse's figures only when filing jointly", () => {
    renderForm();
    expect(screen.queryByLabelText("Your spouse’s birth year")).not.toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: "Income in 2026, before you draw" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Traditional IRAs and 401(k)s")).toBeInTheDocument();

    renderForm(JOINT);
    expect(screen.getByLabelText("Your spouse’s birth year")).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: "Your income in 2026, before you draw" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Your spouse’s income in 2026" })).toBeInTheDocument();
    expect(screen.getByLabelText("Your traditional IRAs and 401(k)s")).toBeInTheDocument();
    expect(screen.getByLabelText("Your spouse’s Roth IRAs")).toBeInTheDocument();
  });

  it("changes one of a spouse's figures and keeps the rest", () => {
    const spouse = { ...NEW_SPOUSE, social_security: 18_000 };
    const { onChange } = renderForm({ ...JOINT, spouse });
    const income = within(screen.getByRole("group", { name: "Your spouse’s income in 2026" }));
    type(income.getByLabelText("Pensions and annuities"), "6000");
    expect(onChange).toHaveBeenLastCalledWith({ spouse: { ...spouse, pension_income: 6_000 } });
  });

  it("reads amounts typed with dollar signs and commas", () => {
    const { onChange } = renderForm();
    type(screen.getByLabelText("Cash and savings"), "$12,500");
    expect(onChange).toHaveBeenLastCalledWith({ cash_savings: 12_500 });
  });

  it("keeps other withdrawals and Roth conversions behind a summary", () => {
    renderForm();
    const details = screen.getByText("Other withdrawals and Roth conversions").closest("details");
    expect(details).not.toHaveAttribute("open");
    expect(within(details as HTMLElement).getByLabelText("Roth conversions")).toBeInTheDocument();
  });

  it("reads each hint to a screen reader with its field", () => {
    renderForm();
    expect(screen.getByLabelText("Tax-exempt interest")).toHaveAccessibleDescription(
      "Such as from municipal bonds. It can make more of your Social Security taxable and raise what you pay for Medicare.",
    );
    expect(screen.getByLabelText("Your birth year")).toHaveAccessibleDescription(
      "We cover people 65 or older by the end of 2026.",
    );
    expect(screen.getByLabelText("Earnings")).not.toHaveAttribute("aria-describedby");
  });

  it("gives the form the id the page's jump link targets", () => {
    renderForm();
    expect(document.getElementById("your-figures")?.tagName).toBe("FORM");
  });
});
