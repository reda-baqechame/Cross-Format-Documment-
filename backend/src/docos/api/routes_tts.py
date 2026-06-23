"""Document → audio (gated TTS seam).

Streams narrated audio when a TTS provider is configured; otherwise returns an honest 501. The text
is gathered redaction-aware so removed content is never spoken.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from docos.api.ratelimit import enforce_op_rate
from docos.api.routes_documents import _load_latest
from docos.api.session import Actor, get_actor
from docos.deps import db_session, get_tts_provider
from docos.services.tts import TtsNotConfigured, TtsProvider, document_text

router = APIRouter(prefix="/documents", tags=["tts"])

_EXT = {"audio/mpeg": "mp3", "audio/wav": "wav", "audio/ogg": "ogg"}


@router.get("/{doc_id}/audio")
def document_audio(
    doc_id: str,
    voice: str | None = Query(default=None),
    session: Session = Depends(db_session),
    actor: Actor = Depends(get_actor),
    tts: TtsProvider = Depends(get_tts_provider),
    _rate: None = Depends(enforce_op_rate),
) -> Response:
    _record, doc = _load_latest(session, doc_id, actor)
    text = document_text(doc)
    if not text.strip():
        raise HTTPException(status_code=422, detail="the document has no narratable text")
    try:
        audio, content_type = tts.synthesize(text, voice=voice)
    except TtsNotConfigured as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - provider/transport failure
        raise HTTPException(status_code=502, detail=f"tts provider error: {exc}") from exc
    ext = _EXT.get(content_type, "mp3")
    return Response(
        content=audio,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{doc_id}.{ext}"'},
    )
