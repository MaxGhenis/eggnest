import fc from "fast-check";
import { describe, expect, it } from "vitest";
import ukRecorded from "../test/fixtures/uk-drawdown-recorded.json";
import usRecorded from "../test/fixtures/us-drawdown-recorded.json";
import { ApiError, NetworkError, SimulationError, TimeoutError } from "./api";
import {
  drawLimitNote,
  failureMessage,
  joinBands,
  jumpAround,
  keyedDraw,
  labelPlacement,
  ladderRangeIn,
  ladderRowsOf,
  resultIsStale,
  rowAt,
  sameDraw,
  stepPlaceIn,
  turningPoints,
} from "./drawdown";

// Invariants these tests hold for every input:
// - rowAt returns the API's own row at each of its draws, and every row it
//   reads lies on a straight line through two of the API's rows, so at every
//   draw its figures add up as the rows do: money to spend is income plus the
//   draw, less tax, plus benefits, and the benefits by program sum to the
//   benefits (page2, after us-page-2).
// - Between two rows that bracket a jump the API located, rowAt reads one
//   side of the jump, never a blend across it that no draw yields: the
//   nearer row, carried to the draw at the rate of a line beside the jump.
//   Each side's line runs from the row beside the jump out to the first row
//   a dollar or more away, over rows outside any jump, so cent rounding can
//   swing its rate by a cent a dollar at most; where no row is that far it
//   runs to the farthest. The nearer side's line serves where it spans a
//   dollar, else the other side's where that does (at either end of the
//   sweep, or beside another jump), else the wider (P3-a). So on figures
//   that rise at one rate, rounded to the cent, a read misses the nearer
//   side's true line by at most half a cent plus a cent a dollar carried,
//   divided by the reach where it is under a dollar: 0.005 + 0.01 x carry /
//   min(1, reach), with reach the farther that rows run outside any jump on
//   either side. A line under a dollar long takes the two rows' rounding
//   over its own length, so a reach of a cent can put the rate a dollar a
//   dollar out. Only a sweep with no two rows outside a jump on either side
//   reads the line across it. Where a change of rate sits inside the dollar
//   the line walks out, as beside the API's cent pairs, the line carries the
//   rate beyond the change, and the read misses the rate beside the jump by
//   up to the change times the distance carried; the page dims it (P2-3).
// - Where the API holds no row at a draw inside a band it marks as a jump,
//   jumpAround names that band; the page dims there and the tooltip says
//   where the jump falls, not a figure (page2). The ladder and the tooltip
//   say where a jump falls in the same words.
// - turningPoints lists only rows the API returned, once each: a band edge or
//   the draw, never a figure read off a line (uk-page-09).
// - A result is stale for a draw past its sweep's top (uk-page-03, us-page-1),
//   and for a draw between the rows of a jump, until the API answers.
// - The slider's keys stay on the step grid, never pass the top, and reach
//   the top itself, the balance included (uk-page-18a).
// - A marker's label always fits inside the chart (us-page-6).
// - The ladder keeps every jump the API marks on a row of its own and joins
//   nothing else across it.

type Row = { draw: number; money_to_spend: number; tax: number };
type Band = { draw_from: number; draw_to: number; jump: boolean; kept: number; to_tax: number };

/** Rows in draw order, a draw apart of at least a penny. */
const sweeps = fc
  .array(
    fc.record({
      gap: fc.integer({ min: 1, max: 2_000_000 }),
      tax: fc.integer({ min: 0, max: 1_000_000 }),
    }),
    { minLength: 2, maxLength: 30 },
  )
  .map((rows): Row[] => {
    let pence = 0;
    return rows.map(({ gap, tax }, index) => {
      if (index > 0) pence += gap;
      // Money to spend is income plus the draw less tax, as on the API's rows.
      return { draw: pence / 100, money_to_spend: 1_000 + (pence - tax) / 100, tax: tax / 100 };
    });
  });

/** A sweep, one of its intervals marked as a jump, and a draw anywhere on it. */
const sweepWithJump = sweeps.chain((sweep) =>
  fc
    .record({
      at: fc.integer({ min: 0, max: sweep.length - 2 }),
      pence: fc.integer({ min: 0, max: Math.round(sweep[sweep.length - 1].draw * 100) }),
    })
    .map(({ at, pence }) => ({
      sweep,
      jump: { draw_from: sweep[at].draw, draw_to: sweep[at + 1].draw, jump: true },
      draw: pence / 100,
    })),
);

type Ledger = {
  draw: number;
  money_to_spend: number;
  tax: number;
  benefits: number;
  by_program: Record<string, number>;
};

/**
 * Rows that add up as the API's do: money to spend is income of 1,000 plus
 * the draw, less tax, plus benefits, and the programs sum to the benefits.
 */
