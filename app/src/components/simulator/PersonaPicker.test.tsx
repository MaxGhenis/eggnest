import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Persona } from "../../lib/simulatorUtils";
import { PersonaPicker } from "./PersonaPicker";

const personas: Persona[] = [
  {
    id: "early-retiree",
    name: "Early retiree",
    description: "55-year-old leaving tech with $1.5M saved",
    emoji: "🏖️",
    params: {
      annual_spending: 80_000,
      initial_capital: 1_500_000,
      current_age: 55,
      max_age: 95,
      gender: "male",
      state: "CA",
      filing_status: "single",
      n_simulations: 10_000,
      stock_allocation: 0.6,
      social_security_monthly: 2_800,
      social_security_start_age: 67,
      employment_income: 0,
      retirement_age: 55,
      pension_annual: 0,
      return_model: "bootstrap",
      inflation_model: "historical",
      inflation_rate: 0.03,
      include_mortality: true,
      spouse_social_security_start_age: 67,
      spending_mode: "real",
      social_security_inflation_adjusted: true,
      pension_cola_rate: 0,
      annuity_cola_rate: 0,
      bond_index: "treasury",
      stock_index: "sp500",
      has_spouse: false,
      has_annuity: false,
    },
  },
];

describe("PersonaPicker", () => {
  it("sets honest expectations about example loading and runtime", () => {
    render(
      <PersonaPicker
        personas={personas}
        isLoading={false}
        progress={{ currentYear: 0, totalYears: 30 }}
        onLoadPersona={vi.fn()}
        onStartFromScratch={vi.fn()}
      />
    );

    expect(screen.getByText(/Model your financial/i)).toBeInTheDocument();
    expect(screen.getByText(/full simulations can take a minute/i)).toBeInTheDocument();
  });

  it("loads quick review without auto-running the simulation", async () => {
    const user = userEvent.setup();
    const onLoadPersona = vi.fn();

    render(
      <PersonaPicker
        personas={personas}
        isLoading={false}
        progress={{ currentYear: 0, totalYears: 30 }}
        onLoadPersona={onLoadPersona}
        onStartFromScratch={vi.fn()}
      />
    );

    await user.click(screen.getByRole("button", { name: /quick review/i }));

    expect(onLoadPersona).toHaveBeenCalledWith(personas[0], "review");
  });

  it("loads the persona into the wizard for customization", async () => {
    const user = userEvent.setup();
    const onLoadPersona = vi.fn();

    render(
      <PersonaPicker
        personas={personas}
        isLoading={false}
        progress={{ currentYear: 0, totalYears: 30 }}
        onLoadPersona={onLoadPersona}
        onStartFromScratch={vi.fn()}
      />
    );

    await user.click(screen.getByRole("button", { name: /customize/i }));

    expect(onLoadPersona).toHaveBeenCalledWith(personas[0], "start");
  });
});
