import fc from "fast-check";
import { describe, expect, it } from "vitest";
import recorded from "../test/fixtures/us-drawdown-recorded.json";
import type {
  USDrawdownMarker,
  USDrawdownOutcome,
  USDrawdownSlice,
  USDrawdownYearInput,
  USDrawdownYearResult,
  USMedicareSurcharge,
  USRequiredMinimum,
} from "./api-us-drawdown";
import {
  EXAMPLE_FORM,
  EXAMPLE_INPUTS,
  NEW_SPOUSE,
  benefitsMoving,
  cashIncome,
  chartTop,
  comparedWithNoDraw,
  compactDollars,
  coverageAt,
  coverageLost,
  describeCoverageEnds,
  describeDollar,
  describeMedicare,
  describeNextStep,
  describeRequiredMinimum,
  describeShortfall,
  describeStep,
  dollars,
  dollarsAndCents,
  emptySourceMessage,
  headline,
  inputProblem,
  inputsFrom,
  isExamplePerson,
  isStep,
  ladderRange,
  ladderRows,
  markerLabel,
  outcomeAt,
  programChanges,
  programName,
  requiredMinimumAt,
  sliceBetween,
  sourceBalance,
  splitCents,
  taxesOf,
  withDrawInBounds,
} from "./us-drawdown";

// Invariants these tests hold for every input:
// - outcomeAt returns a sweep row exactly at its draw and stays between the two
//   neighbouring rows elsewhere, benefits by program included; reading off the
//   line keeps the accounting and keeps the programs adding up to benefits.
// - Each dollar of draw goes somewhere: kept + tax + benefits lost = 1, and the
//   whole-cent split adds up to exactly 100¢.
// - The ladder covers the same draws as the API's bands, moves the same
//   dollars, keeps every jump on its own row and never shows two neighbours
//   that read the same.
// - Coverage only ever ends as the draw grows.
// - A required minimum's shortfall never goes below zero, and withdrawals plus
//   the shortfall always reach the minimum.
// - The draw never exceeds what the chosen source holds; only a joint return
//   carries a spouse or draws from a spouse's account.
// Differential: the page reads amounts off the sweep, the API computes them
// directly; on recorded real-engine runs the two agree.

const INCOME = 24_000;

const money = fc.integer({ min: 0, max: 5_000_000 }).map((cents) => cents / 100);

/** Rows in draw order that satisfy the accounting identity the API guarantees. */
const sweepRows = fc
  .array(
    fc.record({
      gap: fc.integer({ min: 1, max: 20_000 }),
      federal: money,
      state: money,
      other: money,
      snap: money,
      ssi: money,
      taxed: money,
      medicare: money,
      surcharge: money,
    }),
    { minLength: 2, maxLength: 40 },
  )
  .map((rows): USDrawdownOutcome[] => {
    let draw = 0;
    return rows.map(({ gap, federal, state, other, snap, ssi, taxed, medicare, surcharge }, i) => {
      if (i > 0) draw += gap;
      const benefits = snap + ssi;
      return {
        draw,
        taxable_draw: draw,
        federal_income_tax: federal,
        state_income_tax: state,
        other_taxes: other,
        benefits,
        benefits_by_program: { snap, ssi },
        taxable_social_security: taxed,
        medicare_income: medicare,
        later_medicare_surcharge: surcharge,
        money_to_spend: INCOME + draw + benefits - federal - state - other,
      };
    });
  });

/** Draws come in whole cents: a slider step or a typed amount. */
const sweepAndDraw = sweepRows.chain((sweep) =>
  fc
    .integer({ min: 0, max: sweep[sweep.length - 1].draw * 100 })
    .map((cents) => ({ sweep, draw: cents / 100 })),
);

const NUMBERS: (keyof USDrawdownOutcome)[] = [
  "federal_income_tax",
  "state_income_tax",
  "other_taxes",
  "benefits",
  "taxable_social_security",
  "medicare_income",
  "later_medicare_surcharge",
  "money_to_spend",
];

function between(value: number, a: number, b: number) {
  return value >= Math.min(a, b) - 1e-9 && value <= Math.max(a, b) + 1e-9;
}

