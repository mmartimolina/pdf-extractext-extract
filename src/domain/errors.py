class PdfExtractionError(Exception):
    """Base error for PDF extraction failures."""


class InvalidPdfError(PdfExtractionError):
    """The provided bytes are not a valid or readable PDF."""


class PdfTooLargeError(PdfExtractionError):
    """The provided PDF exceeds the configured size limit."""
