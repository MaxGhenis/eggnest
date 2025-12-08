import { useState, type ReactNode } from "react";
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
}

export function Wizard({
  steps,
  onComplete,
  isLoading = false,
  completeButtonText = "Run Simulation",
  loadingButtonText = "Running...",
  loadingContent,
}: WizardProps) {
  const [currentStep, setCurrentStep] = useState(0);

  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === steps.length - 1;
  const step = steps[currentStep];

  const handleNext = () => {
    if (isLastStep) {
      onComplete();
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
    <div className="wizard">
      {/* Progress indicator */}
      <div className="wizard-progress">
        {steps.map((s, index) => (
          <button
            key={s.id}
            className={`wizard-step-indicator ${
              index === currentStep
                ? "active"
                : index < currentStep
                  ? "completed"
                  : ""
            } ${index <= currentStep + 1 ? "clickable" : ""}`}
            onClick={() => handleStepClick(index)}
            disabled={index > currentStep + 1}
          >
            <span className="step-number">
              {index < currentStep ? (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <path d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                index + 1
              )}
            </span>
            <span className="step-title">{s.title}</span>
            {s.optional && <span className="step-optional">Optional</span>}
          </button>
        ))}
      </div>

      {/* Step content */}
      <div className="wizard-content">
        {isLoading && loadingContent ? (
          <div className="wizard-loading">
            {loadingContent}
          </div>
        ) : (
          <>
            <div className="wizard-header">
              <h2>{step.title}</h2>
              {step.subtitle && <p>{step.subtitle}</p>}
            </div>
            <div className="wizard-body">{step.content}</div>
          </>
        )}
      </div>

      {/* Navigation */}
      <div className="wizard-nav">
        <button
          className="wizard-btn wizard-btn-secondary"
          onClick={handleBack}
          disabled={isFirstStep}
        >
          Back
        </button>

        <div className="wizard-nav-info">
          Step {currentStep + 1} of {steps.length}
        </div>

        <button
          className="wizard-btn wizard-btn-primary"
          onClick={handleNext}
          disabled={isLoading}
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
