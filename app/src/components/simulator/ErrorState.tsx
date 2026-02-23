"use client";

import { getErrorInfo } from "../../lib/simulatorUtils";

interface ErrorStateProps {
  error: unknown;
  onRetry: () => void;
  onEditInputs: () => void;
}

export function ErrorState({ error, onRetry, onEditInputs }: ErrorStateProps) {
  const errorInfo = getErrorInfo(error);

  return (
    <div className="flex min-h-[400px] items-center justify-center p-8">
      <div className="mx-auto max-w-md space-y-6 rounded-[var(--radius-xl)] bg-[var(--color-bg-card)] p-8 text-center shadow-[var(--shadow-lg)]">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[var(--color-danger-light)]">
          <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-7 w-7">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-[var(--color-text)]">{errorInfo.title}</h2>
        <p className="text-sm text-[var(--color-text-muted)]">{errorInfo.message}</p>

        {errorInfo.technical && errorInfo.technical !== errorInfo.message && (
          <div className="rounded-[var(--radius-sm)] bg-[var(--color-gray-50)] p-3 text-left">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-light)]">Technical Details</div>
            <p className="text-xs text-[var(--color-text-muted)] break-words">{errorInfo.technical}</p>
          </div>
        )}

        <div className="rounded-[var(--radius-md)] bg-[var(--color-primary-50)] p-3 text-sm text-[var(--color-primary-dark)]">
          <strong>What to do:</strong> {errorInfo.suggestion}
        </div>

        <div className="flex justify-center gap-3">
          <button
            className="inline-flex items-center gap-2 rounded-[var(--radius-md)] bg-gradient-golden px-5 py-2.5 text-sm font-semibold text-white shadow-[var(--shadow-sm)] transition-all hover:shadow-[var(--shadow-md)] hover:brightness-110"
            onClick={onRetry}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
            </svg>
            Try Again
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-5 py-2.5 text-sm font-medium text-[var(--color-text-muted)] transition-all hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text)]"
            onClick={onEditInputs}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
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
