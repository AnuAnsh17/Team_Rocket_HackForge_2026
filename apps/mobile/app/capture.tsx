import { StyleSheet, Text, View } from "react-native";

import { Card, PlaceholderNotice, Screen, touchTarget } from "@/components/ui";
import { colors, radius, spacing, typography } from "@/theme";

/**
 * Receipt capture.
 *
 * No camera is wired up. Requesting the camera permission without a working upload path
 * would ask the employee to grant a sensitive permission in exchange for nothing, so the
 * button is disabled and explains why.
 */
export default function CaptureScreen() {
  return (
    <Screen
      title="Add a receipt"
      description="Photograph the receipt, then check what was read from it before you submit."
    >
      <PlaceholderNotice
        title="Camera and upload are not implemented"
        whatIsMissing={
          "The canonical upload route is POST /api/v1/expenses/{expense_id}/receipts, and no " +
          "extraction provider has been selected, so this build cannot read a receipt. The " +
          "camera permission is not requested either: asking for it without a working upload " +
          "path would trade a sensitive permission for nothing."
        }
        blockedOn="The expense creation and receipt upload routes."
      />

      <View style={styles.button} accessibilityState={{ disabled: true }}>
        <Text style={styles.buttonLabel}>Take a photo (not available yet)</Text>
      </View>
      <View style={styles.button} accessibilityState={{ disabled: true }}>
        <Text style={styles.buttonLabel}>Choose from gallery (not available yet)</Text>
      </View>

      <Card title="What will happen" description="Four steps, and you confirm at the end.">
        <Text style={styles.step}>
          1. The file is checked by its actual contents, not its file name.
        </Text>
        <Text style={styles.step}>
          2. It is stored privately. There is no permanent public link, and only you and
          authorized finance reviewers can view it.
        </Text>
        <Text style={styles.step}>
          3. The details are read as evidence. Anything the reader is unsure about is marked
          uncertain rather than guessed.
        </Text>
        <Text style={styles.step}>4. Nothing is submitted until you have confirmed it.</Text>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: touchTarget,
    justifyContent: "center",
    alignItems: "center",
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    backgroundColor: colors.surfaceMuted,
  },
  buttonLabel: { ...typography.body, color: colors.textMuted },
  step: { ...typography.caption, color: colors.textMuted, marginBottom: spacing.sm },
});
