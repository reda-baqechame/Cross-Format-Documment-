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
  office_editor: boolean;
  pdf_editor: boolean;
  database: string;
  // Gated-capability state (all default to off until the external provider/credential is wired).
  esign_configured?: boolean;
  idp_configured?: boolean;
  handwriting_configured?: boolean;
  tts_configured?: boolean;
  drm_configured?: boolean;
  presence_enabled?: boolean;
  cloud_integrations?: string[];
  billing_configured?: boolean;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${BASE}${path}`, { credentials: "include", ...init });
}

/** Pull the FastAPI `{ "detail": ... }` message out of an error body, if present. */
function errorDetail(body: string): string | null {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    /* not JSON — fall through */
  }
  return null;
}

async function json<T>(res: Response): Promise<T> {
  const contentType = res.headers.get("content-type") ?? "";
  const body = await res.text();
  if (!res.ok) {
    const detail = errorDetail(body);
    const fallback = body.slice(0, 300);
    // Keep the leading "NNN: " status prefix on every thrown error: upload.ts
    // (and similar callers) extract the HTTP status with /^(\d{3}):/ to map
    // 413/415/422/501 to friendly messages. 501 = a capability that isn't wired
    // in this deployment (e.g. translation without an LLM key); present it as an
    // intentional limitation, not a crash.
    if (res.status === 501) {
      throw new Error(`501: ${detail ?? "This feature isn't available in this deployment."}`);
    }
    if (res.status === 402) {
      throw new Error(`402: ${detail ?? "Upgrade required for this feature — see /pricing."}`);
    }
    throw new Error(`${res.status}: ${detail ?? fallback}`);
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

/** Private Mode: delete every document owned by this browser session. */
export async function purgeDocuments(): Promise<{ deleted: number }> {
  return json(await fetch(`${BASE}/documents`, { method: "DELETE" }));
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

// Async ingest/OCR job status (the worker-pipeline seam). Defined inline (like ReadinessCheck) so
// the surface doesn't depend on a codegen run; the backend shape lives in api/schemas.JobStatusResponse.
export interface JobStatus {
  job_id: string;
  kind: string;
  status: "pending" | "processing" | "succeeded" | "failed";
  document_id: string | null;
  finished: boolean;
  error: string | null;
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return json<JobStatus>(await fetch(`${BASE}/jobs/${jobId}`));
}

// Send-Ready Check / Document X-Ray. Defined inline (like BackendHealth) so the surface
// doesn't depend on a codegen run; the backend shapes live in services/provenance/readiness.py.
export interface ReadinessCheck {
  id: string;
  label: string;
  status: "pass" | "warn" | "fail";
  detail: string;
  count: number;
  fixable: boolean;
  fix_action: "redact_pii" | "sanitize_metadata" | "apply_redactions" | null;
}

export interface ReadinessReport {
  verdict: "ready" | "needs_fixes" | "blocked";
  summary: string;
  checks: ReadinessCheck[];
}

export interface ReadinessResponse {
  doc_id: string;
  report: ReadinessReport;
}

/** One verdict on whether a document is safe + complete to send (read-only). */
export async function fetchReadiness(docId: string): Promise<ReadinessResponse> {
  return json<ReadinessResponse>(await fetch(`${BASE}/documents/${docId}/readiness`));
}

export interface CleanResponse {
  doc_id: string;
  applied: boolean;
  new_version_id: string | null;
  report: ReadinessReport;
  validation: ValidationReport; // defined below — output opens, redactions removed, …
}

/** Clean Before You Send: apply the auto-fixes, re-check, and return the verdict + proof. */
export async function cleanDocument(docId: string): Promise<CleanResponse> {
  return json<CleanResponse>(
    await fetch(`${BASE}/documents/${docId}/clean`, { method: "POST" }),
  );
}

export interface RedactionAuditReport {
  is_pdf: boolean;
  scanned_pages: number;
  covered_regions: number;
  recoverable_count: number;
  verdict: "safe" | "leaky" | "not_applicable";
  summary: string;
}

export interface RedactionAuditResponse {
  doc_id: string;
  audit: RedactionAuditReport;
}

/** Un-Redact Test: is text still recoverable under this PDF's "redactions"? */
export async function fetchRedactionAudit(docId: string): Promise<RedactionAuditResponse> {
  return json<RedactionAuditResponse>(
    await fetch(`${BASE}/documents/${docId}/redaction-audit`),
  );
}

export interface EditorSession {
  doc_id: string;
  session_id: string;
  provider: string;
  status: string;
  mode: string;
  source_format: string;
  editor_url: string;
  config: Record<string, unknown>;
  capabilities: string[];
  warnings: string[];
  saved_version_id: string | null;
}

export async function createEditorSession(
  docId: string,
  body: { mode?: string; provider?: string | null } = {},
): Promise<EditorSession> {
  return json<EditorSession>(
    await fetch(`${BASE}/documents/${docId}/editor/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function saveEditorSession(
  docId: string,
  sessionId: string,
  note?: string,
): Promise<EditorSession> {
  return json<EditorSession>(
    await fetch(`${BASE}/documents/${docId}/editor/session/${sessionId}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note }),
    }),
  );
}

export interface OpsAgentAction {
  tool: string;
  label: string;
  destructive: boolean;
  requires_approval: boolean;
  reason: string;
}

export interface OpsAgentPlan {
  doc_id: string;
  goal: string;
  classification: string;
  actions: OpsAgentAction[];
  warnings: string[];
}

export async function planDocumentOps(
  docId: string,
  goal: string,
  allowDestructive = false,
): Promise<OpsAgentPlan> {
  return json<OpsAgentPlan>(
    await fetch(`${BASE}/documents/${docId}/ops-agent/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal, allow_destructive: allowDestructive }),
    }),
  );
}

