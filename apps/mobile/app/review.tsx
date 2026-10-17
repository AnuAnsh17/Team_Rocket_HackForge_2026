import { Card, PlaceholderNotice, Screen } from "@/components/ui";
import { Text } from "react-native";

import { typography, colors, spacing } from "@/theme";

/**
 * Extraction review.
 *
 * This is the screen that decides whether the product is trustworthy: a value read from the
 * receipt and a value typed by the employee must never look the same.
 */
export default function ReviewScreen() {
  return (
    <Screen
      title="Check the details"
      description="Confirm or correct what was read from your receipt before you submit it."
    >
      <PlaceholderNotice
        title="There is nothing to check"
        whatIsMissing={
          "No receipt has been read, because no extraction provider has been selected or " +
          "verified. When one is, this screen will show each value with where it came from " +
          "and mark the ones the reader was unsure about."
        }
        blockedOn="An extraction provider, and the receipt upload route."
      />

      <Card title="Every value will show its source" description="Three sources, never blurred together.">
        <Text style={styles.item}>
          Read from the receipt — printed on the image, with the region it came from where
          the reader supports it.
        </Text>
        <Text style={styles.item}>
          Entered by you — your own context, such as who the client was. Never displayed as
          though it were printed on the receipt.
        </Text>
        <Text style={styles.item}>
          Uncertain — the reader could not be sure. Shown explicitly, and you will be asked
          rather than the value being assumed.
        </Text>
      </Card>

      <Text style={styles.footnote}>
        Some expenses need details a receipt cannot contain, such as a client name or how
        many people attended. Which details apply to which expense type is set by policy,
        and this build has no policy, so it will not guess.
      </Text>
    </Screen>
  );
}

const styles = {
  item: { ...typography.caption, color: colors.textMuted, marginBottom: spacing.sm },
  footnote: { ...typography.caption, color: colors.textMuted },
};
