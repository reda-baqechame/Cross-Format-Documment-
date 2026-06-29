# Canonical document model

The model (`backend/src/docos/model`) is a typed, discriminated **node graph** stored
as a flat registry plus parent/child edges:

```
CanonicalDocument
├── doc_id, root_id, schema_version, content_hash
├── nodes: { node_id -> AnyNode }      # flat registry (the graph store)
├── meta: DocumentMeta                  # title, author, source format, embedded metadata
├── permissions / redaction / accessibility / signature   # cross-format trust state
```

A flat registry keyed by stable id is deliberate: reversible patches target nodes by id,
regardless of nesting, and JSONB storage stays simple.

## Node taxonomy (`nodes.py`)

| Node | Notable fields |
|---|---|
| `RootNode` | document/section root |
| `PageNode` | `page_number`, `width`, `height`, `rotation` |
| `ParagraphNode` | `style`, `alignment` |
| `HeadingNode` | `level` (+ `H{n}` tag) |
| `RunNode` | inline text span: `text`, `bold`, `italic`, `underline`, `font`, `size`, `color`, `link_href` |
| `ListNode` / `ListItemNode` | `ordered` |
| `TableNode` / `TableRowNode` / `TableCellNode` | `rows`/`cols`, `row`/`col`, `row_span`/`col_span`, `header` |
| `ImageNode` | `blob_ref` (bytes live in the blob store), `alt_text`, `ocr_confidence` |
| `FieldNode` | form/template fields: `field_name`, `field_kind`, `value` |
| `CommentNode` / `AnnotationNode` | review artifacts |
| `MetadataBlockNode` | structured embedded metadata |
| `FootnoteReferenceNode` | inline note marker: `footnote_id`, `marker` |
| `FootnoteNode` | note body: `footnote_id`, `marker`, normal paragraph/run children |
| `UnsupportedNode` | forward-compatible wrapper: `original_type`, `raw` |

Every node also carries `bbox`, `reading_order`, `tags` (semantic/a11y), and `attrs`
(format-specific extras preserved on round-trip so fidelity is never silently lost).

Unknown future node types deserialize as `UnsupportedNode` instead of failing validation. The raw
payload and child edges are preserved so older readers can display a visible placeholder and keep
known descendants reachable while newer versions add first-class node classes.

## Reversible patches (`patch.py`)

Edits are not regeneration. A `ReversiblePatch` bundles forward `Patch` ops with the
exact `inverse` ops computed at apply time:

```
ReversiblePatch
├── patches:  [ {op, target_id, payload}, ... ]   # forward
├── inverse:  [ ... ]                              # exact undo
└── intent:   "replace old entity name, keep tracked changes"
```

Supported ops: `add_node`, `remove_node`, `update_node`, `move_node`, `set_text`,
`retag`, `redact`. The orchestrator's `apply`/`revert` are fully functional and tested.

## Serialization & versioning (`serialize.py`)

- `to_dict` / `from_dict` — JSONB-ready round trip.
- `canonical_hash` — stable SHA-256 over the content (excluding `content_hash` itself);
  this hash **is** the version id, so identical content de-duplicates automatically.

## Trust state powers the health panel

`accessibility` (title, tagged, images-missing-alt, reading order, score),
`redaction` (redacted nodes, sanitized flag, pending), `signature` (signed, valid,
ready), and `permissions` are first-class on the document so the provenance service can
compute one `DocumentHealth` DTO from them.
