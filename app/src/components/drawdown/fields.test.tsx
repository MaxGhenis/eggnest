import { fireEvent, render, screen } from "@testing-library/react";
import fc from "fast-check";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { NumberField, parseAmount } from "./fields";

// Invariants these tests hold for every input:
// - A field works with the figure it shows: what parseAmount reads from any
//   typed amount is that amount to two decimals, half up on the decimal
//   typed, as the field prints it once it loses focus. The API rounds money
//   the same way (api/eggnest/money.py), so the page and the API use one
//   figure for an amount typed in fractions of a cent (api3, P2-a).

describe("parseAmount", () => {
  it.each([
    ["0.125", 0.13],
    ["1.005", 1.01],
    ["2.675", 2.68],
    ["£1,234.565", 1_234.57],
    ["$770.005", 770.01],
    ["4.125%", 4.13],
    ["0.004", 0],
    ["10,000", 10_000],
    ["-5", 0],
    ["", 0],
    ["abc", 0],
  ])("reads %s as %s", (text, value) => {
    expect(parseAmount(text)).toBe(value);
  });

  it("reads the amount the field then shows", () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 10_000_000_000 }), fc.integer({ min: 0, max: 5 }), (units, places) => {
        const text = (units / 10 ** places).toString();
        const value = parseAmount(text);
        const shown = value.toLocaleString("en-GB", { maximumFractionDigits: 2 });
        expect(Number(shown.replace(/,/g, ""))).toBe(value);
        expect(Math.abs(value - Number(text))).toBeLessThanOrEqual(0.005 + 1e-9);
      }),
    );
  });
});

describe("NumberField", () => {
  function Field({ onChange }: { onChange: (value: number) => void }) {
    const [value, setValue] = useState(0);
    return (
      <NumberField
        label="Amount to draw"
        prefix="£"
        value={value}
        onChange={(next) => {
          setValue(next);
          onChange(next);
        }}
      />
    );
  }

  it("passes on an amount in fractions of a penny as the penny it shows", () => {
    const onChange = vi.fn();
    render(<Field onChange={onChange} />);
    const field = screen.getByRole("textbox", { name: "Amount to draw" });
    fireEvent.focus(field);
    fireEvent.change(field, { target: { value: "770.005" } });
    expect(onChange).toHaveBeenLastCalledWith(770.01);
    fireEvent.blur(field);
    expect(field).toHaveValue("770.01");
  });
});
