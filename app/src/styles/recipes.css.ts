import { recipe } from '@vanilla-extract/recipes';
import { vars } from './theme.css.ts';

/* ------------------------------------------------------------------ */
/*  Button                                                            */
/* ------------------------------------------------------------------ */

export const button = recipe({
  base: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: vars.font.body,
    fontWeight: vars.fontWeight.semibold,
    lineHeight: vars.lineHeight.tight,
    borderRadius: vars.radius.md,
    border: 'none',
    cursor: 'pointer',
    transition: 'background-color 150ms ease, color 150ms ease, box-shadow 150ms ease',
    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  variants: {
    variant: {
      primary: {
        backgroundColor: vars.color.primary,
        color: vars.color.textInverse,
        ':hover': {
          backgroundColor: vars.color.primaryDark,
        },
        ':focus-visible': {
          outline: `2px solid ${vars.color.primaryLight}`,
          outlineOffset: '2px',
        },
      },
      secondary: {
        backgroundColor: 'transparent',
        color: vars.color.primary,
        border: `1px solid ${vars.color.primary}`,
        ':hover': {
          backgroundColor: vars.color.primary50,
        },
        ':focus-visible': {
          outline: `2px solid ${vars.color.primaryLight}`,
          outlineOffset: '2px',
        },
      },
      ghost: {
        backgroundColor: 'transparent',
        color: vars.color.text,
        ':hover': {
          backgroundColor: vars.color.gray100,
        },
        ':focus-visible': {
          outline: `2px solid ${vars.color.gray400}`,
          outlineOffset: '2px',
        },
      },
    },

    size: {
      sm: {
        fontSize: vars.fontSize.sm,
        padding: `${vars.space.xs} ${vars.space.sm}`,
        gap: vars.space.xs,
      },
      md: {
        fontSize: vars.fontSize.md,
        padding: `${vars.space.sm} ${vars.space.md}`,
        gap: vars.space.sm,
      },
      lg: {
        fontSize: vars.fontSize.lg,
        padding: `${vars.space.sm} ${vars.space.lg}`,
        gap: vars.space.sm,
      },
    },
  },

  defaultVariants: {
    variant: 'primary',
    size: 'md',
  },
});

/* ------------------------------------------------------------------ */
/*  Card                                                              */
/* ------------------------------------------------------------------ */

export const card = recipe({
  base: {
    borderRadius: vars.radius.lg,
    padding: vars.space.lg,
    transition: 'box-shadow 150ms ease, border-color 150ms ease',
  },

  variants: {
    variant: {
      elevated: {
        backgroundColor: vars.color.bgCard,
        boxShadow: vars.shadow.md,
        ':hover': {
          boxShadow: vars.shadow.lg,
        },
      },
      outlined: {
        backgroundColor: vars.color.bgCard,
        border: `1px solid ${vars.color.border}`,
      },
      flat: {
        backgroundColor: vars.color.bgAlt,
      },
    },
  },

  defaultVariants: {
    variant: 'elevated',
  },
});

/* ------------------------------------------------------------------ */
/*  Input                                                             */
/* ------------------------------------------------------------------ */

export const input = recipe({
  base: {
    display: 'block',
    width: '100%',
    fontFamily: vars.font.body,
    backgroundColor: vars.color.bgCard,
    color: vars.color.text,
    borderRadius: vars.radius.md,
    border: `1px solid ${vars.color.border}`,
    transition: 'border-color 150ms ease, box-shadow 150ms ease',
    outline: 'none',
    '::placeholder': {
      color: vars.color.textMuted,
    },
    ':focus': {
      borderColor: vars.color.primaryLight,
      boxShadow: `0 0 0 3px ${vars.color.primary100}`,
    },
  },

  variants: {
    variant: {
      default: {},
      error: {
        borderColor: vars.color.error,
        ':focus': {
          borderColor: vars.color.error,
          boxShadow: `0 0 0 3px ${vars.color.errorLight}`,
        },
      },
    },

    size: {
      sm: {
        fontSize: vars.fontSize.sm,
        padding: `${vars.space.xs} ${vars.space.sm}`,
      },
      md: {
        fontSize: vars.fontSize.md,
        padding: `${vars.space.sm} ${vars.space.md}`,
      },
    },
  },

  defaultVariants: {
    variant: 'default',
    size: 'md',
  },
});

/* ------------------------------------------------------------------ */
/*  Heading                                                           */
/* ------------------------------------------------------------------ */

export const heading = recipe({
  base: {
    fontFamily: vars.font.heading,
    fontWeight: vars.fontWeight.bold,
    lineHeight: vars.lineHeight.tight,
    color: vars.color.text,
    margin: 0,
  },

  variants: {
    level: {
      h1: { fontSize: vars.fontSize['4xl'] },
      h2: { fontSize: vars.fontSize['3xl'] },
      h3: { fontSize: vars.fontSize['2xl'] },
      h4: { fontSize: vars.fontSize.xl },
    },
  },

  defaultVariants: {
    level: 'h2',
  },
});

/* ------------------------------------------------------------------ */
/*  Text                                                              */
/* ------------------------------------------------------------------ */

export const text = recipe({
  base: {
    fontFamily: vars.font.body,
    margin: 0,
  },

  variants: {
    variant: {
      body: {
        fontSize: vars.fontSize.md,
        lineHeight: vars.lineHeight.normal,
        color: vars.color.text,
      },
      caption: {
        fontSize: vars.fontSize.sm,
        lineHeight: vars.lineHeight.normal,
        color: vars.color.textMuted,
      },
      label: {
        fontSize: vars.fontSize.sm,
        fontWeight: vars.fontWeight.medium,
        lineHeight: vars.lineHeight.tight,
        color: vars.color.text,
      },
    },
  },

  defaultVariants: {
    variant: 'body',
  },
});