export type WorkflowPreset =
  | "contract_packet"
  | "invoice_approval"
  | "vendor_onboarding"
  | "employee_form_packet"
  | "proposal_to_signature"
  | "bulk_send_template";

export interface WorkflowStep {
  id: string;
  label: string;
  status: string;
  tool: string;
  requires_approval: boolean;
  destructive: boolean;
  reason: string;
  result: string | null;
}

export interface WorkflowPreview {
  doc_id: string;
  preset: WorkflowPreset;
  classification: string;
  steps: WorkflowStep[];
  warnings: string[];
}

export interface WorkflowExecuteResponse {
  doc_id: string;
  preset: WorkflowPreset;
  classification: string;
  executed_steps: WorkflowStep[];
  skipped_steps: WorkflowStep[];
  next_required_approval: WorkflowStep | null;
  warnings: string[];
}

export async function previewWorkflow(
  docId: string,
  preset: WorkflowPreset,
): Promise<WorkflowPreview> {
  return json<WorkflowPreview>(
    await fetch(`${BASE}/documents/${docId}/workflows/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preset }),
    }),
  );
}

export async function executeWorkflow(
  docId: string,
  body: {
    preset: WorkflowPreset;
    approved_step_ids?: string[];
    confirm_destructive?: boolean;
    recipients?: string[];
    approvers?: string[];
  },
): Promise<WorkflowExecuteResponse> {
  return json<WorkflowExecuteResponse>(
    await fetch(`${BASE}/documents/${docId}/workflows/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        preset: body.preset,
        approved_step_ids: body.approved_step_ids ?? [],
        confirm_destructive: body.confirm_destructive ?? false,
        recipients: body.recipients ?? [],
        approvers: body.approvers ?? [],
      }),
    }),
  );
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
    font?: string | null;
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
  required: boolean;
  placeholder: string | null;
  help_text: string | null;
  options: string[];
  validation_pattern: string | null;
  default_value: string | null;
}

export interface FieldDraft {
  field_name: string;
  field_kind?: string;
  parent_id?: string | null;
  index?: number | null;
  value?: string | null;
  required?: boolean;
  placeholder?: string | null;
  help_text?: string | null;
  options?: string[];
  validation_pattern?: string | null;
  default_value?: string | null;
}

export type FieldUpdate = Partial<Omit<FieldDraft, "parent_id" | "index">>;

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

export async function detectFields(
  docId: string,
): Promise<{ doc_id: string; detected: number; patch: PatchResponse }> {
  return json(await fetch(`${BASE}/documents/${docId}/fields/detect`, { method: "POST" }));
}

