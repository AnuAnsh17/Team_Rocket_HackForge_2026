import { useLocalSearchParams } from "expo-router";
import { StyleSheet, Text } from "react-native";

import { Card, PlaceholderNotice, Screen } from "@/components/ui";
import { colors, typography } from "@/theme";

/**
 * Expense details.
 *
 * Echoes the identifier from the route only. When the endpoint exists, an identifier the
 * caller is not authorized to read must produce the same response as one that does not
 * exist, so another employee's claim is never disclosed by the difference.
 */
export default function ExpenseDetailScreen() {
  const { expenseId } = useLocalSearchParams<{ expenseId: string }>();

  return (
    <Screen
      title="Your claim"
      description="Status, evidence and history for one claim."
    >
      <Card title="Claim">
        <Text style={styles.mono}>{expenseId ?? "unknown"}</Text>
      </Card>

      <PlaceholderNotice
        title="This claim cannot be loaded"
        whatIsMissing={
          "The claim detail route is not implemented. The identifier above comes from the " +
          "navigation route only. A claim belonging to someone else would be answered " +
          "exactly as a claim that does not exist, so nothing about other people's expenses " +
          "is revealed."
        }
        blockedOn="The claim detail route."
      />

      <Text style={styles.footnote}>
        The example id used by the home screen is a placeholder and does not correspond to a
        real claim.
      </Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  mono: { ...typography.caption, color: colors.textMuted, fontFamily: "monospace" },
  footnote: { ...typography.caption, color: colors.textMuted },
});
