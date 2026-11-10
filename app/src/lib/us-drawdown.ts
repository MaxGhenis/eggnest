/**
 * Pure helpers for the one-year US drawdown page. The API calculates every
 * amount; these read amounts off its sweep and put them into words.
 */

import type {
  USCoverage,
  USDrawOwner,
  USDrawSource,
  USDrawdownMarker,
  USDrawdownOutcome,
  USDrawdownPerson,
  USDrawdownSlice,
  USDrawdownYearInput,
  USMedicareSurcharge,
  USRequiredMinimum,
} from "./api-us-drawdown";
import { bandRangeIn, joined, rowAt } from "./drawdown";

export { chartTop, drawStep, niceTicks } from "./drawdown";

const wholeDollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const exactDollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function dollars(value: number): string {
  return wholeDollars.format(Math.round(value) || 0);
}

export function dollarsAndCents(value: number): string {
  return exactDollars.format(value || 0);
}

/** An axis label: $900, $10k, $1.5M. */
export function compactDollars(value: number): string {
  const size = Math.abs(value);
  if (Math.round(size) === 0) return "$0";
  const sign = value < 0 ? "−" : "";
  if (size >= 1_000_000) return `${sign}$${+(size / 1_000_000).toFixed(1)}M`;
  if (size >= 1_000) return `${sign}$${+(size / 1_000).toFixed(1)}k`;
  return `${sign}$${Math.round(size)}`;
}

/** The result at any draw, read along the straight line between sweep rows. */
export function outcomeAt(sweep: USDrawdownOutcome[], draw: number): USDrawdownOutcome {
  return rowAt(sweep, draw);
}

export function taxesOf(row: USDrawdownOutcome): number {
  return row.federal_income_tax + row.state_income_tax + row.other_taxes;
}

/** Where the dollars between two draw amounts go. */
export function sliceBetween(
  sweep: USDrawdownOutcome[],
  from: number,
  to: number,
): USDrawdownSlice | null {
  const a = outcomeAt(sweep, from);
  const b = outcomeAt(sweep, to);
  const width = b.draw - a.draw;
  if (width <= 0) return null;
  return {
    draw_from: a.draw,
    draw_to: b.draw,
    kept: (b.money_to_spend - a.money_to_spend) / width,
    to_tax: (taxesOf(b) - taxesOf(a)) / width,
    to_benefits: (a.benefits - b.benefits) / width,
    social_security_taxed: (b.taxable_social_security - a.taxable_social_security) / width,
  };
}

export interface CentSplit {
  kept: number;
  tax: number;
  /** Cents of benefits lost; below zero when benefits rise. */
  lost: number;
}

/** A slice in whole cents that adds up to 100¢. */
export function splitCents(slice: USDrawdownSlice): CentSplit {
  const tax = Math.round(slice.to_tax * 100) || 0;
  const lost = Math.round(slice.to_benefits * 100) || 0;
  return { kept: 100 - tax - lost, tax, lost };
}

interface ProgramName {
  /** For a table row or a chart label. */
  label: string;
  /** For the middle of a sentence. */
  inline: string;
  plural?: boolean;
}

