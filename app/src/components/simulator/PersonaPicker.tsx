"use client";

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
    <div className="mx-auto max-w-3xl space-y-10 py-4">
      {/* Hero */}
      <div className="text-center">
        <div className="mb-3 inline-block rounded-full border border-[var(--color-primary-200)] bg-[var(--color-primary-50)] px-4 py-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-primary)]">
          Monte Carlo Simulation
        </div>
        <h2 className="text-3xl font-semibold text-[var(--color-text)] md:text-4xl" style={{ letterSpacing: "-0.03em" }}>
          See your financial
          <br />
          <span className="bg-gradient-golden bg-clip-text text-transparent">outlook in seconds</span>
        </h2>
        <p className="mx-auto mt-3 max-w-md text-[var(--color-text-muted)]">
          Choose a profile similar to yours, or start from scratch with your own numbers
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {personas.map((persona, i) => (
          <div
            key={persona.id}
            className="animate-fade-in-up group relative overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-[var(--color-bg-card)] p-5 shadow-[var(--shadow-sm)] transition-all duration-300 hover:border-[var(--color-primary-200)] hover:shadow-[var(--shadow-md)]"
            style={{ animationDelay: `${i * 80}ms` }}
          >
            <div className="mb-3 flex items-start gap-3">
              <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--color-primary-50)] text-xl" aria-hidden="true">{persona.emoji}</span>
              <div>
                <h3 className="font-semibold text-[var(--color-text)]">{persona.name}</h3>
                <p className="text-sm text-[var(--color-text-muted)]">{persona.description}</p>
              </div>
            </div>
            <div className="mb-4 flex gap-2 text-xs">
              <span className="rounded-full border border-[var(--color-border-light)] bg-[var(--color-gray-50)] px-2.5 py-1 font-medium text-[var(--color-text-muted)]">
                {formatCurrency(persona.params.initial_capital ?? 0)} saved
              </span>
              <span className="rounded-full border border-[var(--color-border-light)] bg-[var(--color-gray-50)] px-2.5 py-1 font-medium text-[var(--color-text-muted)]">
                {formatCurrency(persona.params.annual_spending)}/yr spending
              </span>
            </div>
            <div className="flex gap-2">
              <button
                className="flex-1 rounded-[var(--radius-sm)] bg-gradient-golden py-2.5 text-sm font-semibold text-white shadow-[var(--shadow-sm)] transition-all hover:shadow-[var(--shadow-md)] hover:brightness-110 disabled:opacity-50"
                onClick={() => onLoadPersona(persona, true)}
                disabled={isLoading}
              >
                {isLoading ? "Running..." : "Run Simulation"}
              </button>
              <button
                className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--color-text-muted)] transition-all hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text)]"
                onClick={() => onLoadPersona(persona, false)}
              >
                Customize
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-4">
        <div className="divider-fade flex-1" />
        <span className="text-xs font-medium uppercase tracking-wider text-[var(--color-text-light)]">or</span>
        <div className="divider-fade flex-1" />
      </div>

      <div className="text-center">
        <button
          className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-6 py-3 text-sm font-medium text-[var(--color-text)] shadow-[var(--shadow-sm)] transition-all hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] hover:shadow-[var(--shadow-md)]"
          onClick={onStartFromScratch}
        >
          Start from scratch with your own numbers
        </button>
      </div>

      {isLoading && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-white/90 p-6 shadow-[var(--shadow-md)] backdrop-blur-sm animate-pulse-glow">
          <SimulationProgress
            currentYear={progress.currentYear}
            totalYears={progress.totalYears}
          />
        </div>
      )}
    </div>
  );
}
