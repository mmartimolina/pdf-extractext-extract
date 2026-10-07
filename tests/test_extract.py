from fastapi.testclient import TestClient

from src.main import create_app


def make_client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


def test_extract_returns_text_and_page_count(valid_pdf_bytes):
    with make_client() as client:
        response = client.post(
            "/extract",
            content=valid_pdf_bytes,
            headers={"Content-Type": "application/pdf"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "Hello World" in data["content"]
    assert data["page_count"] == 2


def test_extract_rejects_wrong_content_type(valid_pdf_bytes):
    with make_client() as client:
        response = client.post(
            "/extract",
            content=valid_pdf_bytes,
            headers={"Content-Type": "text/plain"},
        )

    assert response.status_code == 415


def test_extract_rejects_missing_content_type(valid_pdf_bytes):
    with make_client() as client:
        response = client.post(
            "/extract",
            content=valid_pdf_bytes,
            headers={"Content-Type": ""},
        )

    assert response.status_code == 415


def test_extract_rejects_invalid_pdf():
    with make_client() as client:
        response = client.post(
            "/extract",
            content=b"this is not a pdf at all, just garbage bytes",
            headers={"Content-Type": "application/pdf"},
        )

    assert response.status_code == 400


def test_extract_rejects_corrupt_pdf():
    corrupt = b"%PDF-1.4\n" + b"\x00\xff" * 100
    with make_client() as client:
        response = client.post(
            "/extract",
            content=corrupt,
            headers={"Content-Type": "application/pdf"},
        )

    assert response.status_code == 400


def test_extract_rejects_empty_body():
    with make_client() as client:
        response = client.post(
            "/extract",
            content=b"",
            headers={"Content-Type": "application/pdf"},
        )

    assert response.status_code == 400


def test_extract_rejects_encrypted_pdf_with_clear_message(valid_pdf_bytes, encrypt_pdf):
    with make_client() as client:
        response = client.post(
            "/extract",
            content=encrypt_pdf(valid_pdf_bytes),
            headers={"Content-Type": "application/pdf"},
        )

    assert response.status_code == 400
    assert "password-protected" in response.json()["detail"]


def test_extract_rejects_pdf_over_size_limit(valid_pdf_bytes, monkeypatch):
    monkeypatch.setenv("MAX_PDF_SIZE_BYTES", "100")
    with make_client() as client:
        response = client.post(
            "/extract",
            content=valid_pdf_bytes,
            headers={"Content-Type": "application/pdf"},
        )

    assert response.status_code == 413