describe("outcomeAt", () => {
  it("returns the row exactly at every sweep point", () => {
    fc.assert(
      fc.property(sweepRows, (sweep) => {
        for (const row of sweep) expect(outcomeAt(sweep, row.draw)).toEqual(row);
      }),
    );
  });

  it("stays between the neighbouring rows, program by program", () => {
    fc.assert(
      fc.property(sweepAndDraw, ({ sweep, draw }) => {
        const row = outcomeAt(sweep, draw);
        const after = sweep.findIndex((candidate) => candidate.draw >= draw);
        const a = sweep[Math.max(after - 1, 0)];
        const b = sweep[after];
        for (const key of NUMBERS) {
          expect(between(row[key] as number, a[key] as number, b[key] as number)).toBe(true);
        }
        for (const program of Object.keys(a.benefits_by_program)) {
          expect(
            between(
              row.benefits_by_program[program],
              a.benefits_by_program[program],
              b.benefits_by_program[program],
            ),
          ).toBe(true);
        }
      }),
    );
  });

  it("keeps the accounting, and the programs adding up, between sweep points", () => {
    fc.assert(
      fc.property(sweepAndDraw, ({ sweep, draw }) => {
        const row = outcomeAt(sweep, draw);
        expect(row.money_to_spend).toBeCloseTo(INCOME + row.draw + row.benefits - taxesOf(row), 6);
        const programs = Object.values(row.benefits_by_program).reduce((a, b) => a + b, 0);
        expect(programs).toBeCloseTo(row.benefits, 6);
      }),
    );
  });

  it("never shares the program record of the row it starts from", () => {
    const sweep = fc.sample(sweepRows, { numRuns: 1, seed: 7 })[0];
    const middle = (sweep[0].draw + sweep[1].draw) / 2;
    const row = outcomeAt(sweep, middle);
    expect(row.benefits_by_program).not.toBe(sweep[0].benefits_by_program);
  });
});

describe("sliceBetween", () => {
  it("sends each dollar of draw somewhere", () => {
    fc.assert(
      fc.property(sweepAndDraw, fc.integer({ min: 1, max: 40_000 }), ({ sweep, draw }, step) => {
        const top = sweep[sweep.length - 1].draw;
        const slice = sliceBetween(sweep, draw, Math.min(draw + step, top));
        if (!slice) return;
        // A range can be a single cent wide, so allow for rounding in the division.
        expect(slice.kept + slice.to_tax + slice.to_benefits).toBeCloseTo(1, 6);
      }),
    );
  });

  it("returns nothing for an empty range", () => {
    const sweep = fc.sample(sweepRows, { numRuns: 1, seed: 3 })[0];
    expect(sliceBetween(sweep, 10, 10)).toBeNull();
  });
});

describe("splitCents", () => {
  it("always adds up to 100¢", () => {
    const share = fc.double({ min: -2, max: 3, noNaN: true });
    fc.assert(
      fc.property(share, share, (to_tax, to_benefits) => {
        const split = splitCents({
          draw_from: 0,
          draw_to: 1,
          kept: 1 - to_tax - to_benefits,
          to_tax,
          to_benefits,
          social_security_taxed: 0,
        });
        expect(split.kept + split.tax + split.lost).toBe(100);
      }),
    );
  });

  it("never reports negative zero", () => {
    const split = splitCents(slice(0, 1, -0.001, -0.001));
    expect(Object.is(split.tax, -0)).toBe(false);
    expect(Object.is(split.lost, -0)).toBe(false);
  });
});

function slice(
  draw_from: number,
  draw_to: number,
  to_tax = 0,
  to_benefits = 0,
  social_security_taxed = 0,
): USDrawdownSlice {
  return {
    draw_from,
    draw_to,
    kept: 1 - to_tax - to_benefits,
    to_tax,
    to_benefits,
    social_security_taxed,
  };
}

/** Contiguous bands with phase-outs, changes of rate and the odd jump. */
const bandList = fc
  .array(
    fc.record({
      width: fc.integer({ min: 1, max: 50_000 }),
      to_tax: fc.oneof(
        fc.double({ min: -0.2, max: 0.6, noNaN: true }),
        fc.constantFrom(0, 0.12, 0.22),
      ),
      to_benefits: fc.oneof(
        fc.constantFrom(0, 0, 0.3, 1),
        fc.double({ min: -0.2, max: 1, noNaN: true }),
        fc.double({ min: 2, max: 400, noNaN: true }),
      ),
      taxed: fc.constantFrom(0, 0.5, 0.85),
    }),
    { minLength: 1, maxLength: 30 },
  )
  .map((specs) => {
    let from = 0;
    return specs.map(({ width, to_tax, to_benefits, taxed }) => {
      const band = slice(from, from + width, to_tax, to_benefits, taxed);
      from += width;
      return band;
    });
  });

