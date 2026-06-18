"""ClamAV INSTREAM client — framing and verdict parsing, against a fake socket."""

from __future__ import annotations

import socket

import pytest

from docos.services.ingestion.scanner import ClamAVScanner


class _FakeSocket:
    def __init__(self, reply: bytes) -> None:
        self.reply = reply
        self.sent = bytearray()
        self._served = False

    def __enter__(self) -> _FakeSocket:
        return self

    def __exit__(self, *_a) -> bool:
        return False

    def settimeout(self, _t) -> None:
        pass

    def sendall(self, b) -> None:
        self.sent += bytes(b)

    def recv(self, _n) -> bytes:
        if self._served:
            return b""
        self._served = True
        return self.reply


@pytest.fixture
def fake_conn(monkeypatch):
    holder: dict[str, _FakeSocket] = {}

    def _factory(reply: bytes):
        def _create_connection(*_a, **_k):
            sock = _FakeSocket(reply)
            holder["sock"] = sock
            return sock

        monkeypatch.setattr(socket, "create_connection", _create_connection)
        return holder

    return _factory


async def test_clean_verdict(fake_conn):
    holder = fake_conn(b"stream: OK\x00")
    result = await ClamAVScanner().scan(b"hello")
    assert result.clean is True
    # Stream was framed: INSTREAM command, a chunk, then the zero-length terminator.
    assert holder["sock"].sent.startswith(b"zINSTREAM\x00")
    assert holder["sock"].sent.endswith(b"\x00\x00\x00\x00")


async def test_infected_verdict_extracts_signature(fake_conn):
    fake_conn(b"stream: Eicar-Test-Signature FOUND\x00")
    result = await ClamAVScanner().scan(b"x" * 100)
    assert result.clean is False
    assert result.signature == "Eicar-Test-Signature"


async def test_protocol_error_raises(fake_conn):
    fake_conn(b"INSTREAM size limit exceeded ERROR\x00")
    with pytest.raises(RuntimeError):
        await ClamAVScanner().scan(b"x")
