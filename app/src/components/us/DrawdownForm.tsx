"use client";

import { useId } from "react";
import type {
  USDrawOwner,
  USDrawSource,
  USDrawdownPerson,
  USFilingStatus,
  USTraditionalAccount,
} from "../../lib/api-us-drawdown";
import { STATES, drawLimitNote, inputsFrom, type USDrawdownForm } from "../../lib/us-drawdown";
import { Choice, Group, INPUT_CLASS, Label, NumberField, hintId } from "../drawdown/fields";

const SOURCES: { value: USDrawSource; label: string }[] = [
  { value: "traditional", label: "Traditional IRA or 401(k)" },
  { value: "roth", label: "Roth IRA" },
  { value: "taxable", label: "Investments" },
  { value: "cash", label: "Cash" },
];

const ACCOUNTS: { value: USTraditionalAccount; label: string }[] = [
  { value: "ira", label: "IRA" },
  { value: "workplace_plan", label: "Workplace plan" },
];

/** Where a person's other traditional withdrawals come from, once they have some. */
function WithdrawalsFrom({
  legend,
  name,
  person,
  onChange,
}: {
  legend: string;
  name: string;
  person: USDrawdownPerson;
  onChange: (update: Partial<USDrawdownPerson>) => void;
}) {
  if (person.other_traditional_withdrawals <= 0) return null;
  return (
    <Choice<USTraditionalAccount>
      legend={legend}
      name={name}
      value={person.other_withdrawals_account}
      options={ACCOUNTS}
      onChange={(other_withdrawals_account) => onChange({ other_withdrawals_account })}
    />
  );
}

function YearField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: number;
  onChange: (value: number) => void;
}) {
  const id = useId();
  return (
    <div>
      <Label htmlFor={id} text={label} hint={hint} />
      <input
        id={id}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        maxLength={4}
        aria-describedby={hint ? hintId(id) : undefined}
        className={`${INPUT_CLASS} mt-1 tabular-nums`}
        value={value ? String(value) : ""}
        onChange={(event) => {
          const digits = event.target.value.replace(/\D/g, "");
          onChange(digits ? Number(digits) : 0);
        }}
      />
    </div>
  );
}

function PersonIncome({
  person,
  onChange,
}: {
  person: USDrawdownPerson;
  onChange: (update: Partial<USDrawdownPerson>) => void;
}) {
  return (
    <>
      <NumberField
        label="Social Security"
        hint="For the year, before Medicare premiums come out."
        prefix="$"
        value={person.social_security}
        onChange={(social_security) => onChange({ social_security })}
      />
      <NumberField
        label="Pensions and annuities"
        hint="The taxable part of private pensions and annuities."
        prefix="$"
        value={person.pension_income}
        onChange={(pension_income) => onChange({ pension_income })}
      />
      <NumberField
        label="Government pensions"
        hint="Federal, state or local government pensions, which some states tax differently."
        prefix="$"
        value={person.government_pension_income}
        onChange={(government_pension_income) => onChange({ government_pension_income })}
      />
      <NumberField
        label="Earnings"
        prefix="$"
        value={person.earnings}
        onChange={(earnings) => onChange({ earnings })}
      />
    </>
  );
}

