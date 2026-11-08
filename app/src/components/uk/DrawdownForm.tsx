"use client";

import { useId, useState, type ReactNode } from "react";
import type {
  DrawPattern,
  DrawRegion,
  DrawSource,
  UKDrawdownYearInput,
} from "../../lib/api-uk-drawdown";
import { LUMP_SUM_ALLOWANCE } from "../../lib/uk-drawdown";

const INPUT_CLASS =
  "w-full rounded-[var(--radius-sm)] border border-[var(--color-border-strong)] bg-[var(--color-bg-card)] px-3 py-2 text-base";

function parseAmount(text: string): number {
  const value = Number(text.replace(/[£,\s]/g, ""));
  return Number.isFinite(value) && value > 0 ? value : 0;
}

function grouped(value: number): string {
  return value.toLocaleString("en-GB", { maximumFractionDigits: 2 });
}

function Label({ htmlFor, text, hint }: { htmlFor: string; text: string; hint?: string }) {
  return (
    <>
      <label htmlFor={htmlFor} className="block font-medium">
        {text}
      </label>
      {hint && <p className="mb-1 text-sm text-[var(--color-text-muted)]">{hint}</p>}
    </>
  );
}

function NumberField({
  label,
  hint,
  value,
  prefix,
  suffix,
  onChange,
}: {
  label: string;
  hint?: string;
  value: number;
  prefix?: string;
  suffix?: string;
  onChange: (value: number) => void;
}) {
  const id = useId();
  const [draft, setDraft] = useState<string | null>(null);
  return (
    <div>
      <Label htmlFor={id} text={label} hint={hint} />
      <div className="relative mt-1">
        {prefix && (
          <span
            aria-hidden="true"
            className="absolute inset-y-0 left-3 flex items-center text-[var(--color-text-muted)]"
          >
            {prefix}
          </span>
        )}
        <input
          id={id}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          className={`${INPUT_CLASS} tabular-nums ${prefix ? "pl-7" : ""}`}
          value={draft ?? grouped(value)}
          onFocus={() => setDraft(value ? String(value) : "")}
          onChange={(event) => {
            setDraft(event.target.value);
            onChange(parseAmount(event.target.value));
          }}
          onBlur={() => setDraft(null)}
        />
        {suffix && (
          <span
            aria-hidden="true"
            className="absolute inset-y-0 right-3 flex items-center text-[var(--color-text-muted)]"
          >
            {suffix}
          </span>
        )}
      </div>
    </div>
  );
}

function Choice<T extends string | number>({
  legend,
  hint,
  name,
  value,
  options,
  onChange,
}: {
  legend: string;
  hint?: string;
  name: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <fieldset>
      <legend className="font-medium">{legend}</legend>
      <div className="mt-1 grid grid-cols-2 gap-1.5">
        {options.map((option) => (
          <label key={String(option.value)} className="cursor-pointer">
            <input
              type="radio"
              className="peer sr-only"
              name={name}
              checked={option.value === value}
              onChange={() => onChange(option.value)}
            />
            <span className="block rounded-[var(--radius-sm)] border border-[var(--color-border-strong)] bg-[var(--color-bg-card)] px-3 py-2 text-center peer-checked:border-[var(--color-primary-dark)] peer-checked:bg-[var(--color-primary-dark)] peer-checked:text-white peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--color-focus-ring)]">
              {option.label}
            </span>
          </label>
        ))}
      </div>
      {hint && <p className="mt-1 text-sm text-[var(--color-text-muted)]">{hint}</p>}
    </fieldset>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-3">
      <legend className="mb-2 font-[var(--font-display)] text-xl">{title}</legend>
      {children}
    </fieldset>
  );
}

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
            <Choice<number>
              legend="Tax-free share of each withdrawal"
              hint="Choose none if you’ve already taken your tax-free cash."
              name="sipp_tax_free_fraction"
              value={inputs.sipp_tax_free_fraction}
              options={[
                { value: 0.25, label: "A quarter" },
                { value: 0, label: "None" },
              ]}
              onChange={(sipp_tax_free_fraction) => onChange({ sipp_tax_free_fraction })}
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
          label="State Pension"
          hint="The full new State Pension pays £12,547.60. Include yours from State Pension age, even if you haven’t claimed it."
          prefix="£"
          value={inputs.state_pension}
          onChange={(state_pension) => onChange({ state_pension })}
        />
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
