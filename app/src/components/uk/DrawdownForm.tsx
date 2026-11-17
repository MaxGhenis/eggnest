"use client";

import { useId } from "react";
import type {
  DrawPattern,
  DrawRegion,
  DrawSource,
  UKDrawdownYearInput,
} from "../../lib/api-uk-drawdown";
import { LUMP_SUM_ALLOWANCE, drawLimitNote } from "../../lib/uk-drawdown";
import { Choice, Group, INPUT_CLASS, Label, NumberField, Toggle, hintId } from "../drawdown/fields";

type TaxFreeChoice = "quarter" | "none" | "first";

function taxFreeChoice(inputs: UKDrawdownYearInput): TaxFreeChoice {
  if (inputs.sipp_tax_free_fraction === 0) return "none";
  return inputs.sipp_tax_free_cash_first ? "first" : "quarter";
}

const TAX_FREE_UPDATES: Record<TaxFreeChoice, Partial<UKDrawdownYearInput>> = {
  quarter: { sipp_tax_free_fraction: 0.25, sipp_tax_free_cash_first: false },
  none: { sipp_tax_free_fraction: 0, sipp_tax_free_cash_first: false },
  first: { sipp_tax_free_fraction: 0.25, sipp_tax_free_cash_first: true },
};

const TAX_FREE_HINTS: Record<TaxFreeChoice, string> = {
  quarter: "A quarter of each withdrawal comes tax free. Choose none if you’ve already taken your tax-free cash.",
  none: "Choose none if you’ve already taken your tax-free cash.",
  first:
    "Up to a quarter of your pot comes out tax free first, within your Lump Sum Allowance, and the rest of the draw is taxed.",
};

const SOURCES: { value: DrawSource; label: string }[] = [
  { value: "sipp", label: "Pension pot" },
  { value: "isa", label: "ISAs" },
  { value: "gia", label: "Investments" },
  { value: "cash", label: "Cash" },
];

const REGIONS: DrawRegion[] = ["England", "Wales", "Northern Ireland"];

