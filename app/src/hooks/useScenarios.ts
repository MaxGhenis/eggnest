import { useState, useEffect, useCallback } from "react";
import type { SimulationInput, SpouseInput, AnnuityInput, Holding } from "../lib/api";
import type { SavedScenario } from "../lib/simulatorUtils";
import { SCENARIOS_STORAGE_KEY, DEFAULT_PARAMS } from "../lib/constants";

export interface UseScenariosReturn {
  savedScenarios: SavedScenario[];
  scenarioName: string;
  setScenarioName: React.Dispatch<React.SetStateAction<string>>;
  showSaveDialog: boolean;
  setShowSaveDialog: React.Dispatch<React.SetStateAction<boolean>>;
  linkCopied: boolean;
  saveScenario: (name: string) => void;
  loadSavedScenario: (scenario: SavedScenario) => void;
  deleteScenario: (name: string) => void;
  copyLinkToClipboard: () => Promise<void>;
}

interface ScenarioDeps {
  params: SimulationInput;
  spouse: SpouseInput;
  annuity: AnnuityInput;
  portfolioMode: "simple" | "detailed";
  holdings: Holding[];
  withdrawalStrategy: "taxable_first" | "traditional_first" | "roth_first" | "pro_rata";
  setParams: React.Dispatch<React.SetStateAction<SimulationInput>>;
  setSpouse: React.Dispatch<React.SetStateAction<SpouseInput>>;
  setAnnuity: React.Dispatch<React.SetStateAction<AnnuityInput>>;
  setPortfolioMode: React.Dispatch<React.SetStateAction<"simple" | "detailed">>;
  setHoldings: React.Dispatch<React.SetStateAction<Holding[]>>;
  setWithdrawalStrategy: React.Dispatch<React.SetStateAction<"taxable_first" | "traditional_first" | "roth_first" | "pro_rata">>;
  setShowPersonaPicker: React.Dispatch<React.SetStateAction<boolean>>;
}

export function useScenarios(deps: ScenarioDeps): UseScenariosReturn {
  const {
    params, spouse, annuity, portfolioMode, holdings, withdrawalStrategy,
    setParams, setSpouse, setAnnuity, setPortfolioMode, setHoldings,
    setWithdrawalStrategy, setShowPersonaPicker,
  } = deps;

  const [savedScenarios, setSavedScenarios] = useState<SavedScenario[]>([]);
  const [scenarioName, setScenarioName] = useState("");
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);

  // Load saved scenarios from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(SCENARIOS_STORAGE_KEY);
      if (stored) {
        setSavedScenarios(JSON.parse(stored));
      }
    } catch (e) {
      console.error("Failed to load saved scenarios:", e);
    }
  }, []);

  const saveScenario = useCallback((name: string) => {
    const scenario: SavedScenario = {
      name,
      savedAt: new Date().toISOString(),
      inputs: { ...params },
      spouse: params.has_spouse ? spouse : undefined,
      annuity: params.has_annuity ? annuity : undefined,
      portfolioMode,
      holdings: portfolioMode === "detailed" ? holdings : undefined,
      withdrawalStrategy: portfolioMode === "detailed" ? withdrawalStrategy : undefined,
    };

    const updated = [...savedScenarios.filter(s => s.name !== name), scenario];
    setSavedScenarios(updated);
    try {
      localStorage.setItem(SCENARIOS_STORAGE_KEY, JSON.stringify(updated));
    } catch (e) {
      console.error("Failed to save scenario (storage quota exceeded?):", e);
    }
    setScenarioName("");
    setShowSaveDialog(false);
  }, [params, spouse, annuity, portfolioMode, holdings, withdrawalStrategy, savedScenarios]);

  const loadSavedScenario = useCallback((scenario: SavedScenario) => {
    if (scenario.inputs) {
      setParams({ ...DEFAULT_PARAMS, ...scenario.inputs } as SimulationInput);
    }
    if (scenario.spouse) {
      setSpouse(scenario.spouse);
    }
    if (scenario.annuity) {
      setAnnuity(scenario.annuity);
    }
    if (scenario.portfolioMode) {
      setPortfolioMode(scenario.portfolioMode);
    }
    if (scenario.holdings) {
      setHoldings(scenario.holdings as Holding[]);
    }
    if (scenario.withdrawalStrategy) {
      setWithdrawalStrategy(scenario.withdrawalStrategy);
    }
    setShowPersonaPicker(false);
  }, [setParams, setSpouse, setAnnuity, setPortfolioMode, setHoldings, setWithdrawalStrategy, setShowPersonaPicker]);

  const deleteScenario = useCallback((name: string) => {
    const updated = savedScenarios.filter(s => s.name !== name);
    setSavedScenarios(updated);
    try {
      localStorage.setItem(SCENARIOS_STORAGE_KEY, JSON.stringify(updated));
    } catch (e) {
      console.error("Failed to persist scenario deletion:", e);
    }
  }, [savedScenarios]);

  const copyLinkToClipboard = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy link:", err);
    }
  }, []);

  return {
    savedScenarios,
    scenarioName,
    setScenarioName,
    showSaveDialog,
    setShowSaveDialog,
    linkCopied,
    saveScenario,
    loadSavedScenario,
    deleteScenario,
    copyLinkToClipboard,
  };
}
