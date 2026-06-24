"""Comment threads as first-class canonical-model nodes.

A comment is a :class:`CommentNode` attached to the node it annotates (or the root for
a document-level comment). A reply is a comment whose parent is another comment, so a
thread is just a comment with comment children. Because comments are real nodes, every
add / reply / resolve / delete flows through the same reversible-patch pipeline as any
other edit — versioned, audited, and undoable — and never touches free-form file bytes.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from docos.model.document import CanonicalDocument
from docos.model.ids import new_node_id, new_patch_id
from docos.model.nodes import CommentNode
from docos.model.patch import Patch, ReversiblePatch


class CommentView(BaseModel):
    id: str
    target_id: str | None  # the node the thread annotates (None ⇒ document-level)
    author: str | None
    text: str
    resolved: bool
    created_at: datetime | None
    replies: list[CommentView] = []


def _is_comment(doc: CanonicalDocument, node_id: str) -> bool:
    node = doc.nodes.get(node_id)
    return node is not None and node.type == "comment"


def _new_comment_patch(
    doc: CanonicalDocument, parent_id: str, text: str, author: str | None, intent: str
) -> tuple[ReversiblePatch, str]:
    comment = CommentNode(
        id=new_node_id("cmt"),
        parent_id=parent_id,
        author=author,
        text=text,
        created_at=datetime.now(UTC),
    )
    patch = ReversiblePatch(
        id=new_patch_id(),
        patches=[
            Patch(
                op="add_node",
                payload={"node": comment.model_dump(mode="json"), "parent_id": parent_id},
            )
        ],
        inverse=[],
        intent=intent,
        created_at=datetime.now(UTC),
    )
    return patch, comment.id


def add_comment_patch(
    doc: CanonicalDocument, target_id: str | None, text: str, author: str | None
) -> tuple[ReversiblePatch, str]:
    """A new top-level comment on ``target_id`` (or the document root)."""
    parent_id = target_id or doc.root_id
    return _new_comment_patch(doc, parent_id, text, author, intent="add comment")


def reply_patch(
    doc: CanonicalDocument, comment_id: str, text: str, author: str | None
) -> tuple[ReversiblePatch, str]:
    """A reply within an existing thread."""
    return _new_comment_patch(doc, comment_id, text, author, intent="reply to comment")


def resolve_patch(doc: CanonicalDocument, comment_id: str, resolved: bool) -> ReversiblePatch:
    """Mark a thread resolved (or reopen it). Replies inherit the thread's state."""
    ids = [comment_id] + [c.id for c in doc.children_of(comment_id) if c.type == "comment"]
    return ReversiblePatch(
        id=new_patch_id(),
        patches=[Patch(op="update_node", target_id=i, payload={"resolved": resolved}) for i in ids],
        inverse=[],
        intent=("resolve comment" if resolved else "reopen comment"),
        created_at=datetime.now(UTC),
    )


def delete_patch(doc: CanonicalDocument, comment_id: str) -> ReversiblePatch:
    """Delete a thread: remove replies first, then the comment itself."""
    reply_ids = [c.id for c in doc.children_of(comment_id) if c.type == "comment"]
    ops = [Patch(op="remove_node", target_id=i) for i in reply_ids]
    ops.append(Patch(op="remove_node", target_id=comment_id))
    return ReversiblePatch(
        id=new_patch_id(),
        patches=ops,
        inverse=[],
        intent="delete comment thread",
        created_at=datetime.now(UTC),
    )


def list_threads(doc: CanonicalDocument) -> list[CommentView]:
    """All top-level comment threads with their replies, in document order."""

    def view(node) -> CommentView:
        parent = node.parent_id
        target = None if parent == doc.root_id or _is_comment(doc, parent) else parent
        return CommentView(
            id=node.id,
            target_id=target,
            author=node.author,
            text=node.text,
            resolved=node.resolved,
            created_at=node.created_at,
            replies=[view(c) for c in doc.children_of(node.id) if c.type == "comment"],
        )

    threads: list[CommentView] = []
    for node in doc.walk():
        if node.type == "comment" and not _is_comment(doc, node.parent_id):
            threads.append(view(node))
    return threads
