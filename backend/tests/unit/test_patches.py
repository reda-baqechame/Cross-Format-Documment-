"""Reversible patches apply and revert exactly."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from docos.model.ids import new_patch_id
from docos.model.nodes import (
    ImageNode,
    ListNode,
    PageNode,
    RunNode,
    TableCellNode,
    TableNode,
    TableRowNode,
)
from docos.model.patch import Patch, ReversiblePatch
from docos.services.docengine.adapters.txt import TxtAdapter
from docos.services.semantic.llm.noop import LocalNoopClient
from docos.services.semantic.orchestrator import SemanticOrchestratorImpl


def _orchestrator():
    return SemanticOrchestratorImpl(LocalNoopClient())


def _first_run(doc):
    return next(n for n in doc.nodes.values() if n.type == "run")


def _table_doc():
    doc = TxtAdapter().parse(b"table doc")
    root = doc.nodes[doc.root_id]
    table = TableNode(id="table_1", parent_id=root.id, rows=2, cols=2)
    root.children.append(table.id)
    doc.add_node(table)
    for ri in range(2):
        row = TableRowNode(id=f"row_{ri}", parent_id=table.id, row=ri)
        table.children.append(row.id)
        doc.add_node(row)
        for ci in range(2):
            cell = TableCellNode(id=f"cell_{ri}_{ci}", parent_id=row.id, row=ri, col=ci)
            run = RunNode(id=f"run_{ri}_{ci}", parent_id=cell.id, text=f"{ri},{ci}")
            cell.children.append(run.id)
            row.children.append(cell.id)
            doc.add_node(cell)
            doc.add_node(run)
    return doc


def _matrix(doc):
    table = doc.nodes["table_1"]
    out = []
    for row_id in table.children:
        row = doc.nodes[row_id]
        out.append(
            [
                "".join(getattr(doc.nodes[rid], "text", "") for rid in doc.nodes[cell_id].children)
                for cell_id in row.children
            ]
        )
    return out


def test_set_text_apply_then_revert_restores_original():
    doc = TxtAdapter().parse(b"original text")
    run = _first_run(doc)
    orch = _orchestrator()
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="set_text", target_id=run.id, payload={"text": "new text"})],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    assert applied.nodes[run.id].text == "new text"

    reverted = orch.revert(applied, patch)
    assert reverted.nodes[run.id].text == "original text"


def test_interpret_with_noop_client_returns_empty_patch():
    doc = TxtAdapter().parse(b"hello")
    orch = _orchestrator()
    patch = asyncio.run(orch.interpret(doc, "make it formal"))
    assert patch.patches == []
    assert patch.intent == "make it formal"


def test_update_node_apply_then_revert_restores_fields():
    doc = TxtAdapter().parse(b"plain run")
    run = _first_run(doc)
    orch = _orchestrator()
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[
            Patch(op="update_node", target_id=run.id, payload={"bold": True, "italic": True})
        ],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    assert applied.nodes[run.id].bold is True and applied.nodes[run.id].italic is True

    reverted = orch.revert(applied, patch)
    assert reverted.nodes[run.id].bold is False and reverted.nodes[run.id].italic is False


def test_update_node_ignores_unknown_payload_keys():
    doc = TxtAdapter().parse(b"text")
    run = _first_run(doc)
    orch = _orchestrator()
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[
            Patch(op="update_node", target_id=run.id, payload={"type": "heading", "bold": True})
        ],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    # 'type' is not an updatable field, so it must be left untouched.
    assert applied.nodes[run.id].type == "run"
    assert applied.nodes[run.id].bold is True


def test_redact_apply_adds_id_and_revert_removes_it():
    doc = TxtAdapter().parse(b"secret value")
    run = _first_run(doc)
    orch = _orchestrator()
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="redact", target_id=run.id)],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    assert run.id in applied.redaction.redacted_node_ids

    reverted = orch.revert(applied, patch)
    assert run.id not in reverted.redaction.redacted_node_ids


def test_remove_node_then_revert_restores_node_and_position():
    doc = TxtAdapter().parse(b"first\n\nsecond\n\nthird")
    runs = [n for n in doc.walk() if n.type == "run"]
    middle_para = doc.nodes[runs[1].parent_id]
    root_children_before = list(doc.children_of(doc.root_id))
    orch = _orchestrator()
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="remove_node", target_id=middle_para.id)],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    assert middle_para.id not in applied.nodes
    assert middle_para.id not in applied.nodes[doc.root_id].children

    reverted = orch.revert(applied, patch)
    assert middle_para.id in reverted.nodes
    # restored to its original index among the root's children
    assert [n.id for n in reverted.children_of(doc.root_id)] == [
        n.id for n in root_children_before
    ]


def test_move_node_reorders_and_revert_restores():
    doc = TxtAdapter().parse(b"a\n\nb\n\nc")
    paras = [n for n in doc.children_of(doc.root_id)]
    orch = _orchestrator()
    # move the last paragraph to the front
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="move_node", target_id=paras[2].id, payload={"index": 0})],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    assert [n.id for n in applied.children_of(doc.root_id)][0] == paras[2].id

    reverted = orch.revert(applied, patch)
    assert [n.id for n in reverted.children_of(doc.root_id)] == [p.id for p in paras]


def test_sanitize_metadata_op_clears_keys_and_revert_restores():
    doc = TxtAdapter().parse(b"body")
    doc.meta.custom = {"author": "Alice", "revision": "3", "keywords": "safe"}
    orch = _orchestrator()
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="sanitize_metadata")],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    assert "author" not in applied.meta.custom
    assert "revision" not in applied.meta.custom
    assert applied.meta.custom.get("keywords") == "safe"  # non-risky key kept
    assert applied.redaction.metadata_sanitized is True

    reverted = orch.revert(applied, patch)
    assert reverted.meta.custom.get("author") == "Alice"
    assert reverted.redaction.metadata_sanitized is False


def test_table_modification_ops_are_reversible():
    doc = _table_doc()
    orch = _orchestrator()
    before = _matrix(doc)
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[
            Patch(op="set_table_cell", target_id="cell_0_0", payload={"text": "changed"}),
            Patch(op="insert_table_row", target_id="table_1", payload={"index": 1}),
            Patch(op="insert_table_col", target_id="table_1", payload={"index": 1}),
            Patch(op="delete_table_col", target_id="table_1", payload={"index": 2}),
            Patch(op="delete_table_row", target_id="table_1", payload={"index": 2}),
        ],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    assert applied.nodes["table_1"].rows == 2
    assert applied.nodes["table_1"].cols == 2
    assert _matrix(applied)[0][0] == "changed"

    reverted = orch.revert(applied, patch)
    assert _matrix(reverted) == before
    assert reverted.nodes["table_1"].rows == 2
    assert reverted.nodes["table_1"].cols == 2


def test_visual_link_list_and_page_ops_are_reversible():
    doc = TxtAdapter().parse(b"hello")
    root = doc.nodes[doc.root_id]
    run = _first_run(doc)
    image = ImageNode(id="img_1", parent_id=root.id, blob_ref="old", alt_text="old")
    page = PageNode(id="page_1", parent_id=root.id, page_number=1, width=100, height=100)
    list_node = ListNode(id="list_1", parent_id=root.id, ordered=False)
    for node in (image, page, list_node):
        root.children.append(node.id)
        doc.add_node(node)
    before_children = list(root.children)
    orch = _orchestrator()
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[
            Patch(op="insert_link", target_id=run.id, payload={"href": "https://example.com"}),
            Patch(op="set_list_attrs", target_id=list_node.id, payload={"ordered": True}),
            Patch(
                op="replace_image",
                target_id=image.id,
                payload={"blob_ref": "new", "alt_text": "new"},
            ),
            Patch(op="set_image_attrs", target_id=image.id, payload={"alt_text": "better"}),
            Patch(
                op="insert_image",
                target_id=root.id,
                payload={"blob_ref": "asset", "mime": "image/png"},
            ),
            Patch(op="set_page_attrs", target_id=page.id, payload={"rotation": 90}),
            Patch(op="duplicate_page", target_id=page.id),
            Patch(op="duplicate_node", target_id=run.parent_id),
        ],
        created_at=datetime.now(UTC),
    )
    applied = orch.apply(doc, patch)
    assert applied.nodes[run.id].link_href == "https://example.com"
    assert applied.nodes[list_node.id].ordered is True
    assert applied.nodes[image.id].blob_ref == "new"
    assert applied.nodes[page.id].rotation == 90
    assert len(applied.nodes[doc.root_id].children) > len(before_children)

    reverted = orch.revert(applied, patch)
    assert reverted.nodes[run.id].link_href is None
    assert reverted.nodes[list_node.id].ordered is False
    assert reverted.nodes[image.id].blob_ref == "old"
    assert reverted.nodes[image.id].alt_text == "old"
    assert reverted.nodes[page.id].rotation == 0
    assert reverted.nodes[doc.root_id].children == before_children
