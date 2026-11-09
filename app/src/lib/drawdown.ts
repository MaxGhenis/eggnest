/**
 * Helpers the UK and US drawdown pages share. The API calculates every
 * amount; these read amounts off its sweep and lay out the chart.
 */

/** The result at any draw, read along the straight line between sweep rows. */
export function rowAt<Row extends { draw: number }>(sweep: readonly Row[], draw: number): Row {
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
  const share = (draw - a.draw) / (b.draw - a.draw);
  const row = { ...a, draw };
  for (const key of Object.keys(a) as (keyof Row)[]) {
    const from = a[key];
    const to = b[key];
    if (key !== "draw" && typeof from === "number" && typeof to === "number") {
      row[key] = (from + share * (to - from)) as Row[keyof Row];
    }
  }
  return row;
}

/** "a", "a and b", "a, b and c". */
export function joined(parts: string[]): string {
  return parts.length < 2
    ? (parts[0] ?? "")
    : `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
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
