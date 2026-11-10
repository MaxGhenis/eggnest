import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { UKDrawdownYearInput } from "../../lib/api-uk-drawdown";
import { EXAMPLE_INPUTS, LUMP_SUM_ALLOWANCE } from "../../lib/uk-drawdown";
import { DrawdownForm } from "./DrawdownForm";

function renderForm(overrides: Partial<UKDrawdownYearInput> = {}) {
  const onChange = vi.fn();
  render(<DrawdownForm inputs={{ ...EXAMPLE_INPUTS, ...overrides }} onChange={onChange} />);
  return onChange;
}

describe("DrawdownForm", () => {
  it("offers the four places to draw from, by name", () => {
    const onChange = renderForm();
    expect(screen.getByRole("radio", { name: "Pension pot" })).toBeChecked();
    fireEvent.click(screen.getByRole("radio", { name: "ISAs" }));
    expect(onChange).toHaveBeenCalledWith({ draw_source: "isa" });
  });

  it("asks how a pension draw comes out only for a pension draw", () => {
    renderForm({ draw_source: "cash" });
    expect(screen.queryByRole("radio", { name: "One-off" })).not.toBeInTheDocument();
    expect(screen.queryByText("Tax-free share of each withdrawal")).not.toBeInTheDocument();
  });

  it("explains how DWP treats each kind of withdrawal", () => {
    renderForm();
    expect(screen.getByText("DWP counts regular withdrawals as income.")).toBeInTheDocument();
    renderForm({ sipp_draw_pattern: "one_off" });
    expect(
      screen.getByText("DWP counts a one-off withdrawal as savings and values what’s left in your pot again."),
    ).toBeInTheDocument();
  });

  it("sends the tax-free share as a number", () => {
    const onChange = renderForm();
    fireEvent.click(screen.getByRole("radio", { name: "None" }));
    expect(onChange).toHaveBeenCalledWith({ sipp_tax_free_fraction: 0 });
  });

  it("reads amounts typed with pound signs and commas", () => {
    const onChange = renderForm();
    const field = screen.getByLabelText("Pension pots");
    fireEvent.focus(field);
    fireEvent.change(field, { target: { value: "£12,500" } });
    expect(onChange).toHaveBeenLastCalledWith({ sipp_balance: 12_500 });
  });

  it("treats anything that isn't a positive amount as nothing", () => {
    const onChange = renderForm();
    const field = screen.getByLabelText("Earnings");
    fireEvent.focus(field);
    fireEvent.change(field, { target: { value: "abc" } });
    expect(onChange).toHaveBeenLastCalledWith({ employment_income: 0 });
    fireEvent.change(field, { target: { value: "-50" } });
    expect(onChange).toHaveBeenLastCalledWith({ employment_income: 0 });
  });

  it("shows grouped figures until someone edits them", () => {
    renderForm({ sipp_balance: 400_000 });
    const field = screen.getByLabelText("Pension pots") as HTMLInputElement;
    expect(field.value).toBe("400,000");
    fireEvent.focus(field);
    expect(field.value).toBe("400000");
    fireEvent.blur(field);
    expect(field.value).toBe("400,000");
  });

  it("uses the table unless a provider's figure is entered", () => {
    const onChange = renderForm();
    const field = screen.getByLabelText("Annuity income per £1,000 of pot");
    fireEvent.focus(field);
    fireEvent.change(field, { target: { value: "75" } });
    expect(onChange).toHaveBeenLastCalledWith({ annuity_income_per_1000: 75 });
    fireEvent.change(field, { target: { value: "" } });
    expect(onChange).toHaveBeenLastCalledWith({ annuity_income_per_1000: null });
  });

  it("caps the Lump Sum Allowance at the legal maximum", () => {
    const onChange = renderForm();
    const field = screen.getByLabelText("Lump Sum Allowance left");
    fireEvent.focus(field);
    fireEvent.change(field, { target: { value: "999999" } });
    expect(onChange).toHaveBeenLastCalledWith({ lump_sum_allowance_remaining: LUMP_SUM_ALLOWANCE });
  });

  it("leaves Scotland out and says why", () => {
    renderForm();
    const options = screen.getAllByRole("option").map((option) => option.textContent);
    expect(options).toEqual(["England", "Wales", "Northern Ireland"]);
    expect(screen.getByLabelText("Where you live")).toHaveAccessibleDescription(
      "The Scottish Parliament sets its own income tax rates, which we don’t cover.",
    );
  });
});
