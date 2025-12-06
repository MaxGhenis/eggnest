/* EggNest Design System - TypeScript tokens for use in JS/TSX */

export const colors = {
  // Primary - Warm Amber
  primary: '#d97706',
  primaryLight: '#f59e0b',
  primaryDark: '#b45309',
  primary50: '#fffbeb',
  primary100: '#fef3c7',
  primary200: '#fde68a',

  // Semantic
  success: '#10b981',
  successLight: '#d1fae5',
  warning: '#eab308',
  warningLight: '#fef9c3',
  danger: '#ef4444',
  dangerLight: '#fee2e2',

  // Neutrals
  gray50: '#f9fafb',
  gray100: '#f3f4f6',
  gray200: '#e5e7eb',
  gray300: '#d1d5db',
  gray400: '#9ca3af',
  gray500: '#6b7280',
  gray600: '#4b5563',
  gray700: '#374151',
  gray800: '#1f2937',
  gray900: '#111827',

  // Semantic aliases
  text: '#1f2937',
  textMuted: '#6b7280',
  bg: '#ffffff',
  bgAlt: '#f9fafb',
  border: '#e5e7eb',
} as const;

// Chart colors for Plotly, Recharts, etc.
export const chartColors = {
  primary: colors.primary,
  primaryLight: colors.primaryLight,
  primaryDark: colors.primaryDark,
  confidence: colors.primary100,  // for confidence bands
  grid: colors.gray200,
} as const;

export type ColorKey = keyof typeof colors;

// Logo/favicon color - use this when updating SVG files
// SVGs can't import variables, so update them manually when this changes
export const logoColor = colors.primary; // #d97706
