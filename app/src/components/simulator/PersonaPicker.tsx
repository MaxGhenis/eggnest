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
    <div className="mx-auto max-w-3xl space-y-8 py-4">
      <div className="text-center">
        <h2 className="text-2xl font-semibold text-[var(--color-text)] md:text-3xl">
          See your financial outlook in seconds
        </h2>
        <p className="mt-2 text-[var(--color-text-muted)]">
          Choose a profile similar to yours, or start from scratch
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {personas.map((persona) => (
          <div
            key={persona.id}
            className="group relative overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border-light)] bg-[var(--color-bg-card)] p-5 shadow-[var(--shadow-sm)] transition-all duration-300 hover:border-[var(--color-primary-200)] hover:shadow-[var(--shadow-md)]"
          >
            <div className="mb-3 flex items-start gap-3">
              <span className="text-2xl" aria-hidden="true">{persona.emoji}</span>
              <div>
                <h3 className="font-semibold text-[var(--color-text)]">{persona.name}</h3>
                <p className="text-sm text-[var(--color-text-muted)]">{persona.description}</p>
              </div>
            </div>
            <div className="mb-4 flex gap-3 text-xs text-[var(--color-text-light)]">
              <span className="rounded-full bg-[var(--color-gray-100)] px-2.5 py-1">
                {formatCurrency(persona.params.initial_capital ?? 0)} saved
              </span>
              <span className="rounded-full bg-[var(--color-gray-100)] px-2.5 py-1">
                {formatCurrency(persona.params.annual_spending)}/yr spending
              </span>
            </div>
            <div className="flex gap-2">
              <button
                className="flex-1 rounded-[var(--radius-sm)] bg-gradient-golden py-2 text-sm font-semibold text-white transition-all hover:brightness-110 disabled:opacity-50"
                onClick={() => onLoadPersona(persona, true)}
                disabled={isLoading}
              >
                {isLoading ? "Running..." : "Run Simulation"}
              </button>
              <button
                className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-white px-3 py-2 text-sm font-medium text-[var(--color-text-muted)] transition-all hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text)]"
                onClick={() => onLoadPersona(persona, false)}
              >
                Customize
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-4">
        <div className="h-px flex-1 bg-[var(--color-border)]" />
        <span className="text-sm text-[var(--color-text-light)]">or</span>
        <div className="h-px flex-1 bg-[var(--color-border)]" />
      </div>

      <div className="text-center">
        <button
          className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-6 py-3 text-sm font-medium text-[var(--color-text)] transition-all hover:border-[var(--color-primary)] hover:text-[var(--color-primary)]"
          onClick={onStartFromScratch}
        >
          Start from scratch with your own numbers
        </button>
      </div>

      {isLoading && (
        <div className="rounded-[var(--radius-lg)] bg-white/80 p-4 backdrop-blur-sm">
          <SimulationProgress
            currentYear={progress.currentYear}
            totalYears={progress.totalYears}
          />
        </div>
      )}
    </div>
  );
}