describe("ladderRows", () => {
  it("covers the same draws and moves the same dollars as the bands", () => {
    fc.assert(
      fc.property(bandList, (bands) => {
        const rows = ladderRows(bands);
        expect(rows[0].draw_from).toBe(bands[0].draw_from);
        expect(rows[rows.length - 1].draw_to).toBe(bands[bands.length - 1].draw_to);
        rows.slice(1).forEach((row, index) => expect(row.draw_from).toBe(rows[index].draw_to));
        const moved = (list: USDrawdownSlice[], key: keyof USDrawdownSlice) =>
          list.reduce(
            (sum, band) => sum + (band[key] as number) * (band.draw_to - band.draw_from),
            0,
          );
        const size = (list: USDrawdownSlice[], key: keyof USDrawdownSlice) =>
          list.reduce(
            (sum, band) => sum + Math.abs((band[key] as number) * (band.draw_to - band.draw_from)),
            0,
          );
        for (const key of ["kept", "to_tax", "to_benefits", "social_security_taxed"] as const) {
          const scale = Math.max(1, size(bands, key));
          expect(Math.abs(moved(rows, key) - moved(bands, key)) / scale).toBeLessThan(1e-9);
        }
        for (const row of rows) expect(row.kept + row.to_tax + row.to_benefits).toBeCloseTo(1, 9);
      }),
    );
  });

  it("keeps every jump on its own row and never repeats a neighbour", () => {
    fc.assert(
      fc.property(bandList, (bands) => {
        const rows = ladderRows(bands);
        expect(rows.filter((row) => row.step)).toHaveLength(bands.filter(isStep).length);
        rows.slice(1).forEach((row, index) => {
          const previous = rows[index];
          if (row.step || previous.step) return;
          const same =
            splitCents(row).tax === splitCents(previous).tax &&
            splitCents(row).lost === splitCents(previous).lost &&
            Math.round(row.social_security_taxed * 100) ===
              Math.round(previous.social_security_taxed * 100);
          expect(same).toBe(false);
        });
      }),
    );
  });

  it("treats a phase-out of up to a dollar per dollar as a phase-out, not a jump", () => {
    expect(isStep(slice(0, 1_000, 0, 1))).toBe(false);
    expect(isStep(slice(0, 10, 0, 20.7))).toBe(true);
    expect(isStep(slice(0, 10, 12, 0))).toBe(true);
  });
});

describe("coverageAt", () => {
  const markersArb = fc.array(
    fc.record({
      program: fc.constantFrom("medicaid", "msp"),
      draw: fc.integer({ min: 0, max: 100_000 }),
    }),
    { maxLength: 4 },
  );

  it("only ever ends coverage as the draw grows", () => {
    fc.assert(
      fc.property(
        markersArb,
        fc.boolean(),
        fc.boolean(),
        fc.integer({ min: 0, max: 100_000 }),
        fc.integer({ min: 0, max: 100_000 }),
        (ends, medicaid, msp, a, b) => {
          const markers: USDrawdownMarker[] = ends.map(({ program, draw }) => ({
            kind: "coverage_ends",
            draw,
            program,
            amount: null,
          }));
          const start = { medicaid, msp };
          const low = coverageAt(start, markers, Math.min(a, b));
          const high = coverageAt(start, markers, Math.max(a, b));
          for (const name of ["medicaid", "msp"] as const) {
            if (high[name]) expect(low[name]).toBe(true);
            if (!start[name]) expect(high[name]).toBe(false);
          }
        },
      ),
    );
  });

  it("ignores markers of other kinds", () => {
    const markers: USDrawdownMarker[] = [
      { kind: "benefit_ends", draw: 100, program: "snap", amount: null },
    ];
    expect(coverageAt({ medicaid: true, msp: true }, markers, 1_000)).toEqual({
      medicaid: true,
      msp: true,
    });
  });
});

function minimum(overrides: Partial<USRequiredMinimum> = {}): USRequiredMinimum {
  return {
    person: "you",
    age: 75,
    balance: 246_000,
    divisor: 24.6,
    amount: 10_000,
    other_withdrawals: 0,
    withdrawn: 0,
    shortfall: 10_000,
    excise_tax_rate: 0.25,
    excise_tax_on_shortfall: 2_500,
    ...overrides,
  };
}

describe("requiredMinimumAt", () => {
  it("never falls below zero and always reaches the minimum", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 200_000 }),
        fc.integer({ min: 0, max: 50_000 }),
        fc.integer({ min: 0, max: 300_000 }),
        fc.constantFrom("traditional", "roth", "taxable", "cash"),
        (amount, other, draw, source) => {
          const atDraw = requiredMinimumAt(minimum({ amount, other_withdrawals: other }), {
            ...EXAMPLE_INPUTS,
            draw_source: source as USDrawdownYearInput["draw_source"],
            draw_amount: draw,
          });
          expect(atDraw.shortfall).toBeGreaterThanOrEqual(0);
          expect(atDraw.withdrawn + atDraw.shortfall).toBeGreaterThanOrEqual(amount - 1e-9);
          expect(atDraw.excise).toBeCloseTo(0.25 * atDraw.shortfall, 9);
        },
      ),
    );
  });

  it("counts only a traditional draw from the person's own account", () => {
    const joint: USDrawdownYearInput = {
      ...EXAMPLE_INPUTS,
      filing_status: "married_filing_jointly",
      spouse: { ...NEW_SPOUSE, traditional_balance: 100_000 },
      draw_owner: "spouse",
      draw_amount: 4_000,
    };
    expect(requiredMinimumAt(minimum(), joint).withdrawn).toBe(0);
    expect(requiredMinimumAt(minimum({ person: "spouse" }), joint).withdrawn).toBe(4_000);
  });
});

