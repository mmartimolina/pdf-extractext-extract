import io

from pypdf import PdfReader

from src.domain.errors import InvalidPdfError
from src.domain.models import ExtractedText


class PypdfTextExtractor:
    """Infrastructure adapter: extracts text from PDF bytes using pypdf."""

    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            if reader.is_encrypted:
                raise InvalidPdfError("The uploaded PDF is password-protected")
            page_count = len(reader.pages)
            text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            ).strip()
        except InvalidPdfError:
            raise
        except Exception as exc:
            raise InvalidPdfError("The uploaded file is not a valid PDF") from exc
        return ExtractedText(text=text, page_count=page_count)
