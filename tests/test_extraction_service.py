import pytest

from src.domain.errors import InvalidPdfError, PdfTooLargeError
from src.domain.models import ExtractedText
from src.service.extraction import ExtractionService


class FakeExtractor:
    def __init__(self):
        self.received: bytes | None = None

    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        self.received = pdf_bytes
        return ExtractedText(content="fake text", page_count=3)


def make_service(max_size: int = 1024) -> tuple[ExtractionService, FakeExtractor]:
    extractor = FakeExtractor()
    return ExtractionService(extractor=extractor, max_pdf_size_bytes=max_size), extractor


def test_service_delegates_to_extractor():
    service, extractor = make_service()
    payload = b"%PDF-1.4 something"

    result = service.extract_text(payload)

    assert extractor.received == payload
    assert result == ExtractedText(content="fake text", page_count=3)


def test_service_rejects_payload_over_size_limit():
    service, extractor = make_service(max_size=10)

    with pytest.raises(PdfTooLargeError):
        service.extract_text(b"%PDF-1.4 way too long")

    assert extractor.received is None


def test_service_rejects_non_pdf_magic_bytes():
    service, extractor = make_service()

    with pytest.raises(InvalidPdfError):
        service.extract_text(b"NOPE not a pdf")

    assert extractor.received is None
