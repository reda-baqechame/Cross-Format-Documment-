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

export interface BackendHealth {
  status: string;
  privacy_mode: string;
  blob_backend: string;
  db: string;
  ai_enabled: boolean;
  llm_provider: string;
}

async function json<T>(res: Response): Promise<T> {
  const contentType = res.headers.get("content-type") ?? "";
  const body = await res.text();
  if (!res.ok) {
    throw new Error(`${res.status}: ${body.slice(0, 300)}`);
  }
  if (!contentType.includes("application/json")) {
    throw new Error(
      "Unexpected response from the server — the backend may not be running (start it on port 8000).",
    );
  }
  return JSON.parse(body) as T;
}

/** Liveness check for the home-page backend banner. */
export async function fetchBackendHealth(): Promise<BackendHealth> {
  return json<BackendHealth>(await fetch(`${BASE}/health`));
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

/** Convenience: set rich formatting on a run (bold/italic/underline/size/color/…). */
export function formatRun(
  docId: string,
  nodeId: string,
  changes: {
    bold?: boolean;
    italic?: boolean;
    underline?: boolean;
    size?: number | null;
    color?: string | null;
  },
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

// ── Forms (fillable fields) ───────────────────────────────────────────────────
export interface FormField {
  node_id: string;
  field_name: string;
  field_kind: string;
  value: string | null;
}

/** List a document's fillable form-field placeholders. */
export async function listFields(docId: string): Promise<FormField[]> {
  const res = await json<{ doc_id: string; fields: FormField[] }>(
    await fetch(`${BASE}/documents/${docId}/fields`),
  );
  return res.fields;
}

/** Fill a single form field (reversible + versioned, like any edit). */
export async function fillField(
  docId: string,
  nodeId: string,
  value: string,
): Promise<PatchResponse> {
  return json<PatchResponse>(
    await fetch(`${BASE}/documents/${docId}/fields`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ node_id: nodeId, value }),
    }),
  );
}

/** Delete a block (reversible — restorable via undo). */
export function deleteNode(docId: string, nodeId: string): Promise<PatchResponse> {
  return submitPatch(docId, { ops: [{ op: "remove_node", target_id: nodeId }] });
}

/** Move a block to a new index under a parent (reversible). */
export function moveNode(
  docId: string,
  nodeId: string,
  parentId: string,
  index: number,
): Promise<PatchResponse> {
  return submitPatch(docId, {
    ops: [{ op: "move_node", target_id: nodeId, payload: { parent_id: parentId, index } }],
  });
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

/** Fetch export bytes and trigger a download — surfaces HTTP errors instead of saving JSON. */
export async function downloadExport(
  docId: string,
  format: ExportFormat,
  filename?: string,
): Promise<void> {
  const res = await fetch(exportUrl(docId, format));
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename ?? `${docId}.${format === "md" ? "md" : format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export interface VersionRef {
  version_id: string;
  parent_id: string | null;
  patch_id: string | null;
  created_at: string;
}

export async function fetchHistory(
  docId: string,
): Promise<{ doc_id: string; versions: VersionRef[] }> {
  return json(await fetch(`${BASE}/documents/${docId}/history`));
}

export async function translateDocument(
  docId: string,
  targetLanguage: string,
): Promise<{ translated_text: string; target_language: string }> {
  return json(
    await fetch(`${BASE}/documents/${docId}/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_language: targetLanguage }),
    }),
  );
}

export interface ExtractEntity {
  type: string;
  value: string;
  node_id: string;
}

export interface ExtractField {
  key: string;
  value: string;
  node_id: string;
}

export async function fetchExtract(docId: string): Promise<{
  doc_id: string;
  extraction: { entities: ExtractEntity[]; fields: ExtractField[] };
}> {
  return json(await fetch(`${BASE}/documents/${docId}/extract`));
}

export interface InsightField {
  key: string;
  value: string;
  node_id: string | null;
  confidence: number;
}

export interface InsightCheck {
  id: string;
  label: string;
  severity: "info" | "warn" | "error";
  passed: boolean;
  detail: string;
}

export interface DocumentInsight {
  doc_type: string;
  confidence: number;
  fields: InsightField[];
  checks: InsightCheck[];
  summary: string;
}

/** Typed, validated read for the detected document kind (invoice/contract/résumé/…). */
export async function fetchIntelligence(
  docId: string,
): Promise<{ doc_id: string; insight: DocumentInsight }> {
  return json(await fetch(`${BASE}/documents/${docId}/intelligence`));
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

// ── Approval / multi-party signing workflow ──────────────────────────────────
export interface ApprovalStepView {
  approver: string;
  order_index: number;
  status: "pending" | "approved" | "rejected";
  note: string | null;
}

export interface WorkflowStatus {
  doc_id: string;
  workflow_id: string | null;
  state: "none" | "in_progress" | "approved" | "rejected";
  ordered: boolean;
  steps: ApprovalStepView[];
  current_approvers: string[];
}

export async function getApprovals(docId: string): Promise<WorkflowStatus> {
  return json<WorkflowStatus>(await fetch(`${BASE}/documents/${docId}/approvals`));
}

export async function startApprovals(
  docId: string,
  approvers: string[],
  ordered: boolean,
): Promise<WorkflowStatus> {
  return json<WorkflowStatus>(
    await fetch(`${BASE}/documents/${docId}/approvals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approvers, ordered }),
    }),
  );
}

export async function decideApproval(
  docId: string,
  approver: string,
  decision: "approve" | "reject",
  note?: string,
): Promise<WorkflowStatus> {
  return json<WorkflowStatus>(
    await fetch(`${BASE}/documents/${docId}/approvals/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approver, decision, note: note ?? null }),
    }),
  );
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