/** Names for the PolicyEngine-US programs a result can list. */
const PROGRAM_NAMES: Record<string, ProgramName> = {
  snap: { label: "SNAP", inline: "SNAP" },
  ssi: { label: "SSI", inline: "SSI" },
  commodity_supplemental_food_program: {
    label: "CSFP food boxes",
    inline: "CSFP food boxes",
    plural: true,
  },
  household_state_benefits: { label: "State benefits", inline: "state benefits", plural: true },
  tanf: { label: "TANF", inline: "TANF" },
  wic: { label: "WIC", inline: "WIC" },
  housing_assistance: { label: "Housing assistance", inline: "housing assistance" },
  acp: {
    label: "Affordable Connectivity Program",
    inline: "the Affordable Connectivity Program",
  },
  ebb: { label: "Emergency Broadband Benefit", inline: "the Emergency Broadband Benefit" },
  free_school_meals: { label: "Free school meals", inline: "free school meals", plural: true },
  reduced_price_school_meals: {
    label: "Reduced-price school meals",
    inline: "reduced-price school meals",
    plural: true,
  },
  ak_permanent_fund_dividend: {
    label: "Alaska Permanent Fund Dividend",
    inline: "the Alaska Permanent Fund Dividend",
  },
  income_tax_refundable_credits: {
    label: "Federal refundable credits",
    inline: "federal refundable credits",
    plural: true,
  },
  household_refundable_state_tax_credits: {
    label: "State refundable credits",
    inline: "state refundable credits",
    plural: true,
  },
  other_benefits: { label: "Other benefits", inline: "other benefits", plural: true },
  other_computed_income: {
    label: "Other income PolicyEngine-US computes",
    inline: "other income PolicyEngine-US computes",
  },
};

export function programName(program: string): ProgramName {
  const known = PROGRAM_NAMES[program];
  if (known) return known;
  const words = program.replace(/_/g, " ");
  return { label: words.charAt(0).toUpperCase() + words.slice(1), inline: words };
}

export const COVERAGE_NAMES: Record<USCoverage, string> = {
  medicaid: "Medicaid",
  msp: "Medicare Savings Program",
};

export interface ProgramChange {
  program: string;
  /** Dollars of the program lost; below zero when it rises. */
  lost: number;
}

/** Each program that changes between two outcomes, biggest loss first. */
export function programChanges(from: USDrawdownOutcome, to: USDrawdownOutcome): ProgramChange[] {
  const names = new Set([
    ...Object.keys(from.benefits_by_program),
    ...Object.keys(to.benefits_by_program),
  ]);
  return [...names]
    .map((program) => ({
      program,
      lost: (from.benefits_by_program[program] ?? 0) - (to.benefits_by_program[program] ?? 0),
    }))
    .filter((change) => Math.round(change.lost) !== 0)
    .sort((a, b) => b.lost - a.lost);
}

/** The benefits that move across a range of draws, in words: one program by name. */
export function benefitsMoving(from: USDrawdownOutcome, to: USDrawdownOutcome): string {
  const width = to.draw - from.draw;
  const moving = Object.keys(from.benefits_by_program).filter(
    (program) =>
      width > 0 &&
      Math.abs((to.benefits_by_program[program] ?? 0) - from.benefits_by_program[program]) /
        width >=
        0.005,
  );
  if (moving.length === 1) return programName(moving[0]).inline;
  if (moving.length > 1) {
    return `benefits (${joined(moving.map((program) => programName(program).inline))})`;
  }
  return "benefits";
}

function cents(amount: number): string {
  return amount >= 100 ? dollarsAndCents(amount / 100) : `${amount}¢`;
}

/** What happens to each extra dollar of draw. */
export function describeDollar(slice: USDrawdownSlice, benefits = "benefits"): string {
  const { kept, tax, lost } = splitCents(slice);
  const costs = [
    ...(tax > 0 ? [`pay ${tax}¢ in tax`] : []),
    ...(lost > 0 ? [`lose ${lost}¢ of ${benefits}`] : []),
  ];
  const gains = [
    ...(tax < 0 ? [`pay ${-tax}¢ less in tax`] : []),
    ...(lost < 0 ? [`gain ${-lost}¢ of ${benefits}`] : []),
  ];
  let sentence: string;
  if (!costs.length && !gains.length) sentence = "You keep the whole dollar.";
  else if (kept <= 0) sentence = `You keep nothing: you ${joined([...costs, ...gains])}.`;
  else if (gains.length) {
    const keep = kept === 100 ? "the whole dollar" : cents(kept);
    sentence = `You keep ${keep}: you ${joined([...costs, ...gains])}.`;
  } else sentence = `You ${joined([`keep ${cents(kept)}`, ...costs])}.`;
  const taxed = Math.round(slice.social_security_taxed * 100);
  return taxed > 0
    ? `${sentence} Each dollar also makes ${cents(taxed)} more of your Social Security taxable.`
    : sentence;
}