export async function createField(docId: string, draft: FieldDraft): Promise<PatchResponse> {
  return json<PatchResponse>(
    await fetch(`${BASE}/documents/${docId}/fields/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    }),
  );
}

export async function updateField(
  docId: string,
  fieldId: string,
  changes: FieldUpdate,
): Promise<PatchResponse> {
  return json<PatchResponse>(
    await fetch(`${BASE}/documents/${docId}/fields/${fieldId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),
  );
}

export async function deleteField(docId: string, fieldId: string): Promise<PatchResponse> {
  return json<PatchResponse>(
    await fetch(`${BASE}/documents/${docId}/fields/${fieldId}`, { method: "DELETE" }),
  );
}

// ── Fill Once: a reusable autofill profile ─────────────────────────────────────
export async function getFillProfile(): Promise<{ data: Record<string, string> }> {
  return json(await fetch(`${BASE}/fill-profile`));
}

export async function saveFillProfile(
  data: Record<string, string>,
): Promise<{ data: Record<string, string> }> {
  return json(
    await fetch(`${BASE}/fill-profile`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ data }),
    }),
  );
}

export async function autofillDocument(
  docId: string,
): Promise<{ doc_id: string; filled: number; new_version_id: string | null }> {
  return json(await fetch(`${BASE}/documents/${docId}/autofill`, { method: "POST" }));
}

// ── CLM: clause library + renewals ─────────────────────────────────────────────
export interface Clause {
  id: string;
  title: string;
  body: string;
  category?: string | null;
}

export async function listClauses(): Promise<Clause[]> {
  return (await json<{ clauses: Clause[] }>(await fetch(`${BASE}/clauses`))).clauses;
}