/** Parse a "1,3,5" or "2-4" page string into 0-based indices (UI is 1-based). */
export function parsePageList(input: string): number[] {
  const out: number[] = [];
  for (const part of input.split(",")) {
    const t = part.trim();
    if (!t) continue;
    const range = t.match(/^(\d+)\s*-\s*(\d+)$/);
    if (range) {
      const lo = Number(range[1]);
      const hi = Number(range[2]);
      for (let p = lo; p <= hi; p++) out.push(p - 1);
    } else if (/^\d+$/.test(t)) {
      out.push(Number(t) - 1);
    }
  }
  return out.filter((n) => n >= 0);
}

export const rotatePdf = (docId: string, pages: number[], degrees: number) =>
  pdfTool(docId, "pages/rotate", { pages, degrees });
export const deletePages = (docId: string, pages: number[]) =>
  pdfTool(docId, "pages/delete", { pages });
export const reorderPages = (docId: string, order: number[]) =>
  pdfTool(docId, "pages/reorder", { order });
/** Merge other documents into this one (all rendered to PDF first). */
export const mergePdfs = (docId: string, docIds: string[]) =>
  pdfTool(docId, "merge", { doc_ids: docIds });

/** Split: extract the given (1-based) pages into a new PDF and download it. */
export async function splitPdf(docId: string, pages: number[]): Promise<void> {
  const q = pages.join(",");
  const res = await fetch(`${BASE}/documents/${docId}/pages/extract?pages=${q}`);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  triggerDownload(await res.blob(), `${docId}_pages.pdf`);
}

/** Generate a searchable PDF (invisible OCR layer for scans; selectable text otherwise). */
export async function downloadSearchablePdf(docId: string, filename?: string): Promise<void> {
  const res = await fetch(`${BASE}/documents/${docId}/searchable-pdf`);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  triggerDownload(await res.blob(), filename ?? `${docId}_searchable.pdf`);
}

// ── Templates & styles library ────────────────────────────────────────────────
export interface TemplateSummary {
  id: string;
  name: string;
  description: string | null;
  source_format: string;
  created_at: string;
}

export async function listTemplates(): Promise<TemplateSummary[]> {
  const res = await json<{ templates: TemplateSummary[] }>(await fetch(`${BASE}/templates`));
  return res.templates;
}

export async function saveAsTemplate(
  docId: string,
  name: string,
  description?: string,
): Promise<TemplateSummary> {
  return json<TemplateSummary>(
    await fetch(`${BASE}/documents/${docId}/save-as-template`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description: description ?? null }),
    }),
  );
}

export async function instantiateTemplate(
  templateId: string,
  title?: string,
): Promise<{ doc_id: string; version_id: string; template_id: string }> {
  return json(
    await fetch(`${BASE}/templates/${templateId}/instantiate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title ?? null }),
    }),
  );
}

export async function deleteTemplate(templateId: string): Promise<void> {
  const res = await fetch(`${BASE}/templates/${templateId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
}

// ── Track-changes / suggest mode ──────────────────────────────────────────────
export interface SuggestionView {
  id: string;
  doc_id: string;
  author: string | null;
  intent: string | null;
  status: "pending" | "accepted" | "rejected";
  op_count: number;
  new_version_id: string | null;
  created_at: string;
  decided_at: string | null;
}

export async function listSuggestions(
  docId: string,
  status?: "pending" | "accepted" | "rejected",
): Promise<SuggestionView[]> {
  const q = status ? `?status=${status}` : "";
  const res = await json<{ doc_id: string; suggestions: SuggestionView[] }>(
    await fetch(`${BASE}/documents/${docId}/suggestions${q}`),
  );
  return res.suggestions;
}

export async function suggestEdit(
  docId: string,
  ops: PatchRequest["ops"],
  opts?: { intent?: string; author?: string },
): Promise<SuggestionView> {
  return json<SuggestionView>(
    await fetch(`${BASE}/documents/${docId}/suggestions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ops, intent: opts?.intent ?? null, author: opts?.author ?? null }),
    }),
  );
}

export async function decideSuggestion(
  docId: string,
  suggestionId: string,
  decision: "accept" | "reject",
): Promise<SuggestionView> {
  return json<SuggestionView>(
    await fetch(`${BASE}/documents/${docId}/suggestions/${suggestionId}/${decision}`, {
      method: "POST",
    }),
  );
}

// ── Bulk send (one packet to many recipients) ─────────────────────────────────
export interface BulkSendPacketView {
  recipient: string;
  packet_doc_id: string;
  state: string;
}

export interface BulkSendBatch {
  batch_id: string;
  source_doc_id: string;
  message: string | null;
  packets: BulkSendPacketView[];
}

export async function bulkSend(
  docId: string,
  recipients: string[],
  message?: string,
): Promise<BulkSendBatch> {
  return json<BulkSendBatch>(
    await fetch(`${BASE}/documents/${docId}/bulk-send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recipients, message: message ?? null }),
    }),
  );
}

export async function listBulkSends(docId: string): Promise<BulkSendBatch[]> {
  const res = await json<{ source_doc_id: string; batches: BulkSendBatch[] }>(
    await fetch(`${BASE}/documents/${docId}/bulk-send`),
  );
  return res.batches;
}
