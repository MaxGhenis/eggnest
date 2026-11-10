import fc from "fast-check";
import { describe, expect, it } from "vitest";
import recorded from "../test/fixtures/uk-drawdown-recorded.json";
import type {
  DrawSource,
  DrawdownOutcome,
  DrawdownSlice,
  UKDrawdownYearInput,
  UKDrawdownYearResult,
} from "./api-uk-drawdown";
import {
  EXAMPLE_INPUTS,
  ageAtTaxYearStart,
  bandRange,
  chartTop,
  comparedWithNoDraw,
  compactPounds,
  describeNextStep,
  describePound,
  emptySourceMessage,
  headline,
  inputProblem,
  isExamplePerson,
  niceTicks,
  outcomeAt,
  pounds,
  poundsAndPence,
  sliceBetween,
  sourceBalance,
  splitPence,
  withDrawInBounds,
} from "./uk-drawdown";

// Invariants these tests hold for every input:
// - outcomeAt returns a sweep row exactly at its draw and stays between the two
//   neighbouring rows elsewhere; reading off the line keeps the accounting.
// - Each pound of draw goes somewhere: kept + tax + lost credit = 1, and the
//   whole-pence split adds up to exactly 100p.
// - The chart always contains the chosen draw, up to the top of the sweep.
// - The draw never exceeds what the chosen source holds.
// Differential: the page reads amounts off the sweep, the API computes them
// directly; on recorded real-engine runs the two agree.

const OTHER_INCOME = 9_360;

const money = fc.integer({ min: 0, max: 5_000_000 }).map((pence) => pence / 100);

/** Rows in draw order that satisfy the accounting identity the API guarantees. */
const sweepRows = fc
  .array(
    fc.record({
      gap: fc.integer({ min: 1, max: 20_000 }),
      income_tax: money,
      employee_ni: money,
      pension_credit: money,
    }),
    { minLength: 2, maxLength: 40 },
  )
  .map((rows): DrawdownOutcome[] => {
    let draw = 0;
    return rows.map(({ gap, income_tax, employee_ni, pension_credit }, index) => {
      if (index > 0) draw += gap;
      return {
        draw,
        taxable_draw: draw * 0.75,
        income_tax,
        employee_ni,
        pension_credit,
        money_to_spend: OTHER_INCOME + draw + pension_credit - income_tax - employee_ni,
      };
    });
  });

/** Draws come in whole pence: a slider step or a typed amount. */
const sweepAndDraw = sweepRows.chain((sweep) =>
  fc
    .integer({ min: 0, max: sweep[sweep.length - 1].draw * 100 })
    .map((pence) => ({ sweep, draw: pence / 100 })),
);

function accountingGap(row: DrawdownOutcome): number {
  return (
    row.money_to_spend -
    (OTHER_INCOME + row.draw + row.pension_credit - row.income_tax - row.employee_ni)
  );
}

function slice(overrides: Partial<DrawdownSlice> = {}): DrawdownSlice {
  return {
    draw_from: 0,
    draw_to: 1_000,
    kept: 1,
    to_tax: 0,
    to_pension_credit: 0,
    ...overrides,
  };
}

describe("outcomeAt", () => {
  it("returns the row exactly at every sweep point", () => {
    fc.assert(
      fc.property(sweepRows, (sweep) => {
        for (const row of sweep) expect(outcomeAt(sweep, row.draw)).toEqual(row);
      }),
    );
  });

  it("stays between the neighbouring rows", () => {
    fc.assert(
      fc.property(sweepAndDraw, ({ sweep, draw }) => {
        const outcome = outcomeAt(sweep, draw);
        const after = sweep.findIndex((row) => row.draw >= draw);
        const a = sweep[Math.max(after - 1, 0)];
        const b = sweep[after];
        for (const field of ["income_tax", "employee_ni", "pension_credit"] as const) {
          expect(outcome[field]).toBeGreaterThanOrEqual(Math.min(a[field], b[field]) - 1e-6);
          expect(outcome[field]).toBeLessThanOrEqual(Math.max(a[field], b[field]) + 1e-6);
        }
      }),
    );
  });

  it("keeps the accounting between sweep points", () => {
    fc.assert(
      fc.property(sweepAndDraw, ({ sweep, draw }) => {
        expect(Math.abs(accountingGap(outcomeAt(sweep, draw)))).toBeLessThan(1e-6);
      }),
    );
  });

  it("stops at the ends of the sweep", () => {
    fc.assert(
      fc.property(sweepRows, (sweep) => {
        const last = sweep[sweep.length - 1];
        expect(outcomeAt(sweep, -1)).toEqual(sweep[0]);
        expect(outcomeAt(sweep, last.draw + 1)).toEqual(last);
      }),
    );
  });
});