export async function createClause(input: {
  title: string;
  body: string;
  category?: string | null;
}): Promise<Clause> {
  return json(
    await fetch(`${BASE}/clauses`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function deleteClause(clauseId: string): Promise<void> {
  const res = await fetch(`${BASE}/clauses/${clauseId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
}

export async function insertClause(
  docId: string,
  input: { clause_id?: string; title?: string; body?: string },
): Promise<{ doc_id: string; inserted: number; new_version_id: string | null }> {
  return json(
    await fetch(`${BASE}/documents/${docId}/insert-clause`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export interface Renewal {
  id: string;
  title: string;
  due_date: string;
  note?: string | null;
  status: string;
  doc_id?: string | null;
  urgency: "overdue" | "soon" | "later";
}

export async function listRenewals(): Promise<Renewal[]> {
  return (await json<{ renewals: Renewal[] }>(await fetch(`${BASE}/renewals`))).renewals;
}

export async function createRenewal(input: {
  title: string;
  due_date: string;
  note?: string | null;
  doc_id?: string | null;
}): Promise<Renewal> {
  return json(
    await fetch(`${BASE}/renewals`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function deleteRenewal(renewalId: string): Promise<void> {
  const res = await fetch(`${BASE}/renewals/${renewalId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
}

export interface SignatureRequest {
  id: string;
  doc_id: string;
  provider: string;
  status: string;
  signing_url?: string | null;
  detail: string;
  legally_binding: boolean;
}

export async function requestSignature(
  docId: string,
  input: { signers?: { name: string; email?: string }[]; subject?: string } = {},
): Promise<SignatureRequest> {
  return json(
    await fetch(`${BASE}/documents/${docId}/signature-request`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ signers: input.signers ?? [], subject: input.subject ?? null }),
    }),
  );
}

export interface Integration {
  name: string;
  label: string;
  configured: boolean;
  connected: boolean;
}

export async function listIntegrations(): Promise<Integration[]> {
  return (await json<{ integrations: Integration[] }>(await fetch(`${BASE}/integrations`)))
    .integrations;
}

/** Begin OAuth: navigates the browser to the provider's consent screen. */
export async function connectIntegration(name: string): Promise<void> {
  const res = await json<{ authorize_url: string }>(
    await fetch(`${BASE}/integrations/${name}/connect`),
  );
  window.location.href = res.authorize_url;
}

export async function disconnectIntegration(name: string): Promise<void> {
  const res = await fetch(`${BASE}/integrations/${name}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
}

/** Fetch narrated audio and trigger a download. Throws "501: …" when no TTS provider is wired. */
export async function downloadAudio(docId: string): Promise<void> {
  const res = await fetch(`${BASE}/documents/${docId}/audio`);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${docId}.mp3`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export interface PresenceViewer {
  viewer_id: string;
  name: string;
  color: string;
  idle_seconds: number;
}

export interface PresenceState {
  doc_id: string;
  viewers: PresenceViewer[];
  ttl_seconds: number;
}

/** Heartbeat this view's presence and get back everyone currently viewing the document. */
export async function presenceHeartbeat(
  docId: string,
  viewerId: string,
  name = "Guest",
): Promise<PresenceState> {
  return json(
    await fetch(`${BASE}/documents/${docId}/presence`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ viewer_id: viewerId, name }),
    }),
  );
}

export async function renewalSuggestions(docId: string): Promise<string[]> {
  return (
    await json<{ doc_id: string; due_dates: string[] }>(
      await fetch(`${BASE}/documents/${docId}/renewal-suggestions`),
    )
  ).due_dates;
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

export const duplicateNode = (docId: string, nodeId: string): Promise<PatchResponse> =>
  submitPatch(docId, { ops: [{ op: "duplicate_node", target_id: nodeId }] });

export const duplicatePage = (docId: string, nodeId: string): Promise<PatchResponse> =>
  submitPatch(docId, { ops: [{ op: "duplicate_page", target_id: nodeId }] });

export const setPageAttrs = (
  docId: string,
  nodeId: string,
  changes: { rotation?: number; width?: number; height?: number; page_number?: number },
): Promise<PatchResponse> =>
  submitPatch(docId, { ops: [{ op: "set_page_attrs", target_id: nodeId, payload: changes }] });

export const setTableCell = (
  docId: string,
  cellId: string,
  changes: {
    text?: string;
    header?: boolean;
    number_format?: string | null;
    formula?: string | null;
  },
): Promise<PatchResponse> =>
  submitPatch(docId, { ops: [{ op: "set_table_cell", target_id: cellId, payload: changes }] });

export const insertTableRow = (
  docId: string,
  tableId: string,
  index?: number,
): Promise<PatchResponse> =>
  submitPatch(docId, {
    ops: [{ op: "insert_table_row", target_id: tableId, payload: { index } }],
  });

export const deleteTableRow = (
  docId: string,
  tableId: string,
  index?: number,
  rowId?: string,
): Promise<PatchResponse> =>
  submitPatch(docId, {
    ops: [{ op: "delete_table_row", target_id: tableId, payload: { index, row_id: rowId } }],
  });

export const insertTableCol = (
  docId: string,
  tableId: string,
  index?: number,
): Promise<PatchResponse> =>
  submitPatch(docId, {
    ops: [{ op: "insert_table_col", target_id: tableId, payload: { index } }],
  });

export const deleteTableCol = (
  docId: string,
  tableId: string,
  index?: number,
): Promise<PatchResponse> =>
  submitPatch(docId, {
    ops: [{ op: "delete_table_col", target_id: tableId, payload: { index } }],
  });

export const insertLink = (docId: string, nodeId: string, href: string): Promise<PatchResponse> =>
  submitPatch(docId, { ops: [{ op: "insert_link", target_id: nodeId, payload: { href } }] });

export const setListAttrs = (
  docId: string,
  nodeId: string,
  ordered: boolean,
): Promise<PatchResponse> =>
  submitPatch(docId, { ops: [{ op: "set_list_attrs", target_id: nodeId, payload: { ordered } }] });

export interface AssetUpload {
  doc_id: string;
  blob_ref: string;
  mime: string;
  filename: string | null;
}

export async function uploadDocumentAsset(docId: string, file: File): Promise<AssetUpload> {
  const body = new FormData();
  body.append("file", file);
  return json<AssetUpload>(
    await fetch(`${BASE}/documents/${docId}/assets`, { method: "POST", body }),
  );
}

export const insertImage = (
  docId: string,
  parentId: string,
  asset: Pick<AssetUpload, "blob_ref" | "mime">,
  altText?: string,
): Promise<PatchResponse> =>
  submitPatch(docId, {
    ops: [
      {
        op: "insert_image",
        target_id: parentId,
        payload: { blob_ref: asset.blob_ref, mime: asset.mime, alt_text: altText ?? null },
      },
    ],
  });

export const replaceImage = (
  docId: string,
  imageId: string,
  asset: Pick<AssetUpload, "blob_ref" | "mime">,
  altText?: string,
): Promise<PatchResponse> =>
  submitPatch(docId, {
    ops: [
      {
        op: "replace_image",
        target_id: imageId,
        payload: { blob_ref: asset.blob_ref, mime: asset.mime, alt_text: altText ?? null },
      },
    ],
  });

export const setImageAttrs = (
  docId: string,
  imageId: string,
  changes: { alt_text?: string | null; attrs?: Record<string, unknown> },
): Promise<PatchResponse> =>
  submitPatch(docId, { ops: [{ op: "set_image_attrs", target_id: imageId, payload: changes }] });

function localNodeId(prefix: string): string {
  const raw =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID().replaceAll("-", "")
      : Math.random().toString(16).slice(2);
  return `${prefix}_${raw.slice(0, 12)}`;
}

export function addTextBlock(
  docId: string,
  parentId: string,
  text: string,
  opts?: { heading?: boolean; index?: number | null },
): Promise<PatchResponse> {
  const blockId = localNodeId(opts?.heading ? "h" : "p");
  const runId = localNodeId("run");
  return submitPatch(docId, {
    ops: [
      {
        op: "add_node",
        payload: {
          node: {
            id: blockId,
            type: opts?.heading ? "heading" : "paragraph",
            parent_id: parentId,
            children: [runId],
            attrs: {},
            tags: opts?.heading ? ["H2"] : [],
            level: opts?.heading ? 2 : undefined,
          },
          nodes: [
            {
              id: blockId,
              type: opts?.heading ? "heading" : "paragraph",
              parent_id: parentId,
              children: [runId],
              attrs: {},
              tags: opts?.heading ? ["H2"] : [],
              level: opts?.heading ? 2 : undefined,
            },
            {
              id: runId,
              type: "run",
              parent_id: blockId,
              children: [],
              attrs: {},
              tags: [],
              text,
            },
          ],
          parent_id: parentId,
          index: opts?.index,
        },
      },
    ],
  });
}

/**
 * Place a new text box at a fixed position on a PDF page. The run carries a `bbox` (PDF points)
 * and is parented under the page node, so `write_back_pdf` inserts it at that location — the
 * tractable, no-SDK slice of PDF authoring (reflow/object-move still need a PDF SDK provider).
 */
export function addPositionedText(
  docId: string,
  pageId: string,
  bbox: { x0: number; y0: number; x1: number; y1: number },
  text: string,
  opts?: { size?: number },
): Promise<PatchResponse> {
  const blockId = localNodeId("p");
  const runId = localNodeId("run");
  const block = {
    id: blockId,
    type: "paragraph",
    parent_id: pageId,
    children: [runId],
    attrs: {},
    tags: [],
  };
  const run = {
    id: runId,
    type: "run",
    parent_id: blockId,
    children: [],
    attrs: {},
    tags: [],
    text,
    bbox,
    size: opts?.size ?? 12,
  };
  return submitPatch(docId, {
    ops: [
      {
        op: "add_node",
        payload: { node: block, nodes: [block, run], parent_id: pageId, index: null },
      },
    ],
  });
}

export type ExportFormat =
  | "docx"
  | "txt"
  | "pdf"
  | "md"
  | "html"
  | "csv"
  | "rtf"
  | "xlsx"
  | "pptx"
  | "png";

export function exportUrl(docId: string, format: ExportFormat): string {
  return `${BASE}/documents/${docId}/export?format=${format}`;
}

/** The proof a download carries in its headers (output opens, redactions removed, …). */
export interface ValidationInfo {
  status: "pass" | "warn" | "fail";
  summary: string;
}

function readValidation(res: Response): ValidationInfo | null {
  const status = res.headers.get("X-DocOS-Validation");
  if (status !== "pass" && status !== "warn" && status !== "fail") return null;
  return { status, summary: res.headers.get("X-DocOS-Validation-Summary") ?? "" };
}

export interface ValidationFinding {
  level: "pass" | "warn" | "fail";
  code: string;
  message: string;
}
export interface ValidationReport {
  ok: boolean;
  operation: string;
  output_format: string;
  summary: string;
  findings: ValidationFinding[];
  checked_at: string;
}

/** The full validation report for an export, without downloading the file. */
export async function exportReport(
  docId: string,
  format: ExportFormat,
): Promise<ValidationReport> {
  const res = await json<{ doc_id: string; validation: ValidationReport }>(
    await fetch(`${BASE}/documents/${docId}/export/report?format=${format}`),
  );
  return res.validation;
}

/** Fetch export bytes and trigger a download — returns the validation proof from the headers. */
export async function downloadExport(
  docId: string,
  format: ExportFormat,
  filename?: string,
): Promise<ValidationInfo | null> {
  const res = await fetch(exportUrl(docId, format));
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  const validation = readValidation(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename ?? `${docId}.${format === "md" ? "md" : format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return validation;
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

/** A structural PNG thumbnail of one slide/page, rendered from the model (works for any format). */
export function slideThumbnailUrl(docId: string, nodeId: string): string {
  return `${BASE}/documents/${docId}/slide-thumbnail?node_id=${encodeURIComponent(nodeId)}`;
}

// ── Document Autopilot ───────────────────────────────────────────────────────
export interface AutopilotField {
  name: string;
  label: string;
  value: string | null;
  confidence: number;
  node_id: string | null;
  status: "found" | "low_confidence" | "missing";
}
export interface AutopilotFinding {
  level: "pass" | "warn" | "fail";
  code: string;
  message: string;
}
export interface AutopilotAction {
  id: string;
  label: string;
  kind: "export" | "redact" | "sign" | "navigate";
  params: Record<string, string>;
}
export interface AutopilotReport {
  category: string;
  type: string;
  type_id: string;
  type_confidence: number;
  skill_label: string;
  title: string;
  deep: boolean;
  fields: AutopilotField[];
  findings: AutopilotFinding[];
  actions: AutopilotAction[];
  needs_review: boolean;
}

export async function fetchAutopilot(docId: string): Promise<AutopilotReport> {
  const res = await json<{ doc_id: string; autopilot: AutopilotReport }>(
    await fetch(`${BASE}/documents/${docId}/autopilot`),
  );
  return res.autopilot;
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

export async function redoDocument(docId: string): Promise<DocumentModelResponse> {
  return json<DocumentModelResponse>(
    await fetch(`${BASE}/documents/${docId}/redo`, { method: "POST" }),
  );
}

// Find & replace across the whole document (one reversible, audited edit). Types mirror
// the backend FindReplace* schemas until `make codegen` folds them into @docos/shared-types.
export interface FindReplaceRequest {
  find: string;
  replace?: string;
  match_case?: boolean;
  whole_word?: boolean;
}

export interface FindReplaceResult {
  doc_id: string;
  applied: boolean;
  occurrences: number;
  nodes_changed: number;
  new_version_id: string | null;
}

export async function replaceText(
  docId: string,
  body: FindReplaceRequest,
): Promise<FindReplaceResult> {
  return json<FindReplaceResult>(
    await fetch(`${BASE}/documents/${docId}/replace`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
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

/** Split: extract the given 0-based page indices (as produced by parsePageList) into a new PDF
 *  and download it. The backend's /pages/extract expects 0-based indices. */
export async function splitPdf(docId: string, pages: number[]): Promise<void> {
  const q = pages.join(",");
  const res = await fetch(`${BASE}/documents/${docId}/pages/extract?pages=${q}`);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  triggerDownload(await res.blob(), `${docId}_pages.pdf`);
}

/** Generate a searchable PDF (invisible OCR layer for scans; selectable text otherwise). */
export async function downloadSearchablePdf(
  docId: string,
  filename?: string,
): Promise<ValidationInfo | null> {
  const res = await fetch(`${BASE}/documents/${docId}/searchable-pdf`);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  const validation = readValidation(res);
  triggerDownload(await res.blob(), filename ?? `${docId}_searchable.pdf`);
  return validation;
}

// ── Templates & styles library ────────────────────────────────────────────────
export interface TemplateSummary {
  id: string;
  name: string;
  description: string | null;
  source_format: string;
  variables: string[];
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
  portal_url?: string | null;
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
    await apiFetch(`/documents/${docId}/bulk-send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recipients, message: message ?? null }),
    }),
  );
}