const ledgers = fc
  .array(
    fc.record({
      gap: fc.integer({ min: 1, max: 2_000_000 }),
      tax: fc.integer({ min: 0, max: 1_000_000 }),
      snap: fc.integer({ min: 0, max: 50_000 }),
      ssi: fc.integer({ min: 0, max: 100_000 }),
    }),
    { minLength: 2, maxLength: 12 },
  )
  .map((rows): Ledger[] => {
    let pence = 0;
    return rows.map(({ gap, tax, snap, ssi }, index) => {
      if (index > 0) pence += gap;
      return {
        draw: pence / 100,
        money_to_spend: 1_000 + (pence - tax + snap + ssi) / 100,
        tax: tax / 100,
        benefits: (snap + ssi) / 100,
        by_program: { snap: snap / 100, ssi: ssi / 100 },
      };
    });
  });

/**
 * A sweep with each interval marked a jump or not on its own, so jumps land
 * at either end, side by side, on every interval or on a sweep of two rows,
 * and a draw that falls inside a jump half the time.
 */
const sweepWithJumps = ledgers.chain((sweep) =>
  fc
    .record({
      marks: fc.array(fc.boolean(), { minLength: sweep.length - 1, maxLength: sweep.length - 1 }),
      end: fc.constantFrom("first", "last", "both", "none"),
      inside: fc.boolean(),
      at: fc.nat(),
      share: fc.integer({ min: 1, max: 999 }),
      pence: fc.integer({ min: 0, max: Math.round(sweep[sweep.length - 1].draw * 100) }),
    })
    .map(({ marks, end, inside, at, share, pence }) => {
      const jumps = marks.map(
        (mark, index) =>
          mark ||
          ((end === "first" || end === "both") && index === 0) ||
          ((end === "last" || end === "both") && index === marks.length - 1),
      );
      const bands = sweep.slice(1).map((row, index) => ({
        draw_from: sweep[index].draw,
        draw_to: row.draw,
        jump: jumps[index],
      }));
      const marked = bands.filter((band) => band.jump);
      let draw = pence / 100;
      if (inside && marked.length) {
        // A draw strictly inside one of the jumps, on a whole penny.
        const band = marked[at % marked.length];
        const from = Math.round(band.draw_from * 100);
        const to = Math.round(band.draw_to * 100);
        if (to - from >= 2) draw = (from + 1 + Math.floor(((to - from - 2) * share) / 999)) / 100;
      }
      return { sweep, bands, draw };
    }),
);

/** The anchor row carried to the draw at the rate of the line through rows x and y. */
function carried(anchor: Ledger, x: Ledger, y: Ledger, draw: number) {
  const at = (start: number, from: number, to: number) =>
    start + ((draw - anchor.draw) / (y.draw - x.draw)) * (to - from);
  return {
    tax: at(anchor.tax, x.tax, y.tax),
    snap: at(anchor.by_program.snap, x.by_program.snap, y.by_program.snap),
  };
}

/**
 * The line rowAt reads inside the jump between rows i and i + 1, as the
 * invariant above words it; jump(j) says whether the interval from row j to
 * row j + 1 is a jump. Null where no two rows outside a jump lie on either
 * side.
 */
function jumpLine<R extends { draw: number }>(
  sweep: readonly R[],
  jump: (index: number) => boolean,
  i: number,
  nearA: boolean,
): readonly [R, R] | null {
  const cents = (line: readonly [R, R] | null) =>
    line ? Math.round((line[1].draw - line[0].draw) * 100) : 0;
  const side = (from: number, step: 1 | -1): [R, R] | null => {
    let far = from;
    for (let next = from + step; next >= 0 && next < sweep.length; next += step) {
      if (jump(Math.min(far, next))) break;
      far = next;
      if (Math.round(Math.abs(sweep[far].draw - sweep[from].draw) * 100) >= 100) break;
    }
    if (far === from) return null;
    return step < 0 ? [sweep[far], sweep[from]] : [sweep[from], sweep[far]];
  };
  const below = side(i, -1);
  const above = side(i + 1, 1);
  const [near, other] = nearA ? [below, above] : [above, below];
  if (cents(near) >= 100) return near;
  if (cents(other) >= 100) return other;
  return cents(near) >= cents(other) ? near : other;
}

/**
 * One figure that rises at a single rate and jumps inside some intervals,
 * rounded to the cent at each row as the API's figures are, with rows a few
 * cents apart as pin_changes leaves beside a change of rate; and a whole-cent
 * draw inside one of the jumps. `exact` holds each row's figure unrounded.
 */