describe("sliceBetween", () => {
  it("sends each pound of draw somewhere", () => {
    fc.assert(
      fc.property(sweepAndDraw, fc.integer({ min: 1, max: 40_000 }), ({ sweep, draw }, step) => {
        const result = sliceBetween(sweep, draw, draw + step);
        if (result === null) {
          expect(draw).toBeCloseTo(sweep[sweep.length - 1].draw, 5);
          return;
        }
        expect(result.kept + result.to_tax + result.to_pension_credit).toBeCloseTo(1, 6);
      }),
    );
  });

  it("returns nothing for an empty range", () => {
    const sweep = [
      { draw: 0, taxable_draw: 0, income_tax: 0, employee_ni: 0, pension_credit: 0, money_to_spend: 0 },
      { draw: 10, taxable_draw: 10, income_tax: 0, employee_ni: 0, pension_credit: 0, money_to_spend: 10 },
    ];
    expect(sliceBetween(sweep, 5, 5)).toBeNull();
    expect(sliceBetween(sweep, 10, 12)).toBeNull();
  });
});

describe("splitPence", () => {
  it("always adds up to 100p", () => {
    const share = fc.double({ min: -2, max: 3, noNaN: true });
    fc.assert(
      fc.property(share, share, (to_tax, to_pension_credit) => {
        const { kept, tax, lost } = splitPence(slice({ to_tax, to_pension_credit }));
        expect(kept + tax + lost).toBe(100);
      }),
    );
  });

  it("counts a rise in Pension Credit as more kept", () => {
    expect(splitPence(slice({ kept: 1.08, to_pension_credit: -0.08 }))).toEqual({
      kept: 108,
      tax: 0,
      lost: -8,
    });
  });

  it("never reports negative zero", () => {
    const { tax, lost } = splitPence(slice({ to_tax: -0.001, to_pension_credit: -0.001 }));
    expect(Object.is(tax, -0)).toBe(false);
    expect(Object.is(lost, -0)).toBe(false);
  });
});

describe("recorded real-engine runs", () => {
  const runs = Object.entries(recorded) as unknown as [
    string,
    {
      inputs: UKDrawdownYearInput;
      envelope: { outputs: { uk_drawdown_year_result: UKDrawdownYearResult }; caveats: string[] };
    },
  ][];

  it("opens on the figures in the fixture's example", () => {
    expect(recorded.example.inputs).toEqual(EXAMPLE_INPUTS);
  });

  it.each(runs)("%s: the sweep keeps the accounting", (_name, { inputs, envelope }) => {
    const { sweep } = envelope.outputs.uk_drawdown_year_result;
    const income =
      inputs.state_pension +
      inputs.other_pension_income +
      inputs.employment_income +
      inputs.savings_interest +
      inputs.dividend_income;
    for (const row of sweep) {
      const expected = income + row.draw + row.pension_credit - row.income_tax - row.employee_ni;
      expect(Math.abs(row.money_to_spend - expected)).toBeLessThanOrEqual(0.02);
    }
  });

  it.each(runs)("%s: the page reads what the API computed", (_name, { envelope }) => {
    const result = envelope.outputs.uk_drawdown_year_result;
    const chosen = result.at_chosen_draw;
    expect(outcomeAt(result.sweep, chosen.draw)).toEqual(chosen);
    expect(outcomeAt(result.sweep, 0)).toEqual(result.with_no_draw);

    const next = result.next_1000;
    expect(next).not.toBeNull();
    const read = sliceBetween(result.sweep, next!.draw_from, next!.draw_to)!;
    expect(read.kept).toBeCloseTo(next!.kept, 5);
    expect(read.to_tax).toBeCloseTo(next!.to_tax, 5);
    expect(read.to_pension_credit).toBeCloseTo(next!.to_pension_credit, 5);
  });

  it.each(runs)("%s: bands agree with the sweep", (_name, { envelope }) => {
    const { sweep, bands } = envelope.outputs.uk_drawdown_year_result;
    for (const band of bands) {
      if (band.draw_to - band.draw_from < 1_000) continue;
      const read = sliceBetween(sweep, band.draw_from, band.draw_to)!;
      expect(Math.abs(read.kept - band.kept)).toBeLessThan(0.05);
    }
    bands.slice(1).forEach((band, index) => {
      expect(band.draw_from).toBe(bands[index].draw_to);
    });
  });

  it("the example shows the fall in Pension Credit", () => {
    const { bands, markers } = recorded.example.envelope.outputs.uk_drawdown_year_result;
    expect(bands.map((band) => splitPence(band).lost)).toEqual([0, 100, 0, 0]);
    expect(markers).toEqual([
      { kind: "pot_income_covered", draw: 800 },
      { kind: "guarantee_credit_ends", draw: 3016 },
    ]);
  });
});

