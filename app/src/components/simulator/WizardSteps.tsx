/* eslint-disable react-refresh/only-export-components */
import { useMemo } from "react";
import type { WizardStep } from "../Wizard";
import type {
  SimulationInput,
  SpouseInput,
  AnnuityInput,
  Holding,
} from "../../lib/api";
import { HoldingsEditor } from "../HoldingsEditor";
import { US_STATES } from "../../lib/constants";
import {
  formatCurrency,
  getWithdrawalRateContext,
  getErrorInfo,
} from "../../lib/simulatorUtils";

interface WizardStepsProps {
  params: SimulationInput;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
  spouse: SpouseInput;
  setSpouse: React.Dispatch<React.SetStateAction<SpouseInput>>;
  annuity: AnnuityInput;
  setAnnuity: React.Dispatch<React.SetStateAction<AnnuityInput>>;
  portfolioMode: "simple" | "detailed";
  setPortfolioMode: React.Dispatch<React.SetStateAction<"simple" | "detailed">>;
  holdings: Holding[];
  setHoldings: React.Dispatch<React.SetStateAction<Holding[]>>;
  withdrawalStrategy: "taxable_first" | "traditional_first" | "roth_first" | "pro_rata";
  setWithdrawalStrategy: React.Dispatch<React.SetStateAction<"taxable_first" | "traditional_first" | "roth_first" | "pro_rata">>;
  isReceivingSS: boolean;
  setIsReceivingSS: React.Dispatch<React.SetStateAction<boolean>>;
  isSpouseReceivingSS: boolean;
  setIsSpouseReceivingSS: React.Dispatch<React.SetStateAction<boolean>>;
  error: unknown;
}

export function useWizardSteps({
  params,
  updateParam,
  spouse,
  setSpouse,
  annuity,
  setAnnuity,
  portfolioMode,
  setPortfolioMode,
  holdings,
  setHoldings,
  withdrawalStrategy,
  setWithdrawalStrategy,
  isReceivingSS,
  setIsReceivingSS,
  isSpouseReceivingSS,
  setIsSpouseReceivingSS,
  error,
}: WizardStepsProps): WizardStep[] {
  return useMemo(() => {
    const steps: WizardStep[] = [
      {
        id: "about",
        title: "About You",
        subtitle: "Let's start with some basic information",
        content: (
          <AboutYouStep
            params={params}
            updateParam={updateParam}
          />
        ),
      },
      {
        id: "money",
        title: "Your Money",
        subtitle: "How much have you saved, and how much do you need?",
        content: (
          <MoneyStep
            params={params}
            updateParam={updateParam}
            portfolioMode={portfolioMode}
            setPortfolioMode={setPortfolioMode}
            holdings={holdings}
            setHoldings={setHoldings}
            withdrawalStrategy={withdrawalStrategy}
            setWithdrawalStrategy={setWithdrawalStrategy}
          />
        ),
      },
      {
        id: "income",
        title: "Income Sources",
        subtitle: "What income sources do you have?",
        content: (
          <IncomeStep
            params={params}
            updateParam={updateParam}
            isReceivingSS={isReceivingSS}
            setIsReceivingSS={setIsReceivingSS}
          />
        ),
      },
      {
        id: "spouse",
        title: "Spouse",
        subtitle: "Retiring with a partner? Include their details.",
        optional: true,
        content: (
          <SpouseStep
            params={params}
            updateParam={updateParam}
            spouse={spouse}
            setSpouse={setSpouse}
            isSpouseReceivingSS={isSpouseReceivingSS}
            setIsSpouseReceivingSS={setIsSpouseReceivingSS}
          />
        ),
      },
      {
        id: "annuity",
        title: "Annuity",
        subtitle: "Compare your portfolio to a guaranteed annuity",
        optional: true,
        content: (
          <AnnuityStep
            params={params}
            updateParam={updateParam}
            annuity={annuity}
            setAnnuity={setAnnuity}
          />
        ),
      },
      {
        id: "review",
        title: "Review",
        subtitle: "Check your inputs and run the simulation",
        content: (
          <ReviewStep
            params={params}
            spouse={spouse}
            annuity={annuity}
            portfolioMode={portfolioMode}
            holdings={holdings}
            error={error}
          />
        ),
      },
    ];

    return steps;
  }, [
    params, spouse, annuity, portfolioMode, holdings, withdrawalStrategy,
    isReceivingSS, isSpouseReceivingSS, error,
    updateParam, setSpouse, setAnnuity, setPortfolioMode,
    setHoldings, setWithdrawalStrategy, setIsReceivingSS, setIsSpouseReceivingSS,
  ]);
}