export function DrawdownForm({
  form,
  onChange,
}: {
  form: USDrawdownForm;
  onChange: (update: Partial<USDrawdownForm>) => void;
}) {
  const stateId = useId();
  const joint = form.filing_status === "married_filing_jointly";
  const ownsAccount = form.draw_source === "traditional" || form.draw_source === "roth";
  const you = (update: Partial<USDrawdownPerson>) => onChange({ you: { ...form.you, ...update } });
  const spouse = (update: Partial<USDrawdownPerson>) =>
    onChange({ spouse: { ...form.spouse, ...update } });
  const yours = joint ? "Your " : "";

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
          value={form.draw_source}
          options={SOURCES}
          onChange={(draw_source) => onChange({ draw_source })}
        />
        {joint && ownsAccount && (
          <Choice<USDrawOwner>
            legend="Whose account"
            name="draw_owner"
            value={form.draw_owner}
            options={[
              { value: "you", label: "Yours" },
              { value: "spouse", label: "Your spouse’s" },
            ]}
            onChange={(draw_owner) => onChange({ draw_owner })}
          />
        )}
        {form.draw_source === "traditional" && (
          <Choice<USTraditionalAccount>
            legend="Kind of account"
            hint="A workplace plan is a 401(k), 403(b) or similar plan from an employer. Some states tax withdrawals from the two differently."
            name="draw_account"
            value={form.draw_account}
            options={ACCOUNTS}
            onChange={(draw_account) => onChange({ draw_account })}
          />
        )}
        <NumberField
          label="Amount to draw in 2026"
          note={drawLimitNote(inputsFrom(form), form.draw_amount)}
          prefix="$"
          value={form.draw_amount}
          onChange={(draw_amount) => onChange({ draw_amount })}
        />
        {form.draw_source === "taxable" && (
          <NumberField
            label="Gain as a share of each sale"
            hint="The part of each sale above what you paid, on investments you’ve held more than a year. You owe no tax on the rest, which returns what you paid."
            suffix="%"
            value={Math.round(form.taxable_gain_share * 1_000) / 10}
            onChange={(value) => onChange({ taxable_gain_share: Math.min(value, 100) / 100 })}
          />
        )}
      </Group>

      <Group title="Your household">
        <div>
          <Label htmlFor={stateId} text="State" />
          <select
            id={stateId}
            className={`${INPUT_CLASS} mt-1`}
            value={form.state}
            onChange={(event) => onChange({ state: event.target.value })}
          >
            {STATES.map(({ code, name }) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        </div>
        <Choice<USFilingStatus>
          legend="Filing status"
          name="filing_status"
          value={form.filing_status}
          options={[
            { value: "single", label: "Single" },
            { value: "married_filing_jointly", label: "Married, filing jointly" },
          ]}
          onChange={(filing_status) => onChange({ filing_status })}
        />
        <YearField
          label="Your birth year"
          hint="We cover people 65 or older by the end of 2026."
          value={form.you.birth_year}
          onChange={(birth_year) => you({ birth_year })}
        />
        {joint && (
          <YearField
            label="Your spouse’s birth year"
            value={form.spouse.birth_year}
            onChange={(birth_year) => spouse({ birth_year })}
          />
        )}
      </Group>

      <Group
        title={joint ? "Your income in 2026, before you draw" : "Income in 2026, before you draw"}
      >
        <PersonIncome person={form.you} onChange={you} />
      </Group>

      {joint && (
        <Group title="Your spouse’s income in 2026">
          <PersonIncome person={form.spouse} onChange={spouse} />
        </Group>
      )}

      <Group title="Interest and dividends in 2026">
        <NumberField
          label="Taxable interest"
          prefix="$"
          value={form.taxable_interest}
          onChange={(taxable_interest) => onChange({ taxable_interest })}
        />
        <NumberField
          label="Tax-exempt interest"
          hint="Such as from municipal bonds. It can make more of your Social Security taxable and raise what you pay for Medicare."
          prefix="$"
          value={form.tax_exempt_interest}
          onChange={(tax_exempt_interest) => onChange({ tax_exempt_interest })}
        />
        <NumberField
          label="Dividends"
          hint="We treat every dividend as qualified."
          prefix="$"
          value={form.dividends}
          onChange={(dividends) => onChange({ dividends })}
        />
      </Group>

      <Group title="What you hold at the start of 2026">
        <NumberField
          label={`${yours}${joint ? "traditional" : "Traditional"} IRAs and 401(k)s`}
          hint="The balance on December 31, 2025. We figure the 2026 required minimum from it."
          prefix="$"
          value={form.you.traditional_balance}
          onChange={(traditional_balance) => you({ traditional_balance })}
        />
        <NumberField
          label={`${yours}Roth IRAs`}
          prefix="$"
          value={form.you.roth_balance}
          onChange={(roth_balance) => you({ roth_balance })}
        />
        {joint && (
          <>
            <NumberField
              label="Your spouse’s traditional IRAs and 401(k)s"
              prefix="$"
              value={form.spouse.traditional_balance}
              onChange={(traditional_balance) => spouse({ traditional_balance })}
            />
            <NumberField
              label="Your spouse’s Roth IRAs"
              prefix="$"
              value={form.spouse.roth_balance}
              onChange={(roth_balance) => spouse({ roth_balance })}
            />
          </>
        )}
        <NumberField
          label="Investments in taxable accounts"
          prefix="$"
          value={form.taxable_balance}
          onChange={(taxable_balance) => onChange({ taxable_balance })}
        />
        <NumberField
          label="Cash and savings"
          hint="Checking, savings and money market balances."
          prefix="$"
          value={form.cash_savings}
          onChange={(cash_savings) => onChange({ cash_savings })}
        />
      </Group>

      <details>
        <summary className="cursor-pointer font-medium">
          Other withdrawals and Roth conversions
        </summary>
        <div className="mt-3 space-y-3">
          <NumberField
            label={`${yours}${joint ? "other" : "Other"} traditional withdrawals`}
            hint="Withdrawals from traditional IRAs and 401(k)s in 2026 besides the draw above. They count toward the required minimum, which we figure on the whole balance, though each workplace plan must pay out its own."
            prefix="$"
            value={form.you.other_traditional_withdrawals}
            onChange={(other_traditional_withdrawals) => you({ other_traditional_withdrawals })}
          />
          <WithdrawalsFrom
            legend={`${yours}${joint ? "other" : "Other"} withdrawals come from`}
            name="you_other_withdrawals_account"
            person={form.you}
            onChange={you}
          />
          <NumberField
            label={`${yours}Roth conversions`}
            hint="Money you move from traditional accounts to a Roth IRA in 2026. It adds taxable income but no money to spend."
            prefix="$"
            value={form.you.roth_conversion}
            onChange={(roth_conversion) => you({ roth_conversion })}
          />
          {joint && (
            <>
              <NumberField
                label="Your spouse’s other traditional withdrawals"
                prefix="$"
                value={form.spouse.other_traditional_withdrawals}
                onChange={(other_traditional_withdrawals) =>
                  spouse({ other_traditional_withdrawals })
                }
              />
              <WithdrawalsFrom
                legend="Your spouse’s other withdrawals come from"
                name="spouse_other_withdrawals_account"
                person={form.spouse}
                onChange={spouse}
              />
              <NumberField
                label="Your spouse’s Roth conversions"
                prefix="$"
                value={form.spouse.roth_conversion}
                onChange={(roth_conversion) => spouse({ roth_conversion })}
              />
            </>
          )}
        </div>
      </details>
    </form>
  );
}
