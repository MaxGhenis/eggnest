"use client";

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
import type { PortfolioMode, WithdrawalStrategy } from "../../hooks/usePortfolio";
import {
  formatCurrency,
  getWithdrawalRateContext,
  getErrorInfo,
} from "../../lib/simulatorUtils";

/* Shared field wrapper classes */
const fieldCls = "space-y-1.5";
const labelCls = "block text-sm font-medium text-[var(--color-text-muted)]";
const inputCls = "w-full rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-3 py-2.5 text-sm transition-colors focus:border-[var(--color-primary)] focus:outline-none";
const selectCls = inputCls;
const hintCls = "text-xs text-[var(--color-text-light)]";
const rowCls = "grid gap-4 sm:grid-cols-2";

interface WizardStepsProps {
  params: SimulationInput;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
  spouse: SpouseInput;
  setSpouse: React.Dispatch<React.SetStateAction<SpouseInput>>;
  annuity: AnnuityInput;
  setAnnuity: React.Dispatch<React.SetStateAction<AnnuityInput>>;
  portfolioMode: PortfolioMode;
  setPortfolioMode: React.Dispatch<React.SetStateAction<PortfolioMode>>;
  holdings: Holding[];
  setHoldings: React.Dispatch<React.SetStateAction<Holding[]>>;
  withdrawalStrategy: WithdrawalStrategy;
  setWithdrawalStrategy: React.Dispatch<React.SetStateAction<WithdrawalStrategy>>;
  isReceivingSS: boolean;
  setIsReceivingSS: React.Dispatch<React.SetStateAction<boolean>>;
  isSpouseReceivingSS: boolean;
  setIsSpouseReceivingSS: React.Dispatch<React.SetStateAction<boolean>>;
  error: unknown;
}

export function useWizardSteps({
  params, updateParam, spouse, setSpouse, annuity, setAnnuity,
  portfolioMode, setPortfolioMode, holdings, setHoldings,
  withdrawalStrategy, setWithdrawalStrategy,
  isReceivingSS, setIsReceivingSS, isSpouseReceivingSS, setIsSpouseReceivingSS, error,
}: WizardStepsProps): WizardStep[] {
  return useMemo((): WizardStep[] => [
    {
      id: "about", title: "About you", subtitle: "Let's start with some basic information",
      content: <AboutYouStep params={params} updateParam={updateParam} />,
    },
    {
      id: "money", title: "Your money", subtitle: "How much have you saved, and how much do you need?",
      content: (
        <MoneyStep params={params} updateParam={updateParam} portfolioMode={portfolioMode}
          setPortfolioMode={setPortfolioMode} holdings={holdings} setHoldings={setHoldings}
          withdrawalStrategy={withdrawalStrategy} setWithdrawalStrategy={setWithdrawalStrategy} />
      ),
    },
    {
      id: "income", title: "Income sources", subtitle: "What income sources do you have?",
      content: <IncomeStep params={params} updateParam={updateParam} isReceivingSS={isReceivingSS} setIsReceivingSS={setIsReceivingSS} />,
    },
    {
      id: "spouse", title: "Spouse", subtitle: "Retiring with a partner? Include their details.", optional: true,
      content: (
        <SpouseStep params={params} updateParam={updateParam} spouse={spouse} setSpouse={setSpouse}
          isSpouseReceivingSS={isSpouseReceivingSS} setIsSpouseReceivingSS={setIsSpouseReceivingSS} />
      ),
    },
    {
      id: "annuity", title: "Annuity", subtitle: "Compare your portfolio to a guaranteed annuity", optional: true,
      content: <AnnuityStep params={params} updateParam={updateParam} annuity={annuity} setAnnuity={setAnnuity} />,
    },
    {
      id: "review", title: "Review", subtitle: "Check your inputs and run the simulation",
      content: <ReviewStep params={params} spouse={spouse} annuity={annuity} portfolioMode={portfolioMode} holdings={holdings} error={error} />,
    },
  ], [
    params, spouse, annuity, portfolioMode, holdings, withdrawalStrategy,
    isReceivingSS, isSpouseReceivingSS, error,
    updateParam, setSpouse, setAnnuity, setPortfolioMode,
    setHoldings, setWithdrawalStrategy, setIsReceivingSS, setIsSpouseReceivingSS,
  ]);
}

