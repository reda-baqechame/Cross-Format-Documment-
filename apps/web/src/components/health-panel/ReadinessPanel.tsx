"use client";

import { VerifyPanel } from "@/components/expert/VerifyPanel";

/** Send-Ready Check — delegates to unified Verify panel with shared expert components. */
export function ReadinessPanel({ docId }: { docId: string }) {
  return <VerifyPanel docId={docId} />;
}
