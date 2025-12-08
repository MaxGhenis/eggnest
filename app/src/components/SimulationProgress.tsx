import "../styles/SimulationProgress.css";

interface SimulationProgressProps {
  currentYear: number;
  totalYears: number;
}

export function SimulationProgress({ currentYear, totalYears }: SimulationProgressProps) {
  const percentage = Math.round((currentYear / totalYears) * 100);

  return (
    <div className="simulation-progress">
      <div className="progress-header">
        <span className="progress-label">Calculating taxes with PolicyEngine...</span>
        <span className="progress-percent">{percentage}%</span>
      </div>
      <div
        className="progress-bar"
        role="progressbar"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="progress-fill"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="progress-detail">
        Year {currentYear} of {totalYears}
      </div>
    </div>
  );
}
