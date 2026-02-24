"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { SimulationInput, SpouseInput, AnnuityInput } from "../lib/api";
import { useSimulation, type UseSimulationReturn } from "../hooks/useSimulation";
import type { PortfolioMode, WithdrawalStrategy } from "../hooks/usePortfolio";
import type { Holding } from "../lib/api";
import {
  DEFAULT_PARAMS,
  DEFAULT_SPOUSE,
  DEFAULT_ANNUITY,
} from "../lib/constants";
import { parseUrlParams, type Persona } from "../lib/simulatorUtils";

interface SimulationContextValue {
  // Core state
  params: SimulationInput;
  setParams: React.Dispatch<React.SetStateAction<SimulationInput>>;
  updateParam: <K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => void;
  spouse: SpouseInput;
  setSpouse: React.Dispatch<React.SetStateAction<SpouseInput>>;
  annuity: AnnuityInput;
  setAnnuity: React.Dispatch<React.SetStateAction<AnnuityInput>>;

  // UI state
  showWizard: boolean;
  setShowWizard: React.Dispatch<React.SetStateAction<boolean>>;
  showPersonaPicker: boolean;
  setShowPersonaPicker: React.Dispatch<React.SetStateAction<boolean>>;
  isReceivingSS: boolean;
  setIsReceivingSS: React.Dispatch<React.SetStateAction<boolean>>;
  isSpouseReceivingSS: boolean;
  setIsSpouseReceivingSS: React.Dispatch<React.SetStateAction<boolean>>;

  // Simulation hook return
  simulation: UseSimulationReturn;

  // Actions
  handleSimulate: () => Promise<void>;
  handleSimulateWithParams: (simParams: SimulationInput, simSpouse?: SpouseInput) => Promise<void>;
  loadPersona: (persona: Persona, runImmediately?: boolean) => void;
  runWhatIfScenario: (modifier: Partial<SimulationInput>) => void;
}

const SimulationContext = createContext<SimulationContextValue | null>(null);

export function useSimulationContext(): SimulationContextValue {
  const ctx = useContext(SimulationContext);
  if (!ctx) throw new Error("useSimulationContext must be used within SimulationProvider");
  return ctx;
}

interface SimulationProviderProps {
  children: ReactNode;
  portfolioMode: PortfolioMode;
  holdings: Holding[];
  withdrawalStrategy: WithdrawalStrategy;
}

export function SimulationProvider({ children, portfolioMode, holdings, withdrawalStrategy }: SimulationProviderProps) {
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

  const simulation = useSimulation();

  const updateParam = useCallback(<K extends keyof SimulationInput>(key: K, value: SimulationInput[K]) => {
    setParams((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSimulate = useCallback(async () => {
    await simulation.handleSimulate(
      params, spouse, annuity,
      portfolioMode, holdings, withdrawalStrategy,
    );
    setShowWizard(false);
  }, [params, spouse, annuity, portfolioMode, holdings, withdrawalStrategy, simulation]);

  const handleSimulateWithParams = useCallback(async (simParams: SimulationInput, simSpouse?: SpouseInput) => {
    await simulation.handleSimulateWithParams(
      simParams, simSpouse, annuity,
      portfolioMode, holdings, withdrawalStrategy,
    );
    setShowWizard(false);
  }, [annuity, portfolioMode, holdings, withdrawalStrategy, simulation]);

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

  return (
    <SimulationContext.Provider value={{
      params, setParams, updateParam,
      spouse, setSpouse,
      annuity, setAnnuity,
      showWizard, setShowWizard,
      showPersonaPicker, setShowPersonaPicker,
      isReceivingSS, setIsReceivingSS,
      isSpouseReceivingSS, setIsSpouseReceivingSS,
      simulation,
      handleSimulate, handleSimulateWithParams, loadPersona, runWhatIfScenario,
    }}>
      {children}
    </SimulationContext.Provider>
  );
}