describe("chartTop", () => {
  it("contains the chosen draw, up to the top of the sweep", () => {
    const amount = fc.integer({ min: 0, max: 5_000_000 });
    fc.assert(
      fc.property(amount, amount, amount, (sweepTop, balance, rawDraw) => {
        const draw = Math.min(rawDraw, balance);
        const top = chartTop(sweepTop, balance, draw);
        expect(top).toBeLessThanOrEqual(sweepTop);
        expect(top).toBeGreaterThanOrEqual(Math.min(draw, sweepTop));
      }),
    );
  });

  it("frames most pots at £100,000 and follows a larger draw", () => {
    expect(chartTop(180_000, 400_000, 30_000)).toBe(100_000);
    expect(chartTop(180_000, 20_000, 2_500)).toBe(20_000);
    expect(chartTop(250_000, 400_000, 200_000)).toBeCloseTo(220_000);
  });
});

describe("niceTicks", () => {
  it("gives evenly spaced ticks inside the range", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 10_000_000 }),
        fc.integer({ min: 1, max: 10_000_000 }),
        fc.integer({ min: 2, max: 8 }),
        (low, span, count) => {
          const ticks = niceTicks(low, low + span, count);
          expect(ticks.length).toBeGreaterThanOrEqual(1);
          expect(ticks.length).toBeLessThanOrEqual(count + 2);
          ticks.forEach((tick) => {
            expect(tick).toBeGreaterThanOrEqual(low - 1e-3);
            expect(tick).toBeLessThanOrEqual(low + span + 1e-3);
          });
          const gaps = ticks.slice(1).map((tick, index) => tick - ticks[index]);
          gaps.forEach((gap) => expect(gap).toBeCloseTo(gaps[0], 3));
        },
      ),
    );
  });

  it("returns one tick for an empty range", () => {
    expect(niceTicks(5, 5, 4)).toEqual([5]);
  });
});

describe("withDrawInBounds", () => {
  const sources: DrawSource[] = ["sipp", "isa", "gia", "cash"];

  it("never draws more than the source holds", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...sources),
        money,
        money,
        (draw_source, balance, draw_amount) => {
          const inputs: UKDrawdownYearInput = {
            ...EXAMPLE_INPUTS,
            draw_source,
            draw_amount,
            sipp_balance: balance,
            isa_balance: balance,
            gia_balance: balance,
            cash_savings: balance,
          };
          const bounded = withDrawInBounds(inputs);
          expect(bounded.draw_amount).toBeLessThanOrEqual(sourceBalance(bounded));
          expect(bounded.draw_amount).toBe(Math.min(draw_amount, balance));
          expect(withDrawInBounds(bounded)).toEqual(bounded);
        },
      ),
    );
  });
});