const roundedWithJumps = fc
  .record({
    basisPoints: fc.integer({ min: 0, max: 10_000 }),
    rows: fc.array(
      fc.record({
        gap: fc.oneof(fc.integer({ min: 1, max: 5 }), fc.integer({ min: 6, max: 2_000_000 })),
        jump: fc.boolean(),
        step: fc.integer({ min: -100_000, max: 100_000 }),
      }),
      { minLength: 1, maxLength: 12 },
    ),
    at: fc.nat(),
    share: fc.integer({ min: 0, max: 999 }),
  })
  .map(({ basisPoints, rows, at, share }) => {
    const chosen = at % rows.length;
    const jumps = rows.map((row, index) => row.jump || index === chosen);
    let pence = 0;
    let offset = 0;
    const exact = [0];
    const sweep = [{ draw: 0, tax: 0 }];
    rows.forEach(({ gap, step }, index) => {
      pence += index === chosen ? Math.max(gap, 2) : gap;
      if (jumps[index]) offset += step;
      const value = (basisPoints * pence) / 10_000 + offset;
      exact.push(value / 100);
      sweep.push({ draw: pence / 100, tax: Math.round(value) / 100 });
    });
    const from = Math.round(sweep[chosen].draw * 100);
    const to = Math.round(sweep[chosen + 1].draw * 100);
    const draw = (from + 1 + Math.floor(((to - from - 2) * share) / 999)) / 100;
    return { rate: basisPoints / 10_000, jumps, exact, sweep, chosen, draw };
  });

