"use client";

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
import { PortfolioProvider, usePortfolioContext } from "../../contexts/PortfolioContext";
import { SimulationProvider, useSimulationContext } from "../../contexts/SimulationContext";
import { ComparisonProvider } from "../../contexts/ComparisonContext";
import { ScenarioProvider } from "../../contexts/ScenarioContext";
import { EXAMPLE_PERSONAS } from "../../lib/simulatorUtils";

export default function SimulatorPage() {
  return (
    <PortfolioProvider>
      <SimulatorWithPortfolio />
    </PortfolioProvider>
  );
}

function SimulatorWithPortfolio() {
  const { portfolioMode, holdings, withdrawalStrategy } = usePortfolioContext();

  return (
    <SimulationProvider portfolioMode={portfolioMode} holdings={holdings} withdrawalStrategy={withdrawalStrategy}>
      <ComparisonProvider>
        <ScenarioProvider>
          <SimulatorShell />
        </ScenarioProvider>
      </ComparisonProvider>
    </SimulationProvider>
  );
}

function SimulatorShell() {
  const sim = useSimulationContext();
  const portfolio = usePortfolioContext();

  const wizardSteps = useWizardSteps({
    params: sim.params, updateParam: sim.updateParam,
    spouse: sim.spouse, setSpouse: sim.setSpouse,
    annuity: sim.annuity, setAnnuity: sim.setAnnuity,
    portfolioMode: portfolio.portfolioMode, setPortfolioMode: portfolio.setPortfolioMode,
    holdings: portfolio.holdings, setHoldings: portfolio.setHoldings,
    withdrawalStrategy: portfolio.withdrawalStrategy, setWithdrawalStrategy: portfolio.setWithdrawalStrategy,
    isReceivingSS: sim.isReceivingSS, setIsReceivingSS: sim.setIsReceivingSS,
    isSpouseReceivingSS: sim.isSpouseReceivingSS, setIsSpouseReceivingSS: sim.setIsSpouseReceivingSS,
    error: sim.simulation.error,
  });

  function renderContent() {
    if (sim.showPersonaPicker && sim.showWizard && !sim.simulation.result) {
      return (
        <PersonaPicker
          personas={EXAMPLE_PERSONAS}
          isLoading={sim.simulation.isLoading}
          progress={sim.simulation.progress}
          onLoadPersona={sim.loadPersona}
          onStartFromScratch={() => sim.setShowPersonaPicker(false)}
        />
      );
    }

    if (sim.showWizard) {
      return (
        <>
          <ScenarioManager />
          <Wizard
            steps={wizardSteps}
            onComplete={sim.handleSimulate}
            isLoading={sim.simulation.isLoading}
            completeButtonText="Run simulation"
            loadingButtonText="Running simulation..."
            loadingContent={
              <SimulationProgress
                currentYear={sim.simulation.progress.currentYear}
                totalYears={sim.simulation.progress.totalYears}
              />
            }
          />
        </>
      );
    }

    if (sim.simulation.isLoading && !sim.simulation.result) {
      return (
        <ResultsSkeleton
          currentYear={sim.simulation.progress.currentYear}
          totalYears={sim.simulation.progress.totalYears}
        />
      );
    }

    if (sim.simulation.error && !sim.simulation.result) {
      return (
        <ErrorState
          error={sim.simulation.error}
          onRetry={() => { sim.simulation.setError(null); sim.handleSimulate(); }}
          onEditInputs={() => { sim.simulation.setError(null); sim.setShowWizard(true); }}
        />
      );
    }

    if (sim.simulation.result) {
      return (
        <ResultsPanel
          onEditInputs={() => sim.setShowWizard(true)}
          onWhatIf={sim.runWhatIfScenario}
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