/** Losses under one verb and gains under another: "lose $651 of CSFP food boxes and $369 of SNAP". */
function changeWords(changes: ProgramChange[], lose: string, gain: string): string[] {
  const amount = ({ program, lost }: ProgramChange) =>
    `${dollars(Math.abs(lost))} of ${programName(program).inline}`;
  const losses = changes.filter((change) => change.lost > 0).map(amount);
  const gains = changes.filter((change) => change.lost < 0).map(amount);
  return [
    ...(losses.length ? [`${lose} ${joined(losses)}`] : []),
    ...(gains.length ? [`${gain} ${joined(gains)}`] : []),
  ];
}

/** The next step of draw, in dollars. */
export function describeNextStep(
  slice: USDrawdownSlice,
  from: USDrawdownOutcome,
  to: USDrawdownOutcome,
): string {
  const width = slice.draw_to - slice.draw_from;
  const kept = slice.kept * width;
  const tax = slice.to_tax * width;
  const parts = [
    ...(Math.round(tax) > 0 ? [`pay ${dollars(tax)} in tax`] : []),
    ...(Math.round(tax) < 0 ? [`pay ${dollars(-tax)} less in tax`] : []),
    ...changeWords(programChanges(from, to), "lose", "gain"),
  ];
  const opening = `Draw another ${dollars(width)} and you`;
  let sentence: string;
  if (!parts.length) sentence = `${opening} keep all of it.`;
  else if (Math.round(kept) < 0) {
    sentence = `${opening}’d have ${dollars(-kept)} less to spend: you ${joined(parts)}.`;
  } else if (Math.round(kept) === 0) sentence = `${opening} keep nothing: you ${joined(parts)}.`;
  else sentence = `${opening} keep ${dollars(kept)}: you ${joined(parts)}.`;
  const taxed = slice.social_security_taxed * width;
  return Math.round(taxed) > 0
    ? `${sentence} It also makes ${dollars(taxed)} more of your Social Security taxable.`
    : sentence;
}

/** No phase-out takes more than this per dollar of draw; a slice that moves faster holds a jump. */
const STEP_RATE = 1.05;

export function isStep(slice: USDrawdownSlice): boolean {
  return Math.abs(slice.to_tax) > STEP_RATE || Math.abs(slice.to_benefits) > STEP_RATE;
}

/** What changes all at once across a jump. */
export function describeStep(from: USDrawdownOutcome, to: USDrawdownOutcome): string {
  const parts = programChanges(from, to).map(({ program, lost }) => {
    const name = programName(program);
    if (lost > 0 && Math.round(to.benefits_by_program[program] ?? 0) === 0) {
      return `${name.label} ${name.plural ? "end" : "ends"}, taking ${dollars(lost)}`;
    }
    return lost > 0
      ? `${name.label} ${name.plural ? "fall" : "falls"} by ${dollars(lost)}`
      : `${name.label} ${name.plural ? "rise" : "rises"} by ${dollars(-lost)}`;
  });
  const tax = taxesOf(to) - taxesOf(from);
  if (Math.round(tax) > 0) parts.push(`your tax rises by ${dollars(tax)}`);
  if (Math.round(tax) < 0) parts.push(`your tax falls by ${dollars(-tax)}`);
  if (!parts.length) return "Your benefits change all at once here.";
  const sentence = joined(parts);
  return `${sentence.charAt(0).toUpperCase()}${sentence.slice(1)} all at once.`;
}

export interface LadderRow extends USDrawdownSlice {
  /** A jump: a tax or benefit changes all at once inside this narrow range. */
  step: boolean;
}