describe("rowAt", () => {
  it("reads the nearer row's side between rows that bracket a located jump", () => {
    // us-page-2: the example's SNAP jump sits between rows at $7,291.67 (SNAP
    // $291) and $7,302.08 (SNAP $75). A blend at $7,300 gave $31,413 and SNAP
    // $118, which no draw yields.
    const result = usRecorded.example.envelope.outputs.us_drawdown_year_result;
    const { sweep, bands } = result;
    const at = (draw: number) => rowAt(sweep, draw, bands);
    const index = sweep.findIndex((row) => row.draw === 7_302.08);
    const [before, left, right, after] = sweep.slice(index - 2, index + 2);
    expect([left.draw, right.draw]).toEqual([7_291.67, 7_302.08]);
    // $7,300 sits nearer $7,302.08: SNAP's lower side, carried along to $7,300.
    const line = (x: typeof left, y: typeof left, draw: number) =>
      x.money_to_spend + ((draw - x.draw) / (y.draw - x.draw)) * (y.money_to_spend - x.money_to_spend);
    expect(at(7_300).draw).toBe(7_300);
    expect(at(7_300).money_to_spend).toBeCloseTo(line(right, after, 7_300), 6);
    expect(at(7_300).benefits_by_program.snap).toBeCloseTo(right.benefits_by_program.snap, 0);
    expect(at(7_292).money_to_spend).toBeCloseTo(line(before, left, 7_292), 6);
    expect(at(7_292).benefits_by_program.snap).toBeCloseTo(left.benefits_by_program.snap, 0);
    // A blend would have given SNAP between the two.
    expect(rowAt(sweep, 7_300).benefits_by_program.snap).toBeCloseTo(118.16, 1);
  });

  it("never blends across a jump, reads the line everywhere else, and keeps the accounting", () => {
    fc.assert(
      fc.property(sweepWithJump, ({ sweep, jump, draw }) => {
        const read = rowAt(sweep, draw, [jump]);
        const plain = rowAt(sweep, draw);
        expect(read.draw).toBe(draw);
        if (draw > jump.draw_from && draw < jump.draw_to) {
          const at = sweep.findIndex((row) => row.draw === jump.draw_from);
          const a = sweep[at];
          const b = sweep[at + 1];
          const nearA = draw - a.draw <= b.draw - draw;
          // A jump at an end of the sweep has no row beyond the nearer row:
          // there it carries the nearer row at the other side's rate.
          const line = jumpLine(sweep, (index) => index === at, at, nearA);
          if (line) {
            const [p, q] = line;
            const anchor = nearA ? a : b;
            expect(read.tax).toBeCloseTo(anchor.tax + ((draw - anchor.draw) / (q.draw - p.draw)) * (q.tax - p.tax), 4);
          } else {
            // A sweep of the jump's two rows has only the line across it.
            expect(read.tax).toBeCloseTo(plain.tax, 4);
          }
          expect(read.money_to_spend).toBeCloseTo(1_000 + draw - read.tax, 4);
        } else {
          expect(read).toEqual(plain);
          expect(read.money_to_spend).toBeCloseTo(1_000 + draw - read.tax, 4);
        }
      }),
    );
  });

  it("adds up at every draw, jumps at either end, side by side or everywhere included", () => {
    fc.assert(
      fc.property(sweepWithJumps, ({ sweep, bands, draw }) => {
        const read = rowAt(sweep, draw, bands);
        expect(read.draw).toBe(draw);
        // Money to spend is income plus the draw, less tax, plus benefits.
        expect(read.money_to_spend).toBeCloseTo(1_000 + draw - read.tax + read.benefits, 4);
        // The programs sum to the benefits, as on the ledger.
        expect(read.by_program.snap + read.by_program.ssi).toBeCloseTo(read.benefits, 4);

        const own = sweep.find((row) => row.draw === draw);
        if (own) {
          expect(read).toBe(own);
          return;
        }
        const i = sweep.findIndex((row, index) => row.draw < draw && draw < sweep[index + 1].draw);
        const [a, b] = [sweep[i], sweep[i + 1]];
        if (!bands[i].jump) {
          expect(read).toEqual(rowAt(sweep, draw));
          return;
        }
        // Inside a jump: one side's line, the nearer row's where it spans a dollar.
        const nearA = draw - a.draw <= b.draw - draw;
        const [x, y] = jumpLine(sweep, (index) => bands[index].jump, i, nearA) ?? [a, b];
        const expected = carried(nearA ? a : b, x, y, draw);
        expect(read.tax).toBeCloseTo(expected.tax, 4);
        expect(read.by_program.snap).toBeCloseTo(expected.snap, 4);
      }),
      { numRuns: 500 },
    );
  });

  it("carries the nearer row at the other side's rate at either end of the sweep", () => {
    // page2: a jump on the sweep's last interval left a draw nearer the top
    // with the top row's figures, so money to spend no longer equalled income
    // plus the draw less tax. Tax here takes 20p a pound and jumps by £100.
    const late = [
      { draw: 0, money_to_spend: 1_000, tax: 0 },
      { draw: 9_950, money_to_spend: 8_960, tax: 1_990 },
      { draw: 10_000, money_to_spend: 8_900, tax: 2_100 },
    ];
    // £9,990 sits nearer the top row, which has no row above it: the rate
    // comes from below the jump.
    const nearTop = rowAt(late, 9_990, [{ draw_from: 9_950, draw_to: 10_000, jump: true }]);
    expect(nearTop.draw).toBe(9_990);
    expect(nearTop.tax).toBeCloseTo(2_098, 6);
    expect(nearTop.money_to_spend).toBeCloseTo(8_892, 6);
    // £10 sits nearer the first row: the rate comes from above the jump.
    const early = [
      { draw: 0, money_to_spend: 1_000, tax: 0 },
      { draw: 50, money_to_spend: 940, tax: 110 },
      { draw: 10_000, money_to_spend: 8_900, tax: 2_100 },
    ];
    const nearFirst = rowAt(early, 10, [{ draw_from: 0, draw_to: 50, jump: true }]);
    expect(nearFirst.draw).toBe(10);
    expect(nearFirst.tax).toBeCloseTo(2, 6);
    expect(nearFirst.money_to_spend).toBeCloseTo(1_008, 6);
  });

  it("takes each side's rate from rows a pound or more apart where it can, else the widest", () => {
    // P3-a: pin_changes brackets a change of rate with rows a penny apart and
    // the API rounds each figure to the penny, so the line through two rows a
    // penny apart can put a rate up to £1 a pound out. Tax here
    // takes 30p a pound and jumps by £100 between £1,000.01 and £1,010.42;
    // £300.003 rounds to £300 at £1,000.01.
    const sweep = [
      { draw: 0, money_to_spend: 1_000, tax: 0 },
      { draw: 1_000, money_to_spend: 1_700, tax: 300 },
      { draw: 1_000.01, money_to_spend: 1_700.01, tax: 300 },
      { draw: 1_010.42, money_to_spend: 1_607.29, tax: 403.13 },
      { draw: 2_000, money_to_spend: 2_300, tax: 700 },
    ];
    const jump = [{ draw_from: 1_000.01, draw_to: 1_010.42, jump: true }];
    // Through the penny pair, tax stood still at £300 while the draw moved
    // £4.99; through the row £1,000.01 below, it rises 30p a pound.
    const below = rowAt(sweep, 1_005, jump);
    expect(below.tax).toBeCloseTo(301.5, 2);
    expect(below.money_to_spend).toBeCloseTo(1_000 + 1_005 - below.tax, 6);
    // Above the jump the next row is far enough already.
    expect(rowAt(sweep, 1_006, jump).tax).toBeCloseTo(401.8, 2);

    // Neither side holds a pound of rows: the wider side's 50p serves, not
    // the top's 2p, through which tax rises 50p a pound.
    const short = [
      { draw: 0, money_to_spend: 1_000, tax: 0 },
      { draw: 0.5, money_to_spend: 1_000.35, tax: 0.15 },
      { draw: 10.5, money_to_spend: 907.35, tax: 103.15 },
      { draw: 10.52, money_to_spend: 907.36, tax: 103.16 },
    ];
    const read = rowAt(short, 10.4, [{ draw_from: 0.5, draw_to: 10.5, jump: true }]);
    expect(read.tax).toBeCloseTo(103.12, 6);
    expect(read.money_to_spend).toBeCloseTo(1_000 + 10.4 - read.tax, 6);
  });

  it("reads a recorded run's cent pair as part of the dollar beyond it", () => {
    // P3-a: the couple's band edge at $74,750.01, where federal tax goes
    // from 27c to 30c a dollar, sits a cent from its grid row at $74,750,
    // and on both the engine's figures, rounded to the cent, give federal
    // tax of $9,944 and Medicare income of $150,000. No recorded jump sits
    // beside such a pair, so this marks the interval above it as one.
    // Carried at the pair's rate, a draw of $74,755 read the same $9,944 and
    // $150,000, though the draw had moved $4.99.
    const { sweep } = usRecorded.couple.envelope.outputs.us_drawdown_year_result;
    const i = sweep.findIndex((row) => row.draw === 74_750.01);
    const [before, left, right, after] = sweep.slice(i - 2, i + 2);
    expect([before.draw, left.draw, right.draw, after.draw]).toEqual([74_708.33, 74_750, 74_750.01, 74_791.67]);
    expect(right.federal_income_tax).toBe(left.federal_income_tax);
    expect(right.medicare_income).toBe(left.medicare_income);

    const read = rowAt(sweep, 74_755, [{ draw_from: right.draw, draw_to: after.draw, jump: true }]);
    // Medicare income moves dollar for dollar with the draw.
    expect(read.medicare_income).toBeCloseTo(150_004.99, 2);
    // Federal tax rises at the rate of the rows $41.68 apart: 27c a dollar.
    const rate = (right.federal_income_tax - before.federal_income_tax) / (right.draw - before.draw);
    expect(rate).toBeCloseTo(0.27, 2);
    expect(read.federal_income_tax).toBeCloseTo(right.federal_income_tax + 4.99 * rate, 6);
    // And the year still adds up: money to spend is the other income plus
    // the draw, less taxes, plus benefits.
    const ledger = (row: typeof right) =>
      row.money_to_spend - row.draw + row.federal_income_tax + row.state_income_tax + row.other_taxes - row.benefits;
    expect(ledger(read)).toBeCloseTo(ledger(right), 6);
  });

  it("carries the rate beyond a change of rate the dollar out crosses, off by the change times the carry", () => {
    // P2-3: the API brackets a change of rate with rows a cent apart, so the
    // walk out to a row a dollar away can cross it. Tax here takes 10c a
    // dollar up to $1,000 and 30c above, and jumps by $100 between
    // $1,000.01 and $1,010.42; $100.003 rounds to $100 at $1,000.01.
    const tax = (draw: number) => 0.1 * Math.min(draw, 1_000) + 0.3 * Math.max(draw - 1_000, 0) + (draw > 1_000.01 ? 100 : 0);
    const draws = [0, 990, 1_000, 1_000.01, 1_010.42, 2_000];
    const sweep = draws.map((draw) => {
      const owed = Math.round(tax(draw) * 100) / 100;
      return { draw, money_to_spend: 1_000 + draw - owed, tax: owed };
    });
    const jump = [{ draw_from: 1_000.01, draw_to: 1_010.42, jump: true }];
    // $1,005 sits nearer $1,000.01. The cent pair spans a cent, so the line
    // runs on to $990 and takes 10c a dollar, the rate below the change.
    const read = rowAt(sweep, 1_005, jump);
    const lineRate = (100 - 99) / 10.01;
    expect(read.tax).toBeCloseTo(100 + 4.99 * lineRate, 6);
    expect(read.money_to_spend).toBeCloseTo(1_000 + 1_005 - read.tax, 6);
    // The rate beside the jump is 30c, so the read misses that side's line
    // by about the 20c change times the $4.99 carried, plus the rounding.
    const beside = tax(1_000.01) + 0.3 * 4.99;
    const miss = Math.abs(read.tax - beside);
    expect(miss).toBeGreaterThan(0.99);
    expect(miss).toBeLessThanOrEqual(0.2 * 4.99 + 0.005 + 0.01 * 4.99);
  });

  it("reads figures rounded to the cent within half a cent plus a cent a dollar carried over the reach up to $1", () => {
    fc.assert(
      fc.property(roundedWithJumps, ({ rate, jumps, exact, sweep, chosen, draw }) => {
        const bands = sweep.slice(1).map((row, index) => ({
          draw_from: sweep[index].draw,
          draw_to: row.draw,
          jump: jumps[index],
        }));
        const read = rowAt(sweep, draw, bands);
        // How far rows run outside any jump on each side.
        let low = chosen;
        while (low > 0 && !jumps[low - 1]) low -= 1;
        let high = chosen + 1;
        while (high < jumps.length && !jumps[high]) high += 1;
        const reach = Math.max(sweep[chosen].draw - sweep[low].draw, sweep[high].draw - sweep[chosen + 1].draw);
        if (reach < 0.005) return; // Only the line across the jump: no side to read.
        const near = draw - sweep[chosen].draw <= sweep[chosen + 1].draw - draw ? chosen : chosen + 1;
        const carry = Math.abs(draw - sweep[near].draw);
        const truth = exact[near] + rate * (draw - sweep[near].draw);
        expect(Math.abs(read.tax - truth)).toBeLessThanOrEqual(0.005 + (0.01 * carry) / Math.min(1, reach) + 1e-6);
      }),
      { numRuns: 1_000 },
    );
  });

  it("ignores bands the API didn't mark as jumps", () => {
    const sweep = [
      { draw: 0, money_to_spend: 0, tax: 0 },
      { draw: 10, money_to_spend: 10, tax: 0 },
    ];
    expect(rowAt(sweep, 2, [{ draw_from: 0, draw_to: 10, jump: false }]).money_to_spend).toBe(2);
  });
});

