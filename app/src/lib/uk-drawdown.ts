/**
 * Pure helpers for the one-year UK drawdown page. The API calculates every
 * amount; these read amounts off its sweep and put them into words.
 */

import type {
  DrawSource,
  DrawdownOutcome,
  DrawdownSlice,
  UKDrawdownYearInput,
} from "./api-uk-drawdown";

const wholePounds = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  maximumFractionDigits: 0,
});

const exactPounds = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function pounds(value: number): string {
  return wholePounds.format(Math.round(value) || 0);
}

export function poundsAndPence(value: number): string {
  return exactPounds.format(value || 0);
}

/** An axis label: £900, £10k, £1.5m. */
export function compactPounds(value: number): string {
  const size = Math.abs(value);
  if (size >= 1_000_000) return `£${+(value / 1_000_000).toFixed(1)}m`;
  if (size >= 1_000) return `£${+(value / 1_000).toFixed(1)}k`;
  return `£${Math.round(value)}`;
}

/** The result at any draw, read along the straight line between sweep rows. */
export function outcomeAt(sweep: DrawdownOutcome[], draw: number): DrawdownOutcome {
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
  const mix = (field: keyof DrawdownOutcome) => a[field] + share * (b[field] - a[field]);
  return {
    draw,
    taxable_draw: mix("taxable_draw"),
    income_tax: mix("income_tax"),
    employee_ni: mix("employee_ni"),
    pension_credit: mix("pension_credit"),
    money_to_spend: mix("money_to_spend"),
  };
}

/** Where the pounds between two draw amounts go. */
export function sliceBetween(
  sweep: DrawdownOutcome[],
  from: number,
  to: number,
): DrawdownSlice | null {
  const a = outcomeAt(sweep, from);
  const b = outcomeAt(sweep, to);
  const width = b.draw - a.draw;
  if (width <= 0) return null;
  return {
    draw_from: a.draw,
    draw_to: b.draw,
    kept: (b.money_to_spend - a.money_to_spend) / width,
    to_tax: (b.income_tax + b.employee_ni - a.income_tax - a.employee_ni) / width,
    to_pension_credit: (a.pension_credit - b.pension_credit) / width,
  };
}

export interface PoundSplit {
  kept: number;
  tax: number;
  /** Pence of Pension Credit lost; below zero when the credit rises. */
  lost: number;
}

/** A slice in whole pence that adds up to 100p. */
export function splitPence(slice: DrawdownSlice): PoundSplit {
  const tax = Math.round(slice.to_tax * 100) || 0;
  const lost = Math.round(slice.to_pension_credit * 100) || 0;
  return { kept: 100 - tax - lost, tax, lost };
}

