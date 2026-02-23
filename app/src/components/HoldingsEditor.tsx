"use client";

import { useState, useCallback } from "react";
import type { Holding, AccountType, FundType } from "../lib/api";
import {
  validateHolding,
  type ValidationError,
} from "../lib/validation";

interface HoldingsEditorProps {
  holdings: Holding[];
  onChange: (holdings: Holding[]) => void;
}

const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  traditional_401k: "Traditional 401(k)",
  traditional_ira: "Traditional IRA",
  roth_401k: "Roth 401(k)",
  roth_ira: "Roth IRA",
  taxable: "Taxable",
};

const ACCOUNT_TAX_TREATMENT: Record<
  AccountType,
  { label: string; colorClass: string }
> = {
  traditional_401k: { label: "Pre-tax", colorClass: "bg-amber-100 text-amber-800" },
  traditional_ira: { label: "Pre-tax", colorClass: "bg-amber-100 text-amber-800" },
  roth_401k: { label: "Tax-free", colorClass: "bg-emerald-100 text-emerald-800" },
  roth_ira: { label: "Tax-free", colorClass: "bg-emerald-100 text-emerald-800" },
  taxable: { label: "Capital gains", colorClass: "bg-stone-100 text-stone-700" },
};

const FUND_TYPE_LABELS: Record<FundType, string> = {
  vt: "VT (Total World)",
  sp500: "S&P 500",
  bnd: "BND (Total Bond)",
  treasury: "Treasury bonds",
};

export function HoldingsEditor({ holdings, onChange }: HoldingsEditorProps) {
  const [touchedFields, setTouchedFields] = useState<Set<string>>(new Set());

  const markTouched = useCallback((fieldId: string) => {
    setTouchedFields((prev) => {
      const next = new Set(prev);
      next.add(fieldId);
      return next;
    });
  }, []);

  const addHolding = () => {
    onChange([
      ...holdings,
      { account_type: "traditional_401k", fund: "vt", balance: 0 },
    ]);
  };

  const removeHolding = (index: number) => {
    onChange(holdings.filter((_, i) => i !== index));
  };

  const updateHolding = (index: number, field: keyof Holding, value: string | number) => {
    const updated = holdings.map((h, i) =>
      i === index ? { ...h, [field]: value } : h
    );
    onChange(updated);
  };

  const totalValue = holdings.reduce((sum, h) => sum + h.balance, 0);

  const getHoldingErrors = (holding: Holding, index: number): ValidationError[] => {
    return validateHolding(holding, index);
  };

  const getFieldError = (errors: ValidationError[], field: string): string | undefined => {
    return errors.find((e) => e.field === field)?.message;
  };

  return (
    <div className="space-y-3" role="group" aria-label="Portfolio holdings">
      {holdings.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-[var(--radius-lg)] border-2 border-dashed border-[var(--color-border)] p-8 text-center" aria-live="polite">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-10 w-10 text-[var(--color-text-light)]" aria-hidden="true">
            <path d="M3 3h18v18H3zM7 7h4v4H7zM13 7h4v4h-4zM7 13h4v4H7zM13 13h4v4h-4z" />
          </svg>
          <p className="font-semibold text-[var(--color-text)]">No holdings added yet</p>
          <p className="max-w-xs text-sm text-[var(--color-text-muted)]">
            Add each retirement account separately. Traditional accounts are
            withdrawn first for tax efficiency, followed by taxable, then Roth.
          </p>
        </div>
      )}

      {holdings.map((holding, index) => {
        const taxTreatment = ACCOUNT_TAX_TREATMENT[holding.account_type];
        const errors = getHoldingErrors(holding, index);
        const balanceFieldId = `balance-${index}`;
        const balanceErrorId = `balance-error-${index}`;
        const balanceError = getFieldError(errors, `holdings[${index}].balance`);
        const isBalanceTouched = touchedFields.has(balanceFieldId);

        return (
          <fieldset
            key={index}
            className="relative grid grid-cols-[1fr_1fr_auto_auto] items-end gap-3 rounded-[var(--radius-md)] border border-[var(--color-border-light)] bg-[var(--color-gray-50)] p-4"
            aria-label={`Holding ${index + 1}`}
          >
            <div>
              <label htmlFor={`account-type-${index}`} className="mb-1 flex items-center gap-2 text-xs font-medium text-[var(--color-text-muted)]">
                Account type
                <span className={`inline-block rounded-full px-2 py-0.5 text-[0.65rem] font-semibold ${taxTreatment.colorClass}`}>
                  {taxTreatment.label}
                </span>
              </label>
              <select
                id={`account-type-${index}`}
                value={holding.account_type}
                onChange={(e) => updateHolding(index, "account_type", e.target.value as AccountType)}
                className="w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-3 py-2 text-sm transition-colors focus:border-[var(--color-primary)] focus:outline-none"
              >
                {Object.entries(ACCOUNT_TYPE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor={`fund-${index}`} className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
                Fund
              </label>
              <select
                id={`fund-${index}`}
                value={holding.fund}
                onChange={(e) => updateHolding(index, "fund", e.target.value as FundType)}
                className="w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-3 py-2 text-sm transition-colors focus:border-[var(--color-primary)] focus:outline-none"
              >
                {Object.entries(FUND_TYPE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor={balanceFieldId} className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
                Balance
              </label>
              <div className="flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white transition-colors focus-within:border-[var(--color-primary)]">
                <span className="pl-3 text-sm text-[var(--color-text-light)]" aria-hidden="true">$</span>
                <input
                  id={balanceFieldId}
                  type="number"
                  value={holding.balance}
                  onChange={(e) => updateHolding(index, "balance", Number(e.target.value))}
                  onBlur={() => markTouched(balanceFieldId)}
                  min={0}
                  step={1000}
                  className="w-24 border-none bg-transparent px-2 py-2 text-sm focus:outline-none"
                  aria-invalid={isBalanceTouched && balanceError ? "true" : undefined}
                  aria-describedby={isBalanceTouched && balanceError ? balanceErrorId : undefined}
                />
              </div>
              {isBalanceTouched && balanceError && (
                <p id={balanceErrorId} className="mt-1 text-xs text-[var(--color-danger)]" role="alert">
                  {balanceError}
                </p>
              )}
            </div>

            <button
              type="button"
              className="mb-0.5 flex h-9 w-9 items-center justify-center rounded-full text-[var(--color-text-light)] transition-colors hover:bg-[var(--color-danger-light)] hover:text-[var(--color-danger)]"
              onClick={() => removeHolding(index)}
              aria-label={`Remove holding ${index + 1}`}
            >
              <span aria-hidden="true" className="text-lg">&times;</span>
            </button>
          </fieldset>
        );
      })}

      <button
        type="button"
        className="w-full rounded-[var(--radius-md)] border-2 border-dashed border-[var(--color-border)] py-2.5 text-sm font-medium text-[var(--color-primary)] transition-all hover:border-[var(--color-primary)] hover:bg-[var(--color-primary-50)]"
        onClick={addHolding}
        aria-label="Add a new holding"
      >
        + Add holding
      </button>

      {holdings.length > 0 && (
        <div className="flex items-center justify-between rounded-[var(--radius-md)] bg-[var(--color-primary-50)] px-4 py-3" aria-live="polite">
          <span className="text-sm font-medium text-[var(--color-text-muted)]">Total portfolio:</span>
          <span className="text-lg font-bold text-[var(--color-primary)]">${totalValue.toLocaleString()}</span>
        </div>
      )}
    </div>
  );
}
