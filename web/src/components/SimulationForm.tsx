import { useState } from "react";
import type { SimulationInput } from "../lib/api";

interface SimulationFormProps {
  onSubmit: (params: SimulationInput) => void;
  isLoading: boolean;
}

const US_STATES = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
];

export function SimulationForm({ onSubmit, isLoading }: SimulationFormProps) {
  const [formData, setFormData] = useState({
    initial_capital: 1000000,
    target_monthly_income: 5000,
    social_security_monthly: 2000,
    current_age: 65,
    retirement_age: 65,
    state: "CA",
    filing_status: "single",
    n_simulations: 10000,
    n_years: 30,
    expected_return: 0.07,
    return_volatility: 0.16,
    dividend_yield: 0.02,
    inflation_rate: 0.03,
  });

  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  const updateField = (field: string, value: number | string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <form onSubmit={handleSubmit} className="simulation-form">
      <div className="form-section">
        <h3>Financial Situation</h3>

        <div className="form-group">
          <label htmlFor="initial_capital">Initial Investment</label>
          <div className="input-with-prefix">
            <span>$</span>
            <input
              type="number"
              id="initial_capital"
              value={formData.initial_capital}
              onChange={(e) => updateField("initial_capital", Number(e.target.value))}
              min={0}
              step={10000}
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="target_monthly_income">Target Monthly Income</label>
          <div className="input-with-prefix">
            <span>$</span>
            <input
              type="number"
              id="target_monthly_income"
              value={formData.target_monthly_income}
              onChange={(e) => updateField("target_monthly_income", Number(e.target.value))}
              min={0}
              step={500}
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="social_security_monthly">Monthly Social Security</label>
          <div className="input-with-prefix">
            <span>$</span>
            <input
              type="number"
              id="social_security_monthly"
              value={formData.social_security_monthly}
              onChange={(e) => updateField("social_security_monthly", Number(e.target.value))}
              min={0}
              step={100}
            />
          </div>
        </div>
      </div>

      <div className="form-section">
        <h3>Personal Details</h3>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="current_age">Current Age</label>
            <input
              type="number"
              id="current_age"
              value={formData.current_age}
              onChange={(e) => updateField("current_age", Number(e.target.value))}
              min={18}
              max={100}
            />
          </div>

          <div className="form-group">
            <label htmlFor="retirement_age">Retirement Age</label>
            <input
              type="number"
              id="retirement_age"
              value={formData.retirement_age}
              onChange={(e) => updateField("retirement_age", Number(e.target.value))}
              min={formData.current_age}
              max={100}
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="state">State</label>
            <select
              id="state"
              value={formData.state}
              onChange={(e) => updateField("state", e.target.value)}
            >
              {US_STATES.map((st) => (
                <option key={st} value={st}>{st}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="filing_status">Filing Status</label>
            <select
              id="filing_status"
              value={formData.filing_status}
              onChange={(e) => updateField("filing_status", e.target.value)}
            >
              <option value="single">Single</option>
              <option value="married_filing_jointly">Married Filing Jointly</option>
              <option value="married_filing_separately">Married Filing Separately</option>
              <option value="head_of_household">Head of Household</option>
            </select>
          </div>
        </div>
      </div>

      <div className="form-section">
        <h3>Simulation Settings</h3>

        <div className="form-group">
          <label htmlFor="n_years">Simulation Years</label>
          <input
            type="number"
            id="n_years"
            value={formData.n_years}
            onChange={(e) => updateField("n_years", Number(e.target.value))}
            min={1}
            max={60}
          />
        </div>

        <button
          type="button"
          className="toggle-advanced"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced ? "Hide" : "Show"} Advanced Settings
        </button>

        {showAdvanced && (
          <div className="advanced-settings">
            <div className="form-group">
              <label htmlFor="n_simulations">Number of Simulations</label>
              <input
                type="number"
                id="n_simulations"
                value={formData.n_simulations}
                onChange={(e) => updateField("n_simulations", Number(e.target.value))}
                min={100}
                max={100000}
                step={1000}
              />
            </div>

            <div className="form-group">
              <label htmlFor="expected_return">Expected Annual Return</label>
              <div className="input-with-suffix">
                <input
                  type="number"
                  id="expected_return"
                  value={(formData.expected_return * 100).toFixed(1)}
                  onChange={(e) => updateField("expected_return", Number(e.target.value) / 100)}
                  step={0.5}
                />
                <span>%</span>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="return_volatility">Return Volatility</label>
              <div className="input-with-suffix">
                <input
                  type="number"
                  id="return_volatility"
                  value={(formData.return_volatility * 100).toFixed(1)}
                  onChange={(e) => updateField("return_volatility", Number(e.target.value) / 100)}
                  step={0.5}
                />
                <span>%</span>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="inflation_rate">Inflation Rate</label>
              <div className="input-with-suffix">
                <input
                  type="number"
                  id="inflation_rate"
                  value={(formData.inflation_rate * 100).toFixed(1)}
                  onChange={(e) => updateField("inflation_rate", Number(e.target.value) / 100)}
                  step={0.5}
                />
                <span>%</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <button type="submit" className="submit-button" disabled={isLoading}>
        {isLoading ? "Running Simulation..." : "Run Simulation"}
      </button>
    </form>
  );
}
