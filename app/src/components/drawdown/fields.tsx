"use client";

import { useId, useState, type ReactNode } from "react";

export const INPUT_CLASS =
  "w-full rounded-[var(--radius-sm)] border border-[var(--color-border-strong)] bg-[var(--color-bg-card)] px-3 py-2 text-base";

/** Reads an amount typed with or without a currency or percent sign or commas. */
export function parseAmount(text: string): number {
  const value = Number(text.replace(/[£$%,\s]/g, ""));
  return Number.isFinite(value) && value > 0 ? value : 0;
}

function grouped(value: number): string {
  return value.toLocaleString("en-GB", { maximumFractionDigits: 2 });
}

/** The id of a field's hint, which the field names as its description. */
export function hintId(fieldId: string): string {
  return `${fieldId}-hint`;
}

export function Label({ htmlFor, text, hint }: { htmlFor: string; text: string; hint?: string }) {
  return (
    <>
      <label htmlFor={htmlFor} className="block font-medium">
        {text}
      </label>
      {hint && (
        <p id={hintId(htmlFor)} className="mb-1 text-sm text-[var(--color-text-muted)]">
          {hint}
        </p>
      )}
    </>
  );
}

export function NumberField({
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
          aria-describedby={hint ? hintId(id) : undefined}
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

export function Choice<T extends string | number>({
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
  const id = useId();
  return (
    <fieldset aria-describedby={hint ? hintId(id) : undefined}>
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
      {hint && (
        <p id={hintId(id)} className="mt-1 text-sm text-[var(--color-text-muted)]">
          {hint}
        </p>
      )}
    </fieldset>
  );
}

export function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-3">
      <legend className="mb-2 font-[var(--font-display)] text-xl">{title}</legend>
      {children}
    </fieldset>
  );
}