describe("inputsFrom", () => {
  const formArb = fc.record({
    filing_status: fc.constantFrom("single", "married_filing_jointly"),
    draw_source: fc.constantFrom("traditional", "roth", "taxable", "cash"),
    draw_owner: fc.constantFrom("you", "spouse"),
    draw_amount: fc.integer({ min: 0, max: 2_000_000 }),
    you_traditional: fc.integer({ min: 0, max: 1_000_000 }),
    spouse_roth: fc.integer({ min: 0, max: 1_000_000 }),
    cash: fc.integer({ min: 0, max: 100_000 }),
  });

  it("never draws more than the source holds and carries a spouse only when filing jointly", () => {
    fc.assert(
      fc.property(formArb, (picked) => {
        const inputs = inputsFrom({
          ...EXAMPLE_FORM,
          filing_status: picked.filing_status as USDrawdownYearInput["filing_status"],
          draw_source: picked.draw_source as USDrawdownYearInput["draw_source"],
          draw_owner: picked.draw_owner as USDrawdownYearInput["draw_owner"],
          draw_amount: picked.draw_amount,
          you: { ...EXAMPLE_FORM.you, traditional_balance: picked.you_traditional },
          spouse: { ...NEW_SPOUSE, roth_balance: picked.spouse_roth },
          cash_savings: picked.cash,
        });
        const joint = inputs.filing_status === "married_filing_jointly";
        expect(inputs.draw_amount).toBeLessThanOrEqual(sourceBalance(inputs));
        expect(inputs.spouse === null).toBe(!joint);
        if (inputs.draw_owner === "spouse") {
          expect(joint).toBe(true);
          expect(["traditional", "roth"]).toContain(inputs.draw_source);
        }
      }),
    );
  });

  it("keeps a spouse's figures in the form through a switch to single and back", () => {
    const spouse = { ...NEW_SPOUSE, social_security: 18_000 };
    const form = { ...EXAMPLE_FORM, filing_status: "single" as const, spouse };
    expect(inputsFrom(form).spouse).toBeNull();
    expect(inputsFrom({ ...form, filing_status: "married_filing_jointly" }).spouse).toEqual(spouse);
  });
});

describe("withDrawInBounds", () => {
  it("stops the draw at the balance", () => {
    expect(withDrawInBounds({ ...EXAMPLE_INPUTS, draw_amount: 400_000 }).draw_amount).toBe(250_000);
    expect(withDrawInBounds(EXAMPLE_INPUTS)).toBe(EXAMPLE_INPUTS);
  });
});

describe("chartTop", () => {
  it("contains the chosen draw, up to the top of the sweep", () => {
    const amount = fc.integer({ min: 0, max: 5_000_000 });
    fc.assert(
      fc.property(amount, amount, amount, (sweepTop, balance, rawDraw) => {
        const draw = Math.min(rawDraw, balance, sweepTop);
        const top = chartTop(sweepTop, balance, draw);
        expect(top).toBeLessThanOrEqual(sweepTop);
        expect(top).toBeGreaterThanOrEqual(draw);
      }),
    );
  });
});

type Recorded = {
  inputs: USDrawdownYearInput;
  envelope: {
    outputs: { us_drawdown_year_result: USDrawdownYearResult };
    caveats: string[];
  };
};

const runs = Object.entries(recorded) as unknown as [string, Recorded][];
const resultOf = (name: keyof typeof recorded) =>
  (recorded[name] as unknown as Recorded).envelope.outputs.us_drawdown_year_result;

/**
 * The API works out a range's rates from the engine's own figures; the page
 * reads them off the sweep, which holds each amount to the cent. Across a
 * range the dollars moved can then differ by a cent for each rounded amount:
 * one for money to spend, benefits and taxable Social Security, three for tax.
 */
function expectSameDollars(read: USDrawdownSlice, api: USDrawdownSlice) {
  expect(read.draw_from).toBe(api.draw_from);
  expect(read.draw_to).toBe(api.draw_to);
  const width = api.draw_to - api.draw_from;
  const off = (key: "kept" | "to_tax" | "to_benefits" | "social_security_taxed") =>
    Math.abs(read[key] - api[key]) * width;
  expect(off("kept")).toBeLessThanOrEqual(0.010_001);
  expect(off("to_tax")).toBeLessThanOrEqual(0.030_001);
  expect(off("to_benefits")).toBeLessThanOrEqual(0.010_001);
  expect(off("social_security_taxed")).toBeLessThanOrEqual(0.010_001);
}

