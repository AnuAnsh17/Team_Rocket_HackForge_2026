/**
 * Shared mobile components.
 *
 * The wording rules here are product requirements. An employee reading a status while
 * standing in a corridor is in a slightly anxious position, and copy implying suspicion
 * changes how they respond to a request for information. The product asserts no wrongdoing,
 * so it has no vocabulary for it either.
 */

import type { ReactNode } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing, TOUCH_TARGET, typography } from "@/theme";

export function Screen({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.screenContent}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.description}>{description}</Text>
      {children}
    </ScrollView>
  );
}

export function Card({
  title,
  description,
  children,
}: {
  title?: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <View style={styles.card}>
      {title ? <Text style={styles.cardTitle}>{title}</Text> : null}
      {description ? <Text style={styles.cardDescription}>{description}</Text> : null}
      {children}
    </View>
  );
}

/**
 * The visible marker for an unfinished feature.
 *
 * Names what is missing rather than saying "coming soon": the person needs to know whether
 * nothing is built or whether they simply have no data - those look identical otherwise.
 */
export function PlaceholderNotice({
  title,
  whatIsMissing,
  blockedOn,
}: {
  title: string;
  whatIsMissing: string;
  blockedOn?: string;
}) {
  return (
    <View style={styles.placeholder} accessibilityRole="summary">
      <Text style={styles.placeholderEyebrow}>Not available yet</Text>
      <Text style={styles.placeholderTitle}>{title}</Text>
      <Text style={styles.placeholderBody}>{whatIsMissing}</Text>
      {blockedOn ? (
        <Text style={styles.placeholderBlocked}>Waiting on: {blockedOn}</Text>
      ) : null}
    </View>
  );
}

export function StatusPill({ status }: { status: string }) {
  const label = STATUS_LABELS_LOCAL[status] ?? "Unknown status";
  const color = statusColorLocal(status);
  return (
    <View style={[styles.pill, { borderColor: color }]}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={styles.pillText}>{label}</Text>
    </View>
  );
}

/**
 * The four states an employee must be able to tell apart.
 *
 * "Possible duplicate" is worded as a possibility with a person checking it, because that
 * is what it is: a candidate, never a confirmed duplicate and never an accusation.
 */
export function EmployeeStateBanner({
  state,
}: {
  state: "needs_info" | "policy_issue" | "possible_duplicate" | "in_review";
}) {
  const copy = STATE_COPY_LOCAL[state];
  return (
    <View style={[styles.banner, { borderLeftColor: copy.color }]}>
      <Text style={styles.bannerTitle}>{copy.label}</Text>
      <Text style={styles.bannerBody}>{copy.explanation}</Text>
    </View>
  );
}

const STATE_COPY_LOCAL = {
  needs_info: {
    label: "We need something from you",
    explanation:
      "Finance has asked for information that is missing from this claim. Add it and we will re-check the claim.",
    color: colors.statusNeedsInfo,
  },
  policy_issue: {
    label: "This claim does not meet the policy",
    explanation:
      "A policy rule that applies to this claim is not satisfied. You can see the clause and the calculation, and comment or correct the claim.",
    color: colors.statusRejected,
  },
  possible_duplicate: {
    label: "This might have been submitted twice",
    explanation:
      "We found another claim that looks similar. A person will check it; nothing is assumed, and you do not need to do anything yet.",
    color: colors.severityWarning,
  },
  in_review: {
    label: "A person is reviewing this",
    explanation: "The claim is with finance. You will see a status change when there is a decision.",
    color: colors.statusInReview,
  },
} as const;

const STATUS_LABELS_LOCAL: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  needs_info: "Needs information",
  in_review: "Under review",
  approved: "Approved",
  rejected: "Not reimbursed",
  withdrawn: "Withdrawn",
};

function statusColorLocal(status: string): string {
  switch (status) {
    case "needs_info":
      return colors.statusNeedsInfo;
    case "in_review":
      return colors.statusInReview;
    case "approved":
      return colors.statusApproved;
    case "rejected":
      return colors.statusRejected;
    case "submitted":
      return colors.statusSubmitted;
    default:
      return colors.statusDraft;
  }
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.surface },
  screenContent: { padding: spacing.md, gap: spacing.md, paddingBottom: spacing.xl },
  title: { ...typography.title, color: colors.text },
  description: { ...typography.body, color: colors.textMuted },
  card: {
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    padding: spacing.md,
    gap: spacing.sm,
  },
  cardTitle: { ...typography.heading, color: colors.text },
  cardDescription: { ...typography.caption, color: colors.textMuted },
  placeholder: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.severityWarning,
    borderStyle: "dashed",
    padding: spacing.md,
    gap: spacing.xs,
  },
  placeholderEyebrow: {
    ...typography.caption,
    color: colors.severityWarning,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  placeholderTitle: { ...typography.heading, color: colors.text },
  placeholderBody: { ...typography.caption, color: colors.textMuted },
  placeholderBlocked: { ...typography.caption, color: colors.textMuted },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    alignSelf: "flex-start",
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    minHeight: spacing.lg,
  },
  dot: { width: 8, height: 8, borderRadius: 4 },
  pillText: { ...typography.caption, color: colors.text },
  banner: {
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.md,
    borderLeftWidth: 4,
    padding: spacing.md,
    gap: spacing.xs,
  },
  bannerTitle: { ...typography.heading, color: colors.text },
  bannerBody: { ...typography.caption, color: colors.textMuted },
});

/** Re-exported so a screen never hard-codes a touch target height. */
export const touchTarget = TOUCH_TARGET;
