import { defineProperties, createSprinkles } from '@vanilla-extract/sprinkles';
import { vars } from './theme.css.ts';

const responsiveConditions = {
  conditions: {
    mobile: {},
    tablet: { '@media': 'screen and (min-width: 768px)' },
    desktop: { '@media': 'screen and (min-width: 1024px)' },
  },
  defaultCondition: 'mobile',
} as const;

const layoutProperties = defineProperties({
  ...responsiveConditions,
  properties: {
    display: ['none', 'flex', 'block', 'inline', 'inline-flex', 'grid', 'inline-block'],
    flexDirection: ['row', 'column', 'row-reverse', 'column-reverse'],
    alignItems: ['stretch', 'flex-start', 'center', 'flex-end', 'baseline'],
    justifyContent: [
      'stretch',
      'flex-start',
      'center',
      'flex-end',
      'space-between',
      'space-around',
      'space-evenly',
    ],
    flexWrap: ['nowrap', 'wrap', 'wrap-reverse'],
    gap: vars.space,
    padding: vars.space,
    paddingTop: vars.space,
    paddingBottom: vars.space,
    paddingLeft: vars.space,
    paddingRight: vars.space,
    margin: vars.space,
    marginTop: vars.space,
    marginBottom: vars.space,
    marginLeft: vars.space,
    marginRight: vars.space,
    width: ['auto', '100%', '50%', 'fit-content', 'max-content', 'min-content'],
    maxWidth: ['100%', '640px', '768px', '1024px', '1280px'],
    textAlign: ['left', 'center', 'right'],
    position: ['static', 'relative', 'absolute', 'fixed', 'sticky'],
    overflow: ['visible', 'hidden', 'scroll', 'auto'],
  },
  shorthands: {
    px: ['paddingLeft', 'paddingRight'],
    py: ['paddingTop', 'paddingBottom'],
    mx: ['marginLeft', 'marginRight'],
    my: ['marginTop', 'marginBottom'],
    placeItems: ['alignItems', 'justifyContent'],
  },
});

const typographyProperties = defineProperties({
  ...responsiveConditions,
  properties: {
    fontSize: vars.fontSize,
    fontWeight: vars.fontWeight,
    lineHeight: vars.lineHeight,
    fontFamily: vars.font,
  },
});

const colorProperties = defineProperties({
  properties: {
    color: vars.color,
    backgroundColor: vars.color,
    borderColor: vars.color,
  },
});

const borderProperties = defineProperties({
  properties: {
    borderRadius: vars.radius,
    borderWidth: ['0', '1px', '2px'],
    borderStyle: ['none', 'solid', 'dashed'],
  },
});

export const sprinkles = createSprinkles(
  layoutProperties,
  typographyProperties,
  colorProperties,
  borderProperties,
);

export type Sprinkles = Parameters<typeof sprinkles>[0];
