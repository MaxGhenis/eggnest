import { getErrorInfo } from "../../lib/simulatorUtils";

interface ErrorStateProps {
  error: unknown;
  onRetry: () => void;
  onEditInputs: () => void;
}

export function ErrorState({ error, onRetry, onEditInputs }: ErrorStateProps) {
  const errorInfo = getErrorInfo(error);

  return (
    <div className="error-state">
      <div className="error-state-card">
        <div className="error-state-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h2 className="error-state-title">{errorInfo.title}</h2>
        <p className="error-state-message">{errorInfo.message}</p>

        {errorInfo.technical && errorInfo.technical !== errorInfo.message && (
          <div className="error-state-details">
            <div className="error-state-details-label">Technical Details</div>
            <p className="error-state-details-text">{errorInfo.technical}</p>
          </div>
        )}

        <div className="error-state-suggestion">
          <strong>What to do:</strong> {errorInfo.suggestion}
        </div>

        <div className="error-state-actions">
          <button
            className="error-state-btn-primary"
            onClick={onRetry}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
            </svg>
            Try Again
          </button>
          <button
            className="error-state-btn-secondary"
            onClick={onEditInputs}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
            Edit Inputs
          </button>
        </div>
      </div>
    </div>
  );
}
