from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes.health import router as health_router
from api.routes.ingest import router as ingest_router
from api.routes.query import router as query_router
from api.routes.system import router as system_router
from api.schemas.common import ErrorResponse
from api.services.errors import ApiServiceError, ResourceNotFoundError

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="RAG Backend API", version="0.1.0")

    cors_origins = [
        origin.strip()
        for origin in os.getenv(
            "API_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(query_router)
    app.include_router(ingest_router)
    app.include_router(system_router)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="Validation failed",
                details=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(ApiServiceError)
    async def handle_service_error(request: Request, exc: ApiServiceError) -> JSONResponse:
        status_code = 404 if isinstance(exc, ResourceNotFoundError) else 400
        return JSONResponse(
            status_code=status_code,
            content=ErrorResponse(
                error=exc.message,
                details=exc.details,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Unexpected server error",
                details=str(exc),
            ).model_dump(),
        )

    return app


app = create_app()
