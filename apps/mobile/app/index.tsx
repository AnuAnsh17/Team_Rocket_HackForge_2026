import { Link } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { Card, EmployeeStateBanner, PlaceholderNotice, Screen, touchTarget } from "@/components/ui";
import { colors, radius, spacing, typography } from "@/theme";

/**
 * Employee home.
 *
 * Shows no totals: every figure must come from the backend and the expense endpoints are
 * not implemented, so a plausible number would be invented and indistinguishable from a
 * real one on a phone screen.
 */
export default function HomeScreen() {
  return (
    <Screen
      title="My expenses"
      description="What you have submitted, what is waiting, and anything that needs you."
    >
      <PlaceholderNotice
        title="Nothing can be submitted yet"
        whatIsMissing={
          "Receipt capture, reading the receipt and submitting a claim are not implemented in " +
          "this build. There is nothing to show here yet."
        }
        blockedOn="The receipt upload and expense routes."
      />

      <View style={styles.actions}>
        <Link href="/capture" style={styles.primaryAction}>
          Add a receipt
        </Link>
        <Link href="/expenses/example" style={styles.secondaryAction}>
          View a claim
        </Link>
      </View>

      <Card title="How your claim will be described" description="Four states, four different meanings.">
        <EmployeeStateBanner state="needs_info" />
        <EmployeeStateBanner state="in_review" />
        <EmployeeStateBanner state="policy_issue" />
        <EmployeeStateBanner state="possible_duplicate" />
      </Card>

      <Text style={styles.footnote}>
        You only ever see your own claims and receipts. That is enforced by the server on
        every request, not by this screen.
      </Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  actions: { gap: spacing.sm },
  primaryAction: {
    minHeight: touchTarget,
    textAlignVertical: "center",
    textAlign: "center",
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.accent,
    color: "#0B1020",
    ...typography.heading,
  },
  secondaryAction: {
    minHeight: touchTarget,
    textAlignVertical: "center",
    textAlign: "center",
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.borderStrong,
    color: colors.text,
    ...typography.body,
  },
  footnote: { ...typography.caption, color: colors.textMuted },
});
