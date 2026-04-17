"use client";

import { useMemo, useState, type ReactNode } from "react";
import type { ValidationError } from "../lib/validation";

export interface WizardStep {
  id: string;
  title: string;
  subtitle?: string;
  optional?: boolean;
  content: ReactNode;
  isComplete?: () => boolean;
  fieldNames?: string[];
}

interface WizardProps {
  steps: WizardStep[];
  onComplete: () => void;
  initialStep?: number;
  isLoading?: boolean;
  completeButtonText?: string;
  loadingButtonText?: string;
  loadingContent?: ReactNode;
  validationErrors?: ValidationError[];
}

export function Wizard({
  steps,
  onComplete,
  initialStep = 0,
  isLoading = false,
  completeButtonText = "Run simulation",
  loadingButtonText = "Running...",
  loadingContent,
  validationErrors = [],
}: WizardProps) {
  const [currentStep, setCurrentStep] = useState(() =>
    Math.max(0, Math.min(initialStep, steps.length - 1))
  );

  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === steps.length - 1;
  const step = steps[currentStep];
  const hasErrors = validationErrors.length > 0;
  const stepValidationErrors = useMemo(
    () =>
      steps.map((wizardStep) => {
        if (!wizardStep.fieldNames?.length) {
          return [];
        }

        return validationErrors.filter((error) =>
          wizardStep.fieldNames!.some((fieldName) => matchesFieldPattern(error.field, fieldName))
        );
      }),
    [steps, validationErrors]
  );
  const currentStepErrors = stepValidationErrors[currentStep] ?? [];
  const firstErrorStepIndex = stepValidationErrors.findIndex((errors) => errors.length > 0);

  function getPrimaryButtonLabel(): string {
    if (!isLastStep) return "Next";
    if (isLoading) return loadingButtonText;
    if (hasErrors) {
      return `Fix ${validationErrors.length} error${validationErrors.length === 1 ? "" : "s"}`;
    }
    return completeButtonText;
  }

  function getPrimaryButtonAriaLabel(): string {
    if (!isLastStep) return "Go to next step";
    if (isLoading) return loadingButtonText;
    if (hasErrors && firstErrorStepIndex >= 0) {
      const firstErrorStep = steps[firstErrorStepIndex];
      return `Go to ${firstErrorStep.title} to fix ${validationErrors.length} validation error${validationErrors.length === 1 ? "" : "s"}`;
    }
    return completeButtonText;
  }

  const handleNext = () => {
    if (isLastStep) {
      if (hasErrors) {
        if (firstErrorStepIndex >= 0) {
          setCurrentStep(firstErrorStepIndex);
        }
        return;
      }
      onComplete();
    } else {
      setCurrentStep((prev) => Math.min(prev + 1, steps.length - 1));
    }
  };

  const handleBack = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 0));
  };

  const handleStepClick = (index: number) => {
    if (index <= currentStep + 1) {
      setCurrentStep(index);
    }
  };

  return (
    <div
      className="mx-auto max-w-2xl overflow-hidden rounded-[var(--radius-xl)] bg-[var(--color-bg-card)] shadow-[var(--shadow-lg)]"
      role="form"
      aria-label="Simulation setup wizard"
    >
      {/* Progress indicator - top bar */}
      <nav className="border-b border-[var(--color-border-light)] bg-[var(--color-gray-50)] px-6 py-4 md:px-8" aria-label="Wizard steps">
        <div className="flex items-center gap-1 overflow-x-auto pb-1">
          {steps.map((s, index) => {
            const isCurrent = index === currentStep;
            const isCompleted = index < currentStep;
            const isClickable = index <= currentStep + 1;
            const errorCount = stepValidationErrors[index]?.length ?? 0;
            const hasStepErrors = errorCount > 0;
            return (
              <button
                key={s.id}
                className={`flex flex-shrink-0 flex-col items-center gap-1.5 rounded-[var(--radius-md)] px-3 py-2 text-center transition-all duration-200 ${
                  isCurrent
                    ? "bg-white text-[var(--color-primary)] shadow-[var(--shadow-sm)]"
                    : isCompleted
                      ? "text-[var(--color-success)]"
                      : hasStepErrors
                        ? "text-[var(--color-warning)]"
                      : "text-[var(--color-text-light)]"
                } ${isClickable ? "cursor-pointer hover:bg-white/80" : "cursor-default opacity-50"}`}
                onClick={() => handleStepClick(index)}
                disabled={!isClickable}
                aria-label={`Step ${index + 1}: ${s.title}${isCompleted ? " (completed)" : isCurrent ? " (current)" : ""}${hasStepErrors ? ` (${errorCount} validation error${errorCount === 1 ? "" : "s"})` : ""}`}
                aria-current={isCurrent ? "step" : undefined}
              >
                <span
                  className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold transition-all duration-200 ${
                    isCurrent
                      ? "bg-[var(--color-primary)] text-white shadow-[var(--shadow-glow-sm)]"
                      : isCompleted
                        ? "bg-[var(--color-success)] text-white"
                        : "bg-[var(--color-gray-200)] text-[var(--color-text-muted)]"
                  }`}
                  aria-hidden="true"
                >
                  {isCompleted ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="h-3.5 w-3.5">
                      <path d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    index + 1
                  )}
                </span>
                <span className="text-[0.65rem] font-medium leading-tight">{s.title}</span>
                {(s.optional || hasStepErrors) && (
                  <div className="flex items-center gap-1">
                    {s.optional && (
                      <span className="text-[0.55rem] text-[var(--color-text-light)]">Optional</span>
                    )}
                    {hasStepErrors && (
                      <span className="rounded-full bg-[var(--color-warning-light)] px-2 py-0.5 text-[0.55rem] font-semibold text-[var(--color-warning)]">
                        {errorCount} issue{errorCount === 1 ? "" : "s"}
                      </span>
                    )}
                  </div>
                )}
              </button>
            );
          })}
        </div>
        {/* Linear progress track */}
        <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-[var(--color-gray-200)]">
          <div
            className="h-full rounded-full bg-gradient-golden transition-all duration-500 ease-out"
            style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }}
          />
        </div>
      </nav>

      {/* Step content */}
      <main className="px-6 py-8 md:px-8" aria-live="polite">
        {isLoading && loadingContent ? (
          <div role="status" aria-label="Loading">
            {loadingContent}
          </div>
        ) : (
          <section aria-labelledby={`wizard-step-heading-${step.id}`}>
            <div className="mb-7">
              <h2
                id={`wizard-step-heading-${step.id}`}
                className="text-xl font-semibold text-[var(--color-text)] md:text-2xl"
              >
                {step.title}
              </h2>
              {step.subtitle && (
                <p className="mt-1.5 text-sm text-[var(--color-text-muted)]">{step.subtitle}</p>
              )}
            </div>
            {currentStepErrors.length > 0 && (
              <div
                className="mb-6 rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-light)] p-4"
                role="alert"
                aria-label="Step validation errors"
              >
                <p className="mb-2 text-sm font-semibold text-[var(--color-warning)]">
                  Fix these inputs on this step before running the simulation.
                </p>
                <ul className="list-inside list-disc space-y-1 text-sm text-[var(--color-text)]">
                  {currentStepErrors.map((err, index) => (
                    <li key={`${err.field}-${index}`}>{err.message}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="space-y-5">{step.content}</div>
          </section>
        )}

        {/* Validation error summary on last step */}
        {isLastStep && hasErrors && (
          <div
            className="mt-6 rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-light)] p-4"
            role="alert"
            aria-label="Validation errors"
          >
            <p className="mb-2 text-sm font-semibold text-[var(--color-danger)]">
              Please fix the following errors:
            </p>
            <ul className="list-inside list-disc space-y-1 text-sm text-[var(--color-danger)]">
              {validationErrors.map((err, i) => (
                <li key={`${err.field}-${i}`}>{err.message}</li>
              ))}
            </ul>
          </div>
        )}
      </main>

      {/* Navigation */}
      <div className="flex items-center justify-between border-t border-[var(--color-border-light)] bg-[var(--color-gray-50)] px-6 py-4 md:px-8" role="navigation" aria-label="Wizard navigation">
        <button
          className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-5 py-2.5 text-sm font-medium text-[var(--color-text-muted)] transition-all duration-200 hover:bg-[var(--color-gray-50)] hover:text-[var(--color-text)] disabled:cursor-not-allowed disabled:opacity-40"
          onClick={handleBack}
          disabled={isFirstStep}
          aria-label="Go to previous step"
        >
          Back
        </button>

        <div className="text-xs font-medium tabular-nums text-[var(--color-text-light)]" aria-live="polite">
          {currentStep + 1} / {steps.length}
        </div>

        <button
          className="rounded-[var(--radius-md)] bg-gradient-golden px-6 py-2.5 text-sm font-semibold text-white shadow-[var(--shadow-sm)] transition-all duration-200 hover:shadow-[var(--shadow-md)] hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          onClick={handleNext}
          disabled={isLoading}
          aria-label={getPrimaryButtonAriaLabel()}
        >
          {getPrimaryButtonLabel()}
        </button>
      </div>
    </div>
  );
}

function matchesFieldPattern(field: string, pattern: string): boolean {
  return (
    field === pattern ||
    field.startsWith(`${pattern}.`) ||
    field.startsWith(`${pattern}[`)
  );
}