// ============================================
// Step sub-components
// ============================================

function AboutYouStep({
  params,
  updateParam,
}: {
  params: SimulationInput;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
}) {
  return (
    <div>
      <div className="wizard-field-row">
        <div className="wizard-field">
          <label>Current Age</label>
          <input
            type="number"
            value={params.current_age}
            onChange={(e) => updateParam("current_age", Number(e.target.value))}
            min={18}
            max={100}
          />
        </div>
        <div className="wizard-field">
          <label>Planning To Age</label>
          <input
            type="number"
            value={params.max_age}
            onChange={(e) => updateParam("max_age", Number(e.target.value))}
            min={params.current_age + 5}
            max={120}
          />
        </div>
      </div>
      <div className="wizard-field-row">
        <div className="wizard-field">
          <label>Gender</label>
          <select
            value={params.gender}
            onChange={(e) => updateParam("gender", e.target.value as "male" | "female")}
          >
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
          <div className="wizard-field-hint">Used for mortality estimates</div>
        </div>
        <div className="wizard-field">
          <label>State</label>
          <select
            value={params.state}
            onChange={(e) => updateParam("state", e.target.value)}
          >
            {US_STATES.map((st) => (
              <option key={st} value={st}>{st}</option>
            ))}
          </select>
          <div className="wizard-field-hint">For state tax calculations</div>
        </div>
      </div>
      <div className="wizard-field">
        <label>Filing Status</label>
        <select
          value={params.filing_status}
          onChange={(e) => updateParam("filing_status", e.target.value as SimulationInput["filing_status"])}
        >
          <option value="single">Single</option>
          <option value="married_filing_jointly">Married (Joint)</option>
          <option value="head_of_household">Head of Household</option>
        </select>
      </div>
    </div>
  );
}

