"""Live presence (single-node heartbeat/poll).

Each open view heartbeats and gets back who else is currently viewing the document. Access is gated
by document ownership (``_load_latest`` 404s for other sessions). Works out of the box; cross-person
sharing + co-editing need collaboration infra (the Redis ``PresenceHub`` seam).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from docos.api.routes_documents import _load_latest
from docos.api.schemas import PresenceBeat, PresenceResponse, ViewerSchema
from docos.api.session import Actor, get_actor
from docos.deps import db_session, get_presence_hub
from docos.settings import get_settings

router = APIRouter(prefix="/documents", tags=["presence"])


def _viewers(raw) -> list[ViewerSchema]:
    return [
        ViewerSchema(viewer_id=v.viewer_id, name=v.name, color=v.color, idle_seconds=v.idle_seconds)
        for v in raw
    ]


@router.post("/{doc_id}/presence", response_model=PresenceResponse)
def heartbeat(
    doc_id: str,
    body: PresenceBeat,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    hub=Depends(get_presence_hub),
) -> PresenceResponse:
    _load_latest(session, doc_id, actor)  # ownership gate (404 for other sessions)
    viewers = hub.heartbeat(doc_id, body.viewer_id, body.name, body.color)
    return PresenceResponse(
        doc_id=doc_id, viewers=_viewers(viewers), ttl_seconds=get_settings().presence_ttl_seconds
    )


@router.get("/{doc_id}/presence", response_model=PresenceResponse)
def list_presence(
    doc_id: str,
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    hub=Depends(get_presence_hub),
) -> PresenceResponse:
    _load_latest(session, doc_id, actor)
    return PresenceResponse(
        doc_id=doc_id,
        viewers=_viewers(hub.viewers(doc_id)),
        ttl_seconds=get_settings().presence_ttl_seconds,
    )
