/** Typed client over the backend API. Types come from @docos/shared-types. */

import type {
  DocumentHealthResponse,
  DocumentModelResponse,
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