function sameInCents(a: USDrawdownSlice, b: USDrawdownSlice): boolean {
  const x = splitCents(a);
  const y = splitCents(b);
  return (
    x.tax === y.tax &&
    x.lost === y.lost &&
    Math.round(a.social_security_taxed * 100) === Math.round(b.social_security_taxed * 100)
  );
}

function joinSlices(a: USDrawdownSlice, b: USDrawdownSlice): USDrawdownSlice {
  const left = a.draw_to - a.draw_from;
  const right = b.draw_to - b.draw_from;
  const mix = (x: number, y: number) => (x * left + y * right) / (left + right);
  return {
    draw_from: a.draw_from,
    draw_to: b.draw_to,
    kept: mix(a.kept, b.kept),
    to_tax: mix(a.to_tax, b.to_tax),
    to_benefits: mix(a.to_benefits, b.to_benefits),
    social_security_taxed: mix(a.social_security_taxed, b.social_security_taxed),
  };
}

/** The API's bands for the ladder: each jump stands alone, and neighbours that read the same in whole cents join. */
export function ladderRows(bands: readonly USDrawdownSlice[]): LadderRow[] {
  const rows: LadderRow[] = [];
  for (const band of bands) {
    const step = isStep(band);
    const last = rows[rows.length - 1];
    if (last && !last.step && !step && sameInCents(last, band)) {
      rows[rows.length - 1] = { ...joinSlices(last, band), step: false };
    } else {
      rows.push({ ...band, step });
    }
  }
  return rows;
}

/** A ladder row's draw amounts, in words. The sweep can stop short of a large balance. */
export function ladderRange(rows: readonly LadderRow[], index: number, balance: number): string {
  const row = rows[index];
  if (row.step) return `At about ${dollars(row.draw_to)}`;
  return bandRangeIn(dollars, rows, index, balance);
}

const SOURCE_NAMES: Record<USDrawSource, (whose: string) => string> = {
  traditional: (whose) => `${whose} traditional IRA or 401(k)`,
  roth: (whose) => `${whose} Roth IRA`,
  taxable: () => "your investments",
  cash: () => "your cash savings",
};

export function sourceName(source: USDrawSource, owner: USDrawOwner): string {
  return SOURCE_NAMES[source](owner === "spouse" ? "your spouse’s" : "your");
}

export function headline(
  source: USDrawSource,
  owner: USDrawOwner,
  draw: number,
  moneyToSpend: number,
): string {
  return draw > 0
    ? `Draw ${dollars(draw)} from ${sourceName(source, owner)} in 2026 and you’ll have ${dollars(moneyToSpend)} to spend.`
    : `Draw nothing in 2026 and you’ll have ${dollars(moneyToSpend)} to spend.`;
}

/** How the chosen draw compares with leaving the money where it sits. */
export function comparedWithNoDraw(
  chosen: USDrawdownOutcome,
  none: USDrawdownOutcome,
): string | null {
  if (chosen.draw <= 0) return null;
  const gain = chosen.money_to_spend - none.money_to_spend;
  const tax = taxesOf(chosen) - taxesOf(none);
  const costs = [
    ...changeWords(programChanges(none, chosen), "losing", "gaining"),
    ...(Math.round(tax) > 0 ? [`paying ${dollars(tax)} more in tax`] : []),
    ...(Math.round(tax) < 0 ? [`paying ${dollars(-tax)} less in tax`] : []),
  ];
  const direction = gain >= 0 ? "more" : "less";
  const lead = `You’d have ${dollars(Math.abs(gain))} ${direction} to spend than if you drew nothing`;
  return costs.length ? `${lead}, after ${joined(costs)}.` : `${lead}.`;
}

