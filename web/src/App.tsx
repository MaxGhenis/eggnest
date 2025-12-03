import { useState } from "react";
import { SimulationForm } from "./components/SimulationForm";
import { ResultsChart } from "./components/ResultsChart";
import { ResultsSummary } from "./components/ResultsSummary";
import { runSimulation, type SimulationInput, type SimulationResult } from "./lib/api";
import "./App.css";

function App() {
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastParams, setLastParams] = useState<SimulationInput | null>(null);

  const handleSimulate = async (params: SimulationInput) => {
    setIsLoading(true);
    setError(null);
    setLastParams(params);

    try {
      const simulationResult = await runSimulation(params);
      setResult(simulationResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed");
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>FinSim</h1>
        <p className="tagline">Retirement Planning Simulator</p>
      </header>

      <main className="app-main">
        <div className="form-panel">
          <SimulationForm onSubmit={handleSimulate} isLoading={isLoading} />
        </div>

        <div className="results-panel">
          {error && (
            <div className="error-message">
              <strong>Error:</strong> {error}
            </div>
          )}

          {result && (
            <>
              <ResultsSummary result={result} />
              <ResultsChart result={result} />
            </>
          )}

          {!result && !error && !isLoading && (
            <div className="empty-state">
              <h2>Configure Your Simulation</h2>
              <p>
                Enter your financial details on the left to run a Monte Carlo
                simulation of your retirement portfolio.
              </p>
              <ul>
                <li>See the probability of your money lasting</li>
                <li>View projected portfolio values over time</li>
                <li>Understand the range of possible outcomes</li>
              </ul>
            </div>
          )}

          {isLoading && (
            <div className="loading-state">
              <div className="spinner" />
              <p>Running {lastParams?.n_simulations.toLocaleString()} simulations...</p>
            </div>
          )}
        </div>
      </main>

      <footer className="app-footer">
        <p>
          FinSim provides educational projections only. Consult a financial
          advisor for personalized advice.
        </p>
      </footer>
    </div>
  );
}

export default App;
