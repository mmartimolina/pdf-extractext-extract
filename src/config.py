import os
from dataclasses import dataclass

DEFAULT_MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


@dataclass(frozen=True)
class Settings:
    max_pdf_size_bytes: int = DEFAULT_MAX_PDF_SIZE_BYTES


def load_settings() -> Settings:
    raw = os.environ.get("MAX_PDF_SIZE_BYTES")
    if raw is None:
        return Settings()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(
            f"MAX_PDF_SIZE_BYTES must be an integer, got {raw!r}"
        ) from exc
    if value <= 0:
        raise ValueError("MAX_PDF_SIZE_BYTES must be positive")
    return Settings(max_pdf_size_bytes=value)