function MoneyStep({
  params,
  updateParam,
  portfolioMode,
  setPortfolioMode,
  holdings,
  setHoldings,
  withdrawalStrategy,
  setWithdrawalStrategy,
}: {
  params: SimulationInput;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
  portfolioMode: "simple" | "detailed";
  setPortfolioMode: React.Dispatch<React.SetStateAction<"simple" | "detailed">>;
  holdings: Holding[];
  setHoldings: React.Dispatch<React.SetStateAction<Holding[]>>;
  withdrawalStrategy: "taxable_first" | "traditional_first" | "roth_first" | "pro_rata";
  setWithdrawalStrategy: React.Dispatch<React.SetStateAction<"taxable_first" | "traditional_first" | "roth_first" | "pro_rata">>;
}) {
  const totalPortfolio = portfolioMode === "detailed" && holdings.length > 0
    ? holdings.reduce((sum, h) => sum + h.balance, 0)
    : (params.initial_capital ?? 0);
  const withdrawalRate = totalPortfolio > 0
    ? (params.annual_spending / totalPortfolio) * 100
    : 0;
  const rateContext = getWithdrawalRateContext(withdrawalRate);

  return (
    <div>
      {/* Portfolio Mode Toggle */}
      <div className="wizard-field">
        <label>Portfolio Entry Mode</label>
        <div className="portfolio-mode-toggle">
          <button
            type="button"
            className={`mode-btn ${portfolioMode === "simple" ? "active" : ""}`}
            onClick={() => setPortfolioMode("simple")}
          >
            Simple
          </button>
          <button
            type="button"
            className={`mode-btn ${portfolioMode === "detailed" ? "active" : ""}`}
            onClick={() => setPortfolioMode("detailed")}
          >
            By Account Type
          </button>
        </div>
        <div className="wizard-field-hint">
          {portfolioMode === "simple"
            ? "Enter a single total value"
            : "Enter each account separately for tax-optimized withdrawals"}
        </div>
      </div>

      {portfolioMode === "simple" ? (
        <>
          <div className="wizard-field">
            <label>Current Portfolio Value</label>
            <div className="wizard-field-prefix">
              <span>$</span>
              <input
                type="number"
                value={params.initial_capital}
                onChange={(e) => updateParam("initial_capital", Number(e.target.value))}
                min={0}
                step={10000}
              />
            </div>
            <div className="wizard-field-hint">Total savings and investments</div>
          </div>
          <div className="wizard-field">
            <label>Investment Mix: {Math.round(params.stock_allocation * 100)}% Stocks / {Math.round((1 - params.stock_allocation) * 100)}% Bonds</label>
            <input
              type="range"
              min={0}
              max={100}
              value={params.stock_allocation * 100}
              onChange={(e) => updateParam("stock_allocation", Number(e.target.value) / 100)}
              style={{ width: "100%" }}
            />
            <div className="wizard-field-hint">
              More stocks = higher growth potential but more volatility
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="wizard-field">
            <label>Your Holdings</label>
            <div className="detailed-mode-explainer">
              <p className="explainer-benefit">
                Track each account separately for tax-optimized withdrawal ordering
              </p>
              <p className="explainer-feature">
                RMDs automatically calculated for traditional accounts at age 73+
              </p>
            </div>
            <HoldingsEditor holdings={holdings} onChange={setHoldings} />
          </div>

          <div className="wizard-field">
            <label htmlFor="withdrawal-strategy">Withdrawal Strategy</label>
            <select
              id="withdrawal-strategy"
              value={withdrawalStrategy}
              onChange={(e) =>
                setWithdrawalStrategy(
                  e.target.value as "taxable_first" | "traditional_first" | "roth_first" | "pro_rata"
                )
              }
            >
              <option value="taxable_first">
                Taxable First - Lets tax-advantaged accounts grow longer
              </option>
              <option value="traditional_first">
                Traditional First - Reduces future RMDs
              </option>
              <option value="roth_first">
                Roth First - Preserves tax-deferred growth
              </option>
              <option value="pro_rata">
                Pro Rata - Withdraw proportionally from all accounts
              </option>
            </select>
            <div className="wizard-field-hint">
              Controls which accounts are withdrawn from first when you need money
            </div>
          </div>
        </>
      )}

      <div className="wizard-field">
        <label>Home Equity</label>
        <div className="wizard-field-prefix">
          <span>$</span>
          <input
            type="number"
            value={params.home_value}
            onChange={(e) => updateParam("home_value", Number(e.target.value))}
            min={0}
            step={10000}
          />
        </div>
        <div className="wizard-field-hint">
          Home value minus mortgage (not used in simulation, shown in net worth)
        </div>
      </div>
      <div className="wizard-field">
        <label>Annual Spending Need</label>
        <div className="wizard-field-prefix">
          <span>$</span>
          <input
            type="number"
            value={params.annual_spending}
            onChange={(e) => updateParam("annual_spending", Number(e.target.value))}
            min={0}
            step={1000}
          />
        </div>
        <div className="wizard-field-hint">
          That's ${(params.annual_spending / 12).toLocaleString()} per month
        </div>
      </div>

      {totalPortfolio > 0 && params.annual_spending > 0 && (
        <div className={`validation-context ${rateContext.warning ? 'warning' : 'success'}`}>
          <div className="validation-rate">
            <strong>{withdrawalRate.toFixed(1)}%</strong> withdrawal rate
          </div>
          <div className="validation-message">{rateContext.message}</div>
        </div>
      )}
    </div>
  );
}