/* ============================================ */
/* Step sub-components                          */
/* ============================================ */

function AboutYouStep({ params, updateParam }: {
  params: SimulationInput;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
}) {
  return (
    <div className="space-y-5">
      <div className={rowCls}>
        <div className={fieldCls}>
          <label className={labelCls}>Current age</label>
          <input type="number" value={params.current_age}
            onChange={(e) => updateParam("current_age", Number(e.target.value))}
            min={18} max={100} className={inputCls} />
        </div>
        <div className={fieldCls}>
          <label className={labelCls}>Planning to age</label>
          <input type="number" value={params.max_age}
            onChange={(e) => updateParam("max_age", Number(e.target.value))}
            min={params.current_age + 5} max={120} className={inputCls} />
        </div>
      </div>
      <div className={rowCls}>
        <div className={fieldCls}>
          <label className={labelCls}>Gender</label>
          <select value={params.gender}
            onChange={(e) => updateParam("gender", e.target.value as "male" | "female")}
            className={selectCls}>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
          <div className={hintCls}>Used for mortality estimates</div>
        </div>
        <div className={fieldCls}>
          <label className={labelCls}>State</label>
          <select value={params.state}
            onChange={(e) => updateParam("state", e.target.value)}
            className={selectCls}>
            {US_STATES.map((st) => <option key={st} value={st}>{st}</option>)}
          </select>
          <div className={hintCls}>For state tax calculations</div>
        </div>
      </div>
      <div className={fieldCls}>
        <label className={labelCls}>Filing status</label>
        <select value={params.filing_status}
          onChange={(e) => updateParam("filing_status", e.target.value as SimulationInput["filing_status"])}
          className={selectCls}>
          <option value="single">Single</option>
          <option value="married_filing_jointly">Married (joint)</option>
          <option value="head_of_household">Head of household</option>
        </select>
      </div>
    </div>
  );
}

