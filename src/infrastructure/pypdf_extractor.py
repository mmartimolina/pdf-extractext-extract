import pymupdf

from src.domain.errors import InvalidPdfError
from src.domain.models import ExtractedText


class PypdfTextExtractor:
    """Infrastructure adapter: extracts text from PDF bytes using PyMuPDF."""

    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        try:
            document = pymupdf.open(stream=pdf_bytes, filetype="pdf")

            if document.is_encrypted:
                document.close()
                raise InvalidPdfError("The uploaded PDF is password-protected")

            page_count = document.page_count
            text = "\n".join(
                page.get_text() or "" for page in document
            ).strip()

            document.close()

        except InvalidPdfError:
            raise
        except Exception as exc:
            raise InvalidPdfError(
                "The uploaded file is not a valid PDF"
            ) from exc

        return ExtractedText(
            content=text,
            page_count=page_count,
        )