const recordedRuns = [
  ...Object.entries(ukRecorded).map(([name, run]) => ({
    name: `uk ${name}`,
    result: run.envelope.outputs.uk_drawdown_year_result as {
      sweep: { draw: number }[];
      bands: { draw_from: number; draw_to: number; jump: boolean }[];
      at_chosen_draw: { draw: number };
    },
  })),
  ...Object.entries(usRecorded).map(([name, run]) => ({
    name: `us ${name}`,
    result: run.envelope.outputs.us_drawdown_year_result as {
      sweep: { draw: number }[];
      bands: { draw_from: number; draw_to: number; jump: boolean }[];
      at_chosen_draw: { draw: number };
    },
  })),
];

describe("turningPoints", () => {
  it.each(recordedRuns)("$name: lists the API's own row at every band edge and the draw", ({ result }) => {
    const { sweep, bands, at_chosen_draw } = result;
    const rows = turningPoints(sweep, bands, at_chosen_draw.draw);
    for (const row of rows) expect(sweep).toContain(row);
    const edges = new Set(bands.flatMap((band) => [band.draw_from, band.draw_to]));
    expect(rows.map((row) => row.draw)).toEqual(
      [...new Set([...edges, at_chosen_draw.draw])].sort((a, b) => a - b),
    );
  });

  it("leaves out a draw the API holds no row for, rather than read it off a line", () => {
    // uk-page-09: read off a line, the table missed the API by tens of pounds.
    const sweep = [
      { draw: 0, money_to_spend: 100 },
      { draw: 1_000, money_to_spend: 900 },
      { draw: 5_000, money_to_spend: 4_000 },
    ];
    const bands = [
      { draw_from: 0, draw_to: 1_000, jump: false },
      { draw_from: 1_000, draw_to: 5_000, jump: false },
    ];
    expect(turningPoints(sweep, bands, 2_500).map((row) => row.draw)).toEqual([0, 1_000, 5_000]);
    expect(turningPoints(sweep, bands, 1_000.004).map((row) => row.draw)).toEqual([0, 1_000, 5_000]);
  });

  it("lists the sweep's last row once for a draw past the top", () => {
    // us-page-1: the clamped row repeated the last band edge, and React warned
    // of two rows with the same key.
    const sweep = [
      { draw: 0, money_to_spend: 0 },
      { draw: 250_000, money_to_spend: 207_175 },
    ];
    const rows = turningPoints(sweep, [{ draw_from: 0, draw_to: 250_000, jump: false }], 600_000);
    expect(rows.map((row) => row.draw)).toEqual([0, 250_000]);
  });
});

