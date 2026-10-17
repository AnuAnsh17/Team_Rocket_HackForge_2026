/**
 * Design tokens.
 *
 * The values are declared once in app/globals.css with Tailwind v4's `@theme`, which is
 * what makes them available as utility classes. This module exposes the same names to
 * TypeScript so a component can reason about a token without duplicating a hex value.
 *
 * Keep these two in sync. The smoke test in tests/tokens.test.ts checks that every token
 * listed here also appears in the stylesheet, so a token cannot be added in one place and
 * forgotten in the other.
 */

export const COLOR_TOKENS = {
  /** Neutral surfaces. Finance reviewers read dense tables for long stretches. */
  surface: "--color-surface",
  surfaceMuted: "--color-surface-muted",
  surfaceRaised: "--color-surface-raised",
  border: "--color-border",
  borderStrong: "--color-border-strong",
  text: "--color-text",
  textMuted: "--color-text-muted",
  textInverse: "--color-text-inverse",

  /** Brand accent. Used sparingly: it indicates an action, not a status. */
  accent: "--color-accent",
  accentHover: "--color-accent-hover",

  /**
   * Status colours.
   *
   * These map to workflow states, NOT to judgements about a person. In particular there
   * is no "fraud" colour: the product does not assert fraud, so it must not have a visual
   * language for it.
   */
  statusDraft: "--color-status-draft",
  statusSubmitted: "--color-status-submitted",
  statusNeedsInfo: "--color-status-needs-info",
  statusInReview: "--color-status-in-review",
  statusApproved: "--color-status-approved",
  statusRejected: "--color-status-rejected",
  statusWithdrawn: "--color-status-withdrawn",

  /** Finding severity. Impact and routing only - never guilt. */
  severityInfo: "--color-severity-info",
  severityWarning: "--color-severity-warning",
  severityBlocking: "--color-severity-blocking",

  /** Tri-state rule result. UNKNOWN is a first-class outcome and gets a real colour. */
  resultPass: "--color-result-pass",
  resultFail: "--color-result-fail",
  resultUnknown: "--color-result-unknown",
} as const;

export const SPACING_TOKENS = {
  xs: "--spacing-xs",
  sm: "--spacing-sm",
  md: "--spacing-md",
  lg: "--spacing-lg",
  xl: "--spacing-xl",
} as const;

export type ColorToken = keyof typeof COLOR_TOKENS;
