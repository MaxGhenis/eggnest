import { SimulationProgress } from "../SimulationProgress";
import { formatCurrency, type Persona } from "../../lib/simulatorUtils";

interface PersonaPickerProps {
  personas: Persona[];
  isLoading: boolean;
  progress: { currentYear: number; totalYears: number };
  onLoadPersona: (persona: Persona, runImmediately: boolean) => void;
  onStartFromScratch: () => void;
}

export function PersonaPicker({
  personas,
  isLoading,
  progress,
  onLoadPersona,
  onStartFromScratch,
}: PersonaPickerProps) {
  return (
    <div className="persona-picker">
      <div className="persona-header">
        <h2>See your financial outlook in seconds</h2>
        <p>Choose a profile similar to yours, or start from scratch</p>
      </div>

      <div className="persona-grid">
        {personas.map((persona) => (
          <div key={persona.id} className="persona-card">
            <div className="persona-emoji">{persona.emoji}</div>
            <div className="persona-info">
              <h3>{persona.name}</h3>
              <p>{persona.description}</p>
              <div className="persona-stats">
                <span>{formatCurrency(persona.params.initial_capital ?? 0)} saved</span>
                <span>{formatCurrency(persona.params.annual_spending)}/yr spending</span>
              </div>
            </div>
            <div className="persona-actions">
              <button
                className="persona-btn-run"
                onClick={() => onLoadPersona(persona, true)}
                disabled={isLoading}
              >
                {isLoading ? "Running..." : "Run Simulation"}
              </button>
              <button
                className="persona-btn-customize"
                onClick={() => onLoadPersona(persona, false)}
              >
                Customize First
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="persona-divider">
        <span>or</span>
      </div>

      <button
        className="persona-start-scratch"
        onClick={onStartFromScratch}
      >
        Start from scratch with your own numbers
      </button>

      {isLoading && (
        <div className="persona-loading">
          <SimulationProgress
            currentYear={progress.currentYear}
            totalYears={progress.totalYears}
          />
        </div>
      )}
    </div>
  );
}
