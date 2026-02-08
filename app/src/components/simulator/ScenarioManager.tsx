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
    <div className="saved-scenarios-section">
      <div className="saved-scenarios-header">
        <div className="saved-scenarios-actions">
          <button
            className="btn-save-scenario"
            onClick={() => setShowSaveDialog(true)}
            title="Save current scenario"
          >
            Save Scenario
          </button>
          {savedScenarios.length > 0 && (
            <select
              className="scenario-select"
              value=""
              onChange={(e) => {
                const scenario = savedScenarios.find(s => s.name === e.target.value);
                if (scenario) {
                  onLoad(scenario);
                }
              }}
            >
              <option value="" disabled>Load Saved...</option>
              {savedScenarios.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Save Dialog */}
      {showSaveDialog && (
        <div className="save-dialog">
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
          />
          <button
            className="btn-confirm-save"
            onClick={() => scenarioName.trim() && onSave(scenarioName.trim())}
            disabled={!scenarioName.trim()}
          >
            Save
          </button>
          <button
            className="btn-cancel-save"
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
        <div className="saved-scenarios-list">
          {savedScenarios.map((scenario) => (
            <div key={scenario.name} className="saved-scenario-item">
              <button
                className="scenario-load-btn"
                onClick={() => onLoad(scenario)}
              >
                <span className="scenario-name">{scenario.name}</span>
                <span className="scenario-date">
                  {new Date(scenario.savedAt).toLocaleDateString()}
                </span>
              </button>
              <button
                className="scenario-delete-btn"
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
