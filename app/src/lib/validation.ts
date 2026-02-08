/**
 * Client-side form validation for EggNest.
 * Validates simulation parameters, holdings, and life event inputs
 * before sending to the API.
 */

import type { SimulationInput, Holding, HouseholdInput } from "./api";
import {
  US_STATES,
  MIN_AGE,
  MAX_AGE,
  SS_MIN_CLAIMING_AGE,
  SS_MAX_CLAIMING_AGE,
} from "./constants";

export interface ValidationError {
  field: string;
  message: string;
}

/**
 * Validate the full simulation input form.
 */
export function validateSimulationInput(
  params: SimulationInput
): ValidationError[] {
  const errors: ValidationError[] = [];

  // Current age: 18-100, integer only
  if (!Number.isInteger(params.current_age)) {
    errors.push({
      field: "current_age",
      message: "Age must be a whole integer",
    });
  } else if (params.current_age < MIN_AGE || params.current_age > MAX_AGE) {
    errors.push({
      field: "current_age",
      message: `Age must be between ${MIN_AGE} and ${MAX_AGE}`,
    });
  }

  // Retirement age: > current age, <= 100
  if (params.retirement_age <= params.current_age) {
    errors.push({
      field: "retirement_age",
      message: "Retirement age must be greater than current age",
    });
  } else if (params.retirement_age > MAX_AGE) {
    errors.push({
      field: "retirement_age",
      message: `Retirement age must be ${MAX_AGE} or less`,
    });
  }

  // Max age (plan horizon): must be > current age
  if (params.max_age <= params.current_age) {
    errors.push({
      field: "max_age",
      message: "Plan horizon age must be greater than current age",
    });
  } else if (params.max_age > 120) {
    errors.push({
      field: "max_age",
      message: "Plan horizon age must be 120 or less",
    });
  }

  // Annual spending: > 0
  if (params.annual_spending <= 0) {
    errors.push({
      field: "annual_spending",
      message: "Annual spending must be greater than 0",
    });
  }

  // Employment income: >= 0
  if (params.employment_income < 0) {
    errors.push({
      field: "employment_income",
      message: "Employment income must be 0 or greater",
    });
  }

  // Initial capital: >= 0 (if provided)
  if (
    params.initial_capital !== undefined &&
    params.initial_capital !== null &&
    params.initial_capital < 0
  ) {
    errors.push({
      field: "initial_capital",
      message: "Initial capital must be 0 or greater",
    });
  }

  // Stock allocation: 0-1 (stored as decimal fraction)
  if (params.stock_allocation < 0 || params.stock_allocation > 1) {
    errors.push({
      field: "stock_allocation",
      message: "Stock allocation must be between 0% and 100%",
    });
  }

  // Social security claiming age: 62-70
  if (
    params.social_security_start_age < SS_MIN_CLAIMING_AGE ||
    params.social_security_start_age > SS_MAX_CLAIMING_AGE
  ) {
    errors.push({
      field: "social_security_start_age",
      message: `SS claiming age must be between ${SS_MIN_CLAIMING_AGE} and ${SS_MAX_CLAIMING_AGE}`,
    });
  }

  // State: valid US state
  if (!US_STATES.includes(params.state as (typeof US_STATES)[number])) {
    errors.push({
      field: "state",
      message: "Please select a valid US state",
    });
  }

  // Spouse validation (only when spouse is enabled)
  if (params.has_spouse && params.spouse) {
    const spouse = params.spouse;

    if (spouse.age < MIN_AGE || spouse.age > MAX_AGE) {
      errors.push({
        field: "spouse.age",
        message: `Spouse age must be between ${MIN_AGE} and ${MAX_AGE}`,
      });
    }

    if (
      spouse.social_security_start_age < SS_MIN_CLAIMING_AGE ||
      spouse.social_security_start_age > SS_MAX_CLAIMING_AGE
    ) {
      errors.push({
        field: "spouse.social_security_start_age",
        message: `Spouse SS claiming age must be between ${SS_MIN_CLAIMING_AGE} and ${SS_MAX_CLAIMING_AGE}`,
      });
    }

    if (spouse.retirement_age <= spouse.age) {
      errors.push({
        field: "spouse.retirement_age",
        message: "Spouse retirement age must be greater than spouse age",
      });
    }

    if (spouse.employment_income < 0) {
      errors.push({
        field: "spouse.employment_income",
        message: "Spouse employment income must be 0 or greater",
      });
    }
  }

  return errors;
}

/**
 * Validate a single holding entry.
 */
export function validateHolding(
  holding: Holding,
  index: number
): ValidationError[] {
  const errors: ValidationError[] = [];

  if (holding.balance < 0) {
    errors.push({
      field: `holdings[${index}].balance`,
      message: "Balance must be 0 or greater",
    });
  }

  return errors;
}

/**
 * Validate all holdings in the portfolio.
 */
export function validateHoldings(holdings: Holding[]): ValidationError[] {
  const errors: ValidationError[] = [];

  for (let i = 0; i < holdings.length; i++) {
    errors.push(...validateHolding(holdings[i], i));
  }

  return errors;
}

/**
 * Validate household input for the life event calculator.
 */
export function validateLifeEventInput(
  household: HouseholdInput
): ValidationError[] {
  const errors: ValidationError[] = [];

  // State validation
  if (!US_STATES.includes(household.state as (typeof US_STATES)[number])) {
    errors.push({
      field: "state",
      message: "Please select a valid US state",
    });
  }

  // Validate each person
  for (let i = 0; i < household.people.length; i++) {
    const person = household.people[i];
    const isDependent = person.is_tax_unit_dependent === true;

    // Age validation: dependents can be any age (including 0), adults must be 18-100
    if (!isDependent) {
      if (person.age < MIN_AGE || person.age > MAX_AGE) {
        errors.push({
          field: `people[${i}].age`,
          message: `Age must be between ${MIN_AGE} and ${MAX_AGE}`,
        });
      }
    }

    // Employment income: >= 0
    if (
      person.employment_income !== undefined &&
      person.employment_income < 0
    ) {
      errors.push({
        field: `people[${i}].employment_income`,
        message: "Employment income must be 0 or greater",
      });
    }
  }

  return errors;
}

/**
 * Get the error message for a specific field, or undefined if no error.
 */
export function getFieldError(
  errors: ValidationError[],
  field: string
): string | undefined {
  return errors.find((e) => e.field === field)?.message;
}

/**
 * Check if a specific field has an error.
 */
export function hasFieldError(
  errors: ValidationError[],
  field: string
): boolean {
  return errors.some((e) => e.field === field);
}
