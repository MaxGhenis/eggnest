/**
 * Pure helpers for the one-year UK drawdown page. The API calculates every
 * amount; these read amounts off its sweep and put them into words.
 */

import type {
  DrawSource,
  DrawdownBand,
  DrawdownOutcome,
  DrawdownSlice,
  UKDrawdownYearInput,
} from "./api-uk-drawdown";
import {
  bandRangeIn,
  drawLimitNote as drawLimitNoteIn,
  joined,
  ladderRangeIn,
  ladderRowsOf,
  rowAt,
  type MarkedSpan,
} from "./drawdown";

export { chartTop, drawStep, failureMessage, niceTicks } from "./drawdown";

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

/**
 * The result at any draw, read along the straight line between sweep rows,
 * or, inside a band the API marks as a jump, on the nearer row's side of it
 * (rowAt). Either way its figures add up as the API's rows do.
 */
export function outcomeAt(
  sweep: DrawdownOutcome[],
  draw: number,
  bands: readonly MarkedSpan[] = [],
): DrawdownOutcome {
  return rowAt(sweep, draw, bands);
}

/** Where the pounds between two draw amounts go. */
export function sliceBetween(
  sweep: DrawdownOutcome[],
  from: number,
  to: number,
  bands: readonly MarkedSpan[] = [],
): DrawdownSlice | null {
  const a = outcomeAt(sweep, from, bands);
  const b = outcomeAt(sweep, to, bands);
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
  return bandRangeIn(pounds, bands, index, balance);
}

export type PoundLadderRow = DrawdownBand & {
  /** A jump the API placed: income tax changes all at once at this penny. */
  step: boolean;
};

function sameInPence(a: DrawdownSlice, b: DrawdownSlice): boolean {
  const x = splitPence(a);
  const y = splitPence(b);
  return x.tax === y.tax && x.lost === y.lost;
}

/**
 * The API's bands for the ladder: each band the API marks as a jump stands
 * alone as a step, and neighbours that read the same in whole pence join.
 */
export function ladderRows(bands: readonly DrawdownBand[]): PoundLadderRow[] {
  return ladderRowsOf(bands, sameInPence);
}

/** A ladder row's draw amounts, in words; a jump by where it falls, to the penny. */
export function ladderRange(rows: readonly PoundLadderRow[], index: number, balance: number): string {
  return ladderRangeIn(pounds, rows, index, balance);
}

/** What changes all at once across a jump. */
export function describeStep(from: DrawdownOutcome, to: DrawdownOutcome): string {
  const tax = to.income_tax + to.employee_ni - from.income_tax - from.employee_ni;
  const credit = to.pension_credit - from.pension_credit;
  const parts = [
    ...(Math.round(tax) > 0 ? [`your tax rises by ${pounds(tax)}`] : []),
    ...(Math.round(tax) < 0 ? [`your tax falls by ${pounds(-tax)}`] : []),
    ...(Math.round(credit) < 0 ? [`your Pension Credit falls by ${pounds(-credit)}`] : []),
    ...(Math.round(credit) > 0 ? [`your Pension Credit rises by ${pounds(credit)}`] : []),
  ];
  if (!parts.length) return "Your tax changes all at once here.";
  const sentence = joined(parts);
  return `${sentence.charAt(0).toUpperCase()}${sentence.slice(1)} all at once.`;
}

export const FULL_NEW_STATE_PENSION = 12_547.6;
export const LUMP_SUM_ALLOWANCE = 268_275;
const LARGEST_AMOUNT = 100_000_000;
/** The last birth date of someone who is 55 by 5 April 2027. */
const LAST_BIRTH_FOR_POT = "1972-04-05";

/** The figures the page opens with, for anyone to replace. */
export const EXAMPLE_INPUTS: UKDrawdownYearInput = {
  birth_date: "1958-06-15",
  region: "England",
  tax_year: 2026,
  state_pension: 9_360,
  state_pension_deferred: false,
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
  sipp_tax_free_cash_first: false,
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
      sipp_tax_free_cash_first: false,
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

/**
 * True when the pot drawn from can pay nothing in 2026/27. Pension rules let a
 * pot pay out from age 55 (Finance Act 2004 s.165 pension rule 1, Sch 29 paras
 * 1(1)(d) and 4A(1)(c), s.279), and the API costs a pot draw for anyone 55 by
 * 5 April 2027.
 */
export function potLockedAllYear(inputs: UKDrawdownYearInput): boolean {
  return inputs.draw_source === "sipp" && inputs.birth_date > LAST_BIRTH_FOR_POT;
}

/** The last day of the 2026/27 tax year. */
const TAX_YEAR_END = "2027-04-05";
/**
 * The API counts Pension Credit in the 52 weeks from 6 April 2026 that start on
 * or after the qualifying date. The last of them starts on this day.
 */
export const LAST_PENSION_CREDIT_WEEK_STARTS = "2027-03-29";

/**
 * True when the qualifying date for Pension Credit falls after 2026/27 ends.
 * A date from 30 March to 5 April 2027 is false here: it falls in the tax year,
 * though after the last counted week starts, so the API counts no week.
 */
export function reachesPensionCreditAgeAfterTaxYear(qualifyingDate: string): boolean {
  return qualifyingDate > TAX_YEAR_END;
}

/** What the page shows in place of the curve for a pot locked all year. */
export const LOCKED_POT_MESSAGE =
  "You turn 55 after this tax year ends on 5 April 2027, so your pension pot can’t pay you a pension or lump sum in 2026/27. Take money from your savings instead to see what you’d keep.";

/** What stops the calculation running, in words someone can act on. */
export function inputProblem(inputs: UKDrawdownYearInput): string | null {
  const age = ageAtTaxYearStart(inputs.birth_date);
  if (age === null) return "Enter your date of birth.";
  if (age < 18 || age > 120) {
    return "Enter a date of birth for someone aged 18 to 120 on 6 April 2026.";
  }
  if (inputs.draw_amount > 0 && potLockedAllYear(inputs)) {
    return "You can’t draw from a pension pot before age 55, and you turn 55 after this tax year ends on 5 April 2027. Draw from your savings, or set the draw to £0.";
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

/** What the draw field says when it holds more than the chosen source. */
export function drawLimitNote(inputs: UKDrawdownYearInput): string | null {
  return drawLimitNoteIn(
    pounds,
    inputs.draw_amount,
    sourceBalance(inputs),
    SOURCE_NAMES[inputs.draw_source],
  );
}

/** Keeps the draw inside what the chosen source holds. */
export function withDrawInBounds(inputs: UKDrawdownYearInput): UKDrawdownYearInput {
  const balance = sourceBalance(inputs);
  return inputs.draw_amount > balance ? { ...inputs, draw_amount: balance } : inputs;
}

/**
 * Tax-free cash first applies only to a one-off pot draw with a quarter tax
 * free; any other choice turns it off, as the API requires.
 */
export function withTaxFreeChoiceInBounds(inputs: UKDrawdownYearInput): UKDrawdownYearInput {
  const fits =
    inputs.draw_source === "sipp" &&
    inputs.sipp_draw_pattern === "one_off" &&
    inputs.sipp_tax_free_fraction === 0.25;
  return inputs.sipp_tax_free_cash_first && !fits
    ? { ...inputs, sipp_tax_free_cash_first: false }
    : inputs;
}

/** What the page sends: the draw within the balance and a tax-free choice that applies. */
export function inputsToSend(inputs: UKDrawdownYearInput): UKDrawdownYearInput {
  return withDrawInBounds(withTaxFreeChoiceInBounds(inputs));
}
