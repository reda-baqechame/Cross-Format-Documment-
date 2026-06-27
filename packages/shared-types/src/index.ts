/**
 * Shared API types.
 *
 * These hand-written types are the committed baseline so the frontend typechecks
 * out of the box. Running `make codegen` regenerates `generated.ts` from the live
 * OpenAPI schema for full fidelity; prefer importing from there once available.
 */

export type NodeType =
  | "root"
  | "page"
  | "paragraph"
  | "run"
  | "heading"
  | "list"
  | "list_item"
  | "table"
  | "table_row"
  | "table_cell"
  | "image"
  | "field"
  | "comment"
  | "annotation"
  | "metadata_block";

export interface BBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface DocNode {
  id: string;
  type: NodeType;
  parent_id: string | null;
  children: string[];
  bbox?: BBox | null;
  reading_order?: number | null;
  attrs: Record<string, unknown>;
  tags: string[];
  // run
  text?: string;
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  font?: string | null;
  size?: number | null;
  color?: string | null;
  link_href?: string | null;
  // heading
  level?: number;
  // list
  ordered?: boolean;
  // page
  page_number?: number;
  width?: number;
  height?: number;
  rotation?: number;
  // table
  rows?: number;
  cols?: number;
  row?: number;
  col?: number;
  header?: boolean;
  // image
  alt_text?: string | null;
  blob_ref?: string;
  mime?: string;
  // field
  field_name?: string;
  field_kind?: string;
  value?: string | null;
  required?: boolean;
  placeholder?: string | null;
  help_text?: string | null;
  options?: string[];
  validation_pattern?: string | null;
  default_value?: string | null;
}

export interface DocumentMeta {
  title: string | null;
  author: string | null;
  source_format: string;
  source_mime: string;
  page_count: number;
  custom: Record<string, unknown>;
}

export interface AccessibilityState {
  has_doc_title: boolean;
  tagged: boolean;
  images_missing_alt: string[];
  reading_order_ok: boolean;
  score: number;
}

export interface RedactionState {
  redacted_node_ids: string[];
  metadata_sanitized: boolean;
  pending: string[];
}

export interface Permissions {
  can_edit: boolean;
  can_export: boolean;
  can_copy: boolean;
  encrypted: boolean;
  password_protected: boolean;
}

export interface SignatureState {
  signed: boolean;
  signature_valid: boolean | null;
  ready_for_signing: boolean;
  signer?: string | null;
  signed_at?: string | null;
}

export interface CanonicalDocument {
  schema_version: string;
  doc_id: string;
  root_id: string;
  nodes: Record<string, DocNode>;
  meta: DocumentMeta;
  permissions?: Permissions;
  redaction?: RedactionState;
  accessibility: AccessibilityState;
  signature?: SignatureState;
  content_hash: string | null;
}

export interface HealthFinding {
  level: "ok" | "info" | "warn" | "fail";
  code: string;
  message: string;
}

export interface DocumentHealth {
  accessibility_score: number;
  metadata_risk: boolean;
  has_pending_redactions: boolean;
  signed: boolean;
  ready_for_signing: boolean;
  findings: HealthFinding[];
}

export interface UploadResponse {
  // Sync mode returns doc_id/version_id immediately. Async mode returns job_id + status instead
  // (doc_id arrives via GET /jobs/{job_id} once the worker finishes).
  doc_id?: string | null;
  version_id?: string | null;
  detected_format?: string | null;
  job_id?: string | null;
  status?: string | null;
}

export interface DocumentModelResponse {
  document: CanonicalDocument;
  version_id: string | null;
}

export interface DocumentHealthResponse {
  doc_id: string;
  health: DocumentHealth;
}

export type PatchOpName =
  | "add_node"
  | "remove_node"
  | "update_node"
  | "move_node"
  | "set_text"
  | "retag"
  | "redact"
  | "unredact"
  | "sanitize_metadata"
  | "restore_metadata"
  | "duplicate_node"
  | "insert_table_row"
  | "delete_table_row"
  | "insert_table_col"
  | "delete_table_col"
  | "set_table_cell"
  | "insert_image"
  | "replace_image"
  | "set_image_attrs"
  | "insert_link"
  | "set_list_attrs"
  | "duplicate_page"
  | "set_page_attrs";

export interface PatchOpDTO {
  op: PatchOpName;
  target_id?: string | null;
  payload?: Record<string, unknown>;
}

export interface PatchRequest {
  instruction?: string;
  ops?: PatchOpDTO[];
}

export interface PatchResponse {
  doc_id: string;
  patch_id: string;
  applied: boolean;
  new_version_id: string | null;
  intent: string | null;
}

export interface DocumentSummary {
  doc_id: string;
  title: string | null;
  source_format: string;
  current_version_id: string | null;
  created_at: string;
  tags?: string[];
}

export interface DocumentListResponse {
  documents: DocumentSummary[];
}

export interface SignatureResponse {
  doc_id: string;
  signed: boolean;
  valid: boolean;
  signer: string | null;
  signed_at: string | null;
}
