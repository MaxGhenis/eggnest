import { useState, useCallback } from "react";
import type { Holding, AccountType, FundType } from "../lib/api";
import {
  validateHolding,
  type ValidationError,
} from "../lib/validation";
import "../styles/Wizard.css";

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
  { label: string; className: string }
> = {
  traditional_401k: { label: "Pre-tax", className: "tax-badge-pretax" },
  traditional_ira: { label: "Pre-tax", className: "tax-badge-pretax" },
  roth_401k: { label: "Tax-free", className: "tax-badge-roth" },
  roth_ira: { label: "Tax-free", className: "tax-badge-roth" },
  taxable: { label: "Capital gains", className: "tax-badge-taxable" },
};

const FUND_TYPE_LABELS: Record<FundType, string> = {
  vt: "VT (Total World)",
  sp500: "S&P 500",
  bnd: "BND (Total Bond)",
  treasury: "Treasury Bonds",
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
      {
        account_type: "traditional_401k",
        fund: "vt",
        balance: 0,
      },
    ]);
  };

  const removeHolding = (index: number) => {
    onChange(holdings.filter((_, i) => i !== index));
  };

  const updateHolding = (
    index: number,
    field: keyof Holding,
    value: string | number
  ) => {
    const updated = holdings.map((h, i) => {
      if (i === index) {
        return { ...h, [field]: value };
      }
      return h;
    });
    onChange(updated);
  };

  const totalValue = holdings.reduce((sum, h) => sum + h.balance, 0);

  // Compute per-holding validation errors
  const getHoldingErrors = (holding: Holding, index: number): ValidationError[] => {
    return validateHolding(holding, index);
  };

  const getFieldError = (
    errors: ValidationError[],
    field: string
  ): string | undefined => {
    return errors.find((e) => e.field === field)?.message;
  };

  return (
    <div className="holdings-editor" role="group" aria-label="Portfolio holdings">
      {holdings.length === 0 && (
        <div className="holdings-empty" aria-live="polite">
          <div className="empty-icon" aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              width="40"
              height="40"
              aria-hidden="true"
            >
              <path d="M3 3h18v18H3zM7 7h4v4H7zM13 7h4v4h-4zM7 13h4v4H7zM13 13h4v4h-4z" />
            </svg>
          </div>
          <p className="empty-title">No holdings added yet</p>
          <p className="empty-description">
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
        const balanceError = getFieldError(
          errors,
          `holdings[${index}].balance`
        );
        const isBalanceTouched = touchedFields.has(balanceFieldId);

        return (
          <fieldset
            key={index}
            className="holding-row"
            aria-label={`Holding ${index + 1}`}
          >
            <div className="holding-field">
              <label htmlFor={`account-type-${index}`}>
                Account type
                <span className={`tax-badge ${taxTreatment.className}`}>
                  {taxTreatment.label}
                </span>
              </label>
              <select
                id={`account-type-${index}`}
                value={holding.account_type}
                onChange={(e) =>
                  updateHolding(
                    index,
                    "account_type",
                    e.target.value as AccountType
                  )
                }
                aria-label={`Account type for holding ${index + 1}`}
              >
                {Object.entries(ACCOUNT_TYPE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            <div className="holding-field">
              <label htmlFor={`fund-${index}`}>Fund</label>
              <select
                id={`fund-${index}`}
                value={holding.fund}
                onChange={(e) =>
                  updateHolding(index, "fund", e.target.value as FundType)
                }
                aria-label={`Fund type for holding ${index + 1}`}
              >
                {Object.entries(FUND_TYPE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            <div className="holding-field">
              <label htmlFor={balanceFieldId}>Balance</label>
              <div className="wizard-field-prefix">
                <span aria-hidden="true">$</span>
                <input
                  id={balanceFieldId}
                  type="number"
                  value={holding.balance}
                  onChange={(e) =>
                    updateHolding(index, "balance", Number(e.target.value))
                  }
                  onBlur={() => markTouched(balanceFieldId)}
                  min={0}
                  step={1000}
                  aria-invalid={
                    isBalanceTouched && balanceError ? "true" : undefined
                  }
                  aria-describedby={
                    isBalanceTouched && balanceError
                      ? balanceErrorId
                      : undefined
                  }
                  aria-label={`Balance for holding ${index + 1}`}
                />
              </div>
              {isBalanceTouched && balanceError && (
                <p
                  id={balanceErrorId}
                  className="field-error"
                  role="alert"
                >
                  {balanceError}
                </p>
              )}
            </div>

            <button
              type="button"
              className="remove-holding-btn"
              onClick={() => removeHolding(index)}
              aria-label={`Remove holding ${index + 1}`}
            >
              <span aria-hidden="true">&times;</span>
            </button>
          </fieldset>
        );
      })}

      <button
        type="button"
        className="add-holding-btn"
        onClick={addHolding}
        aria-label="Add a new holding"
      >
        + Add Holding
      </button>

      {holdings.length > 0 && (
        <div className="holdings-total" aria-live="polite">
          <span>Total Portfolio:</span>
          <span className="total-value">${totalValue.toLocaleString()}</span>
        </div>
      )}
    </div>
  );
}