export async function listBulkSends(docId: string): Promise<BulkSendBatch[]> {
  const res = await json<{ source_doc_id: string; batches: BulkSendBatch[] }>(
    await apiFetch(`/documents/${docId}/bulk-send`),
  );
  return res.batches;
}

// Auth
export interface UserView {
  id: string;
  email: string;
  name: string | null;
}

export interface AuthResponse {
  user: UserView;
  claimed?: Record<string, number>;
}

export async function registerUser(
  email: string,
  password: string,
  name?: string,
): Promise<AuthResponse> {
  return json<AuthResponse>(
    await apiFetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name: name ?? null }),
    }),
  );
}

export async function loginUser(email: string, password: string): Promise<AuthResponse> {
  return json<AuthResponse>(
    await apiFetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),
  );
}

export async function logoutUser(): Promise<{ ok: boolean }> {
  return json(await apiFetch("/auth/logout", { method: "POST" }));
}

export async function fetchMe(): Promise<UserView | null> {
  const res = await apiFetch("/auth/me");
  if (res.status === 204) return null;
  const body = await res.text();
  if (!body || body === "null") return null;
  if (!res.ok) throw new Error(body);
  return JSON.parse(body) as UserView | null;
}

// Share / portal
export interface ShareView {
  id: string;
  token: string;
  document_id: string;
  permission: string;
  recipient_label: string | null;
  expires_at: string | null;
  portal_url: string;
  revoked: boolean;
}

