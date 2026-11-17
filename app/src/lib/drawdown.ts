/**
 * Helpers the UK and US drawdown pages share. The API calculates every
 * amount; these read amounts off its sweep and lay out the chart.
 */

import { ApiError, NetworkError, TimeoutError } from "./api";

/** A range of draws, as the API's bands give it. */
export interface DrawSpan {
  draw_from: number;
  draw_to: number;
}

/** A band of the API's, which marks where a tax or benefit jumps. */
export interface MarkedSpan extends DrawSpan {
  jump?: boolean;
}

/** Draws are money: two that agree to the penny are the same draw. */
export function sameDraw(a: number, b: number): boolean {
  return Math.abs(a - b) < 0.005;
}

function isAmounts(value: unknown): value is Record<string, number> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every((entry) => typeof entry === "number")
  );
}

/**
 * The anchor row carried to a draw at the rate of the line through rows x and
 * y, nested amounts included. Every figure moves by the same share of y less
 * x, so a row read this way adds up as the API's rows do.
 */
function carried<Row extends { draw: number }>(anchor: Row, x: Row, y: Row, draw: number): Row {
  const share = (draw - anchor.draw) / (y.draw - x.draw);
  const row = { ...anchor, draw };
  for (const key of Object.keys(anchor) as (keyof Row)[]) {
    const start = anchor[key];
    const from = x[key];
    const to = y[key];
    if (key !== "draw" && typeof start === "number" && typeof from === "number" && typeof to === "number") {
      row[key] = (start + share * (to - from)) as Row[keyof Row];
    } else if (isAmounts(start) && isAmounts(from) && isAmounts(to)) {
      const moved: Record<string, number> = {};
      for (const name of new Set([...Object.keys(start), ...Object.keys(from), ...Object.keys(to)])) {
        moved[name] = (start[name] ?? 0) + share * ((to[name] ?? 0) - (from[name] ?? 0));
      }
      row[key] = moved as Row[keyof Row];
    }
  }
  return row;
}

/**
 * Rows at least this many cents apart give a rate that rounding each figure
 * to the cent moves by a cent a dollar at most.
 */
const STEADY_CENTS = 100;

/**
 * The result at any draw, read along the straight line between sweep rows.
 * Amounts nested one level down, such as benefits by program, follow the same
 * line. Between two rows inside a band the API marks as a jump, that line
 * would give a figure no draw yields, so this reads the nearer row's side of
 * the jump: the nearer row, carried to the draw at the rate of a line beside
 * the jump. Each side's line runs from the row beside the jump out to the
 * first row a dollar or more away, over rows outside any jump, or to the
 * farthest where none is that far: the API brackets a change of rate with
 * rows a cent apart and rounds each figure to the cent, so a line through
 * two such rows can show any rate from nothing to a dollar a dollar. The
 * nearer row's side serves where its line spans a dollar; else the other
 * side's where that does (at either end of the sweep, or beside another
 * jump), so the read still sits no further than half the band from one of
 * the API's rows; else the wider line. Only a sweep with no two rows outside
 * the jump on either side reads the line across it. Every read is a sum of
 * the API's rows whose weights add to one, so its figures add up as the rows
 * do. The API places the jump only to within the band, so they can still be
 * the other side's until the API answers for the draw. The API's own rows
 * come back as they are.
 */
export function rowAt<Row extends { draw: number }>(
  sweep: readonly Row[],
  draw: number,
  bands: readonly MarkedSpan[] = [],
): Row {
  const first = sweep[0];
  const last = sweep[sweep.length - 1];
  if (draw <= first.draw) return first;
  if (draw >= last.draw) return last;
  let low = 0;
  let high = sweep.length - 1;
  while (high - low > 1) {
    const middle = (low + high) >> 1;
    if (sweep[middle].draw <= draw) low = middle;
    else high = middle;
  }
  const a = sweep[low];
  const b = sweep[high];
  if (a.draw === draw) return a;
  const inJump = (x: Row, y: Row) =>
    bands.some((band) => band.jump && band.draw_from <= x.draw && y.draw <= band.draw_to);
  if (!inJump(a, b)) return carried(a, a, b, draw);
  const cents = (line: readonly [Row, Row] | null) =>
    line ? Math.round((line[1].draw - line[0].draw) * 100) : 0;
  // The line beside the jump on one side: from the row next to it out to the
  // first row a dollar or more away, over rows outside any jump, or the
  // farthest such row. Null where the next row out is past a jump or the end.
  const sideLine = (from: number, step: 1 | -1): [Row, Row] | null => {
    let far = from;
    for (let next = from + step; next >= 0 && next < sweep.length; next += step) {
      const [x, y] = step < 0 ? [sweep[next], sweep[far]] : [sweep[far], sweep[next]];
      if (inJump(x, y)) break;
      far = next;
      if (Math.round(Math.abs(sweep[far].draw - sweep[from].draw) * 100) >= STEADY_CENTS) break;
    }
    if (far === from) return null;
    return step < 0 ? [sweep[far], sweep[from]] : [sweep[from], sweep[far]];
  };
  const nearA = draw - a.draw <= b.draw - draw;
  const below = sideLine(low, -1);
  const above = sideLine(high, 1);
  const [near, other] = nearA ? [below, above] : [above, below];
  const line =
    cents(near) >= STEADY_CENTS
      ? near
      : cents(other) >= STEADY_CENTS || cents(other) > cents(near)
        ? other
        : near;
  const [x, y] = line ?? [a, b];
  return carried(nearA ? a : b, x, y, draw);
}