function joined(parts: string[]): string {
  return parts.length < 2
    ? (parts[0] ?? "")
    : `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

/** What happens to each extra pound of draw. */
export function describePound(slice: DrawdownSlice): string {
  const { kept, tax, lost } = splitPence(slice);
  if (lost < 0) {
    return tax > 0
      ? `You keep ${kept}p: you pay ${tax}p in tax and gain ${-lost}p of Pension Credit.`
      : `You keep the whole pound and gain ${-lost}p of Pension Credit.`;
  }
  if (tax === 0 && lost === 0) return "You keep the whole pound.";
  const costs = [
    ...(tax > 0 ? [`pay ${tax}p in tax`] : []),
    ...(lost > 0 ? [`lose ${lost}p of Pension Credit`] : []),
  ];
  return kept > 0
    ? `You ${joined([`keep ${kept}p`, ...costs])}.`
    : `You keep nothing: you ${joined(costs)}.`;
}

/** The next step of draw, in pounds. */
export function describeNextStep(slice: DrawdownSlice): string {
  const width = slice.draw_to - slice.draw_from;
  const keep = pounds(slice.kept * width);
  const tax = pounds(slice.to_tax * width);
  const change = slice.to_pension_credit * width;
  const parts = [
    ...(Math.round(slice.to_tax * width) > 0 ? [`pay ${tax} in tax`] : []),
    ...(Math.round(change) > 0 ? [`lose ${pounds(change)} of Pension Credit`] : []),
    ...(Math.round(change) < 0 ? [`gain ${pounds(-change)} of Pension Credit`] : []),
  ];
  const opening = `Draw another ${pounds(width)} and you`;
  if (slice.kept * width < 0.5) return `${opening} keep nothing: you ${joined(parts)}.`;
  return parts.length
    ? `${opening} keep ${keep}: you ${joined(parts)}.`
    : `${opening} keep all of it.`;
}

const SOURCE_NAMES: Record<DrawSource, string> = {
  sipp: "your pension pot",
  isa: "your ISAs",
  gia: "your investments",
  cash: "your cash savings",
};

export function headline(
  source: DrawSource,
  draw: number,
  moneyToSpend: number,
  taxYear: string,
): string {
  return draw > 0
    ? `Draw ${pounds(draw)} from ${SOURCE_NAMES[source]} in ${taxYear} and you’ll have ${pounds(moneyToSpend)} to spend.`
    : `Draw nothing in ${taxYear} and you’ll have ${pounds(moneyToSpend)} to spend.`;
}

/** How the chosen draw compares with leaving the money where it sits. */
export function comparedWithNoDraw(
  chosen: DrawdownOutcome,
  none: DrawdownOutcome,
): string | null {
  if (chosen.draw <= 0) return null;
  const gain = chosen.money_to_spend - none.money_to_spend;
  const lost = none.pension_credit - chosen.pension_credit;
  const tax =
    chosen.income_tax + chosen.employee_ni - none.income_tax - none.employee_ni;
  const costs = [
    ...(Math.round(lost) > 0 ? [`losing ${pounds(lost)} of Pension Credit`] : []),
    ...(Math.round(lost) < 0 ? [`gaining ${pounds(-lost)} of Pension Credit`] : []),
    ...(Math.round(tax) > 0 ? [`paying ${pounds(tax)} more in tax`] : []),
  ];
  const direction = gain >= 0 ? "more" : "less";
  const lead = `You’d have ${pounds(Math.abs(gain))} ${direction} to spend than if you drew nothing`;
  return costs.length ? `${lead}, after ${joined(costs)}.` : `${lead}.`;
}

/** What to do when the chosen source holds nothing to draw. */
export function emptySourceMessage(source: DrawSource): string {
  return `Enter how much you have in ${SOURCE_NAMES[source]} to see what you’d keep.`;
}

/** A band's draw amounts, in words. The sweep can stop short of a large pot. */
export function bandRange(bands: DrawdownSlice[], index: number, balance: number): string {
  const band = bands[index];
  if (index === 0) return `Up to ${pounds(band.draw_to)}`;
  if (index === bands.length - 1 && band.draw_to < balance) {
    return `Above ${pounds(band.draw_from)}`;
  }
  return `${pounds(band.draw_from)} to ${pounds(band.draw_to)}`;
}

/** Most draws of interest sit below this, whatever the size of the pot. */
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

export const FULL_NEW_STATE_PENSION = 12_547.6;
export const LUMP_SUM_ALLOWANCE = 268_275;
const LARGEST_AMOUNT = 100_000_000;

/** The figures the page opens with, for anyone to replace. */
export const EXAMPLE_INPUTS: UKDrawdownYearInput = {
  birth_date: "1958-06-15",
  region: "England",
  tax_year: 2026,
  state_pension: 9_360,
  other_pension_income: 0,
  employment_income: 0,
  savings_interest: 0,
  dividend_income: 0,
  sipp_balance: 10_000,
  isa_balance: 0,
  gia_balance: 0,
  cash_savings: 0,
  draw_source: "sipp",
  draw_amount: 2_500,
  sipp_draw_pattern: "regular",
  sipp_tax_free_fraction: 0.25,
  lump_sum_allowance_remaining: LUMP_SUM_ALLOWANCE,
  gilt_yield_percent: 5.25,
  annuity_income_per_1000: null,
};

/** True until someone changes a figure about themselves; choosing a draw doesn't count. */
export function isExamplePerson(inputs: UKDrawdownYearInput): boolean {
  const aboutThePerson = (figures: UKDrawdownYearInput) =>
    JSON.stringify({
      ...figures,
      draw_amount: 0,
      draw_source: "sipp",
      sipp_draw_pattern: "regular",
      sipp_tax_free_fraction: 0,
    });
  return aboutThePerson(inputs) === aboutThePerson(EXAMPLE_INPUTS);
}

export function sourceBalance(inputs: UKDrawdownYearInput): number {
  return {
    sipp: inputs.sipp_balance,
    isa: inputs.isa_balance,
    gia: inputs.gia_balance,
    cash: inputs.cash_savings,
  }[inputs.draw_source];
}

/** Age in complete years at the start of the 2026/27 tax year. */
export function ageAtTaxYearStart(birthDate: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(birthDate);
  if (!match) return null;
  const [year, month, day] = match.slice(1).map(Number);
  const hadBirthday = 4 > month || (month === 4 && 6 >= day);
  return 2026 - year - (hadBirthday ? 0 : 1);
}

/** What stops the calculation running, in words someone can act on. */
export function inputProblem(inputs: UKDrawdownYearInput): string | null {
  const age = ageAtTaxYearStart(inputs.birth_date);
  if (age === null) return "Enter your date of birth.";
  if (age < 18 || age > 120) {
    return "Enter a date of birth for someone aged 18 to 120 on 6 April 2026.";
  }
  if (inputs.draw_source === "sipp" && inputs.draw_amount > 0 && age < 55) {
    return "You can’t draw from a pension pot before age 55. Draw from your savings, or set the draw to £0.";
  }
  const amounts = [
    inputs.state_pension,
    inputs.other_pension_income,
    inputs.employment_income,
    inputs.savings_interest,
    inputs.dividend_income,
    inputs.sipp_balance,
    inputs.isa_balance,
    inputs.gia_balance,
    inputs.cash_savings,
  ];
  if (amounts.some((amount) => amount > LARGEST_AMOUNT)) return "Enter amounts up to £100 million.";
  if (inputs.gilt_yield_percent > 20) return "Enter a gilt yield of 20% or less.";
  if ((inputs.annuity_income_per_1000 ?? 0) > 1_000) {
    return "Enter annuity income of £1,000 or less per £1,000 of pot.";
  }
  return null;
}

/** Keeps the draw inside what the chosen source holds. */
export function withDrawInBounds(inputs: UKDrawdownYearInput): UKDrawdownYearInput {
  const balance = sourceBalance(inputs);
  return inputs.draw_amount > balance ? { ...inputs, draw_amount: balance } : inputs;
}