function MoneyStep({ params, updateParam, portfolioMode, setPortfolioMode, holdings, setHoldings, withdrawalStrategy, setWithdrawalStrategy }: {
  params: SimulationInput;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
  portfolioMode: PortfolioMode;
  setPortfolioMode: React.Dispatch<React.SetStateAction<PortfolioMode>>;
  holdings: Holding[];
  setHoldings: React.Dispatch<React.SetStateAction<Holding[]>>;
  withdrawalStrategy: WithdrawalStrategy;
  setWithdrawalStrategy: React.Dispatch<React.SetStateAction<WithdrawalStrategy>>;
}) {
  const totalPortfolio = portfolioMode === "detailed" && holdings.length > 0
    ? holdings.reduce((sum, h) => sum + h.balance, 0)
    : (params.initial_capital ?? 0);
  const withdrawalRate = totalPortfolio > 0 ? (params.annual_spending / totalPortfolio) * 100 : 0;
  const rateContext = getWithdrawalRateContext(withdrawalRate);

  return (
    <div className="space-y-5">
      {/* Portfolio Mode Toggle */}
      <div className={fieldCls}>
        <label className={labelCls}>Portfolio entry mode</label>
        <div className="flex rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-gray-50)] p-1">
          <button type="button"
            className={`flex-1 rounded-[var(--radius-sm)] py-2 text-sm font-medium transition-all ${portfolioMode === "simple" ? "bg-white text-[var(--color-primary)] shadow-[var(--shadow-sm)]" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"}`}
            onClick={() => setPortfolioMode("simple")}>Simple</button>
          <button type="button"
            className={`flex-1 rounded-[var(--radius-sm)] py-2 text-sm font-medium transition-all ${portfolioMode === "detailed" ? "bg-white text-[var(--color-primary)] shadow-[var(--shadow-sm)]" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"}`}
            onClick={() => setPortfolioMode("detailed")}>By account type</button>
        </div>
        <div className={hintCls}>
          {portfolioMode === "simple" ? "Enter a single total value" : "Enter each account separately for tax-optimized withdrawals"}
        </div>
      </div>

      {portfolioMode === "simple" ? (
        <>
          <div className={fieldCls}>
            <label className={labelCls}>Current portfolio value</label>
            <div className="flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white focus-within:border-[var(--color-primary)]">
              <span className="pl-3 text-sm text-[var(--color-text-light)]">$</span>
              <input type="number" value={params.initial_capital}
                onChange={(e) => updateParam("initial_capital", Number(e.target.value))}
                min={0} step={10000}
                className="w-full border-none bg-transparent px-2 py-2.5 text-sm focus:outline-none" />
            </div>
            <div className={hintCls}>Total savings and investments</div>
          </div>
          <div className={fieldCls}>
            <label className={labelCls}>
              Investment Mix: {Math.round(params.stock_allocation * 100)}% Stocks / {Math.round((1 - params.stock_allocation) * 100)}% Bonds
            </label>
            <input type="range" min={0} max={100} value={params.stock_allocation * 100}
              onChange={(e) => updateParam("stock_allocation", Number(e.target.value) / 100)}
              className="w-full accent-[var(--color-gold)]" />
            <div className={hintCls}>More stocks = higher growth potential but more volatility</div>
          </div>
        </>
      ) : (
        <>
          <div className={fieldCls}>
            <label className={labelCls}>Your holdings</label>
            <div className="rounded-[var(--radius-md)] border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] p-3 text-sm">
              <p className="font-medium text-[var(--color-primary-dark)]">Track each account for tax-optimized withdrawals</p>
              <p className="mt-1 text-xs text-[var(--color-primary)]">RMDs automatically calculated for traditional accounts at age 73+</p>
            </div>
            <HoldingsEditor holdings={holdings} onChange={setHoldings} />
          </div>
          <div className={fieldCls}>
            <label htmlFor="withdrawal-strategy" className={labelCls}>Withdrawal strategy</label>
            <select id="withdrawal-strategy" value={withdrawalStrategy}
              onChange={(e) => setWithdrawalStrategy(e.target.value as WithdrawalStrategy)}
              className={selectCls}>
              <option value="taxable_first">Taxable first - Lets tax-advantaged accounts grow longer</option>
              <option value="traditional_first">Traditional first - Reduces future RMDs</option>
              <option value="roth_first">Roth first - Preserves tax-deferred growth</option>
              <option value="pro_rata">Pro rata - Withdraw proportionally from all accounts</option>
            </select>
            <div className={hintCls}>Controls which accounts are withdrawn from first</div>
          </div>
        </>
      )}

      <div className={fieldCls}>
        <label className={labelCls}>Home equity</label>
        <div className="flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white focus-within:border-[var(--color-primary)]">
          <span className="pl-3 text-sm text-[var(--color-text-light)]">$</span>
          <input type="number" value={params.home_value}
            onChange={(e) => updateParam("home_value", Number(e.target.value))}
            min={0} step={10000}
            className="w-full border-none bg-transparent px-2 py-2.5 text-sm focus:outline-none" />
        </div>
        <div className={hintCls}>Home value minus mortgage (not used in simulation, shown in net worth)</div>
      </div>

      <div className={fieldCls}>
        <label className={labelCls}>Annual spending need</label>
        <div className="flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white focus-within:border-[var(--color-primary)]">
          <span className="pl-3 text-sm text-[var(--color-text-light)]">$</span>
          <input type="number" value={params.annual_spending}
            onChange={(e) => updateParam("annual_spending", Number(e.target.value))}
            min={0} step={1000}
            className="w-full border-none bg-transparent px-2 py-2.5 text-sm focus:outline-none" />
        </div>
        <div className={hintCls}>That's ${(params.annual_spending / 12).toLocaleString()} per month</div>
      </div>

      {totalPortfolio > 0 && params.annual_spending > 0 && (
        <div className={`rounded-[var(--radius-md)] px-4 py-3 text-sm ${rateContext.warning ? "border border-[var(--color-warning)] bg-[var(--color-warning-light)]" : "border border-[var(--color-success)] bg-[var(--color-success-light)]"}`}>
          <div className="font-semibold">{withdrawalRate.toFixed(1)}% withdrawal rate</div>
          <div className="text-xs mt-0.5 opacity-80">{rateContext.message}</div>
        </div>
      )}
    </div>
  );
}

