/** Typed client over the backend API. Types come from @docos/shared-types. */

import type {
  DocumentHealthResponse,
  DocumentListResponse,
  DocumentModelResponse,
  PatchRequest,
  PatchResponse,
  SignatureResponse,
  UploadResponse,
} from "@docos/shared-types";

// All calls go through the same-origin proxy at /api/* (see app/api/[...path]/route.ts),
// so there's no API URL baked into the client bundle and no CORS to configure.
const BASE = "/api";

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

/** Convenience: toggle rich formatting on a run (bold/italic/underline/…). */
export function formatRun(
  docId: string,
  nodeId: string,
  changes: { bold?: boolean; italic?: boolean; underline?: boolean },
): Promise<PatchResponse> {
  return submitPatch(docId, {
    ops: [{ op: "update_node", target_id: nodeId, payload: changes }],
  });
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

export type ExportFormat =
  | "docx"
  | "txt"
  | "pdf"
  | "md"
  | "html"
  | "csv"
  | "xlsx"
  | "pptx"
  | "png";

export function exportUrl(docId: string, format: ExportFormat): string {
  return `${BASE}/documents/${docId}/export?format=${format}`;
}

export function previewUrl(docId: string, page: number): string {
  return `${BASE}/documents/${docId}/preview?page=${page}`;
}

/** Natural-language AI edit: routed through the LLM when a provider is configured. */
export function instructEdit(docId: string, instruction: string): Promise<PatchResponse> {
  return submitPatch(docId, { instruction });
}

export async function listDocuments(): Promise<DocumentListResponse> {
  return json<DocumentListResponse>(await fetch(`${BASE}/documents`));
}

export async function undoDocument(docId: string): Promise<DocumentModelResponse> {
  return json<DocumentModelResponse>(
    await fetch(`${BASE}/documents/${docId}/undo`, { method: "POST" }),
  );
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await fetch(`${BASE}/documents/${docId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
}

export async function signDocument(docId: string, signer: string): Promise<SignatureResponse> {
  return json<SignatureResponse>(
    await fetch(`${BASE}/documents/${docId}/sign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signer }),
    }),
  );
}

export async function fetchSignature(docId: string): Promise<SignatureResponse> {
  return json<SignatureResponse>(await fetch(`${BASE}/documents/${docId}/signature`));
}

// Sensitive-data detection. Types mirror the backend SensitiveScanResponse; `make codegen`
// will fold these into @docos/shared-types once the backend is running.
export interface SensitiveFinding {
  node_id: string;
  category: string;
  label: string;
  excerpt: string; // masked — never the raw value
}

export interface SensitiveScanResponse {
  doc_id: string;
  findings: SensitiveFinding[];
  summary: Record<string, number>;
  node_count: number;
}

/** Detect PII/secrets without changing the document (preview for redaction). */
export async function scanSensitive(docId: string): Promise<SensitiveScanResponse> {
  return json<SensitiveScanResponse>(await fetch(`${BASE}/documents/${docId}/sensitive`));
}

/** One-click "clean before export": redact every detected PII/secret as a reversible patch. */
export async function redactSensitive(docId: string): Promise<PatchResponse> {
  return json<PatchResponse>(
    await fetch(`${BASE}/documents/${docId}/redact-sensitive`, { method: "POST" }),
  );
}

// Document Q&A / summary. Answers cite the canonical-model nodes they draw from and run
// fully offline (used_llm=false) unless an LLM provider is configured.
export interface Citation {
  node_id: string;
  excerpt: string;
}

export interface AskResponse {
  doc_id: string;
  answer: string;
  citations: Citation[];
  used_llm: boolean;
}

export interface SummaryResponse {
  doc_id: string;
  summary: string;
  citations: Citation[];
  used_llm: boolean;
}