describe("ageAtTaxYearStart", () => {
  it("counts a birthday on 6 April as reached", () => {
    expect(ageAtTaxYearStart("1958-04-06")).toBe(68);
    expect(ageAtTaxYearStart("1958-04-07")).toBe(67);
    expect(ageAtTaxYearStart("1958-06-15")).toBe(67);
    expect(ageAtTaxYearStart("1958-01-01")).toBe(68);
  });

  it("agrees with counting complete years on the calendar", () => {
    fc.assert(
      fc.property(
        fc.date({ min: new Date("1900-01-01"), max: new Date("2010-12-31"), noInvalidDate: true }),
        (birth) => {
          const iso = birth.toISOString().slice(0, 10);
          const start = Date.UTC(2026, 3, 6);
          let years = 2026 - birth.getUTCFullYear();
          if (Date.UTC(birth.getUTCFullYear() + years, birth.getUTCMonth(), birth.getUTCDate()) > start) {
            years -= 1;
          }
          expect(ageAtTaxYearStart(iso)).toBe(years);
        },
      ),
    );
  });

  it("rejects anything else", () => {
    expect(ageAtTaxYearStart("")).toBeNull();
    expect(ageAtTaxYearStart("15/06/1958")).toBeNull();
  });
});

describe("bandRange", () => {
  const bands = [
    slice({ draw_from: 0, draw_to: 800 }),
    slice({ draw_from: 800, draw_to: 3_016 }),
    slice({ draw_from: 3_016, draw_to: 4_280 }),
    slice({ draw_from: 4_280, draw_to: 10_000 }),
  ];

  it("names the first band by its top and the others as ranges", () => {
    expect(bands.map((_, index) => bandRange(bands, index, 10_000))).toEqual([
      "Up to £800",
      "£800 to £3,016",
      "£3,016 to £4,280",
      "£4,280 to £10,000",
    ]);
  });

  it("leaves the last band open when the sweep stops short of the pot", () => {
    expect(bandRange(bands, 2, 400_000)).toBe("£3,016 to £4,280");
    expect(bandRange(bands, 3, 400_000)).toBe("Above £4,280");
  });
});

describe("wording", () => {
  it("formats pounds", () => {
    expect(pounds(12_375.6)).toBe("£12,376");
    expect(pounds(-0.2)).toBe("£0");
    expect(poundsAndPence(9.9)).toBe("£9.90");
    expect(compactPounds(900)).toBe("£900");
    expect(compactPounds(12_500)).toBe("£12.5k");
    expect(compactPounds(1_500_000)).toBe("£1.5m");
  });

  it("describes where a pound goes", () => {
    expect(describePound(slice())).toBe("You keep the whole pound.");
    expect(describePound(slice({ kept: 0, to_pension_credit: 1 }))).toBe(
      "You keep nothing: you lose 100p of Pension Credit.",
    );
    expect(describePound(slice({ kept: 0.85, to_tax: 0.15 }))).toBe(
      "You keep 85p and pay 15p in tax.",
    );
    expect(describePound(slice({ kept: 0.5, to_tax: 0.2, to_pension_credit: 0.3 }))).toBe(
      "You keep 50p, pay 20p in tax and lose 30p of Pension Credit.",
    );
    expect(describePound(slice({ kept: 1.08, to_pension_credit: -0.08 }))).toBe(
      "You keep the whole pound and gain 8p of Pension Credit.",
    );
    expect(describePound(slice({ kept: 0.93, to_tax: 0.15, to_pension_credit: -0.08 }))).toBe(
      "You keep 93p: you pay 15p in tax and gain 8p of Pension Credit.",
    );
  });

  it("describes the next step of draw", () => {
    expect(describeNextStep(slice())).toBe("Draw another £1,000 and you keep all of it.");
    expect(describeNextStep(slice({ kept: 0.484, to_pension_credit: 0.516 }))).toBe(
      "Draw another £1,000 and you keep £484: you lose £516 of Pension Credit.",
    );
    expect(describeNextStep(slice({ kept: 0, to_pension_credit: 1 }))).toBe(
      "Draw another £1,000 and you keep nothing: you lose £1,000 of Pension Credit.",
    );
    expect(describeNextStep(slice({ draw_to: 500, kept: 0.85, to_tax: 0.15 }))).toBe(
      "Draw another £500 and you keep £425: you pay £75 in tax.",
    );
  });

  it("writes the headline for a draw and for no draw", () => {
    expect(headline("sipp", 2_500, 12_376, "2026/27")).toBe(
      "Draw £2,500 from your pension pot in 2026/27 and you’ll have £12,376 to spend.",
    );
    expect(headline("cash", 0, 11_576, "2026/27")).toBe(
      "Draw nothing in 2026/27 and you’ll have £11,576 to spend.",
    );
  });

  it("compares a draw with drawing nothing", () => {
    const none: DrawdownOutcome = {
      draw: 0,
      taxable_draw: 0,
      income_tax: 0,
      employee_ni: 0,
      pension_credit: 2_216,
      money_to_spend: 11_576,
    };
    expect(
      comparedWithNoDraw(
        { ...none, draw: 2_500, pension_credit: 516, money_to_spend: 12_376 },
        none,
      ),
    ).toBe("You’d have £800 more to spend than if you drew nothing, after losing £1,700 of Pension Credit.");
    expect(
      comparedWithNoDraw(
        { ...none, draw: 10_000, income_tax: 858, pension_credit: 0, money_to_spend: 18_502 },
        none,
      ),
    ).toBe(
      "You’d have £6,926 more to spend than if you drew nothing, after losing £2,216 of Pension Credit and paying £858 more in tax.",
    );
    expect(
      comparedWithNoDraw({ ...none, draw: 100, money_to_spend: 11_676 }, none),
    ).toBe("You’d have £100 more to spend than if you drew nothing.");
    expect(comparedWithNoDraw(none, none)).toBeNull();
  });

  it("asks for a balance when the source holds nothing", () => {
    expect(emptySourceMessage("isa")).toBe("Enter how much you have in your ISAs to see what you’d keep.");
  });
});

