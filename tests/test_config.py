import pytest

from src.config import DEFAULT_MAX_PDF_SIZE_BYTES, load_settings


def test_default_max_pdf_size_is_20_mb(monkeypatch):
    monkeypatch.delenv("MAX_PDF_SIZE_BYTES", raising=False)

    settings = load_settings()

    assert settings.max_pdf_size_bytes == 20 * 1024 * 1024
    assert settings.max_pdf_size_bytes == DEFAULT_MAX_PDF_SIZE_BYTES


def test_max_pdf_size_is_configurable(monkeypatch):
    monkeypatch.setenv("MAX_PDF_SIZE_BYTES", "1024")

    assert load_settings().max_pdf_size_bytes == 1024


def test_invalid_max_pdf_size_raises(monkeypatch):
    monkeypatch.setenv("MAX_PDF_SIZE_BYTES", "not-a-number")

    with pytest.raises(ValueError):
        load_settings()