function IncomeStep({ params, updateParam, isReceivingSS, setIsReceivingSS }: {
  params: SimulationInput;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
  isReceivingSS: boolean;
  setIsReceivingSS: React.Dispatch<React.SetStateAction<boolean>>;
}) {
  return (
    <div className="space-y-5">
      <div className={fieldCls}>
        <label className={labelCls}>Monthly Social Security benefit</label>
        <div className="flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white focus-within:border-[var(--color-primary)]">
          <span className="pl-3 text-sm text-[var(--color-text-light)]">$</span>
          <input type="number" value={params.social_security_monthly}
            onChange={(e) => updateParam("social_security_monthly", Number(e.target.value))}
            min={0} step={100}
            className="w-full border-none bg-transparent px-2 py-2.5 text-sm focus:outline-none" />
        </div>
        <div className={hintCls}>
          {isReceivingSS ? "Your current monthly benefit amount" : "Your estimated PIA at full retirement age (check ssa.gov/myaccount)"}
        </div>
      </div>
      {params.social_security_monthly > 0 && params.current_age >= 62 && (
        <label className="flex items-center gap-2 cursor-pointer text-sm text-[var(--color-text)]">
          <input type="checkbox" checked={isReceivingSS}
            onChange={(e) => { setIsReceivingSS(e.target.checked); if (e.target.checked) updateParam("social_security_start_age", params.current_age); }}
            className="h-4 w-4 rounded border-[var(--color-border)] accent-[var(--color-primary)]" />
          Already receiving Social Security
        </label>
      )}
      {params.social_security_monthly > 0 && !isReceivingSS && (
        <div className={fieldCls}>
          <label className={labelCls}>Planned start age</label>
          <select value={params.social_security_start_age}
            onChange={(e) => updateParam("social_security_start_age", Number(e.target.value))}
            className={selectCls}>
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
          <div className={hintCls}>Claiming earlier reduces benefits; waiting increases them</div>
        </div>
      )}
      <div className={fieldCls}>
        <label className={labelCls}>Annual pension</label>
        <div className="flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white focus-within:border-[var(--color-primary)]">
          <span className="pl-3 text-sm text-[var(--color-text-light)]">$</span>
          <input type="number" value={params.pension_annual}
            onChange={(e) => updateParam("pension_annual", Number(e.target.value))}
            min={0} step={1000}
            className="w-full border-none bg-transparent px-2 py-2.5 text-sm focus:outline-none" />
        </div>
        <div className={hintCls}>Enter 0 if you don't have a pension</div>
      </div>
      <div className={fieldCls}>
        <label className={labelCls}>Current employment income</label>
        <div className="flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white focus-within:border-[var(--color-primary)]">
          <span className="pl-3 text-sm text-[var(--color-text-light)]">$</span>
          <input type="number" value={params.employment_income}
            onChange={(e) => updateParam("employment_income", Number(e.target.value))}
            min={0} step={5000}
            className="w-full border-none bg-transparent px-2 py-2.5 text-sm focus:outline-none" />
        </div>
        <div className={hintCls}>If still working, enter your annual salary</div>
      </div>
      {params.employment_income > 0 && (
        <div className={fieldCls}>
          <label className={labelCls}>Retirement age</label>
          <input type="number" value={params.retirement_age}
            onChange={(e) => updateParam("retirement_age", Number(e.target.value))}
            min={params.current_age} max={80} className={inputCls} />
          <div className={hintCls}>When employment income will stop</div>
        </div>
      )}
    </div>
  );
}