/** Health coverage at a draw: what the household has with no draw, less each coverage that has ended by then. */
export function coverageAt(
  withNoDraw: Record<USCoverage, boolean>,
  markers: readonly USDrawdownMarker[],
  draw: number,
): Record<USCoverage, boolean> {
  const coverage = { ...withNoDraw };
  for (const { kind, program, draw: end } of markers) {
    if (kind === "coverage_ends" && program && program in coverage && end <= draw) {
      coverage[program as USCoverage] = false;
    }
  }
  return coverage;
}

/** Each coverage as the subject of a sentence. */
export const COVERAGE_SUBJECTS: Record<USCoverage, string> = {
  medicaid: "Medicaid",
  msp: "help from a Medicare Savings Program",
};

/** Where the household's health coverage ends, in words. */
export function describeCoverageEnds(markers: readonly USDrawdownMarker[]): string | null {
  const ends = markers.filter(
    (marker) =>
      marker.kind === "coverage_ends" && marker.program && marker.program in COVERAGE_SUBJECTS,
  );
  if (!ends.length) return null;
  const sentence = joined(
    ends.map((marker, index) => {
      const subject = COVERAGE_SUBJECTS[marker.program as USCoverage];
      return index === 0
        ? `${subject} ends at a draw of about ${dollars(marker.draw)}`
        : `${subject} at about ${dollars(marker.draw)}`;
    }),
  );
  return `${sentence.charAt(0).toUpperCase()}${sentence.slice(1)}.`;
}

/** Coverage the household has with no draw and loses at this one. */
export function coverageLost(
  withNoDraw: Record<USCoverage, boolean>,
  atDraw: Record<USCoverage, boolean>,
): USCoverage[] {
  return (Object.keys(withNoDraw) as USCoverage[]).filter(
    (name) => withNoDraw[name] && !atDraw[name],
  );
}

export interface RequiredMinimumAtDraw {
  withdrawn: number;
  shortfall: number;
  excise: number;
}

/** A required minimum against the draw on the page, which can be newer than the API's. */
export function requiredMinimumAt(
  minimum: USRequiredMinimum,
  inputs: USDrawdownYearInput,
): RequiredMinimumAtDraw {
  const drawsHere = inputs.draw_source === "traditional" && inputs.draw_owner === minimum.person;
  const withdrawn = minimum.other_withdrawals + (drawsHere ? inputs.draw_amount : 0);
  const shortfall = Math.max(minimum.amount - withdrawn, 0);
  return { withdrawn, shortfall, excise: shortfall * minimum.excise_tax_rate };
}

/** A required minimum in words, for the person it falls on. */
export function describeRequiredMinimum(
  minimum: USRequiredMinimum,
  atDraw: RequiredMinimumAtDraw,
  inputs: USDrawdownYearInput,
): string[] {
  const spouse = minimum.person === "spouse";
  const opening =
    `${spouse ? "Your spouse" : "You"} must take at least ${dollars(minimum.amount)} from ` +
    `traditional IRAs and 401(k)s in 2026. We divide ${spouse ? "their" : "your"} ` +
    `${dollars(minimum.balance)} balance at the end of 2025 by ${minimum.divisor}, ` +
    `the IRS Uniform Lifetime Table’s factor for age ${minimum.age}.`;
  if (Math.round(atDraw.shortfall) <= 0) {
    const fromDraw =
      inputs.draw_source === "traditional" &&
      inputs.draw_owner === minimum.person &&
      inputs.draw_amount > 0;
    const others = `${spouse ? "their" : "your"} other withdrawals`;
    const cover =
      fromDraw && minimum.other_withdrawals > 0
        ? `This draw and ${others} cover it.`
        : fromDraw
          ? "This draw covers it."
          : `${others.charAt(0).toUpperCase()}${others.slice(1)} cover it.`;
    return [opening, cover];
  }
  const taking =
    Math.round(atDraw.withdrawn) > 0
      ? `Withdrawals of ${dollars(atDraw.withdrawn)} fall`
      : "Withdrawing nothing falls";
  return [
    opening,
    `${taking} ${dollars(atDraw.shortfall)} short, so ${spouse ? "your spouse would" : "you’d"} ` +
      `owe an excise tax of ${dollars(atDraw.excise)} ` +
      `(${Math.round(minimum.excise_tax_rate * 100)}% of the shortfall). ` +
      "We leave it out of money to spend.",
  ];
}

