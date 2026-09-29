import { fireEvent, render, screen as view } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BenefitsCheck } from "../components/uk/BenefitsCheck";
import type { UKPensionCreditScreen } from "./api-uk";
import { citationLabel, formatQualifyingAge, summarizePensionCredit } from "./uk-benefits";

const citations = [
  {
    id: "Pensions Act 1995 Sch 4 para 1(8)",
    url: "https://www.legislation.gov.uk/ukpga/1995/26/schedule/4/part/I",
  },
  {
    id: "uk:regulations/uksi/2002/1792/15#capital_deemed_weekly_income",
    url: "https://www.legislation.gov.uk/uksi/2002/1792/regulation/15",
  },
];

function screened(overrides: Partial<UKPensionCreditScreen> = {}): UKPensionCreditScreen {
  return {
    status: "screened",
    qualifying_age_years: 67,
    qualifying_age_months: 0,
    weekly_minimum_guarantee: 238,
    paths_screened: 500,
    share_of_paths_indicated: 0.18,
    ages: [67, 68, 69],
    share_indicated_by_age: [0.1, 0.12, 0.18],
    median_annual_amount_by_age: [900, 1_100, 1_400],
    first_age_indicated: 68,
    citations,
    ...overrides,
  };
}

describe("formatQualifyingAge", () => {
  it("shows whole years plainly and months when there are some", () => {
    expect(formatQualifyingAge(67, 0)).toBe("67");
    expect(formatQualifyingAge(66, 1)).toBe("66 years and 1 month");
    expect(formatQualifyingAge(66, 7)).toBe("66 years and 7 months");
  });
});

describe("summarizePensionCredit", () => {
  it("reports how many paths fall below the minimum guarantee", () => {
    const summary = summarizePensionCredit(screened(), 90);
    expect(summary.tone).toBe("indicated");
    expect(summary.headline).toBe(
      "In 18% of 500 simulated paths, income as Pension Credit counts it falls " +
        "below the minimum guarantee (£238/week) in at least one year from your " +
        "State Pension age (67), typically from age 68.",
    );
    expect(summary.detail).toMatch(/around £1k\/year/);
  });

  it("says plainly when no screened path qualifies", () => {
    const summary = summarizePensionCredit(
      screened({
        share_of_paths_indicated: 0,
        share_indicated_by_age: [0, 0, 0],
        median_annual_amount_by_age: [0, 0, 0],
        first_age_indicated: null,
      }),
      90,
    );
    expect(summary.tone).toBe("clear");
    expect(summary.headline).toMatch(/^In none of the 500 simulated paths/);
    expect(summary.detail).toBeNull();
  });

  it("does not screen a plan that ends before State Pension age", () => {
    const summary = summarizePensionCredit(
      {
        status: "under_qualifying_age",
        qualifying_age_years: 66,
        qualifying_age_months: 7,
        weekly_minimum_guarantee: null,
        paths_screened: 0,
        share_of_paths_indicated: 0,
        ages: [],
        share_indicated_by_age: [],
        median_annual_amount_by_age: [],
        first_age_indicated: null,
        citations,
      },
      60,
    );
    expect(summary.tone).toBe("not_screened");
    expect(summary.headline).toBe(
      "Pension Credit starts at State Pension age, 66 years and 7 months for " +
        "you, which comes after this plan ends at 60, so it isn't screened.",
    );
    // No "£0/week" minimum guarantee claim.
    expect(summary.headline).not.toMatch(/£0/);
  });

  it("keeps a decimal for small shares", () => {
    expect(
      summarizePensionCredit(screened({ share_of_paths_indicated: 0.004 }), 90).headline,
    ).toMatch(/^In 0\.4% of 500/);
  });
});

describe("citationLabel", () => {
  it("drops the engine prefix and splits the rule name", () => {
    expect(citationLabel(citations[1].id)).toBe(
      "regulations/uksi/2002/1792/15 — capital_deemed_weekly_income",
    );
    expect(citationLabel(citations[0].id)).toBe(citations[0].id);
  });
});

describe("BenefitsCheck", () => {
  it("renders the summary and toggles its sources", () => {
    render(<BenefitsCheck screen={screened()} maxAge={90} />);
    expect(view.getByText(/In 18% of 500 simulated paths/)).toBeTruthy();
    const toggle = view.getByRole("button", { name: "Sources (2)" });
    expect(view.queryByRole("link")).toBeNull();
    fireEvent.click(toggle);
    const links = view.getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[1].getAttribute("href")).toBe(citations[1].url);
    expect(view.getByRole("button", { name: "Hide sources" })).toBeTruthy();
  });

  it("renders the not-screened state without a guarantee amount", () => {
    render(
      <BenefitsCheck
        screen={screened({
          status: "under_qualifying_age",
          weekly_minimum_guarantee: null,
          paths_screened: 0,
          share_of_paths_indicated: 0,
          ages: [],
          share_indicated_by_age: [],
          median_annual_amount_by_age: [],
          first_age_indicated: null,
        })}
        maxAge={60}
      />,
    );
    expect(view.getByText(/isn't screened/)).toBeTruthy();
    expect(view.queryByText(/\/week/)).toBeNull();
  });
});