function IncomeStep({
  params,
  updateParam,
  isReceivingSS,
  setIsReceivingSS,
}: {
  params: SimulationInput;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
  isReceivingSS: boolean;
  setIsReceivingSS: React.Dispatch<React.SetStateAction<boolean>>;
}) {
  return (
    <div>
      <div className="wizard-field">
        <label>Monthly Social Security</label>
        <div className="wizard-field-prefix">
          <span>$</span>
          <input
            type="number"
            value={params.social_security_monthly}
            onChange={(e) => updateParam("social_security_monthly", Number(e.target.value))}
            min={0}
            step={100}
          />
        </div>
        <div className="wizard-field-hint">
          {isReceivingSS
            ? "Your current monthly benefit amount"
            : "Your estimated PIA at full retirement age (check ssa.gov/myaccount)"}
        </div>
      </div>
      {params.social_security_monthly > 0 && params.current_age >= 62 && (
        <div className="wizard-field">
          <label>
            <input
              type="checkbox"
              checked={isReceivingSS}
              onChange={(e) => {
                setIsReceivingSS(e.target.checked);
                if (e.target.checked) {
                  updateParam("social_security_start_age", params.current_age);
                }
              }}
              style={{ marginRight: "8px" }}
            />
            Already receiving Social Security
          </label>
        </div>
      )}
      {params.social_security_monthly > 0 && !isReceivingSS && (
        <div className="wizard-field">
          <label>Planned Start Age</label>
          <select
            value={params.social_security_start_age}
            onChange={(e) => updateParam("social_security_start_age", Number(e.target.value))}
          >
            <option value={62}>62 (reduced ~30%)</option>
            <option value={63}>63 (reduced ~25%)</option>
            <option value={64}>64 (reduced ~20%)</option>
            <option value={65}>65 (reduced ~13%)</option>
            <option value={66}>66 (reduced ~7%)</option>
            <option value={67}>67 (full retirement age)</option>
            <option value={68}>68 (8% bonus)</option>
            <option value={69}>69 (16% bonus)</option>
            <option value={70}>70 (24% bonus)</option>
          </select>
          <div className="wizard-field-hint">
            Claiming earlier reduces benefits; waiting increases them
          </div>
        </div>
      )}
      <div className="wizard-field">
        <label>Annual Pension</label>
        <div className="wizard-field-prefix">
          <span>$</span>
          <input
            type="number"
            value={params.pension_annual}
            onChange={(e) => updateParam("pension_annual", Number(e.target.value))}
            min={0}
            step={1000}
          />
        </div>
        <div className="wizard-field-hint">Enter 0 if you don't have a pension</div>
      </div>
      <div className="wizard-field">
        <label>Current Employment Income</label>
        <div className="wizard-field-prefix">
          <span>$</span>
          <input
            type="number"
            value={params.employment_income}
            onChange={(e) => updateParam("employment_income", Number(e.target.value))}
            min={0}
            step={5000}
          />
        </div>
        <div className="wizard-field-hint">If still working, enter your annual salary</div>
      </div>
      {params.employment_income > 0 && (
        <div className="wizard-field">
          <label>Retirement Age</label>
          <input
            type="number"
            value={params.retirement_age}
            onChange={(e) => updateParam("retirement_age", Number(e.target.value))}
            min={params.current_age}
            max={80}
          />
          <div className="wizard-field-hint">When employment income will stop</div>
        </div>
      )}
    </div>
  );
}