export async function createShare(
  docId: string,
  opts: { permission?: string; expires_in_days?: number; pin?: string; recipient_label?: string },
): Promise<ShareView> {
  return json<ShareView>(
    await apiFetch(`/documents/${docId}/shares`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts),
    }),
  );
}

export async function listShares(docId: string): Promise<{ doc_id: string; shares: ShareView[] }> {
  return json(await apiFetch(`/documents/${docId}/shares`));
}

export async function revokeShare(docId: string, shareId: string): Promise<{ ok: boolean }> {
  return json(await apiFetch(`/documents/${docId}/shares/${shareId}`, { method: "DELETE" }));
}

export async function fetchPortalInfo(token: string, pin?: string): Promise<ShareView> {
  const q = pin ? `?pin=${encodeURIComponent(pin)}` : "";
  return json(await apiFetch(`/portal/${token}${q}`));
}

export async function fetchPortalModel(token: string, pin?: string): Promise<DocumentModelResponse> {
  const q = pin ? `?pin=${encodeURIComponent(pin)}` : "";
  return json(await apiFetch(`/portal/${token}/model${q}`));
}

export async function fetchPortalReadiness(token: string, pin?: string): Promise<ReadinessResponse> {
  const q = pin ? `?pin=${encodeURIComponent(pin)}` : "";
  return json(await apiFetch(`/portal/${token}/readiness${q}`));
}

