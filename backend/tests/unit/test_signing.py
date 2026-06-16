"""E-signature is tamper-evident: any edit after signing fails verification."""

from __future__ import annotations

from docos.services.docengine.adapters.txt import TxtAdapter
from docos.services.provenance import signing

_SECRET = "unit-test-secret"


def _doc():
    return TxtAdapter().parse(b"contract body")


def test_sign_then_verify_passes():
    doc = _doc()
    assert signing.verify(doc, secret=_SECRET) is False  # unsigned

    signed = signing.sign(doc, signer="Alice", secret=_SECRET)
    assert signed.signature.signed is True
    assert signed.signature.signer == "Alice"
    assert signing.verify(signed, secret=_SECRET) is True


def test_edit_after_signing_invalidates():
    signed = signing.sign(_doc(), signer="Alice", secret=_SECRET)
    run = next(n for n in signed.nodes.values() if n.type == "run")
    run.text = "tampered body"
    assert signing.verify(signed, secret=_SECRET) is False


def test_wrong_secret_fails_verification():
    signed = signing.sign(_doc(), signer="Alice", secret=_SECRET)
    assert signing.verify(signed, secret="attacker-secret") is False
