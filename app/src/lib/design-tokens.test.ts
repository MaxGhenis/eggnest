/**
 * Design-token contrast matrix.
 *
 * Locks the WCAG AA contrast guarantees for the EggNest palette so that
 * accidental palette changes (or downgraded `*Text` variants) fail CI
 * before they reach users.
 *
 * Contracts:
 *  - Body / paragraph text on the page bg must meet WCAG AA (>= 4.5:1).
 *  - Status/text variants on their matching tinted fill must meet AA too,
 *    so that warning/success/danger callouts read cleanly inside their
 *    `*-light` cards.
 *  - Form-control borders must meet WCAG SC 1.4.11 (>= 3.0:1) on the page bg.
 *  - White text on small filled badges must meet AA (>= 4.5:1) — we use the
 *    darker `*Text` shade as the fill in those cases.
 */

import { describe, it, expect } from "vitest";
import { colors } from "./design-tokens";

// Linear-luminance per WCAG 2.1 relative-luminance formula.
function relLum(hex: string): number {
  const m = hex.replace("#", "").match(/.{2}/g);
  if (!m) throw new Error(`bad hex: ${hex}`);
  const [r, g, b] = m.map((c) => {
    const v = parseInt(c, 16) / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a: string, b: string): number {
  const la = relLum(a);
  const lb = relLum(b);
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

const AA_TEXT = 4.5;
const AA_LARGE = 3.0;
const NON_TEXT_UI = 3.0; // SC 1.4.11

describe("design-tokens contrast matrix", () => {
  describe("body text on page bg (AA, 4.5:1)", () => {
    it.each([
      ["text", colors.text],
      ["textMuted", colors.textMuted],
      ["primary", colors.primary],
      ["primaryDark", colors.primaryDark],
      ["goldText", colors.goldText],
      ["successText", colors.successText],
      ["warningText", colors.warningText],
      ["dangerText", colors.dangerText],
    ])("%s on bg meets AA", (_name, fg) => {
      expect(ratio(fg, colors.bg)).toBeGreaterThanOrEqual(AA_TEXT);
    });
  });

  describe("status text on tinted fill (AA, 4.5:1)", () => {
    it("successText on successLight", () => {
      expect(ratio(colors.successText, colors.successLight)).toBeGreaterThanOrEqual(AA_TEXT);
    });
    it("warningText on warningLight", () => {
      expect(ratio(colors.warningText, colors.warningLight)).toBeGreaterThanOrEqual(AA_TEXT);
    });
    it("dangerText on dangerLight", () => {
      expect(ratio(colors.dangerText, colors.dangerLight)).toBeGreaterThanOrEqual(AA_TEXT);
    });
    it("goldText on goldPale", () => {
      expect(ratio(colors.goldText, colors.goldPale)).toBeGreaterThanOrEqual(AA_TEXT);
    });
  });

  describe("white text on filled badges (AA, 4.5:1)", () => {
    // We use the darker *Text shade as the badge fill so that small white
    // text/icon labels meet AA. This guards against accidentally swapping
    // back to the brand fill (e.g. `bg-success`) which fails ~2.85:1.
    it("white on successText", () => {
      expect(ratio("#ffffff", colors.successText)).toBeGreaterThanOrEqual(AA_TEXT);
    });
    it("white on warningText", () => {
      expect(ratio("#ffffff", colors.warningText)).toBeGreaterThanOrEqual(AA_TEXT);
    });
    it("white on dangerText", () => {
      expect(ratio("#ffffff", colors.dangerText)).toBeGreaterThanOrEqual(AA_TEXT);
    });
    it("white on primary (button)", () => {
      expect(ratio("#ffffff", colors.primary)).toBeGreaterThanOrEqual(AA_TEXT);
    });
  });

  describe("form-control borders on bg (SC 1.4.11, 3:1)", () => {
    it("borderStrong meets 3:1 on bg", () => {
      expect(ratio(colors.borderStrong, colors.bg)).toBeGreaterThanOrEqual(NON_TEXT_UI);
    });
    // Sanity: the legacy `border` is decorative-only and should NOT pass —
    // if it ever does, we can promote it and retire `borderStrong`.
    it("legacy border is decorative (below 3:1)", () => {
      expect(ratio(colors.border, colors.bg)).toBeLessThan(NON_TEXT_UI);
    });
  });

  describe("focus indicator (SC 2.4.7, AA, 3:1)", () => {
    it("focusRing meets 3:1 on bg", () => {
      expect(ratio(colors.focusRing, colors.bg)).toBeGreaterThanOrEqual(NON_TEXT_UI);
    });
    it("focusRing also meets AA (4.5:1) for thin outlines", () => {
      expect(ratio(colors.focusRing, colors.bg)).toBeGreaterThanOrEqual(AA_TEXT);
    });
  });

  describe("status fills retain visual identity (large-text 3:1)", () => {
    // The brand FILL values intentionally fail body-text AA; they're used
    // for badges, status dots, and tinted bg pairs. They must still meet
    // 3:1 vs. the canvas so they read as distinct colored regions.
    //
    // Exception: `warning` (#ca8a04, ~2.85:1 on bg) — by design preserved
    // as the brand alert color. Wherever it appears as a meaningful UI
    // boundary or as small text, the consumer should switch to
    // `warningText` (which is locked above to AA on bg AND warning-light).
    it.each([
      ["gold", colors.gold],
      ["success", colors.success],
      ["danger", colors.danger],
    ])("%s on bg meets 3:1 (visible as fill)", (_name, fill) => {
      expect(ratio(fill, colors.bg)).toBeGreaterThanOrEqual(AA_LARGE);
    });
  });
});
