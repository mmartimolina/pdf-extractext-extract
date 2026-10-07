import asyncio

import pytest

from src.api.routes import read_body_with_limit
from src.domain.errors import PdfTooLargeError


class FakeRequest:
    def __init__(self, chunks: list[bytes], headers: dict[str, str] | None = None):
        self._chunks = chunks
        self.headers = headers or {}

    async def stream(self):
        for chunk in self._chunks:
            yield chunk


def test_declared_content_length_over_limit_is_rejected_early():
    chunks_read: list[bytes] = []

    async def stream():
        raise AssertionError("stream must not be read when Content-Length is over the limit")
        yield b""

    request = FakeRequest(chunks=[b"x"], headers={"content-length": "999999999"})
    request.stream = stream

    with pytest.raises(PdfTooLargeError):
        asyncio.run(read_body_with_limit(request, 100))


def test_streaming_body_over_limit_is_capped_without_content_length():
    request = FakeRequest(chunks=[b"chunk-"] * 10)

    with pytest.raises(PdfTooLargeError, match="exceeds"):
        asyncio.run(read_body_with_limit(request, 20))


def test_unparseable_content_length_falls_back_to_streaming():
    request = FakeRequest(
        chunks=[b"abc", b"def"], headers={"content-length": "!bad!"}
    )

    body = asyncio.run(read_body_with_limit(request, 100))

    assert body == b"abcdef"
