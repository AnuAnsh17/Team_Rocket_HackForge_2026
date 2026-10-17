import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { colors } from "@/theme";

export default function RootLayout() {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.surfaceRaised },
          headerTintColor: colors.text,
          contentStyle: { backgroundColor: colors.surface },
        }}
      >
        <Stack.Screen name="index" options={{ title: "Proofline" }} />
        <Stack.Screen name="capture" options={{ title: "Add a receipt" }} />
        <Stack.Screen name="review" options={{ title: "Check the details" }} />
        <Stack.Screen name="status" options={{ title: "Claim status" }} />
        <Stack.Screen name="expenses/[expenseId]" options={{ title: "Claim" }} />
      </Stack>
    </>
  );
}
