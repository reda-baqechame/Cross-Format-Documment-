"""TTS seam: honest 501 by default, streams audio when a provider is configured."""

from __future__ import annotations

from docos.deps import get_tts_provider
from docos.services.tts import TtsProvider, document_text


def _upload(client, text: bytes = b"Hello there. This is a document.") -> str:
    return client.post("/documents", files={"file": ("d.txt", text, "text/plain")}).json()["doc_id"]


def test_audio_501_when_not_configured(client):
    doc_id = _upload(client)
    res = client.get(f"/documents/{doc_id}/audio")
    assert res.status_code == 501
    assert "not configured" in res.json()["detail"].lower()


def test_audio_streams_when_provider_configured(client):
    class _FakeTts(TtsProvider):
        name = "external"

        def synthesize(self, text, *, voice=None):
            assert "Hello there" in text  # got the narration text
            return b"ID3fake-mp3-bytes", "audio/mpeg"

    client.app.dependency_overrides[get_tts_provider] = lambda: _FakeTts()
    try:
        doc_id = _upload(client)
        res = client.get(f"/documents/{doc_id}/audio")
        assert res.status_code == 200
        assert res.headers["content-type"] == "audio/mpeg"
        assert "attachment" in res.headers["content-disposition"]
        assert res.content == b"ID3fake-mp3-bytes"
    finally:
        client.app.dependency_overrides.pop(get_tts_provider, None)


def test_document_text_is_redaction_aware():
    from docos.services.docengine.adapters.txt import TxtAdapter

    doc = TxtAdapter().parse(b"Keep this line.\n\nSecret line.")
    # Redact the second paragraph's run and confirm it isn't narrated.
    from docos.services.docengine.writers.redaction import is_redacted

    runs = [n for n in doc.nodes.values() if n.type == "run"]
    target = next(r for r in runs if "Secret" in (r.text or ""))
    doc.redaction.redacted_node_ids.append(target.id)
    assert is_redacted(doc, target.id)
    text = document_text(doc)
    assert "Keep this line." in text
    assert "Secret" not in text
