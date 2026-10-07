import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.routes import router
from src.config import load_settings
from src.infrastructure.pypdf_extractor import PypdfTextExtractor
from src.service.extraction import ExtractionService

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="pdf-extractext-extract")
    app.state.settings = settings
    app.state.extraction_service = ExtractionService(
        extractor=PypdfTextExtractor(),
        max_pdf_size_bytes=settings.max_pdf_size_bytes,
    )
    app.include_router(router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()
