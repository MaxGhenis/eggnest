import { useState, type ReactNode } from "react";
import type { ValidationError } from "../lib/validation";
import "../styles/Wizard.css";

export interface WizardStep {
  id: string;
  title: string;
  subtitle?: string;
  optional?: boolean;
  content: ReactNode;
  isComplete?: () => boolean;
}

interface WizardProps {
  steps: WizardStep[];
  onComplete: () => void;
  isLoading?: boolean;
  completeButtonText?: string;
  loadingButtonText?: string;
  loadingContent?: ReactNode;
  /** Validation errors to display; disables complete button when non-empty */
  validationErrors?: ValidationError[];
}

export function Wizard({
  steps,
  onComplete,
  isLoading = false,
  completeButtonText = "Run Simulation",
  loadingButtonText = "Running...",
  loadingContent,
  validationErrors = [],
}: WizardProps) {
  const [currentStep, setCurrentStep] = useState(0);

  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === steps.length - 1;
  const step = steps[currentStep];
  const hasErrors = validationErrors.length > 0;

  const handleNext = () => {
    if (isLastStep) {
      if (!hasErrors) {
        onComplete();
      }
    } else {
      setCurrentStep((prev) => Math.min(prev + 1, steps.length - 1));
    }
  };

  const handleBack = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 0));
  };

  const handleStepClick = (index: number) => {
    // Allow clicking on any previous step or the next step
    if (index <= currentStep + 1) {
      setCurrentStep(index);
    }
  };

  return (
    <div className="wizard" role="form" aria-label="Simulation setup wizard">
      {/* Progress indicator */}
      <nav className="wizard-progress" aria-label="Wizard steps">
        {steps.map((s, index) => {
          const isCurrent = index === currentStep;
          const isCompleted = index < currentStep;
          return (
            <button
              key={s.id}
              className={`wizard-step-indicator ${
                isCurrent
                  ? "active"
                  : isCompleted
                    ? "completed"
                    : ""
              } ${index <= currentStep + 1 ? "clickable" : ""}`}
              onClick={() => handleStepClick(index)}
              disabled={index > currentStep + 1}
              aria-label={`Step ${index + 1}: ${s.title}${isCompleted ? " (completed)" : isCurrent ? " (current)" : ""}`}
              aria-current={isCurrent ? "step" : undefined}
            >
              <span className="step-number" aria-hidden="true">
                {isCompleted ? (
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    aria-hidden="true"
                  >
                    <path d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  index + 1
                )}
              </span>
              <span className="step-title">{s.title}</span>
              {s.optional && <span className="step-optional">Optional</span>}
            </button>
          );
        })}
      </nav>

      {/* Step content */}
      <main className="wizard-content" aria-live="polite">
        {isLoading && loadingContent ? (
          <div className="wizard-loading" role="status" aria-label="Loading">
            {loadingContent}
          </div>
        ) : (
          <section aria-labelledby={`wizard-step-heading-${step.id}`}>
            <div className="wizard-header">
              <h2 id={`wizard-step-heading-${step.id}`}>{step.title}</h2>
              {step.subtitle && <p>{step.subtitle}</p>}
            </div>
            <div className="wizard-body">{step.content}</div>
          </section>
        )}

        {/* Inline validation error summary on last step */}
        {isLastStep && hasErrors && (
          <div
            className="wizard-validation-errors"
            role="alert"
            aria-label="Validation errors"
          >
            <p className="wizard-validation-title">
              Please fix the following errors:
            </p>
            <ul>
              {validationErrors.map((err, i) => (
                <li key={`${err.field}-${i}`}>{err.message}</li>
              ))}
            </ul>
          </div>
        )}
      </main>

      {/* Navigation */}
      <div className="wizard-nav" role="navigation" aria-label="Wizard navigation">
        <button
          className="wizard-btn wizard-btn-secondary"
          onClick={handleBack}
          disabled={isFirstStep}
          aria-label="Go to previous step"
        >
          Back
        </button>

        <div className="wizard-nav-info" aria-live="polite">
          Step {currentStep + 1} of {steps.length}
        </div>

        <button
          className="wizard-btn wizard-btn-primary"
          onClick={handleNext}
          disabled={isLoading || (isLastStep && hasErrors)}
          aria-label={
            isLastStep
              ? isLoading
                ? loadingButtonText
                : hasErrors
                  ? "Fix validation errors to continue"
                  : completeButtonText
              : "Go to next step"
          }
        >
          {isLastStep
            ? isLoading
              ? loadingButtonText
              : completeButtonText
            : "Next"}
        </button>
      </div>
    </div>
  );
}
