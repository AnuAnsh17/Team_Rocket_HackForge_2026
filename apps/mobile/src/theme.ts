/**
 * Design tokens for the employee app.
 *
 * The palette matches the employee web portal so that a status means the same thing on a
 * phone and in a browser. Values live here rather than in components because an employee
 * app gets read on a phone, in a corridor, in poor light - the contrast choices matter and
 * should be made once.
 *
 * There is deliberately no colour for fraud or risk. The product does not accuse anyone,
 * so it has no visual language for it.
 */

export const colors = {
  surface: "#0B1020",
  surfaceMuted: "#161C2F",
  surfaceRaised: "#111726",
  border: "#26304A",
  borderStrong: "#38446A",
  text: "#E8ECF8",
  textMuted: "#97A2C0",
  accent: "#5B8CFF",

  statusDraft: "#6B7691",
  statusSubmitted: "#4A8FE7",
  statusNeedsInfo: "#E0A33A",
  statusInReview: "#8B7CF0",
  statusApproved: "#3FA87A",
  statusRejected: "#D4665F",
  statusWithdrawn: "#6B7691",

  severityInfo: "#4A8FE7",
  severityWarning: "#E0A33A",
  severityBlocking: "#D4665F",

  resultPass: "#3FA87A",
  resultFail: "#D4665F",
  resultUnknown: "#8B7CF0",
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const typography = {
  title: { fontSize: 22, fontWeight: "600" as const },
  heading: { fontSize: 17, fontWeight: "600" as const },
  body: { fontSize: 15, fontWeight: "400" as const },
  caption: { fontSize: 13, fontWeight: "400" as const },
} as const;

export const radius = { sm: 6, md: 12, lg: 16 } as const;

/** Minimum touch target. This app gets used one-handed, outdoors, holding a receipt. */
export const TOUCH_TARGET = 48;

/**
 * Workflow status wording.
 *
 * "Not reimbursed" rather than "Rejected": a rejected claim means the expense was not
 * reimbursed, not that the employee did anything wrong.
 */
export const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  needs_info: "Needs information",
  in_review: "Under review",
  approved: "Approved",
  rejected: "Not reimbursed",
  withdrawn: "Withdrawn",
};

export function statusColor(status: string): string {
  switch (status) {
    case "draft":
      return colors.statusDraft;
    case "submitted":
      return colors.statusSubmitted;
    case "needs_info":
      return colors.statusNeedsInfo;
    case "in_review":
      return colors.statusInReview;
    case "approved":
      return colors.statusApproved;
    case "rejected":
      return colors.statusRejected;
    case "withdrawn":
      return colors.statusWithdrawn;
    default:
      return colors.surfaceMuted;
  }
}

/**
 * Tri-state rule result.
 *
 * UNKNOWN is not an error state. It is the correct answer when evidence or policy context
 * is missing, and it is rendered with its own colour so it can never be mistaken for a
 * pass.
 */
export const RESULT_LABELS: Record<string, string> = {
  PASS: "Meets the policy",
  FAIL: "Does not meet the policy",
  UNKNOWN: "We could not confirm this yet",
};

export function resultColor(result: string): string {
  switch (result) {
    case "PASS":
      return colors.resultPass;
    case "FAIL":
      return colors.resultFail;
    case "UNKNOWN":
      return colors.resultUnknown;
    default:
      return colors.surfaceMuted;
  }
}