/** The warning beside the headline when a draw leaves a required minimum short. */
export function describeShortfall(
  minimum: USRequiredMinimum,
  atDraw: RequiredMinimumAtDraw,
): string {
  const short =
    minimum.person === "spouse"
      ? `Your spouse would fall ${dollars(atDraw.shortfall)} short of their required minimum`
      : `You’d fall ${dollars(atDraw.shortfall)} short of your required minimum`;
  return `${short} and owe an excise tax of ${dollars(atDraw.excise)}, which we leave out of money to spend.`;
}

/** Medicare's income-related premiums two years on, in words. */
export function describeMedicare(
  row: USDrawdownOutcome,
  surcharge: USMedicareSurcharge,
  markers: readonly USDrawdownMarker[],
): string[] {
  const income = row.medicare_income;
  const year = surcharge.premium_year;
  const passed = surcharge.lines.filter((line) => income >= line);
  const nextLine = surcharge.lines.find((line) => income < line) ?? null;
  const nextStep =
    markers.find((marker) => marker.kind === "medicare_surcharge_step" && marker.draw > row.draw) ??
    null;
  const shared = surcharge.people_on_medicare > 1 ? " between the two of you" : "";
  const sentences = [
    row.draw > 0
      ? `This draw puts your 2026 income for Medicare at ${dollars(income)}: adjusted gross income plus tax-exempt interest.`
      : `With no draw, your 2026 income for Medicare comes to ${dollars(income)}: adjusted gross income plus tax-exempt interest.`,
  ];
  if (Math.round(row.later_medicare_surcharge) > 0 && passed.length) {
    sentences.push(
      `That reaches Medicare’s ${dollars(passed[passed.length - 1])} income line, so your ${year} Part B and Part D premiums rise by ${dollars(row.later_medicare_surcharge)} for the year${shared}.`,
    );
  }
  if (nextLine !== null) {
    const again = passed.length ? "again " : "";
    const where = nextStep
      ? `, which a draw of about ${dollars(nextStep.draw)} would do, adding ${dollars(nextStep.amount ?? 0)} a year`
      : "";
    sentences.push(
      `Your ${year} premiums rise ${again}once it reaches ${dollars(nextLine)}${where}.`,
    );
  }
  sentences.push(
    surcharge.rates_year < year
      ? `We apply Medicare’s ${surcharge.rates_year} income lines and amounts. Medicare raises the lines with inflation, so its ${year} lines will exceed these.`
      : `We apply Medicare’s ${surcharge.rates_year} income lines and amounts.`,
  );
  return sentences;
}

const NOBODY: Omit<USDrawdownPerson, "birth_year"> = {
  social_security: 0,
  pension_income: 0,
  government_pension_income: 0,
  earnings: 0,
  traditional_balance: 0,
  roth_balance: 0,
  other_traditional_withdrawals: 0,
  roth_conversion: 0,
};

/** The figures the page opens with, for anyone to replace. */
export const EXAMPLE_INPUTS: USDrawdownYearInput = {
  tax_year: 2026,
  state: "NC",
  filing_status: "single",
  you: { ...NOBODY, birth_year: 1952, social_security: 24_000, traditional_balance: 250_000 },
  spouse: null,
  taxable_interest: 0,
  tax_exempt_interest: 0,
  dividends: 0,
  taxable_balance: 0,
  taxable_gain_share: 0.5,
  cash_savings: 15_000,
  draw_source: "traditional",
  draw_owner: "you",
  draw_amount: 30_000,
};

