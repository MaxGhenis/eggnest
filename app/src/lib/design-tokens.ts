/**
 * EggNest design system tokens for use in JS/TSX (e.g. Plotly chart config).
 * CSS custom properties are defined in globals.css; these mirror the values
 * for contexts where CSS variables are not available.
 */

export const colors = {
  // Primary - Golden Hour Amber
  primary: '#c2410c',
  primaryLight: '#ea580c',
  primaryDark: '#9a3412',
  primary50: '#fff7ed',
  primary100: '#ffedd5',
  primary200: '#fed7aa',

  // Secondary - Warm Gold
  gold: '#d97706',
  goldLight: '#fbbf24',
  goldPale: '#fef3c7',

  // Semantic
  success: '#16a34a',
  successLight: '#dcfce7',
  warning: '#ca8a04',
  warningLight: '#fef9c3',
  danger: '#dc2626',
  dangerLight: '#fee2e2',

  // Neutrals - Warm tinted
  gray50: '#fafaf9',
  gray100: '#f5f5f4',
  gray200: '#e7e5e4',
  gray300: '#d6d3d1',
  gray400: '#a8a29e',
  gray500: '#78716c',
  gray600: '#57534e',
  gray700: '#44403c',
  gray800: '#292524',
  gray900: '#1c1917',

  // Semantic aliases
  text: '#292524',
  textMuted: '#78716c',
  bg: '#fffbf5',
  bgAlt: '#fef7ed',
  bgCard: '#ffffff',
  border: '#e7e5e4',
} as const;

// Chart colors for Plotly, Recharts, etc.
export const chartColors = {
  primary: colors.gold,
  primaryLight: colors.goldLight,
  primaryDark: colors.primary,
  confidence: colors.primary100,
  grid: colors.gray200,
  // Band colors with opacity
  bandOuter: 'rgba(217, 119, 6, 0.1)',
  bandInner: 'rgba(217, 119, 6, 0.15)',
  lineOuter: 'rgba(217, 119, 6, 0.2)',
  lineInner: 'rgba(217, 119, 6, 0.3)',
} as const;

export type ColorKey = keyof typeof colors;

// Logo/favicon color
export const logoColor = colors.gold; // #d97706