export function DrawdownForm({
  inputs,
  onChange,
}: {
  inputs: UKDrawdownYearInput;
  onChange: (update: Partial<UKDrawdownYearInput>) => void;
}) {
  const birthId = useId();
  const regionId = useId();
  const onPot = inputs.draw_source === "sipp";
  const oneOff = inputs.sipp_draw_pattern === "one_off";
  // Cash first applies only to a one-off draw; a regular draw shows a quarter.
  const taxFree = taxFreeChoice(inputs) === "first" && !oneOff ? "quarter" : taxFreeChoice(inputs);

  return (
    <form
      id="your-figures"
      className="scroll-mt-20 space-y-7 rounded-[var(--radius-lg)] bg-[var(--color-bg-card)] p-5 shadow-[var(--shadow-sm)]"
      onSubmit={(event) => event.preventDefault()}
    >
      <Group title="Your draw">
        <Choice
          legend="Take money from"
          name="draw_source"
          value={inputs.draw_source}
          options={SOURCES}
          onChange={(draw_source) => onChange({ draw_source })}
        />
        <NumberField
          label="Amount to draw in 2026/27"
          note={drawLimitNote(inputs)}
          prefix="£"
          value={inputs.draw_amount}
          onChange={(draw_amount) => onChange({ draw_amount })}
        />
        {onPot && (
          <>
            <Choice<DrawPattern>
              legend="How you’ll take it"
              hint={
                inputs.sipp_draw_pattern === "regular"
                  ? "DWP counts regular withdrawals as income."
                  : "DWP counts a one-off withdrawal as savings and values what’s left in your pot again."
              }
              name="sipp_draw_pattern"
              value={inputs.sipp_draw_pattern}
              options={[
                { value: "regular", label: "Regular" },
                { value: "one_off", label: "One-off" },
              ]}
              onChange={(sipp_draw_pattern) => onChange({ sipp_draw_pattern })}
            />
            <Choice<TaxFreeChoice>
              legend="Tax-free cash"
              hint={TAX_FREE_HINTS[taxFree]}
              name="sipp_tax_free"
              value={taxFree}
              options={[
                { value: "quarter", label: "A quarter" },
                { value: "none", label: "None" },
                ...(oneOff
                  ? [{ value: "first" as const, label: "Tax-free cash first", wide: true }]
                  : []),
              ]}
              onChange={(choice) => onChange(TAX_FREE_UPDATES[choice])}
            />
          </>
        )}
      </Group>

      <Group title="About you">
        <div>
          <Label htmlFor={birthId} text="Date of birth" />
          <input
            id={birthId}
            type="date"
            className={`${INPUT_CLASS} mt-1`}
            value={inputs.birth_date}
            onChange={(event) => onChange({ birth_date: event.target.value })}
          />
        </div>
        <div>
          <Label
            htmlFor={regionId}
            text="Where you live"
            hint="The Scottish Parliament sets its own income tax rates, which we don’t cover."
          />
          <select
            id={regionId}
            aria-describedby={hintId(regionId)}
            className={`${INPUT_CLASS} mt-1`}
            value={inputs.region}
            onChange={(event) => onChange({ region: event.target.value as DrawRegion })}
          >
            {REGIONS.map((region) => (
              <option key={region}>{region}</option>
            ))}
          </select>
        </div>
      </Group>

      <Group title="Income in 2026/27, before you draw">
        <NumberField
          label="State Pension, yearly rate"
          hint="The full new State Pension is £12,547.60 a year. We count yours from State Pension age."
          prefix="£"
          value={inputs.state_pension}
          onChange={(state_pension) => onChange({ state_pension })}
        />
        {inputs.state_pension > 0 && (
          <Toggle
            label="I’m putting off claiming it"
            hint="Pension Credit still counts a State Pension you could claim."
            checked={inputs.state_pension_deferred}
            onChange={(state_pension_deferred) => onChange({ state_pension_deferred })}
          />
        )}
        <NumberField
          label="Other pensions and annuities"
          prefix="£"
          value={inputs.other_pension_income}
          onChange={(other_pension_income) => onChange({ other_pension_income })}
        />
        <NumberField
          label="Earnings"
          prefix="£"
          value={inputs.employment_income}
          onChange={(employment_income) => onChange({ employment_income })}
        />
        <NumberField
          label="Interest outside ISAs"
          prefix="£"
          value={inputs.savings_interest}
          onChange={(savings_interest) => onChange({ savings_interest })}
        />
        <NumberField
          label="Dividends outside ISAs"
          prefix="£"
          value={inputs.dividend_income}
          onChange={(dividend_income) => onChange({ dividend_income })}
        />
      </Group>

      <Group title="What you hold on 6 April 2026">
        <NumberField
          label="Pension pots"
          prefix="£"
          value={inputs.sipp_balance}
          onChange={(sipp_balance) => onChange({ sipp_balance })}
        />
        <NumberField
          label="ISAs"
          prefix="£"
          value={inputs.isa_balance}
          onChange={(isa_balance) => onChange({ isa_balance })}
        />
        <NumberField
          label="Investments outside ISAs"
          prefix="£"
          value={inputs.gia_balance}
          onChange={(gia_balance) => onChange({ gia_balance })}
        />
        <NumberField
          label="Cash and other savings"
          prefix="£"
          value={inputs.cash_savings}
          onChange={(cash_savings) => onChange({ cash_savings })}
        />
      </Group>

      <details>
        <summary className="cursor-pointer font-medium">Change the assumptions</summary>
        <div className="mt-3 space-y-3">
          <NumberField
            label="15-year gilt yield"
            hint="Pension providers use the Government Actuary’s tables to tell DWP what an untouched pot could pay, from this yield and your age. We start from the Bank of England’s 15-year rate of 5.47% on 5 November 2026 and round down to the table’s 5.25% step."
            suffix="%"
            value={inputs.gilt_yield_percent}
            onChange={(gilt_yield_percent) => onChange({ gilt_yield_percent })}
          />
          <NumberField
            label="Annuity income per £1,000 of pot"
            hint="Enter your provider’s figure to use it in place of the table."
            prefix="£"
            value={inputs.annuity_income_per_1000 ?? 0}
            onChange={(value) => onChange({ annuity_income_per_1000: value > 0 ? value : null })}
          />
          <NumberField
            label="Lump Sum Allowance left"
            hint="The most tax-free cash you can still take from your pensions."
            prefix="£"
            value={inputs.lump_sum_allowance_remaining}
            onChange={(value) =>
              onChange({ lump_sum_allowance_remaining: Math.min(value, LUMP_SUM_ALLOWANCE) })
            }
          />
        </div>
      </details>
    </form>
  );
}
