"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { Wizard } from "../../components/Wizard";
import { SimulationProgress } from "../../components/SimulationProgress";
import { ResultsSkeleton } from "../../components/ResultsSkeleton";
import {
  PersonaPicker,
  ResultsPanel,
  ErrorState,
  ScenarioManager,
  useWizardSteps,
} from "../../components/simulator";
import { useSimulation } from "../../hooks/useSimulation";
import { useComparisons } from "../../hooks/useComparisons";
import { useScenarios } from "../../hooks/useScenarios";
import { usePortfolio } from "../../hooks/usePortfolio";
import type { SimulationInput, SpouseInput } from "../../lib/api";
import {
  DEFAULT_PARAMS,
  DEFAULT_SPOUSE,
  DEFAULT_ANNUITY,
} from "../../lib/constants";
import {
  EXAMPLE_PERSONAS,
  parseUrlParams,
  type Persona,
} from "../../lib/simulatorUtils";

export default function SimulatorPage() {
  const [urlData] = useState(() => parseUrlParams());
  const hasUrlParams = Object.keys(urlData.params).length > 0;

  const [params, setParams] = useState<SimulationInput>(() =>
    hasUrlParams ? { ...DEFAULT_PARAMS, ...urlData.params } : DEFAULT_PARAMS
  );
  const [spouse, setSpouse] = useState<SpouseInput>(() =>
    Object.keys(urlData.spouse).length > 0
      ? { ...DEFAULT_SPOUSE, ...urlData.spouse }
      : DEFAULT_SPOUSE
  );
  const [annuity, setAnnuity] = useState(DEFAULT_ANNUITY);

  const [showWizard, setShowWizard] = useState(true);
  const [showPersonaPicker, setShowPersonaPicker] = useState(!hasUrlParams);

  const [isReceivingSS, setIsReceivingSS] = useState(false);
  const [isSpouseReceivingSS, setIsSpouseReceivingSS] = useState(false);

  const portfolio = usePortfolio();
  const simulation = useSimulation();
  const comparisons = useComparisons({
    params, spouse, annuity,
    portfolioMode: portfolio.portfolioMode,
    holdings: portfolio.holdings,
    withdrawalStrategy: portfolio.withdrawalStrategy,
    result: simulation.result,
    setError: simulation.setError,
  });
  const scenarios = useScenarios({
    params, spouse, annuity,
    portfolioMode: portfolio.portfolioMode,
    holdings: portfolio.holdings,
    withdrawalStrategy: portfolio.withdrawalStrategy,
    setParams, setSpouse, setAnnuity,
    setPortfolioMode: portfolio.setPortfolioMode,
    setHoldings: portfolio.setHoldings,
    setWithdrawalStrategy: portfolio.setWithdrawalStrategy,
    setShowPersonaPicker,
  });

  const updateParam = useCallback(<K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => {
    setParams((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSimulate = useCallback(async () => {
    await simulation.handleSimulate(
      params, spouse, annuity,
      portfolio.portfolioMode, portfolio.holdings, portfolio.withdrawalStrategy,
    );
    setShowWizard(false);
  }, [params, spouse, annuity, portfolio.portfolioMode, portfolio.holdings, portfolio.withdrawalStrategy, simulation]);

  const handleSimulateWithParams = useCallback(async (simParams: SimulationInput, simSpouse?: SpouseInput) => {
    await simulation.handleSimulateWithParams(
      simParams, simSpouse, annuity,
      portfolio.portfolioMode, portfolio.holdings, portfolio.withdrawalStrategy,
    );
    setShowWizard(false);
  }, [annuity, portfolio.portfolioMode, portfolio.holdings, portfolio.withdrawalStrategy, simulation]);

  const loadPersona = useCallback((persona: Persona, runImmediately: boolean = false) => {
    setParams(persona.params);
    if (persona.spouse) setSpouse(persona.spouse);
    setShowPersonaPicker(false);
    if (runImmediately) {
      setTimeout(() => handleSimulateWithParams(persona.params, persona.spouse), 0);
    }
  }, [handleSimulateWithParams]);

  const runWhatIfScenario = useCallback((modifier: Partial<SimulationInput>) => {
    setParams((prev) => ({ ...prev, ...modifier }));
    setShowWizard(true);
  }, []);

  const wizardSteps = useWizardSteps({
    params, updateParam, spouse, setSpouse, annuity, setAnnuity,
    portfolioMode: portfolio.portfolioMode,
    setPortfolioMode: portfolio.setPortfolioMode,
    holdings: portfolio.holdings,
    setHoldings: portfolio.setHoldings,
    withdrawalStrategy: portfolio.withdrawalStrategy,
    setWithdrawalStrategy: portfolio.setWithdrawalStrategy,
    isReceivingSS, setIsReceivingSS,
    isSpouseReceivingSS, setIsSpouseReceivingSS,
    error: simulation.error,
  });

  function renderContent() {
    if (showPersonaPicker && showWizard && !simulation.result) {
      return (
        <PersonaPicker
          personas={EXAMPLE_PERSONAS}
          isLoading={simulation.isLoading}
          progress={simulation.progress}
          onLoadPersona={loadPersona}
          onStartFromScratch={() => setShowPersonaPicker(false)}
        />
      );
    }

    if (showWizard) {
      return (
        <>
          <ScenarioManager
            savedScenarios={scenarios.savedScenarios}
            scenarioName={scenarios.scenarioName}
            setScenarioName={scenarios.setScenarioName}
            showSaveDialog={scenarios.showSaveDialog}
            setShowSaveDialog={scenarios.setShowSaveDialog}
            onSave={scenarios.saveScenario}
            onLoad={scenarios.loadSavedScenario}
            onDelete={scenarios.deleteScenario}
          />
          <Wizard
            steps={wizardSteps}
            onComplete={handleSimulate}
            isLoading={simulation.isLoading}
            completeButtonText="Run simulation"
            loadingButtonText="Running simulation..."
            loadingContent={
              <SimulationProgress
                currentYear={simulation.progress.currentYear}
                totalYears={simulation.progress.totalYears}
              />
            }
          />
        </>
      );
    }

    if (simulation.isLoading && !simulation.result) {
      return (
        <ResultsSkeleton
          currentYear={simulation.progress.currentYear}
          totalYears={simulation.progress.totalYears}
        />
      );
    }

    if (simulation.error && !simulation.result) {
      return (
        <ErrorState
          error={simulation.error}
          onRetry={() => { simulation.setError(null); handleSimulate(); }}
          onEditInputs={() => { simulation.setError(null); setShowWizard(true); }}
        />
      );
    }

    if (simulation.result) {
      return (
        <ResultsPanel
          result={simulation.result}
          params={params}
          annuity={annuity}
          annuityResult={simulation.annuityResult}
          selectedYearIndex={simulation.selectedYearIndex}
          setSelectedYearIndex={simulation.setSelectedYearIndex}
          linkCopied={scenarios.linkCopied}
          onCopyLink={scenarios.copyLinkToClipboard}
          onEditInputs={() => setShowWizard(true)}
          onWhatIf={runWhatIfScenario}
          stateComparisonResult={comparisons.stateComparisonResult}
          isComparingStates={comparisons.isComparingStates}
          selectedCompareStates={comparisons.selectedCompareStates}
          onCompareStates={comparisons.handleCompareStates}
          onToggleCompareState={comparisons.toggleCompareState}
          onResetStateComparison={() => { comparisons.setStateComparisonResult(null); comparisons.setSelectedCompareStates([]); }}
          ssTimingResult={comparisons.ssTimingResult}
          isComparingSSTiming={comparisons.isComparingSSTiming}
          birthYear={comparisons.birthYear}
          setBirthYear={comparisons.setBirthYear}
          piaMonthly={comparisons.piaMonthly}
          setPiaMonthly={comparisons.setPiaMonthly}
          onCompareSSTimings={comparisons.handleCompareSSTimings}
          onResetSSTimings={() => comparisons.setSSTimingResult(null)}
          allocationResult={comparisons.allocationResult}
          isComparingAllocations={comparisons.isComparingAllocations}
          onCompareAllocations={comparisons.handleCompareAllocations}
          onResetAllocations={() => comparisons.setAllocationResult(null)}
        />
      );
    }

    return null;
  }

  return (
    <div className="min-h-screen">
      <header className="header-glass sticky top-0 z-50 border-b border-[var(--color-border-light)]">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 md:px-6">
          <Link href="/" className="flex items-center gap-2.5 transition-opacity hover:opacity-80">
            <img src="/logo.svg" alt="EggNest" height="28" className="h-7" />
          </Link>
          <span className="hidden text-xs font-semibold uppercase tracking-widest text-[var(--color-text-muted)] sm:block">Financial simulator</span>
          <Link href="/life-event" className="rounded-full border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] px-4 py-1.5 text-xs font-semibold text-[var(--color-primary)] transition-all hover:bg-[var(--color-primary)] hover:text-white hover:border-[var(--color-primary)]">
            Tax & benefits calculator
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-10 md:px-6 md:py-12">
        {renderContent()}
      </main>
    </div>
  );
}
