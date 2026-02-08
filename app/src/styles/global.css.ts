import { globalStyle } from '@vanilla-extract/css';
import { vars } from './theme.css.ts';

/* ------------------------------------------------------------------ */
/*  CSS reset / base styles                                           */
/* ------------------------------------------------------------------ */

globalStyle('*, *::before, *::after', {
  boxSizing: 'border-box',
  margin: 0,
  padding: 0,
});

globalStyle('html', {
  WebkitFontSmoothing: 'antialiased',
  MozOsxFontSmoothing: 'grayscale',
  textSizeAdjust: '100%',
  lineHeight: 1.5,
});

globalStyle('body', {
  fontFamily: vars.font.body,
  fontSize: vars.fontSize.md,
  lineHeight: vars.lineHeight.normal,
  color: vars.color.text,
  backgroundColor: vars.color.bg,
  minHeight: '100vh',
});

globalStyle('img, picture, video, canvas, svg', {
  display: 'block',
  maxWidth: '100%',
});

globalStyle('input, button, textarea, select', {
  font: 'inherit',
});

globalStyle('h1, h2, h3, h4, h5, h6', {
  overflowWrap: 'break-word',
  fontFamily: vars.font.heading,
  fontWeight: vars.fontWeight.bold,
  lineHeight: vars.lineHeight.tight,
});

globalStyle('p', {
  overflowWrap: 'break-word',
});

globalStyle('a', {
  color: vars.color.primary,
  textDecoration: 'none',
});

globalStyle('a:hover', {
  color: vars.color.primaryDark,
  textDecoration: 'underline',
});

globalStyle('code, pre', {
  fontFamily: vars.font.mono,
});

/* Focus-visible for keyboard navigation */
globalStyle(':focus-visible', {
  outline: `2px solid ${vars.color.primaryLight}`,
  outlineOffset: '2px',
});

/* Selection color */
globalStyle('::selection', {
  backgroundColor: vars.color.primary100,
  color: vars.color.primaryDark,
});