describe("recorded real-engine runs", () => {
  it("opens on the figures in the fixture's example", () => {
    expect(recorded.example.inputs).toEqual(EXAMPLE_INPUTS);
  });

  it.each(runs)("%s: the sweep keeps the accounting", (_name, { inputs, envelope }) => {
    const { sweep } = envelope.outputs.us_drawdown_year_result;
    const income = cashIncome(inputs);
    for (const row of sweep) {
      expect(
        Math.abs(row.money_to_spend - (income + row.draw + row.benefits - taxesOf(row))),
      ).toBeLessThanOrEqual(0.02);
      const programs = Object.values(row.benefits_by_program).reduce((a, b) => a + b, 0);
      expect(Math.abs(programs - row.benefits)).toBeLessThanOrEqual(1);
    }
  });

  it.each(runs)("%s: the page reads what the API computed", (_name, { inputs, envelope }) => {
    const result = envelope.outputs.us_drawdown_year_result;
    const chosen = result.at_chosen_draw;
    expect(outcomeAt(result.sweep, chosen.draw)).toEqual(chosen);
    expect(outcomeAt(result.sweep, 0)).toEqual(result.with_no_draw);

    const next = result.next_1000!;
    expectSameDollars(sliceBetween(result.sweep, next.draw_from, next.draw_to)!, next);

    expect(coverageAt(result.coverage_with_no_draw, result.markers, chosen.draw)).toEqual(
      result.coverage_at_chosen_draw,
    );

    for (const required of result.required_minimums) {
      const atDraw = requiredMinimumAt(required, inputs);
      expect(atDraw.withdrawn).toBeCloseTo(required.withdrawn, 2);
      expect(atDraw.shortfall).toBeCloseTo(required.shortfall, 2);
      expect(atDraw.excise).toBeCloseTo(required.excise_tax_on_shortfall, 2);
    }
  });

  it.each(runs)("%s: bands agree with the sweep", (_name, { envelope }) => {
    const { sweep, bands } = envelope.outputs.us_drawdown_year_result;
    for (const band of bands)
      expectSameDollars(sliceBetween(sweep, band.draw_from, band.draw_to)!, band);
    bands.slice(1).forEach((band, index) => {
      expect(band.draw_from).toBe(bands[index].draw_to);
    });
  });

  it("the example's ladder shows SNAP's two steps and its end", () => {
    const { bands, sweep } = resultOf("example");
    const steps = ladderRows(bands).filter((row) => row.step);
    expect(
      steps.map((row) =>
        describeStep(outcomeAt(sweep, row.draw_from), outcomeAt(sweep, row.draw_to)),
      ),
    ).toEqual(["SNAP falls by $216 all at once.", "SNAP ends, taking $75 all at once."]);
  });

  it("the low-income household loses SNAP, CSFP food boxes and its coverage", () => {
    const { bands, sweep, markers } = resultOf("low_income");
    const steps = ladderRows(bands).filter((row) => row.step);
    expect(
      steps.map((row) =>
        describeStep(outcomeAt(sweep, row.draw_from), outcomeAt(sweep, row.draw_to)),
      ),
    ).toEqual([
      "SNAP falls by $216 all at once.",
      "SNAP ends, taking $75 all at once.",
      "CSFP food boxes end, taking $651 all at once.",
    ]);
    expect(markers.map(markerLabel)).toEqual([
      "SNAP ends",
      "Medicare Savings Program ends",
      "CSFP food boxes end",
      "Medicaid ends",
    ]);
    expect(describeCoverageEnds(markers)).toBe(
      "Help from a Medicare Savings Program ends at a draw of about $7,394 and Medicaid at about $12,785.",
    );
  });
});

function outcome(
  draw: number,
  programs: Record<string, number>,
  federal = 0,
  overrides: Partial<USDrawdownOutcome> = {},
): USDrawdownOutcome {
  const benefits = Object.values(programs).reduce((a, b) => a + b, 0);
  return {
    draw,
    taxable_draw: draw,
    federal_income_tax: federal,
    state_income_tax: 0,
    other_taxes: 0,
    benefits,
    benefits_by_program: programs,
    taxable_social_security: 0,
    medicare_income: draw,
    later_medicare_surcharge: 0,
    money_to_spend: INCOME + draw + benefits - federal,
    ...overrides,
  };
}

