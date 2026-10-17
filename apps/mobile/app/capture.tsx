import { useEffect, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import * as ImagePicker from "expo-image-picker";

import { ApiError, unwrap, type components } from "@proofline/api-client";
import { Card, Screen, touchTarget } from "@/components/ui";
import { colors, radius, spacing, typography } from "@/theme";
import { API_BASE_URL, createMobileApi, getDemoActorId } from "@/api";

const api = createMobileApi();
type Receipt = components["schemas"]["ReceiptResponse"];

export default function CaptureScreen() {
  const [assets, setAssets] = useState<ImagePicker.ImagePickerAsset[]>([]);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [expenseId, setExpenseId] = useState<string | null>(null);
  const [draftKey, setDraftKey] = useState<string | null>(null);
  const [batchKey, setBatchKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const active = receipts.some((receipt) => ["pending", "running"].includes(receipt.extraction_status));

  useEffect(() => {
    if (!expenseId || !active) return;
    const timer = setInterval(() => {
      void unwrap(api.GET("/api/v1/expenses/{expense_id}/receipts", { params: { path: { expense_id: expenseId } } }))
        .then((items) => setReceipts((current) => current.map((receipt) => items.find((item) => item.id === receipt.id) ?? receipt)))
        .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : "Receipt status could not refresh."));
    }, 2500);
    return () => clearInterval(timer);
  }, [expenseId, active]);

  async function pick(camera: boolean) {
    setMessage(null);
    const result = camera
      ? await ImagePicker.launchCameraAsync({ mediaTypes: ["images"], quality: 1 })
      : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], allowsMultipleSelection: true, selectionLimit: 20, quality: 1 });
    if (result.canceled) return;
    const next = camera ? result.assets.slice(0, 1) : result.assets.slice(0, 20);
    if (next.some((asset) => !["image/jpeg", "image/png", "image/webp"].includes(asset.mimeType ?? "") || (asset.fileSize ?? 0) > 10 * 1024 * 1024)) {
      setMessage("Choose JPEG, PNG or WebP images up to 10 MiB each.");
      return;
    }
    setBatchKey(null);
    setAssets((current) => [...current, ...next].slice(0, 20));
  }

  async function upload() {
    setMessage(null);
    if (assets.length === 0 || assets.length > 20) return;
    setBusy(true);
    try {
      let targetExpenseId = expenseId;
      if (!targetExpenseId) {
        const key = draftKey ?? crypto.randomUUID();
        setDraftKey(key);
        const draft = await unwrap(api.POST("/api/v1/expenses", {
          params: { header: { "Idempotency-Key": key } },
          body: { channel: "android" },
        }));
        targetExpenseId = draft.id;
        setExpenseId(targetExpenseId);
        setDraftKey(null);
      }
      const files = await Promise.all(assets.map(async (asset, index) => {
        const blob = await (await fetch(asset.uri)).blob();
        return new File([blob], asset.fileName ?? `receipt-${index + 1}.jpg`, { type: asset.mimeType ?? blob.type });
      }));
      const form = new FormData();
      for (const file of files) form.append("files", file, file.name);
      const key = batchKey ?? crypto.randomUUID();
      setBatchKey(key);
      const uploaded = await unwrap(api.POST("/api/v1/expenses/{expense_id}/receipts/batch", {
        params: { path: { expense_id: targetExpenseId }, header: { "Idempotency-Key": key } },
        body: form as unknown as { files: string[] },
      }));
      setReceipts(uploaded.map(({ receipt }) => receipt));
      setAssets([]);
      setBatchKey(null);
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "Upload failed. No receipt values were submitted.");
    } finally {
      setBusy(false);
    }
  }

  async function retry(receiptId: string) {
    setMessage(null);
    try {
      const updated = await unwrap(api.POST("/api/v1/receipts/{receipt_id}/extractions", {
        params: { path: { receipt_id: receiptId }, header: { "Idempotency-Key": crypto.randomUUID() } },
      }));
      setReceipts((current) => current.map((receipt) => receipt.id === receiptId ? updated : receipt));
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "Extraction retry could not be scheduled.");
    }
  }

  return (
    <Screen title="Add receipts" description="Capture or choose up to 20 images. Each receipt is processed independently and uncertain values stay marked for review.">
      <Card title="Select receipt images" description="JPEG, PNG or WebP, up to 10 MiB each.">
        <View style={styles.actions}>
          <Text accessibilityRole="button" onPress={() => void pick(true)} style={styles.button}>Take photo</Text>
          <Text accessibilityRole="button" onPress={() => void pick(false)} style={styles.button}>Choose images</Text>
        </View>
        <Text style={styles.body}>{assets.length} image(s) selected.</Text>
        <Text accessibilityRole="button" onPress={() => void upload()} style={[styles.button, busy && styles.disabled]}>{busy ? "Uploading…" : "Create draft and upload"}</Text>
        {message && <Text accessibilityRole="alert" style={styles.alert}>{message}</Text>}
      </Card>
      {expenseId && <Text style={styles.muted}>Draft expense {expenseId}</Text>}
      {receipts.map((receipt) => {
        const run = receipt.extraction_runs?.at(-1);
        return <Card key={receipt.id} title={`Receipt ${receipt.id.slice(0, 8)}`} description={`${receipt.extraction_status} · ${run?.provider ?? "queued"}`}>
          <Image
            source={{
              uri: `${API_BASE_URL}${receipt.content_url}`,
              headers: getDemoActorId() ? { "X-Demo-Actor-Id": getDemoActorId()! } : undefined,
            }}
            accessibilityLabel="Original receipt loaded through the authorized private content endpoint"
            resizeMode="contain"
            style={styles.receiptImage}
            onError={() => setMessage("The API could not authorize or load this receipt image.")}
          />
          {run?.structured_result ? (["merchant", "transaction_date", "currency", "subtotal", "tax_total", "tip", "discount", "grand_total", "receipt_number"] as const).map((key) => {
            const field = run.structured_result?.[key];
            if (typeof field !== "object" || field === null || !("status" in field)) return null;
            return <Text key={key} style={styles.body}>{key.replaceAll("_", " ")}: {field.value ?? "Needs review"} ({field.status})</Text>;
          }) : <Text style={styles.body}>{run?.error_code ?? `Extraction ${run?.status ?? receipt.extraction_status}`}</Text>}
          {run?.structured_result?.line_items?.map((item, index) => <Text key={index} style={styles.body}>{item.description?.value ?? "Description needs review"} · {item.line_total?.value ?? "Amount needs review"} ({item.line_total?.status ?? "missing"})</Text>)}
          {run && ["failed", "unavailable"].includes(run.status) && <Text accessibilityRole="button" onPress={() => void retry(receipt.id)} style={styles.retry}>Retry extraction</Text>}
        </Card>;
      })}
    </Screen>
  );
}

const styles = StyleSheet.create({
  actions: { flexDirection: "row", gap: spacing.sm },
  button: { minHeight: touchTarget, flex: 1, textAlignVertical: "center", textAlign: "center", borderRadius: radius.md, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border, backgroundColor: colors.surfaceMuted, color: colors.text, ...typography.body },
  disabled: { opacity: 0.5 },
  receiptImage: { width: "100%", height: 220, borderRadius: radius.md, backgroundColor: colors.surfaceMuted },
  body: { ...typography.caption, color: colors.text, marginTop: spacing.sm },
  muted: { ...typography.caption, color: colors.textMuted },
  alert: { ...typography.caption, color: colors.severityBlocking, marginTop: spacing.sm },
  retry: { ...typography.caption, color: colors.accent, marginTop: spacing.sm, textDecorationLine: "underline" },
});