describe("resultIsStale", () => {
  const sweep = [{ draw: 0 }, { draw: 90_000 }, { draw: 180_000 }];

  it("holds a result for other figures stale", () => {
    expect(resultIsStale("a", "b", sweep, 1_000)).toBe(true);
    expect(resultIsStale("a", "a", sweep, 1_000)).toBe(false);
  });

  it("holds a draw between a jump's rows stale until the API answers for it", () => {
    // us-page-2: the API places a jump only to within its band, so a draw
    // between the band's rows could fall on either side.
    const rows = [{ draw: 0 }, { draw: 7_291.67 }, { draw: 7_302.08 }, { draw: 10_000 }];
    const bands = [
      { draw_from: 0, draw_to: 7_291.67, jump: false },
      { draw_from: 7_291.67, draw_to: 7_302.08, jump: true },
      { draw_from: 7_302.08, draw_to: 10_000, jump: false },
    ];
    expect(resultIsStale("a", "a", rows, 7_300, bands)).toBe(true);
    expect(resultIsStale("a", "a", rows, 7_302.08, bands)).toBe(false);
    expect(resultIsStale("a", "a", rows, 8_000, bands)).toBe(false);
    expect(resultIsStale("a", "a", rows, 7_300, bands.map((band) => ({ ...band, jump: false })))).toBe(false);
  });

  it("holds a draw past the sweep's top stale until the API answers", () => {
    // uk-page-03: a draw of £300,000 showed the £180,000 row's figures, undimmed.
    expect(resultIsStale("a", "a", sweep, 300_000)).toBe(true);
    expect(resultIsStale("a", "a", sweep, 180_000)).toBe(false);
  });

  it("compares draws to the penny", () => {
    expect(sameDraw(2_500, 2_500.004)).toBe(true);
    expect(sameDraw(2_500, 2_500.01)).toBe(false);
  });
});

