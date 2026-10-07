import io

import pytest
from pypdf import PdfReader, PdfWriter


def build_pdf(text: str = "Hello World", pages: int = 1) -> bytes:
    """Build a minimal but valid PDF containing the given text on each page."""
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    kids = " ".join(f"{3 + i} 0 R" for i in range(pages))
    objects.append(
        f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode()
    )

    font_obj_num = 3 + pages * 2
    for i in range(pages):
        content_obj_num = 3 + pages + i
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_obj_num} 0 R "
                f"/Resources << /Font << /F1 {font_obj_num} 0 R >> >> >>"
            ).encode()
        )

    stream = f"BT /F1 24 Tf 100 700 Td ({text}) Tj ET".encode()
    for _ in range(pages):
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
            + stream + b"\nendstream"
        )

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for num, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{num} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    ).encode()
    return bytes(out)


@pytest.fixture
def valid_pdf_bytes() -> bytes:
    return build_pdf("Hello World", pages=2)


def _encrypt_pdf(pdf_bytes: bytes, password: str = "secret") -> bytes:
    """Encrypt an existing PDF with a user password."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=password)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def encrypt_pdf():
    return _encrypt_pdf
