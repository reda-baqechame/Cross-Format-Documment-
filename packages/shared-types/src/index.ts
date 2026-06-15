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
  // table
  rows?: number;
  cols?: number;
  // image
  alt_text?: string | null;
  blob_ref?: string;
  mime?: string;
  // field
  field_name?: string;
  value?: string | null;
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

export interface CanonicalDocument {
  schema_version: string;
  doc_id: string;
  root_id: string;
  nodes: Record<string, DocNode>;
  meta: DocumentMeta;
  permissions?: Permissions;
  redaction?: RedactionState;
  accessibility: AccessibilityState;
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
  doc_id: string;
  version_id: string;
  detected_format: string | null;
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
  | "restore_metadata";

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
}

export interface DocumentListResponse {
  documents: DocumentSummary[];
}
