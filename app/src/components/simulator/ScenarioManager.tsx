"use client";

import type { SavedScenario } from "../../lib/simulatorUtils";

interface ScenarioManagerProps {
  savedScenarios: SavedScenario[];
  scenarioName: string;
  setScenarioName: (name: string) => void;
  showSaveDialog: boolean;
  setShowSaveDialog: (show: boolean) => void;
  onSave: (name: string) => void;
  onLoad: (scenario: SavedScenario) => void;
  onDelete: (name: string) => void;
}

export function ScenarioManager({
  savedScenarios,
  scenarioName,
  setScenarioName,
  showSaveDialog,
  setShowSaveDialog,
  onSave,
  onLoad,
  onDelete,
}: ScenarioManagerProps) {
  return (
    <div className="mb-4 space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <button
          className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-4 py-2 text-sm font-medium text-[var(--color-text-muted)] transition-all hover:border-[var(--color-primary)] hover:text-[var(--color-primary)]"
          onClick={() => setShowSaveDialog(true)}
          title="Save current scenario"
        >
          Save scenario
        </button>
        {savedScenarios.length > 0 && (
          <select
            className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-3 py-2 text-sm text-[var(--color-text-muted)] transition-colors focus:border-[var(--color-primary)] focus:outline-none"
            value=""
            onChange={(e) => {
              const scenario = savedScenarios.find(s => s.name === e.target.value);
              if (scenario) onLoad(scenario);
            }}
          >
            <option value="" disabled>Load saved...</option>
            {savedScenarios.map((s) => (
              <option key={s.name} value={s.name}>{s.name}</option>
            ))}
          </select>
        )}
      </div>

      {/* Save Dialog */}
      {showSaveDialog && (
        <div className="flex items-center gap-2 rounded-[var(--radius-md)] border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] p-3">
          <input
            type="text"
            placeholder="Scenario name..."
            value={scenarioName}
            onChange={(e) => setScenarioName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && scenarioName.trim()) {
                onSave(scenarioName.trim());
              } else if (e.key === "Escape") {
                setShowSaveDialog(false);
                setScenarioName("");
              }
            }}
            autoFocus
            className="flex-1 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-3 py-2 text-sm focus:border-[var(--color-primary)] focus:outline-none"
          />
          <button
            className="rounded-[var(--radius-sm)] bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition-all hover:brightness-110 disabled:opacity-40"
            onClick={() => scenarioName.trim() && onSave(scenarioName.trim())}
            disabled={!scenarioName.trim()}
          >
            Save
          </button>
          <button
            className="rounded-[var(--radius-sm)] px-3 py-2 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            onClick={() => {
              setShowSaveDialog(false);
              setScenarioName("");
            }}
          >
            Cancel
          </button>
        </div>
      )}

      {/* Saved Scenarios List */}
      {savedScenarios.length > 0 && (
        <div className="space-y-1">
          {savedScenarios.map((scenario) => (
            <div key={scenario.name} className="flex items-center gap-2 rounded-[var(--radius-sm)] transition-colors hover:bg-[var(--color-gray-50)]">
              <button
                className="flex flex-1 items-center justify-between px-3 py-2 text-left text-sm"
                onClick={() => onLoad(scenario)}
              >
                <span className="font-medium text-[var(--color-text)]">{scenario.name}</span>
                <span className="text-xs text-[var(--color-text-light)]">
                  {new Date(scenario.savedAt).toLocaleDateString()}
                </span>
              </button>
              <button
                className="flex h-7 w-7 items-center justify-center rounded-full text-[var(--color-text-light)] transition-colors hover:bg-[var(--color-danger-light)] hover:text-[var(--color-danger)]"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(scenario.name);
                }}
                title="Delete scenario"
              >
                x
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