/** "a", "a and b", "a, b and c". */
export function joined(parts: string[]): string {
  return parts.length < 2
    ? (parts[0] ?? "")
    : `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

/** The API's row at this draw, if it returned one. */
export function rowOn<Row extends { draw: number }>(
  sweep: readonly Row[],
  draw: number,
): Row | null {
  let low = 0;
  let high = sweep.length - 1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (sameDraw(sweep[middle].draw, draw)) return sweep[middle];
    if (sweep[middle].draw < draw) low = middle + 1;
    else high = middle - 1;
  }
  return null;
}

/**
 * The rows for the turning-points table: the API's own row at each band edge
 * and at the draw, once each, lowest first. A draw the API holds no row for
 * (one past the sweep's top, or a new draw before the API answers) stays out
 * rather than be read off a line.
 */
export function turningPoints<Row extends { draw: number }>(
  sweep: readonly Row[],
  bands: readonly MarkedSpan[],
  draw: number,
): Row[] {
  const rows = new Set<Row>();
  for (const amount of [...bands.flatMap((band) => [band.draw_from, band.draw_to]), draw]) {
    const row = rowOn(sweep, amount);
    if (row) rows.add(row);
  }
  return [...rows].sort((a, b) => a.draw - b.draw);
}

/**
 * The band the API marks as a jump that a draw falls inside, where the API
 * holds no row at the draw; otherwise null. The API places a jump only to
 * within its band, so there it doesn't know which side of the jump the draw
 * falls.
 */
export function jumpAround<Band extends MarkedSpan>(
  sweep: readonly { draw: number }[],
  draw: number,
  bands: readonly Band[],
): Band | null {
  if (rowOn(sweep, draw) !== null) return null;
  return bands.find((band) => band.jump && band.draw_from < draw && draw < band.draw_to) ?? null;
}

/**
 * True while the figures on show can't be the API's for the inputs on the
 * page: a run for other figures; a draw past the top of its sweep, where the
 * page would repeat the top row's figures; or a draw inside a jump the API
 * holds no row for (jumpAround).
 */
export function resultIsStale(
  runBaseKey: string,
  baseKey: string,
  sweep: readonly { draw: number }[],
  draw: number,
  bands: readonly MarkedSpan[] = [],
): boolean {
  if (runBaseKey !== baseKey || draw > sweep[sweep.length - 1].draw + 0.005) return true;
  return jumpAround(sweep, draw, bands) !== null;
}

/**
 * Where a jump falls, in words, for the ladder and the chart's tooltip alike.
 * A jump placed to the penny lands there; a wider one lies somewhere between
 * its band's ends, which this names unless they print alike.
 */
export function stepPlaceIn(format: (value: number) => string, band: DrawSpan): string {
  if (band.draw_to - band.draw_from <= 0.015) return `At ${format(band.draw_to)}`;
  const from = format(band.draw_from);
  const to = format(band.draw_to);
  return from === to ? `At about ${to}` : `Between ${from} and ${to}`;
}

/** What the draw field says when it holds more than the source the draw comes from. */
export function drawLimitNote(
  format: (value: number) => string,
  draw: number,
  balance: number,
  source: string,
): string | null {
  if (!(balance > 0) || draw <= balance + 0.005) return null;
  return `You can draw up to ${format(balance)} from ${source}, so we use ${format(balance)}.`;
}

/** Why a run failed, in words that say what to do next. */
export function failureMessage(error: unknown): string {
  if (error instanceof NetworkError) {
    return "We couldn’t reach the calculator. Check your connection and try again.";
  }
  if (error instanceof TimeoutError) {
    return "The calculator took too long to answer. Try again.";
  }
  if (error instanceof ApiError && error.statusCode === 503) {
    return "The calculator isn’t running right now. Try again later.";
  }
  if (error instanceof ApiError && error.statusCode !== undefined) {
    return "The calculator couldn’t work out this year. Try again, or change a figure.";
  }
  return "We couldn’t work this out. Try again.";
}

/** Two neighbouring bands as one, each rate weighted by its band's width. */
export function joinBands<Band extends DrawSpan & { jump?: boolean }>(a: Band, b: Band): Band {
  const left = a.draw_to - a.draw_from;
  const right = b.draw_to - b.draw_from;
  const joined = { ...a, draw_to: b.draw_to };
  for (const key of Object.keys(a) as (keyof Band)[]) {
    const x = a[key];
    const y = b[key];
    if (key !== "draw_from" && key !== "draw_to" && typeof x === "number" && typeof y === "number") {
      joined[key] = ((x * left + y * right) / (left + right)) as Band[keyof Band];
    }
  }
  if ("jump" in a) joined.jump = false;
  return joined;
}

/**
 * The API's bands for the ladder. A band the API marks as a jump stands alone
 * and shows as a step; neighbours that read the same join.
 */
export function ladderRowsOf<Band extends DrawSpan & { jump: boolean }>(
  bands: readonly Band[],
  same: (a: Band, b: Band) => boolean,
): (Band & { step: boolean })[] {
  const rows: (Band & { step: boolean })[] = [];
  for (const band of bands) {
    const last = rows[rows.length - 1];
    if (last && !last.step && !band.jump && same(last, band)) {
      rows[rows.length - 1] = { ...joinBands<Band>(last, band), step: false };
    } else {
      rows.push({ ...band, step: band.jump });
    }
  }
  return rows;
}

/** A ladder row's draw amounts, in words; a jump by where it falls (stepPlaceIn). */
export function ladderRangeIn(
  format: (value: number) => string,
  rows: readonly (DrawSpan & { step: boolean })[],
  index: number,
  balance: number,
): string {
  const row = rows[index];
  return row.step ? stepPlaceIn(format, row) : bandRangeIn(format, rows, index, balance);
}

/** A band's draw amounts, in words. The sweep can stop short of a large balance. */
export function bandRangeIn(
  format: (value: number) => string,
  bands: readonly { draw_from: number; draw_to: number }[],
  index: number,
  balance: number,
): string {
  const band = bands[index];
  if (index === 0) return `Up to ${format(band.draw_to)}`;
  if (index === bands.length - 1 && band.draw_to < balance) {
    return `Above ${format(band.draw_from)}`;
  }
  return `${format(band.draw_from)} to ${format(band.draw_to)}`;
}

/** Most draws of interest sit below this, whatever the size of the balance. */
const CHART_VIEW = 100_000;

export function chartTop(sweepTop: number, balance: number, draw: number): number {
  return Math.min(sweepTop, Math.max(Math.min(balance, CHART_VIEW), draw * 1.1));
}

export function drawStep(top: number): number {
  if (top <= 30_000) return 50;
  if (top <= 120_000) return 100;
  return 500;
}

/**
 * The draw a key moves the slider to, or null to leave the key alone. Keys
 * step along the slider's grid, and the top of the range is a stop of its own
 * even off the grid, so the keyboard reaches a balance such as £10,025.
 */
export function keyedDraw(key: string, draw: number, top: number, step: number): number | null {
  // The grid point just below or just above a value, kept inside 0 to top.
  const below = (value: number) => Math.max(Math.ceil(value / step - 1e-9) - 1, 0) * step;
  const above = (value: number) => Math.min((Math.floor(value / step + 1e-9) + 1) * step, top);
  switch (key) {
    case "Home":
      return 0;
    case "End":
      return top;
    case "ArrowRight":
    case "ArrowUp":
      return draw >= top ? top : above(draw);
    case "ArrowLeft":
    case "ArrowDown":
      return draw <= 0 ? 0 : below(draw);
    case "PageUp":
      return draw >= top ? top : above(draw + 9 * step);
    case "PageDown":
      return draw <= 0 ? 0 : below(Math.max(draw - 9 * step, 0));
    default:
      return null;
  }
}

/** Room a marker's label needs, before the page has measured it: 12 px text. */
export function estimatedLabelWidth(label: string): number {
  return label.length * 6.6;
}

/**
 * Where a marker's label goes: just right of its line if it fits there, else
 * just left of it, else as near its line as the chart's edges allow.
 */
export function labelPlacement(
  lineX: number,
  labelWidth: number,
  width: number,
  gap = 5,
  edge = 2,
): { x: number; anchor: "start" | "end" } {
  if (lineX + gap + labelWidth <= width - edge) return { x: lineX + gap, anchor: "start" };
  if (lineX - gap - labelWidth >= edge) return { x: lineX - gap, anchor: "end" };
  return { x: Math.max(Math.min(lineX + gap, width - edge - labelWidth), 0), anchor: "start" };
}

/** Round axis values across a range; always at least the two ends' worth. */
export function niceTicks(low: number, high: number, count: number): number[] {
  if (!(high > low)) return [low];
  const rough = (high - low) / Math.max(count, 1);
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step =
    [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((candidate) => candidate >= rough) ??
    10 * magnitude;
  const ticks: number[] = [];
  for (let tick = Math.ceil(low / step) * step; tick <= high + step * 1e-9; tick += step) {
    ticks.push(Math.round(tick * 1e6) / 1e6);
  }
  return ticks;
}
