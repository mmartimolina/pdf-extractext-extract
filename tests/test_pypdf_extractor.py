import pytest

from src.domain.errors import InvalidPdfError
from src.infrastructure.pypdf_extractor import PypdfTextExtractor


def test_adapter_extracts_text_and_page_count(valid_pdf_bytes):
    extractor = PypdfTextExtractor()

    result = extractor.extract(valid_pdf_bytes)

    assert "Hello World" in result.content
    assert result.page_count == 2


def test_adapter_raises_invalid_pdf_on_garbage():
    extractor = PypdfTextExtractor()

    with pytest.raises(InvalidPdfError):
        extractor.extract(b"%PDF-1.4\nTotallyBroken" + b"\x00" * 50)


def test_adapter_raises_clear_error_on_encrypted_pdf(valid_pdf_bytes, encrypt_pdf):
    extractor = PypdfTextExtractor()

    with pytest.raises(InvalidPdfError, match="password-protected"):
        extractor.extract(encrypt_pdf(valid_pdf_bytes))