function SpouseStep({
  params,
  updateParam,
  spouse,
  setSpouse,
  isSpouseReceivingSS,
  setIsSpouseReceivingSS,
}: {
  params: SimulationInput;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
  spouse: SpouseInput;
  setSpouse: React.Dispatch<React.SetStateAction<SpouseInput>>;
  isSpouseReceivingSS: boolean;
  setIsSpouseReceivingSS: React.Dispatch<React.SetStateAction<boolean>>;
}) {
  return (
    <div>
      <label className="wizard-checkbox">
        <input
          type="checkbox"
          checked={params.has_spouse}
          onChange={(e) => updateParam("has_spouse", e.target.checked)}
        />
        <div className="wizard-checkbox-content">
          <div className="wizard-checkbox-label">Include Spouse</div>
          <div className="wizard-checkbox-hint">
            Model finances for both of you together
          </div>
        </div>
      </label>

      {params.has_spouse && (
        <div style={{ marginTop: "1.5rem" }}>
          <div className="wizard-field-row">
            <div className="wizard-field">
              <label>Spouse Age</label>
              <input
                type="number"
                value={spouse.age}
                onChange={(e) => setSpouse({ ...spouse, age: Number(e.target.value) })}
                min={18}
                max={100}
              />
            </div>
            <div className="wizard-field">
              <label>Spouse Gender</label>
              <select
                value={spouse.gender}
                onChange={(e) => setSpouse({ ...spouse, gender: e.target.value as "male" | "female" })}
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
          </div>
          <div className="wizard-field">
            <label>Spouse Monthly Social Security</label>
            <div className="wizard-field-prefix">
              <span>$</span>
              <input
                type="number"
                value={spouse.social_security_monthly}
                onChange={(e) => setSpouse({ ...spouse, social_security_monthly: Number(e.target.value) })}
                min={0}
                step={100}
              />
            </div>
          </div>
          {spouse.social_security_monthly > 0 && spouse.age >= 62 && (
            <div className="wizard-field">
              <label>
                <input
                  type="checkbox"
                  checked={isSpouseReceivingSS}
                  onChange={(e) => {
                    setIsSpouseReceivingSS(e.target.checked);
                    if (e.target.checked) {
                      setSpouse({ ...spouse, social_security_start_age: spouse.age });
                    }
                  }}
                  style={{ marginRight: "8px" }}
                />
                Already receiving Social Security
              </label>
            </div>
          )}
          {spouse.social_security_monthly > 0 && !isSpouseReceivingSS && (
            <div className="wizard-field">
              <label>Planned Start Age</label>
              <select
                value={spouse.social_security_start_age}
                onChange={(e) => setSpouse({ ...spouse, social_security_start_age: Number(e.target.value) })}
              >
                <option value={62}>62 (reduced ~30%)</option>
                <option value={63}>63 (reduced ~25%)</option>
                <option value={64}>64 (reduced ~20%)</option>
                <option value={65}>65 (reduced ~13%)</option>
                <option value={66}>66 (reduced ~7%)</option>
                <option value={67}>67 (full retirement age)</option>
                <option value={68}>68 (8% bonus)</option>
                <option value={69}>69 (16% bonus)</option>
                <option value={70}>70 (24% bonus)</option>
              </select>
            </div>
          )}
          <div className="wizard-field">
            <label>Spouse Annual Pension</label>
            <div className="wizard-field-prefix">
              <span>$</span>
              <input
                type="number"
                value={spouse.pension_annual}
                onChange={(e) => setSpouse({ ...spouse, pension_annual: Number(e.target.value) })}
                min={0}
                step={1000}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AnnuityStep({
  params,
  updateParam,
  annuity,
  setAnnuity,
}: {
  params: SimulationInput;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
  annuity: AnnuityInput;
  setAnnuity: React.Dispatch<React.SetStateAction<AnnuityInput>>;
}) {
  return (
    <div>
      <label className="wizard-checkbox">
        <input
          type="checkbox"
          checked={params.has_annuity}
          onChange={(e) => updateParam("has_annuity", e.target.checked)}
        />
        <div className="wizard-checkbox-content">
          <div className="wizard-checkbox-label">Compare to Annuity</div>
          <div className="wizard-checkbox-hint">
            See if buying an annuity might be better than investing
          </div>
        </div>
      </label>

      {params.has_annuity && (
        <div style={{ marginTop: "1.5rem" }}>
          <div className="wizard-field">
            <label>Monthly Annuity Payment</label>
            <div className="wizard-field-prefix">
              <span>$</span>
              <input
                type="number"
                value={annuity.monthly_payment}
                onChange={(e) => setAnnuity({ ...annuity, monthly_payment: Number(e.target.value) })}
                min={100}
                step={100}
              />
            </div>
            <div className="wizard-field-hint">Get a quote from an insurance company</div>
          </div>
          <div className="wizard-field">
            <label>Annuity Type</label>
            <select
              value={annuity.annuity_type}
              onChange={(e) => setAnnuity({ ...annuity, annuity_type: e.target.value as AnnuityInput["annuity_type"] })}
            >
              <option value="life_with_guarantee">Life with Guarantee</option>
              <option value="fixed_period">Fixed Period</option>
              <option value="life_only">Life Only</option>
            </select>
          </div>
          {annuity.annuity_type !== "life_only" && (
            <div className="wizard-field">
              <label>Guarantee Period (years)</label>
              <input
                type="number"
                value={annuity.guarantee_years}
                onChange={(e) => setAnnuity({ ...annuity, guarantee_years: Number(e.target.value) })}
                min={1}
                max={30}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ReviewStep({
  params,
  spouse,
  annuity,
  portfolioMode,
  holdings,
  error,
}: {
  params: SimulationInput;
  spouse: SpouseInput;
  annuity: AnnuityInput;
  portfolioMode: "simple" | "detailed";
  holdings: Holding[];
  error: unknown;
}) {
  return (
    <div>
      <div className="wizard-review">
        <div className="wizard-review-section">
          <div className="wizard-review-title">About You</div>
          <div className="wizard-review-row">
            <span className="wizard-review-label">Age Range</span>
            <span className="wizard-review-value">
              {params.current_age} to {params.max_age}
            </span>
          </div>
          <div className="wizard-review-row">
            <span className="wizard-review-label">Location</span>
            <span className="wizard-review-value">
              {params.state}, {params.filing_status.replace(/_/g, " ")}
            </span>
          </div>
        </div>

        <div className="wizard-review-section">
          <div className="wizard-review-title">Finances</div>
          {portfolioMode === "detailed" && holdings.length > 0 ? (
            <>
              <div className="wizard-review-row">
                <span className="wizard-review-label">Portfolio</span>
                <span className="wizard-review-value">
                  {formatCurrency(holdings.reduce((sum, h) => sum + h.balance, 0))}
                </span>
              </div>
              <div className="wizard-review-row" style={{ fontSize: "0.875rem", color: "#6b7280" }}>
                <span className="wizard-review-label">&nbsp;&nbsp;Holdings</span>
                <span className="wizard-review-value">{holdings.length} accounts</span>
              </div>
            </>
          ) : (
            <div className="wizard-review-row">
              <span className="wizard-review-label">Portfolio</span>
              <span className="wizard-review-value">
                {formatCurrency(params.initial_capital ?? 0)}
              </span>
            </div>
          )}
          <div className="wizard-review-row">
            <span className="wizard-review-label">Annual Spending</span>
            <span className="wizard-review-value">
              {formatCurrency(params.annual_spending)}
            </span>
          </div>
          <div className="wizard-review-row">
            <span className="wizard-review-label">Social Security</span>
            <span className="wizard-review-value">
              ${params.social_security_monthly.toLocaleString()}/mo @ age {params.social_security_start_age}
            </span>
          </div>
          {params.pension_annual > 0 && (
            <div className="wizard-review-row">
              <span className="wizard-review-label">Pension</span>
              <span className="wizard-review-value">
                {formatCurrency(params.pension_annual)}/yr
              </span>
            </div>
          )}
        </div>

        {params.has_spouse && (
          <div className="wizard-review-section">
            <div className="wizard-review-title">Spouse</div>
            <div className="wizard-review-row">
              <span className="wizard-review-label">Age</span>
              <span className="wizard-review-value">{spouse.age}</span>
            </div>
            <div className="wizard-review-row">
              <span className="wizard-review-label">Social Security</span>
              <span className="wizard-review-value">
                ${spouse.social_security_monthly.toLocaleString()}/mo
              </span>
            </div>
          </div>
        )}

        {params.has_annuity && (
          <div className="wizard-review-section">
            <div className="wizard-review-title">Annuity Comparison</div>
            <div className="wizard-review-row">
              <span className="wizard-review-label">Monthly Payment</span>
              <span className="wizard-review-value">
                ${annuity.monthly_payment.toLocaleString()}
              </span>
            </div>
          </div>
        )}
      </div>

      {error ? (() => {
        const errorInfo = getErrorInfo(error);
        return (
          <div className="error-banner" style={{ marginTop: "1rem" }}>
            <strong>{errorInfo.title}:</strong> {errorInfo.message}
            {errorInfo.field && (
              <span style={{ display: "block", marginTop: "0.5rem", fontStyle: "italic" }}>
                Check: {errorInfo.field.replace(/_/g, " ")}
              </span>
            )}
          </div>
        );
      })() : null}
    </div>
  );
}