describe("wording", () => {
  it("formats dollars", () => {
    expect(dollars(51_473.73)).toBe("$51,474");
    expect(dollars(-0.4)).toBe("$0");
    expect(dollarsAndCents(2_434.8)).toBe("$2,434.80");
    expect(compactDollars(900)).toBe("$900");
    expect(compactDollars(10_000)).toBe("$10k");
    expect(compactDollars(1_500_000)).toBe("$1.5M");
    expect(compactDollars(-5_000)).toBe("−$5k");
    expect(compactDollars(-0.2)).toBe("$0");
  });

  it("names programs, and humanizes one it doesn't know", () => {
    expect(programName("snap").label).toBe("SNAP");
    expect(programName("commodity_supplemental_food_program").plural).toBe(true);
    expect(programName("trump_dividend")).toEqual({
      label: "Trump dividend",
      inline: "trump dividend",
    });
  });

  it("describes where a dollar goes", () => {
    expect(describeDollar(slice(0, 1, 0, 0))).toBe("You keep the whole dollar.");
    expect(describeDollar(slice(0, 1, 0.26, 0, 0.85))).toBe(
      "You keep 74¢ and pay 26¢ in tax. Each dollar also makes 85¢ more of your Social Security taxable.",
    );
    expect(describeDollar(slice(0, 1, 0, 0.45), "SNAP")).toBe("You keep 55¢ and lose 45¢ of SNAP.");
    expect(describeDollar(slice(0, 1, 0.1, 1), "SSI")).toBe(
      "You keep nothing: you pay 10¢ in tax and lose 100¢ of SSI.",
    );
    expect(describeDollar(slice(0, 1, 0.1, -0.1), "SNAP")).toBe(
      "You keep the whole dollar: you pay 10¢ in tax and gain 10¢ of SNAP.",
    );
    expect(describeDollar(slice(0, 1, 0, -0.08))).toBe("You keep $1.08: you gain 8¢ of benefits.");
  });

  it("names the one program that moves across a range, or lists several", () => {
    const from = outcome(0, { snap: 1_000, commodity_supplemental_food_program: 651 });
    expect(
      benefitsMoving(from, outcome(1_000, { snap: 550, commodity_supplemental_food_program: 651 })),
    ).toBe("SNAP");
    expect(
      benefitsMoving(from, outcome(1_000, { snap: 550, commodity_supplemental_food_program: 0 })),
    ).toBe("benefits (SNAP and CSFP food boxes)");
    expect(benefitsMoving(from, from)).toBe("benefits");
  });

  it("describes the next step of draw, program by program", () => {
    const from = outcome(3_000, { snap: 369, commodity_supplemental_food_program: 651 });
    const to = outcome(4_000, { snap: 291, commodity_supplemental_food_program: 651 });
    const next = slice(3_000, 4_000, 0, 0.078);
    expect(describeNextStep(next, from, to)).toBe(
      "Draw another $1,000 and you keep $922: you lose $78 of SNAP.",
    );

    const cliff = outcome(4_000, { snap: 0, commodity_supplemental_food_program: 0 });
    expect(describeNextStep(slice(3_000, 4_000, 0, 1.02), from, cliff)).toBe(
      "Draw another $1,000 and you’d have $20 less to spend: you lose $651 of CSFP food boxes and $369 of SNAP.",
    );
    const mixed = outcome(4_000, { snap: 0, commodity_supplemental_food_program: 700 }, 50);
    expect(describeNextStep(slice(3_000, 4_000, 0.05, 0.32), from, mixed)).toBe(
      "Draw another $1,000 and you keep $630: you pay $50 in tax, lose $369 of SNAP and gain $49 of CSFP food boxes.",
    );
    expect(describeNextStep(slice(0, 1_000), outcome(0, {}), outcome(1_000, {}))).toBe(
      "Draw another $1,000 and you keep all of it.",
    );
    expect(
      describeNextStep(slice(0, 1_000, 0.263, 0, 0.85), outcome(0, {}), outcome(1_000, {}, 263)),
    ).toBe(
      "Draw another $1,000 and you keep $737: you pay $263 in tax. It also makes $850 more of your Social Security taxable.",
    );
  });

  it("describes a jump, and agrees with the plural", () => {
    const before = outcome(7_290, { snap: 291 });
    expect(describeStep(before, outcome(7_300, { snap: 75 }))).toBe(
      "SNAP falls by $216 all at once.",
    );
    expect(
      describeStep(
        outcome(11_940, { commodity_supplemental_food_program: 651 }),
        outcome(11_942, { commodity_supplemental_food_program: 0 }),
      ),
    ).toBe("CSFP food boxes end, taking $651 all at once.");
    expect(describeStep(outcome(0, {}), outcome(10, {}, 500))).toBe(
      "Your tax rises by $500 all at once.",
    );
  });

  it("writes the headline for each source and for no draw", () => {
    expect(headline("traditional", "you", 30_000, 51_473.73)).toBe(
      "Draw $30,000 from your traditional IRA or 401(k) in 2026 and you’ll have $51,474 to spend.",
    );
    expect(headline("roth", "spouse", 5_000, 30_000)).toBe(
      "Draw $5,000 from your spouse’s Roth IRA in 2026 and you’ll have $30,000 to spend.",
    );
    expect(headline("cash", "you", 0, 24_290)).toBe(
      "Draw nothing in 2026 and you’ll have $24,290 to spend.",
    );
  });

  it("compares a draw with drawing nothing", () => {
    const none = outcome(0, { snap: 291 });
    const chosen = outcome(30_000, { snap: 0 }, 2_525);
    expect(comparedWithNoDraw(chosen, none)).toBe(
      "You’d have $27,184 more to spend than if you drew nothing, after losing $291 of SNAP and paying $2,525 more in tax.",
    );
    expect(comparedWithNoDraw(none, none)).toBeNull();
    expect(comparedWithNoDraw(outcome(1_000, {}), outcome(0, {}))).toBe(
      "You’d have $1,000 more to spend than if you drew nothing.",
    );
  });

  it("lists program changes biggest loss first", () => {
    const changes = programChanges(
      outcome(0, { snap: 300, ssi: 100, tanf: 0 }),
      outcome(1, { snap: 0, ssi: 90, tanf: 50 }),
    );
    expect(changes.map((change) => change.program)).toEqual(["snap", "ssi", "tanf"]);
  });

  it("says where coverage ends and what a draw loses", () => {
    expect(describeCoverageEnds([])).toBeNull();
    expect(
      describeCoverageEnds([
        { kind: "coverage_ends", draw: 12_785.42, program: "medicaid", amount: null },
      ]),
    ).toBe("Medicaid ends at a draw of about $12,785.");
    expect(coverageLost({ medicaid: true, msp: true }, { medicaid: true, msp: false })).toEqual([
      "msp",
    ]);
  });

  const SURCHARGE: USMedicareSurcharge = {
    premium_year: 2028,
    rates_year: 2026,
    people_on_medicare: 1,
    lines: [109_001, 137_001, 171_001, 205_001, 500_000],
    at_chosen_draw: 0,
    with_no_draw: 0,
  };

  it("explains Medicare premiums below the first line", () => {
    const markers: USDrawdownMarker[] = [
      { kind: "medicare_surcharge_step", draw: 88_601, program: null, amount: 1_148.4 },
    ];
    expect(
      describeMedicare(outcome(30_000, {}, 0, { medicare_income: 41_300 }), SURCHARGE, markers),
    ).toEqual([
      "This draw puts your 2026 income for Medicare at $41,300: adjusted gross income plus tax-exempt interest.",
      "Your 2028 premiums rise once it reaches $109,001, which a draw of about $88,601 would do, adding $1,148 a year.",
      "We apply Medicare’s 2026 income lines and amounts. Medicare raises the lines with inflation, so its 2028 lines will exceed these.",
    ]);
  });

  it("explains Medicare premiums above a line, for a couple", () => {
    const couple = { ...SURCHARGE, people_on_medicare: 2, lines: [218_001, 274_001] };
    const row = outcome(150_000, {}, 0, {
      medicare_income: 225_250,
      later_medicare_surcharge: 2_296.8,
    });
    expect(describeMedicare(row, couple, [])).toEqual([
      "This draw puts your 2026 income for Medicare at $225,250: adjusted gross income plus tax-exempt interest.",
      "That reaches Medicare’s $218,001 income line, so your 2028 Part B and Part D premiums rise by $2,297 for the year between the two of you.",
      "Your 2028 premiums rise again once it reaches $274,001.",
      "We apply Medicare’s 2026 income lines and amounts. Medicare raises the lines with inflation, so its 2028 lines will exceed these.",
    ]);
  });

  it("drops the inflation sentence once Medicare publishes the premium year's lines", () => {
    const published = { ...SURCHARGE, rates_year: 2028 };
    const row = outcome(30_000, {}, 0, { medicare_income: 41_300 });
    expect(describeMedicare(row, published, []).at(-1)).toBe(
      "We apply Medicare’s 2028 income lines and amounts.",
    );
  });

  it("explains a required minimum the draw covers and one it misses", () => {
    const covered = minimum({ amount: 9_803.92, balance: 250_000, divisor: 25.5, age: 74 });
    expect(
      describeRequiredMinimum(covered, requiredMinimumAt(covered, EXAMPLE_INPUTS), EXAMPLE_INPUTS),
    ).toEqual([
      "You must take at least $9,804 from traditional IRAs and 401(k)s in 2026. We divide your $250,000 balance at the end of 2025 by 25.5, the IRS Uniform Lifetime Table’s factor for age 74.",
      "This draw covers it.",
    ]);
    const roth = { ...EXAMPLE_INPUTS, draw_source: "roth" as const };
    expect(describeRequiredMinimum(covered, requiredMinimumAt(covered, roth), roth)[1]).toBe(
      "Withdrawing nothing falls $9,804 short, so you’d owe an excise tax of $2,451 (25% of the shortfall). We leave it out of money to spend.",
    );
    const spouse = minimum({ person: "spouse", other_withdrawals: 12_000 });
    expect(
      describeRequiredMinimum(spouse, requiredMinimumAt(spouse, EXAMPLE_INPUTS), EXAMPLE_INPUTS),
    ).toEqual([
      "Your spouse must take at least $10,000 from traditional IRAs and 401(k)s in 2026. We divide their $246,000 balance at the end of 2025 by 24.6, the IRS Uniform Lifetime Table’s factor for age 75.",
      "Their other withdrawals cover it.",
    ]);
    const spouseShort = minimum({ person: "spouse", other_withdrawals: 2_000 });
    expect(
      describeRequiredMinimum(
        spouseShort,
        requiredMinimumAt(spouseShort, EXAMPLE_INPUTS),
        EXAMPLE_INPUTS,
      )[1],
    ).toBe(
      "Withdrawals of $2,000 fall $8,000 short, so your spouse would owe an excise tax of $2,000 (25% of the shortfall). We leave it out of money to spend.",
    );
  });

  it("warns of a shortfall in the words of whoever owns the account", () => {
    const short = { withdrawn: 0, shortfall: 9_803.92, excise: 2_450.98 };
    expect(describeShortfall(minimum(), short)).toBe(
      "You’d fall $9,804 short of your required minimum and owe an excise tax of $2,451, which we leave out of money to spend.",
    );
    expect(describeShortfall(minimum({ person: "spouse" }), short)).toBe(
      "Your spouse would fall $9,804 short of their required minimum and owe an excise tax of $2,451, which we leave out of money to spend.",
    );
  });

  it("labels the chart's markers", () => {
    expect(markerLabel({ kind: "benefit_ends", draw: 1, program: "snap", amount: null })).toBe(
      "SNAP ends",
    );
    expect(markerLabel({ kind: "coverage_ends", draw: 1, program: "msp", amount: null })).toBe(
      "Medicare Savings Program ends",
    );
    expect(
      markerLabel({ kind: "medicare_surcharge_step", draw: 1, program: null, amount: 1_148.4 }),
    ).toBe("2028 Medicare premiums up $1,148");
    expect(
      markerLabel({ kind: "required_minimum_reached", draw: 1, program: null, amount: 9_804 }),
    ).toBe("Covers the required minimum");
  });

  it("names the ladder's ranges, a jump by where it lands", () => {
    const rows = ladderRows([
      slice(0, 7_291.67),
      slice(7_291.67, 7_302.08, 0, 20.75),
      slice(7_302.08, 9_000),
    ]);
    expect(rows.map((_row, index) => ladderRange(rows, index, 250_000))).toEqual([
      "Up to $7,292",
      "At about $7,302",
      "Above $7,302",
    ]);
  });

  it("asks for a balance when the source holds nothing", () => {
    expect(emptySourceMessage("roth", "spouse")).toBe(
      "Enter how much your spouse has in their Roth IRA to see what you’d keep.",
    );
  });
});