/** A spouse's figures before anyone enters them. */
export const NEW_SPOUSE: USDrawdownPerson = { ...NOBODY, birth_year: 1955 };

/** What the form holds. A spouse's figures survive a switch to filing single and back. */
export interface USDrawdownForm extends Omit<USDrawdownYearInput, "spouse"> {
  spouse: USDrawdownPerson;
}

export const EXAMPLE_FORM: USDrawdownForm = { ...EXAMPLE_INPUTS, spouse: NEW_SPOUSE };

export function sourceBalance(inputs: USDrawdownYearInput): number {
  if (inputs.draw_source === "taxable") return inputs.taxable_balance;
  if (inputs.draw_source === "cash") return inputs.cash_savings;
  const owner = inputs.draw_owner === "spouse" ? inputs.spouse : inputs.you;
  if (!owner) return 0;
  return inputs.draw_source === "traditional" ? owner.traditional_balance : owner.roth_balance;
}

/** Keeps the draw inside what the chosen source holds. */
export function withDrawInBounds(inputs: USDrawdownYearInput): USDrawdownYearInput {
  const balance = sourceBalance(inputs);
  return inputs.draw_amount > balance ? { ...inputs, draw_amount: balance } : inputs;
}

/** The inputs the API takes, from what the form holds. */
export function inputsFrom(form: USDrawdownForm): USDrawdownYearInput {
  const joint = form.filing_status === "married_filing_jointly";
  const ownsAccount = form.draw_source === "traditional" || form.draw_source === "roth";
  return withDrawInBounds({
    ...form,
    spouse: joint ? form.spouse : null,
    draw_owner: joint && ownsAccount ? form.draw_owner : "you",
  });
}

/** JSON with every object's keys in order, so equal figures always read the same. */
function sortedJSON(value: unknown): string {
  return JSON.stringify(value, (_key, entry) =>
    entry && typeof entry === "object" && !Array.isArray(entry)
      ? Object.fromEntries(Object.entries(entry).sort(([a], [b]) => a.localeCompare(b)))
      : entry,
  );
}

/** True until someone changes a figure about themselves; choices about the draw don't count. */
export function isExamplePerson(inputs: USDrawdownYearInput): boolean {
  const aboutThePerson = (figures: USDrawdownYearInput) =>
    sortedJSON({
      ...figures,
      draw_amount: 0,
      draw_source: "traditional",
      draw_owner: "you",
      taxable_gain_share: 0,
    });
  return aboutThePerson(inputs) === aboutThePerson(EXAMPLE_INPUTS);
}

/** Money the household receives in 2026 before any draw. */
export function cashIncome(inputs: USDrawdownYearInput): number {
  const people = inputs.spouse ? [inputs.you, inputs.spouse] : [inputs.you];
  return (
    people.reduce(
      (sum, person) =>
        sum +
        person.social_security +
        person.pension_income +
        person.government_pension_income +
        person.earnings +
        person.other_traditional_withdrawals,
      0,
    ) +
    inputs.taxable_interest +
    inputs.tax_exempt_interest +
    inputs.dividends
  );
}

/** 120 at the end of 2026. */
export const OLDEST_BIRTH_YEAR = 1906;
/** 65 at the end of 2026, the youngest the calculator covers. */
export const YOUNGEST_BIRTH_YEAR = 1961;
const LARGEST_AMOUNT = 100_000_000;

