"""Comment threads — collaborative review over the canonical model.

Every mutation builds a reversible patch and runs it through the shared apply → commit
→ audit path, so comments are versioned and undoable like any other edit. Threads work
identically across every format because they live in the model, not the source file.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from docos.api._apply import apply_and_commit
from docos.api.routes_documents import _load_latest
from docos.deps import db_session
from docos.services.collab import comments

router = APIRouter(prefix="/documents", tags=["comments"])


class AddCommentRequest(BaseModel):
    text: str
    target_id: str | None = None
    author: str | None = None


class ReplyRequest(BaseModel):
    text: str
    author: str | None = None


class ResolveRequest(BaseModel):
    resolved: bool = True


class CommentsResponse(BaseModel):
    doc_id: str
    threads: list[comments.CommentView]


class CommentCreatedResponse(BaseModel):
    doc_id: str
    comment_id: str
    threads: list[comments.CommentView]


def _require_comment(doc, comment_id: str) -> None:
    node = doc.nodes.get(comment_id)
    if node is None or node.type != "comment":
        raise HTTPException(status_code=404, detail="comment not found")


@router.get("/{doc_id}/comments", response_model=CommentsResponse)
def list_comments(doc_id: str, session: Session = Depends(db_session)) -> CommentsResponse:
    _record, doc = _load_latest(session, doc_id)
    return CommentsResponse(doc_id=doc_id, threads=comments.list_threads(doc))


@router.post("/{doc_id}/comments", response_model=CommentCreatedResponse)
def add_comment(
    doc_id: str, body: AddCommentRequest, session: Session = Depends(db_session)
) -> CommentCreatedResponse:
    _record, doc = _load_latest(session, doc_id)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="comment text is required")
    if body.target_id is not None and body.target_id not in doc.nodes:
        raise HTTPException(status_code=422, detail="unknown target_id")

    patch, comment_id = comments.add_comment_patch(doc, body.target_id, text, body.author)
    _, updated = apply_and_commit(
        session, doc_id, doc, patch, event="comment.added", detail={"comment_id": comment_id}
    )
    return CommentCreatedResponse(
        doc_id=doc_id, comment_id=comment_id, threads=comments.list_threads(updated)
    )


@router.post("/{doc_id}/comments/{comment_id}/replies", response_model=CommentCreatedResponse)
def reply(
    doc_id: str, comment_id: str, body: ReplyRequest, session: Session = Depends(db_session)
) -> CommentCreatedResponse:
    _record, doc = _load_latest(session, doc_id)
    _require_comment(doc, comment_id)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="reply text is required")

    patch, reply_id = comments.reply_patch(doc, comment_id, text, body.author)
    _, updated = apply_and_commit(
        session, doc_id, doc, patch, event="comment.replied", detail={"comment_id": comment_id}
    )
    return CommentCreatedResponse(
        doc_id=doc_id, comment_id=reply_id, threads=comments.list_threads(updated)
    )


@router.post("/{doc_id}/comments/{comment_id}/resolve", response_model=CommentsResponse)
def resolve(
    doc_id: str,
    comment_id: str,
    body: ResolveRequest,
    session: Session = Depends(db_session),
) -> CommentsResponse:
    _record, doc = _load_latest(session, doc_id)
    _require_comment(doc, comment_id)
    patch = comments.resolve_patch(doc, comment_id, body.resolved)
    _, updated = apply_and_commit(
        session, doc_id, doc, patch, event="comment.resolved", detail={"comment_id": comment_id}
    )
    return CommentsResponse(doc_id=doc_id, threads=comments.list_threads(updated))


@router.delete("/{doc_id}/comments/{comment_id}", response_model=CommentsResponse)
def delete_comment(
    doc_id: str, comment_id: str, session: Session = Depends(db_session)
) -> CommentsResponse:
    _record, doc = _load_latest(session, doc_id)
    _require_comment(doc, comment_id)
    patch = comments.delete_patch(doc, comment_id)
    _, updated = apply_and_commit(
        session, doc_id, doc, patch, event="comment.deleted", detail={"comment_id": comment_id}
    )
    return CommentsResponse(doc_id=doc_id, threads=comments.list_threads(updated))