function SpouseStep({ params, updateParam, spouse, setSpouse, isSpouseReceivingSS, setIsSpouseReceivingSS }: {
  params: SimulationInput;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
  spouse: SpouseInput;
  setSpouse: React.Dispatch<React.SetStateAction<SpouseInput>>;
  isSpouseReceivingSS: boolean;
  setIsSpouseReceivingSS: React.Dispatch<React.SetStateAction<boolean>>;
}) {
  return (
    <div className="space-y-5">
      <label className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-md)] border border-[var(--color-border-light)] p-4 transition-colors hover:bg-[var(--color-gray-50)]">
        <input type="checkbox" checked={params.has_spouse}
          onChange={(e) => updateParam("has_spouse", e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-[var(--color-border)] accent-[var(--color-primary)]" />
        <div>
          <div className="text-sm font-semibold text-[var(--color-text)]">Include spouse</div>
          <div className="text-xs text-[var(--color-text-muted)]">Model finances for both of you together</div>
        </div>
      </label>

      {params.has_spouse && (
        <div className="space-y-5 pt-2">
          <div className={rowCls}>
            <div className={fieldCls}>
              <label className={labelCls}>Spouse age</label>
              <input type="number" value={spouse.age}
                onChange={(e) => setSpouse({ ...spouse, age: Number(e.target.value) })}
                min={18} max={100} className={inputCls} />
            </div>
            <div className={fieldCls}>
              <label className={labelCls}>Spouse gender</label>
              <select value={spouse.gender}
                onChange={(e) => setSpouse({ ...spouse, gender: e.target.value as "male" | "female" })}
                className={selectCls}>
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
          </div>
          <div className={fieldCls}>
            <label className={labelCls}>Spouse monthly Social Security</label>
            <div className="flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white focus-within:border-[var(--color-primary)]">
              <span className="pl-3 text-sm text-[var(--color-text-light)]">$</span>
              <input type="number" value={spouse.social_security_monthly}
                onChange={(e) => setSpouse({ ...spouse, social_security_monthly: Number(e.target.value) })}
                min={0} step={100}
                className="w-full border-none bg-transparent px-2 py-2.5 text-sm focus:outline-none" />
            </div>
          </div>
          {spouse.social_security_monthly > 0 && spouse.age >= 62 && (
            <label className="flex items-center gap-2 cursor-pointer text-sm">
              <input type="checkbox" checked={isSpouseReceivingSS}
                onChange={(e) => { setIsSpouseReceivingSS(e.target.checked); if (e.target.checked) setSpouse({ ...spouse, social_security_start_age: spouse.age }); }}
                className="h-4 w-4 rounded border-[var(--color-border)] accent-[var(--color-primary)]" />
              Already receiving Social Security
            </label>
          )}
          {spouse.social_security_monthly > 0 && !isSpouseReceivingSS && (
            <div className={fieldCls}>
              <label className={labelCls}>Planned start age</label>
              <select value={spouse.social_security_start_age}
                onChange={(e) => setSpouse({ ...spouse, social_security_start_age: Number(e.target.value) })}
                className={selectCls}>
                {[62,63,64,65,66,67,68,69,70].map(a => (
                  <option key={a} value={a}>{a} {a === 67 ? "(full retirement age)" : a < 67 ? `(reduced ~${Math.round((67-a)*7.14)}%)` : `(${(a-67)*8}% bonus)`}</option>
                ))}
              </select>
            </div>
          )}
          <div className={fieldCls}>
            <label className={labelCls}>Spouse annual pension</label>
            <div className="flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white focus-within:border-[var(--color-primary)]">
              <span className="pl-3 text-sm text-[var(--color-text-light)]">$</span>
              <input type="number" value={spouse.pension_annual}
                onChange={(e) => setSpouse({ ...spouse, pension_annual: Number(e.target.value) })}
                min={0} step={1000}
                className="w-full border-none bg-transparent px-2 py-2.5 text-sm focus:outline-none" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AnnuityStep({ params, updateParam, annuity, setAnnuity }: {
  params: SimulationInput;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
  annuity: AnnuityInput;
  setAnnuity: React.Dispatch<React.SetStateAction<AnnuityInput>>;
}) {
  return (
    <div className="space-y-5">
      <label className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-md)] border border-[var(--color-border-light)] p-4 transition-colors hover:bg-[var(--color-gray-50)]">
        <input type="checkbox" checked={params.has_annuity}
          onChange={(e) => updateParam("has_annuity", e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-[var(--color-border)] accent-[var(--color-primary)]" />
        <div>
          <div className="text-sm font-semibold text-[var(--color-text)]">Compare to annuity</div>
          <div className="text-xs text-[var(--color-text-muted)]">See if buying an annuity might be better than investing</div>
        </div>
      </label>

      {params.has_annuity && (
        <div className="space-y-5 pt-2">
          <div className={fieldCls}>
            <label className={labelCls}>Monthly annuity payment</label>
            <div className="flex items-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white focus-within:border-[var(--color-primary)]">
              <span className="pl-3 text-sm text-[var(--color-text-light)]">$</span>
              <input type="number" value={annuity.monthly_payment}
                onChange={(e) => setAnnuity({ ...annuity, monthly_payment: Number(e.target.value) })}
                min={100} step={100}
                className="w-full border-none bg-transparent px-2 py-2.5 text-sm focus:outline-none" />
            </div>
            <div className={hintCls}>Get a quote from an insurance company</div>
          </div>
          <div className={fieldCls}>
            <label className={labelCls}>Annuity type</label>
            <select value={annuity.annuity_type}
              onChange={(e) => setAnnuity({ ...annuity, annuity_type: e.target.value as AnnuityInput["annuity_type"] })}
              className={selectCls}>
              <option value="life_with_guarantee">Life with guarantee</option>
              <option value="fixed_period">Fixed period</option>
              <option value="life_only">Life only</option>
            </select>
          </div>
          {annuity.annuity_type !== "life_only" && (
            <div className={fieldCls}>
              <label className={labelCls}>Guarantee period (years)</label>
              <input type="number" value={annuity.guarantee_years}
                onChange={(e) => setAnnuity({ ...annuity, guarantee_years: Number(e.target.value) })}
                min={1} max={30} className={inputCls} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-[var(--color-text-muted)]">{label}</span>
      <span className="text-sm font-medium text-[var(--color-text)]">{value}</span>
    </div>
  );
}

function ReviewStep({ params, spouse, annuity, portfolioMode, holdings, error }: {
  params: SimulationInput; spouse: SpouseInput; annuity: AnnuityInput;
  portfolioMode: PortfolioMode; holdings: Holding[]; error: unknown;
}) {
  return (
    <div className="space-y-5">
      <div className="space-y-4 divide-y divide-[var(--color-border-light)]">
        <div className="space-y-1">
          <div className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-light)]">About you</div>
          <ReviewRow label="Age range" value={`${params.current_age} to ${params.max_age}`} />
          <ReviewRow label="Location" value={`${params.state}, ${params.filing_status.replace(/_/g, " ")}`} />
        </div>
        <div className="space-y-1 pt-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-light)]">Finances</div>
          {portfolioMode === "detailed" && holdings.length > 0 ? (
            <>
              <ReviewRow label="Portfolio" value={formatCurrency(holdings.reduce((s, h) => s + h.balance, 0))} />
              <div className="flex justify-between py-1 text-xs text-[var(--color-text-light)]">
                <span className="pl-4">Holdings</span>
                <span>{holdings.length} accounts</span>
              </div>
            </>
          ) : (
            <ReviewRow label="Portfolio" value={formatCurrency(params.initial_capital ?? 0)} />
          )}
          <ReviewRow label="Annual spending" value={formatCurrency(params.annual_spending)} />
          <ReviewRow label="Social Security" value={`$${params.social_security_monthly.toLocaleString()}/mo @ age ${params.social_security_start_age}`} />
          {params.pension_annual > 0 && <ReviewRow label="Pension" value={`${formatCurrency(params.pension_annual)}/yr`} />}
        </div>
        {params.has_spouse && (
          <div className="space-y-1 pt-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-light)]">Spouse</div>
            <ReviewRow label="Age" value={String(spouse.age)} />
            <ReviewRow label="Social Security" value={`$${spouse.social_security_monthly.toLocaleString()}/mo`} />
          </div>
        )}
        {params.has_annuity && (
          <div className="space-y-1 pt-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-light)]">Annuity comparison</div>
            <ReviewRow label="Monthly payment" value={`$${annuity.monthly_payment.toLocaleString()}`} />
          </div>
        )}
      </div>
      {error ? <ReviewErrorBanner error={error} /> : null}
    </div>
  );
}

function ReviewErrorBanner({ error }: { error: unknown }) {
  const errorInfo = getErrorInfo(error);
  return (
    <div className="mt-4 rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-light)] p-4 text-sm">
      <strong className="text-[var(--color-danger)]">{errorInfo.title}:</strong>{" "}
      <span className="text-[var(--color-danger)]">{errorInfo.message}</span>
      {errorInfo.field && (
        <span className="mt-1 block italic text-[var(--color-danger)]">
          Check: {errorInfo.field.replace(/_/g, " ")}
        </span>
      )}
    </div>
  );
}