/** What stops the calculation running, in words someone can act on. */
export function inputProblem(inputs: USDrawdownYearInput): string | null {
  const people: [string, USDrawdownPerson][] = [["your", inputs.you]];
  if (inputs.spouse) people.push(["your spouse’s", inputs.spouse]);
  for (const [whose, person] of people) {
    const year = person.birth_year;
    if (!Number.isInteger(year) || year < OLDEST_BIRTH_YEAR || year > YOUNGEST_BIRTH_YEAR) {
      return `Enter ${whose} birth year, from ${OLDEST_BIRTH_YEAR} to ${YOUNGEST_BIRTH_YEAR}. We cover people 65 or older by the end of 2026.`;
    }
  }
  const amounts = [
    ...people.flatMap(([, person]) => [
      person.social_security,
      person.pension_income,
      person.government_pension_income,
      person.earnings,
      person.traditional_balance,
      person.roth_balance,
      person.other_traditional_withdrawals,
      person.roth_conversion,
    ]),
    inputs.taxable_interest,
    inputs.tax_exempt_interest,
    inputs.dividends,
    inputs.taxable_balance,
    inputs.cash_savings,
  ];
  if (amounts.some((amount) => amount > LARGEST_AMOUNT)) return "Enter amounts up to $100 million.";
  return null;
}

/** What to do when the chosen source holds nothing to draw. */
export function emptySourceMessage(source: USDrawSource, owner: USDrawOwner): string {
  const spouses = owner === "spouse" && (source === "traditional" || source === "roth");
  return spouses
    ? `Enter how much your spouse has in ${SOURCE_NAMES[source]("their")} to see what you’d keep.`
    : `Enter how much you have in ${sourceName(source, owner)} to see what you’d keep.`;
}

/** Labels for the chart's markers. */
export function markerLabel(marker: USDrawdownMarker): string {
  switch (marker.kind) {
    case "benefit_ends": {
      const name = programName(marker.program ?? "benefits");
      return `${name.label} ${name.plural ? "end" : "ends"}`;
    }
    case "coverage_ends":
      return `${COVERAGE_NAMES[marker.program as USCoverage] ?? "Coverage"} ends`;
    case "medicare_surcharge_step":
      return `2028 Medicare premiums up ${dollars(marker.amount ?? 0)}`;
    case "required_minimum_reached":
      return "Covers the required minimum";
  }
}

/** The 50 states and DC, by name. */
export const STATES: { code: string; name: string }[] = [
  ["AL", "Alabama"],
  ["AK", "Alaska"],
  ["AZ", "Arizona"],
  ["AR", "Arkansas"],
  ["CA", "California"],
  ["CO", "Colorado"],
  ["CT", "Connecticut"],
  ["DE", "Delaware"],
  ["DC", "District of Columbia"],
  ["FL", "Florida"],
  ["GA", "Georgia"],
  ["HI", "Hawaii"],
  ["ID", "Idaho"],
  ["IL", "Illinois"],
  ["IN", "Indiana"],
  ["IA", "Iowa"],
  ["KS", "Kansas"],
  ["KY", "Kentucky"],
  ["LA", "Louisiana"],
  ["ME", "Maine"],
  ["MD", "Maryland"],
  ["MA", "Massachusetts"],
  ["MI", "Michigan"],
  ["MN", "Minnesota"],
  ["MS", "Mississippi"],
  ["MO", "Missouri"],
  ["MT", "Montana"],
  ["NE", "Nebraska"],
  ["NV", "Nevada"],
  ["NH", "New Hampshire"],
  ["NJ", "New Jersey"],
  ["NM", "New Mexico"],
  ["NY", "New York"],
  ["NC", "North Carolina"],
  ["ND", "North Dakota"],
  ["OH", "Ohio"],
  ["OK", "Oklahoma"],
  ["OR", "Oregon"],
  ["PA", "Pennsylvania"],
  ["RI", "Rhode Island"],
  ["SC", "South Carolina"],
  ["SD", "South Dakota"],
  ["TN", "Tennessee"],
  ["TX", "Texas"],
  ["UT", "Utah"],
  ["VT", "Vermont"],
  ["VA", "Virginia"],
  ["WA", "Washington"],
  ["WV", "West Virginia"],
  ["WI", "Wisconsin"],
  ["WY", "Wyoming"],
].map(([code, name]) => ({ code, name }));
