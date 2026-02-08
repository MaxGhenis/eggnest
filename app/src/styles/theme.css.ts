import {
  createThemeContract,
  createTheme,
} from '@vanilla-extract/css';

/**
 * Theme contract: defines the shape of all theme variables.
 * Actual values are provided by light/dark theme definitions below.
 */
export const vars = createThemeContract({
  color: {
    // Primary - Golden Hour Amber
    primary: null,
    primaryLight: null,
    primaryDark: null,
    primary50: null,
    primary100: null,
    primary200: null,

    // Secondary - Warm Gold
    gold: null,
    goldLight: null,
    goldPale: null,

    // Semantic
    success: null,
    successLight: null,
    warning: null,
    warningLight: null,
    error: null,
    errorLight: null,

    // Neutrals - Warm tinted
    gray50: null,
    gray100: null,
    gray200: null,
    gray300: null,
    gray400: null,
    gray500: null,
    gray600: null,
    gray700: null,
    gray800: null,
    gray900: null,

    // Semantic surface aliases
    text: null,
    textMuted: null,
    textInverse: null,
    bg: null,
    bgAlt: null,
    bgCard: null,
    border: null,
  },

  space: {
    none: null,
    xs: null,
    sm: null,
    md: null,
    lg: null,
    xl: null,
    '2xl': null,
    '3xl': null,
    '4xl': null,
  },

  font: {
    body: null,
    heading: null,
    mono: null,
  },

  fontSize: {
    xs: null,
    sm: null,
    md: null,
    lg: null,
    xl: null,
    '2xl': null,
    '3xl': null,
    '4xl': null,
  },

  fontWeight: {
    normal: null,
    medium: null,
    semibold: null,
    bold: null,
  },

  lineHeight: {
    tight: null,
    normal: null,
    relaxed: null,
  },

  radius: {
    none: null,
    sm: null,
    md: null,
    lg: null,
    xl: null,
    full: null,
  },

  shadow: {
    sm: null,
    md: null,
    lg: null,
    xl: null,
  },
});

// Shared non-color tokens (identical in light and dark themes)
const sharedTokens = {
  space: {
    none: '0',
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '48px',
    '3xl': '64px',
    '4xl': '96px',
  },

  font: {
    body: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    heading: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    mono: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
  },

  fontSize: {
    xs: '0.75rem',
    sm: '0.875rem',
    md: '1rem',
    lg: '1.125rem',
    xl: '1.25rem',
    '2xl': '1.5rem',
    '3xl': '1.875rem',
    '4xl': '2.25rem',
  },

  fontWeight: {
    normal: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
  },

  lineHeight: {
    tight: '1.25',
    normal: '1.5',
    relaxed: '1.75',
  },

  radius: {
    none: '0',
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',
  },
} as const;

/**
 * Light theme - warm amber palette matching the existing design-tokens.ts
 */
export const lightThemeClass = createTheme(vars, {
  color: {
    primary: '#c2410c',
    primaryLight: '#ea580c',
    primaryDark: '#9a3412',
    primary50: '#fff7ed',
    primary100: '#ffedd5',
    primary200: '#fed7aa',

    gold: '#d97706',
    goldLight: '#fbbf24',
    goldPale: '#fef3c7',

    success: '#16a34a',
    successLight: '#dcfce7',
    warning: '#ca8a04',
    warningLight: '#fef9c3',
    error: '#dc2626',
    errorLight: '#fee2e2',

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

    text: '#292524',
    textMuted: '#78716c',
    textInverse: '#ffffff',
    bg: '#fffbf5',
    bgAlt: '#fef7ed',
    bgCard: '#ffffff',
    border: '#e7e5e4',
  },

  ...sharedTokens,

  shadow: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
  },
});

/**
 * Dark theme - inverted palette with dark surfaces and lighter text
 */
export const darkThemeClass = createTheme(vars, {
  color: {
    primary: '#ea580c',
    primaryLight: '#f97316',
    primaryDark: '#c2410c',
    primary50: '#431407',
    primary100: '#7c2d12',
    primary200: '#9a3412',

    gold: '#fbbf24',
    goldLight: '#fde68a',
    goldPale: '#451a03',

    success: '#4ade80',
    successLight: '#14532d',
    warning: '#facc15',
    warningLight: '#422006',
    error: '#f87171',
    errorLight: '#450a0a',

    gray50: '#1c1917',
    gray100: '#292524',
    gray200: '#44403c',
    gray300: '#57534e',
    gray400: '#78716c',
    gray500: '#a8a29e',
    gray600: '#d6d3d1',
    gray700: '#e7e5e4',
    gray800: '#f5f5f4',
    gray900: '#fafaf9',

    text: '#f5f5f4',
    textMuted: '#a8a29e',
    textInverse: '#1c1917',
    bg: '#1c1917',
    bgAlt: '#292524',
    bgCard: '#292524',
    border: '#44403c',
  },

  ...sharedTokens,

  shadow: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.3)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -2px rgba(0, 0, 0, 0.3)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -4px rgba(0, 0, 0, 0.3)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.3)',
  },
});

/** @deprecated Use `lightThemeClass` instead. Alias for backward compatibility. */
export const themeClass = lightThemeClass;
