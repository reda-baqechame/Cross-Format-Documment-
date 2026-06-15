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
  // heading
  level?: number;
  // table
  rows?: number;
  cols?: number;
  // image
  alt_text?: string | null;
  blob_ref?: string;
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

export interface CanonicalDocument {
  schema_version: string;
  doc_id: string;
  root_id: string;
  nodes: Record<string, DocNode>;
  meta: DocumentMeta;
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