describe("isExamplePerson", () => {
  it("treats choices about the draw as still the example", () => {
    expect(isExamplePerson(EXAMPLE_INPUTS)).toBe(true);
    expect(
      isExamplePerson({
        ...EXAMPLE_INPUTS,
        draw_source: "cash",
        draw_amount: 1_000,
        taxable_gain_share: 0.9,
      }),
    ).toBe(true);
  });

  it("stops once a figure about the person changes, whatever the key order", () => {
    expect(isExamplePerson({ ...EXAMPLE_INPUTS, state: "TX" })).toBe(false);
    expect(
      isExamplePerson({
        ...EXAMPLE_INPUTS,
        you: { ...EXAMPLE_INPUTS.you, social_security: 25_000 },
      }),
    ).toBe(false);
    const reordered = Object.fromEntries(Object.entries(EXAMPLE_INPUTS).reverse());
    expect(isExamplePerson(reordered as unknown as USDrawdownYearInput)).toBe(true);
  });
});

describe("inputProblem", () => {
  it("accepts the example", () => {
    expect(inputProblem(EXAMPLE_INPUTS)).toBeNull();
  });

  it("asks for a birth year that makes someone 65 to 120 by the end of 2026", () => {
    expect(
      inputProblem({ ...EXAMPLE_INPUTS, you: { ...EXAMPLE_INPUTS.you, birth_year: 1962 } }),
    ).toBe(
      "Enter your birth year, from 1906 to 1961. We cover people 65 or older by the end of 2026.",
    );
    expect(
      inputProblem({ ...EXAMPLE_INPUTS, you: { ...EXAMPLE_INPUTS.you, birth_year: 19 } }),
    ).not.toBeNull();
    expect(
      inputProblem({
        ...EXAMPLE_INPUTS,
        filing_status: "married_filing_jointly",
        spouse: { ...NEW_SPOUSE, birth_year: 1970 },
      }),
    ).toBe(
      "Enter your spouse’s birth year, from 1906 to 1961. We cover people 65 or older by the end of 2026.",
    );
    expect(
      inputProblem({ ...EXAMPLE_INPUTS, you: { ...EXAMPLE_INPUTS.you, birth_year: 1961 } }),
    ).toBeNull();
  });

  it("accepts the API's limits on amounts", () => {
    expect(inputProblem({ ...EXAMPLE_INPUTS, cash_savings: 100_000_001 })).toBe(
      "Enter amounts up to $100 million.",
    );
    expect(inputProblem({ ...EXAMPLE_INPUTS, cash_savings: 100_000_000 })).toBeNull();
  });
});