/** Ask a question answered from the document's own text, with citations. */
export async function askDocument(docId: string, question: string): Promise<AskResponse> {
  return json<AskResponse>(
    await fetch(`${BASE}/documents/${docId}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
  );
}

/** Summarize the document, with citations. */
export async function fetchSummary(docId: string): Promise<SummaryResponse> {
  return json<SummaryResponse>(await fetch(`${BASE}/documents/${docId}/summary`));
}

// Cross-document compare (redline).
export interface DiffSegment {
  op: "equal" | "insert" | "delete" | "replace";
  a_text: string | null;
  b_text: string | null;
}

export interface DiffResponse {
  doc_id: string;
  against: string;
  result: {
    segments: DiffSegment[];
    added: number;
    removed: number;
    changed: number;
    unchanged: number;
  };
}

/** Block-level redline between this document and another (cross-format). */
export async function diffDocuments(docId: string, against: string): Promise<DiffResponse> {
  return json<DiffResponse>(
    await fetch(`${BASE}/documents/${docId}/diff?against=${encodeURIComponent(against)}`),
  );
}

// Library: tags + cross-corpus search.
export interface TagsResponse {
  doc_id: string;
  tags: string[];
}

export interface SearchResponse {
  query: string;
  hits: { doc_id: string; title: string | null; snippet: string }[];
}

export async function listTags(docId: string): Promise<TagsResponse> {
  return json<TagsResponse>(await fetch(`${BASE}/documents/${docId}/tags`));
}

export async function addTag(docId: string, tag: string): Promise<TagsResponse> {
  return json<TagsResponse>(
    await fetch(`${BASE}/documents/${docId}/tags`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tag }),
    }),
  );
}

export async function removeTag(docId: string, tag: string): Promise<TagsResponse> {
  return json<TagsResponse>(
    await fetch(`${BASE}/documents/${docId}/tags/${encodeURIComponent(tag)}`, { method: "DELETE" }),
  );
}

/** Full-text search across every document (redaction-aware). */
export async function searchDocuments(query: string): Promise<SearchResponse> {
  return json<SearchResponse>(await fetch(`${BASE}/search?q=${encodeURIComponent(query)}`));
}

export interface SemanticHit {
  doc_id: string;
  title: string | null;
  score: number;
  snippet: string;
}

/** Relevance-ranked semantic search across the corpus (TF-IDF cosine). */
export async function semanticSearch(query: string): Promise<SemanticHit[]> {
  return json<SemanticHit[]>(await fetch(`${BASE}/search/semantic?q=${encodeURIComponent(query)}`));
}

export interface NotebookCitation {
  doc_id: string;
  title: string | null;
  node_id: string;
  excerpt: string;
}

export interface NotebookResponse {
  question: string;
  answer: string;
  citations: NotebookCitation[];
  used_llm: boolean;
  document_count: number;
}

/** Ask one question across every document (or a chosen subset), with cited sources. */
export async function notebookAsk(
  question: string,
  docIds?: string[],
): Promise<NotebookResponse> {
  return json<NotebookResponse>(
    await fetch(`${BASE}/notebook/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, doc_ids: docIds ?? null }),
    }),
  );
}

// ── Comment threads ──────────────────────────────────────────────────────────
export interface CommentThread {
  id: string;
  target_id: string | null;
  author: string | null;
  text: string;
  resolved: boolean;
  created_at: string | null;
  replies: CommentThread[];
}

interface CommentsPayload {
  doc_id: string;
  threads: CommentThread[];
}

export async function listComments(docId: string): Promise<CommentThread[]> {
  const res = await json<CommentsPayload>(await fetch(`${BASE}/documents/${docId}/comments`));
  return res.threads;
}

export async function addComment(
  docId: string,
  text: string,
  targetId?: string | null,
  author?: string,
): Promise<CommentThread[]> {
  const res = await json<CommentsPayload>(
    await fetch(`${BASE}/documents/${docId}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, target_id: targetId ?? null, author: author ?? null }),
    }),
  );
  return res.threads;
}

export async function replyToComment(
  docId: string,
  commentId: string,
  text: string,
  author?: string,
): Promise<CommentThread[]> {
  const res = await json<CommentsPayload>(
    await fetch(`${BASE}/documents/${docId}/comments/${commentId}/replies`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, author: author ?? null }),
    }),
  );
  return res.threads;
}

export async function resolveComment(
  docId: string,
  commentId: string,
  resolved: boolean,
): Promise<CommentThread[]> {
  const res = await json<CommentsPayload>(
    await fetch(`${BASE}/documents/${docId}/comments/${commentId}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resolved }),
    }),
  );
  return res.threads;
}

export async function deleteComment(docId: string, commentId: string): Promise<CommentThread[]> {
  const res = await json<CommentsPayload>(
    await fetch(`${BASE}/documents/${docId}/comments/${commentId}`, { method: "DELETE" }),
  );
  return res.threads;
}

/** Auto-fix accessibility (heading tags, reading order, image alt) as a reversible patch. */
export async function remediateAccessibility(docId: string): Promise<PatchResponse> {
  return json<PatchResponse>(
    await fetch(`${BASE}/documents/${docId}/remediate-accessibility`, { method: "POST" }),
  );
}

export interface Classification {
  label: string;
  confidence: number;
  signals: string[];
}

/** Detect the document type (invoice/contract/resume/…). */
export async function classifyDocument(docId: string): Promise<Classification> {
  const res = await json<{ classification: Classification }>(
    await fetch(`${BASE}/documents/${docId}/classify`),
  );
  return res.classification;
}

// PDF tools that POST and stream a resulting PDF back for download.
function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function pdfTool(docId: string, path: string, body?: unknown): Promise<void> {
  const res = await fetch(`${BASE}/documents/${docId}/${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  triggerDownload(await res.blob(), `${docId}.pdf`);
}

export const compressPdf = (docId: string) => pdfTool(docId, "compress");
export const protectPdf = (docId: string, password: string) =>
  pdfTool(docId, "protect", { password });
export const watermarkPdf = (docId: string, text: string) => pdfTool(docId, "watermark", { text });
