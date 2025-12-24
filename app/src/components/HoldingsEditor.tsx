import type { Holding, AccountType, FundType } from '../lib/api';
import '../styles/Wizard.css';

interface HoldingsEditorProps {
  holdings: Holding[];
  onChange: (holdings: Holding[]) => void;
}

const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  traditional_401k: 'Traditional 401(k)',
  traditional_ira: 'Traditional IRA',
  roth_401k: 'Roth 401(k)',
  roth_ira: 'Roth IRA',
  taxable: 'Taxable',
};

const FUND_TYPE_LABELS: Record<FundType, string> = {
  vt: 'VT (Total World)',
  sp500: 'S&P 500',
  bnd: 'BND (Total Bond)',
  treasury: 'Treasury Bonds',
};

export function HoldingsEditor({ holdings, onChange }: HoldingsEditorProps) {
  const addHolding = () => {
    onChange([
      ...holdings,
      {
        account_type: 'traditional_401k',
        fund: 'vt',
        balance: 0,
      },
    ]);
  };

  const removeHolding = (index: number) => {
    onChange(holdings.filter((_, i) => i !== index));
  };

  const updateHolding = (index: number, field: keyof Holding, value: string | number) => {
    const updated = holdings.map((h, i) => {
      if (i === index) {
        return { ...h, [field]: value };
      }
      return h;
    });
    onChange(updated);
  };

  const totalValue = holdings.reduce((sum, h) => sum + h.balance, 0);

  return (
    <div className="holdings-editor">
      {holdings.length === 0 && (
        <div className="holdings-empty">
          <p>Add your portfolio holdings below. Each holding represents an account with a specific fund.</p>
        </div>
      )}

      {holdings.map((holding, index) => (
        <div key={index} className="holding-row">
          <div className="holding-field">
            <label htmlFor={`account-type-${index}`}>Account Type</label>
            <select
              id={`account-type-${index}`}
              value={holding.account_type}
              onChange={(e) =>
                updateHolding(index, 'account_type', e.target.value as AccountType)
              }
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
              onChange={(e) => updateHolding(index, 'fund', e.target.value as FundType)}
            >
              {Object.entries(FUND_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div className="holding-field">
            <label htmlFor={`balance-${index}`}>Balance</label>
            <div className="wizard-field-prefix">
              <span>$</span>
              <input
                id={`balance-${index}`}
                type="number"
                value={holding.balance}
                onChange={(e) => updateHolding(index, 'balance', Number(e.target.value))}
                min={0}
                step={1000}
              />
            </div>
          </div>

          <button
            type="button"
            className="remove-holding-btn"
            onClick={() => removeHolding(index)}
            aria-label="Remove holding"
          >
            ×
          </button>
        </div>
      ))}

      <button type="button" className="add-holding-btn" onClick={addHolding}>
        + Add Holding
      </button>

      {holdings.length > 0 && (
        <div className="holdings-total">
          <span>Total Portfolio:</span>
          <span className="total-value">${totalValue.toLocaleString()}</span>
        </div>
      )}
    </div>
  );
}