describe("jumpAround", () => {
  const rows = [{ draw: 0 }, { draw: 7_291.67 }, { draw: 7_300 }, { draw: 7_302.08 }, { draw: 10_000 }];
  const bands = [
    { draw_from: 0, draw_to: 7_291.67, jump: false },
    { draw_from: 7_291.67, draw_to: 7_302.08, jump: true },
    { draw_from: 7_302.08, draw_to: 10_000, jump: false },
  ];

  it("names the jump a draw falls inside where the API holds no row for it", () => {
    expect(jumpAround(rows, 7_295, bands)).toBe(bands[1]);
    expect(jumpAround(rows, 7_301, bands)).toBe(bands[1]);
  });

  it("names none at the API's own rows, outside a jump, or in a band not marked as one", () => {
    for (const draw of [7_291.67, 7_300, 7_302.08, 8_000, 0]) expect(jumpAround(rows, draw, bands)).toBeNull();
    expect(jumpAround(rows, 7_295, bands.map((band) => ({ ...band, jump: false })))).toBeNull();
  });

  it("holds a draw stale exactly where it names a jump", () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 1_000_000 }), (pence) => {
        const draw = pence / 100;
        expect(resultIsStale("a", "a", rows, draw, bands)).toBe(jumpAround(rows, draw, bands) !== null);
      }),
    );
  });
});

describe("stepPlaceIn", () => {
  const dollars = (value: number) => "$" + Math.round(value).toLocaleString("en-US");

  it("says a jump falls somewhere between its band's ends", () => {
    // page2: the API places the example's SNAP jump only to within $7,291.67
    // to $7,302.08; "At about $7,302" said more than it knows.
    expect(stepPlaceIn(dollars, { draw_from: 7_291.67, draw_to: 7_302.08 })).toBe(
      "Between $7,292 and $7,302",
    );
  });

  it("places a jump to the penny where it lands, and one whose ends print alike at about there", () => {
    expect(stepPlaceIn(dollars, { draw_from: 770, draw_to: 770.01 })).toBe("At $770");
    expect(stepPlaceIn(dollars, { draw_from: 16_499.6, draw_to: 16_500.4 })).toBe("At about $16,500");
  });

  it("is the ladder's range for a step", () => {
    const rows = [
      { draw_from: 0, draw_to: 7_291.67, step: false },
      { draw_from: 7_291.67, draw_to: 7_302.08, step: true },
      { draw_from: 7_302.08, draw_to: 9_000, step: false },
    ];
    expect(ladderRangeIn(dollars, rows, 1, 9_000)).toBe("Between $7,292 and $7,302");
  });
});

describe("drawLimitNote", () => {
  const pounds = (value: number) => `£${value.toLocaleString("en-GB")}`;

  it("says the draw stops at the balance when the field holds more", () => {
    // uk-page-02, us-page-4: the field kept 50,000 while the page used 10,000.
    expect(drawLimitNote(pounds, 50_000, 10_000, "your pension pot")).toBe(
      "You can draw up to £10,000 from your pension pot, so we use £10,000.",
    );
  });

  it("says nothing for a draw the balance covers, or an empty source", () => {
    expect(drawLimitNote(pounds, 10_000, 10_000, "your pension pot")).toBeNull();
    expect(drawLimitNote(pounds, 5_000, 0, "your cash savings")).toBeNull();
  });
});

describe("keyedDraw", () => {
  const steps = fc.constantFrom(50, 100, 500);
  const slider = steps.chain((step) =>
    fc
      .integer({ min: 1, max: 4_000_000 })
      .chain((topPence) =>
        fc
          .integer({ min: 0, max: topPence })
          .map((drawPence) => ({ step, top: topPence / 100, draw: drawPence / 100 })),
      ),
  );
  const onGrid = (value: number, step: number, top: number) =>
    value === top || Math.abs(value / step - Math.round(value / step)) < 1e-9;

  it("reaches the balance itself from the keyboard", () => {
    // uk-page-18a: with a pot of £10,025 and £50 steps the keys stopped at £10,000.
    expect(keyedDraw("End", 0, 10_025, 50)).toBe(10_025);
    expect(keyedDraw("ArrowRight", 10_000, 10_025, 50)).toBe(10_025);
    expect(keyedDraw("ArrowUp", 10_000, 10_025, 50)).toBe(10_025);
    expect(keyedDraw("ArrowLeft", 10_025, 10_025, 50)).toBe(10_000);
    expect(keyedDraw("Home", 10_025, 10_025, 50)).toBe(0);
    expect(keyedDraw("Tab", 10_025, 10_025, 50)).toBeNull();
  });

  it("steps along the grid without passing either end", () => {
    fc.assert(
      fc.property(slider, fc.constantFrom("ArrowRight", "ArrowUp", "ArrowLeft", "ArrowDown", "PageUp", "PageDown"), ({ step, top, draw }, key) => {
        const next = keyedDraw(key, draw, top, step)!;
        expect(next).toBeGreaterThanOrEqual(0);
        expect(next).toBeLessThanOrEqual(top);
        expect(onGrid(next, step, top)).toBe(true);
        const up = key === "ArrowRight" || key === "ArrowUp" || key === "PageUp";
        if (up && draw < top) expect(next).toBeGreaterThan(draw);
        if (!up && draw > 0) expect(next).toBeLessThan(draw);
      }),
    );
  });

  it("gets from either end to the other one key at a time", () => {
    fc.assert(
      fc.property(slider, ({ step, top }) => {
        let draw = 0;
        let presses = 0;
        while (draw < top && presses <= top / step + 1) {
          draw = keyedDraw("ArrowRight", draw, top, step)!;
          presses += 1;
        }
        expect(draw).toBe(top);
        while (draw > 0 && presses <= 2 * (top / step + 2)) {
          draw = keyedDraw("ArrowLeft", draw, top, step)!;
          presses += 1;
        }
        expect(draw).toBe(0);
      }),
      { numRuns: 50 },
    );
  });
});