export async function fetchPortalApprovals(token: string, pin?: string): Promise<WorkflowStatus> {
  const q = pin ? `?pin=${encodeURIComponent(pin)}` : "";
  return json(await apiFetch(`/portal/${token}/approvals${q}`));
}

export async function portalApprove(
  token: string,
  opts?: { note?: string; pin?: string },
): Promise<WorkflowStatus> {
  const params = new URLSearchParams();
  if (opts?.pin) params.set("pin", opts.pin);
  const q = params.toString() ? `?${params}` : "";
  return json(
    await apiFetch(`/portal/${token}/approve${q}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: opts?.note ?? null }),
    }),
  );
}

// Billing
export interface PlanView {
  id: string;
  name: string;
  price_monthly: number;
  features: string[];
}

export interface BillingStatus {
  configured: boolean;
  plan: string;
  status: string;
  plans: PlanView[];
}

export async function fetchBillingStatus(): Promise<BillingStatus> {
  return json(await apiFetch("/billing/status"));
}

export async function startCheckout(plan: "pro" | "team"): Promise<{ checkout_url: string }> {
  return json(
    await apiFetch("/billing/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan }),
    }),
  );
}

export function downloadReadinessReport(docId: string, _report?: ReadinessResponse): void {
  const a = document.createElement("a");
  a.href = `${BASE}/documents/${docId}/readiness/report?format=html`;
  a.download = `${docId}-readiness-report.html`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function downloadPortalReadinessReport(token: string, report: ReadinessResponse): void {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `portal-${token.slice(0, 8)}-readiness-report.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
