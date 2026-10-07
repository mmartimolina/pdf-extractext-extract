from typing import Protocol

from src.domain.errors import InvalidPdfError, PdfTooLargeError
from src.domain.models import ExtractedText

PDF_MAGIC = b"%PDF-"


class TextExtractor(Protocol):
    def extract(self, pdf_bytes: bytes) -> ExtractedText: ...


class ExtractionService:
    """Application service: validates input and delegates text extraction."""

    def __init__(self, extractor: TextExtractor, max_pdf_size_bytes: int) -> None:
        self._extractor = extractor
        self._max_pdf_size_bytes = max_pdf_size_bytes

    def extract_text(self, pdf_bytes: bytes) -> ExtractedText:
        if len(pdf_bytes) > self._max_pdf_size_bytes:
            raise PdfTooLargeError(
                f"PDF size {len(pdf_bytes)} bytes exceeds limit of "
                f"{self._max_pdf_size_bytes} bytes"
            )
        if not pdf_bytes.startswith(PDF_MAGIC):
            raise InvalidPdfError("The uploaded file is not a valid PDF")
        return self._extractor.extract(pdf_bytes)
