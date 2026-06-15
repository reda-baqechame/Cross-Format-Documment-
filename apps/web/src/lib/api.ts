/** Typed client over the backend API. Types come from @docos/shared-types. */

import type {
  DocumentHealthResponse,
  DocumentModelResponse,
  PatchRequest,
  PatchResponse,
  UploadResponse,
} from "@docos/shared-types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const body = new FormData();
  body.append("file", file);
  return json<UploadResponse>(await fetch(`${BASE}/documents`, { method: "POST", body }));
}

export async function fetchModel(docId: string): Promise<DocumentModelResponse> {
  return json<DocumentModelResponse>(await fetch(`${BASE}/documents/${docId}/model`));
}

export async function fetchHealth(docId: string): Promise<DocumentHealthResponse> {
  return json<DocumentHealthResponse>(await fetch(`${BASE}/documents/${docId}/health`));
}

export async function submitPatch(docId: string, body: PatchRequest): Promise<PatchResponse> {
  return json<PatchResponse>(
    await fetch(`${BASE}/documents/${docId}/patches`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

/** Convenience: rewrite a single run's text via an explicit set_text op. */
export function setRunText(docId: string, nodeId: string, text: string): Promise<PatchResponse> {
  return submitPatch(docId, { ops: [{ op: "set_text", target_id: nodeId, payload: { text } }] });
}

/** Convenience: redact a node (true removal applied on export). */
export function redactNode(docId: string, nodeId: string): Promise<PatchResponse> {
  return submitPatch(docId, { ops: [{ op: "redact", target_id: nodeId }] });
}

export async function sanitizeMetadata(docId: string): Promise<PatchResponse> {
  return json<PatchResponse>(
    await fetch(`${BASE}/documents/${docId}/sanitize-metadata`, { method: "POST" }),
  );
}

export function exportUrl(docId: string, format: "docx" | "txt"): string {
  return `${BASE}/documents/${docId}/export?format=${format}`;
}

export function previewUrl(docId: string, page: number): string {
  return `${BASE}/documents/${docId}/preview?page=${page}`;
}