describe("isExamplePerson", () => {
  it("treats choices about the draw as still the example", () => {
    expect(isExamplePerson(EXAMPLE_INPUTS)).toBe(true);
    expect(
      isExamplePerson({
        ...EXAMPLE_INPUTS,
        draw_amount: 900,
        draw_source: "cash",
        sipp_draw_pattern: "one_off",
        sipp_tax_free_fraction: 0,
      }),
    ).toBe(true);
  });

  it("stops once a figure about the person changes", () => {
    expect(isExamplePerson({ ...EXAMPLE_INPUTS, state_pension: 12_547.6 })).toBe(false);
    expect(isExamplePerson({ ...EXAMPLE_INPUTS, birth_date: "1960-01-01" })).toBe(false);
    expect(isExamplePerson({ ...EXAMPLE_INPUTS, sipp_balance: 20_000 })).toBe(false);
  });
});

describe("inputProblem", () => {
  it("accepts the example", () => {
    expect(inputProblem(EXAMPLE_INPUTS)).toBeNull();
  });

  it.each([
    [{ birth_date: "" }, "Enter your date of birth."],
    [{ birth_date: "2010-01-01" }, "Enter a date of birth for someone aged 18 to 120 on 6 April 2026."],
    [{ birth_date: "1900-01-01" }, "Enter a date of birth for someone aged 18 to 120 on 6 April 2026."],
    [
      { birth_date: "1975-01-01" },
      "You can’t draw from a pension pot before age 55. Draw from your savings, or set the draw to £0.",
    ],
    [{ cash_savings: 100_000_001 }, "Enter amounts up to £100 million."],
    [{ gilt_yield_percent: 21 }, "Enter a gilt yield of 20% or less."],
    [{ annuity_income_per_1000: 1_001 }, "Enter annuity income of £1,000 or less per £1,000 of pot."],
  ] as [Partial<UKDrawdownYearInput>, string][])("explains %j", (change, message) => {
    expect(inputProblem({ ...EXAMPLE_INPUTS, ...change })).toBe(message);
  });

  it("lets someone under 55 draw from savings or draw nothing", () => {
    const young = { ...EXAMPLE_INPUTS, birth_date: "1975-01-01" };
    expect(inputProblem({ ...young, draw_amount: 0 })).toBeNull();
    expect(inputProblem({ ...young, draw_source: "isa" })).toBeNull();
  });

  it("accepts the API's limits", () => {
    expect(
      inputProblem({
        ...EXAMPLE_INPUTS,
        cash_savings: 100_000_000,
        gilt_yield_percent: 20,
        annuity_income_per_1000: 1_000,
      }),
    ).toBeNull();
  });
});
