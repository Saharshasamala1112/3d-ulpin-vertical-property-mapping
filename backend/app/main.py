from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, health
from app.core.config import settings

logger = logging.getLogger("geosix")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=settings.app_name,
        description=(
            "GEOSIX — A Layered Vertical-Cadastre Engine for 3D ULPIN Generation "
            "& Volumetric Property Governance. This API provides endpoints for "
            "parcel management, building/floor/unit hierarchy, VDC generation, "
            "and 3D cadastral topology validation."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {"name": "Health", "description": "Service health and status"},
            {
                "name": "Authentication",
                "description": "User registration, login, and token management",
            },
            {"name": "Root", "description": "API metadata and version information"},
        ],
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID and timing middleware
    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
        logger.info(
            "%s %s %s %s %.2fms",
            request_id[:8],
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    # Routers
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])

    @app.get("/api/v1", tags=["Root"])
    async def root():
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "redoc": "/redoc",
        }

    return app


app = create_app()
