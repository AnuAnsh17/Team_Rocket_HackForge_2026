import { Card, EmployeeStateBanner, Screen, StatusPill } from "@/components/ui";
import { StyleSheet, Text, View } from "react-native";

import { colors, spacing, typography } from "@/theme";

/**
 * Claim status.
 *
 * Uses example statuses to fix the vocabulary. It does not fetch anything, because the
 * claim routes are not implemented, and it says so.
 */
export default function StatusScreen() {
  return (
    <Screen
      title="Claim status"
      description="Where each of your claims stands, in plain language."
    >
      <Card title="Example statuses" description="Shown to fix the wording, not as your data.">
        <View style={styles.row}>
          <StatusPill status="submitted" />
          <StatusPill status="in_review" />
          <StatusPill status="needs_info" />
          <StatusPill status="approved" />
          <StatusPill status="rejected" />
        </View>
      </Card>

      <EmployeeStateBanner state="needs_info" />
      <EmployeeStateBanner state="possible_duplicate" />

      <Text style={styles.footnote}>
        &quot;Not reimbursed&quot; means the expense was not reimbursed. It is not a statement
        about you.
      </Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  footnote: { ...typography.caption, color: colors.textMuted },
});
