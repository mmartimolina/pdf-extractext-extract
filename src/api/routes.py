from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from src.domain.errors import InvalidPdfError, PdfTooLargeError

router = APIRouter()

PDF_CONTENT_TYPES = {"application/pdf"}


async def read_body_with_limit(request: Request, limit: int) -> bytes:
    """Reject early via Content-Length, then read the stream bounded to `limit`."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            declared = 0
        if declared > limit:
            raise PdfTooLargeError(
                f"PDF size {declared} bytes exceeds limit of {limit} bytes"
            )

    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise PdfTooLargeError(
                f"PDF size exceeds limit of {limit} bytes"
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/extract")
async def extract(request: Request) -> JSONResponse:
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type not in PDF_CONTENT_TYPES:
        return JSONResponse(
            status_code=415,
            content={"detail": "Content-Type must be application/pdf"},
        )

    max_size = request.app.state.settings.max_pdf_size_bytes
    try:
        body = await read_body_with_limit(request, max_size)
    except PdfTooLargeError as exc:
        return JSONResponse(status_code=413, content={"detail": str(exc)})

    if not body:
        return JSONResponse(
            status_code=400,
            content={"detail": "Request body is empty"},
        )

    service = request.app.state.extraction_service
    try:
        result = await run_in_threadpool(service.extract_text, body)
    except PdfTooLargeError as exc:
        return JSONResponse(status_code=413, content={"detail": str(exc)})
    except InvalidPdfError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return JSONResponse(
        status_code=200,
        content={"content": result.content, "page_count": result.page_count},
    )