describe("labelPlacement", () => {
  it("keeps a long label inside a phone-width chart", () => {
    // us-page-6: "Medicare Savings Program ends" at x=141 of a 288 px chart ran
    // 27 to 42 px off the right edge.
    const width = 175;
    const placed = labelPlacement(141, width, 288);
    const left = placed.anchor === "start" ? placed.x : placed.x - width;
    expect(left).toBeGreaterThanOrEqual(0);
    expect(left + width).toBeLessThanOrEqual(288);
  });

  it("puts a label beside its line when it fits, on whichever side has room", () => {
    expect(labelPlacement(100, 80, 640)).toEqual({ x: 105, anchor: "start" });
    expect(labelPlacement(600, 80, 640)).toEqual({ x: 595, anchor: "end" });
  });

  it("always fits a label that fits the chart", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 280, max: 1_400 }),
        fc.double({ min: 0, max: 1, noNaN: true }),
        fc.double({ min: 0, max: 1, noNaN: true }),
        (width, at, share) => {
          const labelWidth = share * (width - 4);
          const placed = labelPlacement(at * width, labelWidth, width);
          const left = placed.anchor === "start" ? placed.x : placed.x - labelWidth;
          expect(left).toBeGreaterThanOrEqual(-1e-9);
          expect(left + labelWidth).toBeLessThanOrEqual(width + 1e-9);
        },
      ),
    );
  });
});

describe("ladderRowsOf", () => {
  const band = (draw_from: number, draw_to: number, to_tax: number, jump = false): Band => ({
    draw_from,
    draw_to,
    jump,
    kept: 1 - to_tax,
    to_tax,
  });
  const sameInPence = (a: Band, b: Band) => Math.round(a.to_tax * 100) === Math.round(b.to_tax * 100);

  it("keeps a jump the API marks on its own row, whatever its rate", () => {
    // R3: a £100 Personal Savings Allowance step in one penny has a rate of
    // 10,000 a pound; it reads as a jump, not as a split pound.
    const rows = ladderRowsOf(
      [band(0, 770, 0.2), band(770, 770.01, 10_000.2, true), band(770.01, 1_770, 0.2)],
      sameInPence,
    );
    expect(rows.map((row) => row.step)).toEqual([false, true, false]);
  });

  it("joins neighbours that read the same, and moves the same amounts", () => {
    fc.assert(
      fc.property(
        fc.array(fc.record({ width: fc.integer({ min: 1, max: 100_000 }), tax: fc.integer({ min: 0, max: 60 }), jump: fc.boolean() }), {
          minLength: 1,
          maxLength: 12,
        }),
        (parts) => {
          let from = 0;
          const bands = parts.map(({ width, tax, jump }) => {
            const made = band(from, from + width, tax / 100, jump);
            from += width;
            return made;
          });
          const rows = ladderRowsOf(bands, sameInPence);
          expect(rows.filter((row) => row.step)).toHaveLength(bands.filter((b) => b.jump).length);
          rows.slice(1).forEach((row, index) => {
            expect(row.draw_from).toBe(rows[index].draw_to);
            if (!row.step && !rows[index].step) expect(sameInPence(row, rows[index])).toBe(false);
          });
          const moved = (list: Band[]) => list.reduce((sum, b) => sum + b.to_tax * (b.draw_to - b.draw_from), 0);
          expect(moved(rows)).toBeCloseTo(moved(bands), 6);
        },
      ),
    );
  });

  it("joins two bands by width", () => {
    expect(joinBands(band(0, 100, 0.2), band(100, 400, 0.4))).toEqual({
      draw_from: 0,
      draw_to: 400,
      jump: false,
      kept: 0.65,
      to_tax: 0.35,
    });
  });
});

describe("failureMessage", () => {
  it.each([
    [new NetworkError("down"), "We couldn’t reach the calculator. Check your connection and try again."],
    [new TimeoutError("slow"), "The calculator took too long to answer. Try again."],
    [new ApiError("off", 503), "The calculator isn’t running right now. Try again later."],
    [new SimulationError("bug", 500), "The calculator couldn’t work out this year. Try again, or change a figure."],
    [new ApiError("bad", 422), "The calculator couldn’t work out this year. Try again, or change a figure."],
    [new Error("other"), "We couldn’t work this out. Try again."],
  ])("words %s", (error, message) => {
    expect(failureMessage(error)).toBe(message);
  });
});
