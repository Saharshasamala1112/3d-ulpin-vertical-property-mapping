from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Mapping
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import (
    auth,
    buildings,
    floors,
    geometry,
    health,
    ownership,
    parcels,
    topology,
    units,
    vdc,
)
from app.core.config import settings
from app.core.database import engine
from app.schemas.error import (
    ERROR_CODE_CONFLICT,
    ERROR_CODE_INTERNAL_ERROR,
    ERROR_CODE_NOT_FOUND,
    ERROR_CODE_VALIDATION_ERROR,
)

logger = logging.getLogger("geosix")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Verify database connectivity before accepting requests."""

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    yield


def _setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    _setup_logging(debug=settings.debug)

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
        lifespan=lifespan,
        openapi_tags=[
            {"name": "Health", "description": "Service health and status"},
            {
                "name": "Authentication",
                "description": "User registration, login, and token management",
            },
            {
                "name": "Parcels",
                "description": "Parcel and ULPIN management — CRUD with GeoJSON spatial data",
            },
            {
                "name": "Buildings",
                "description": (
                    "Building management within parcels — CRUD with optional footprint geometry"
                ),
            },
            {
                "name": "Floors",
                "description": "Floor management within buildings — CRUD with elevation data",
            },
            {
                "name": "Units",
                "description": (
                    "Unit management within floors — CRUD with bounding-box data and VDC lookup"
                ),
            },
            {
                "name": "Geometry",
                "description": "Read and replace persisted 3D bounding-box geometry for units",
            },
            {
                "name": "Topology",
                "description": "Read-only 3D geometry, overlap, gap, and elevation validation",
            },
            {
                "name": "VDC",
                "description": (
                    "Vertical DNA Code generation, validation and parsing — pure, "
                    "deterministic and idempotent operations with no persistence"
                ),
            },
            {
                "name": "Ownership",
                "description": "Project ownership allocations and effective-dated history",
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
    app.include_router(health.router, prefix="/api", tags=["Health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(
        parcels.router,
        prefix="/api/v1/parcels",
        tags=["Parcels"],
        responses={
            404: {
                "description": "Not found",
                "content": {
                    "application/json": {
                        "example": {"error": {"code": "NOT_FOUND", "message": "Resource not found"}}
                    }
                },
            },
        },
    )
    app.include_router(buildings.router, prefix="/api/v1", tags=["Buildings"])
    app.include_router(floors.router, prefix="/api/v1", tags=["Floors"])
    app.include_router(units.router, prefix="/api/v1", tags=["Units"])
    app.include_router(geometry.router, prefix="/api/v1", tags=["Geometry"])
    app.include_router(vdc.router, prefix="/api/v1/vdc", tags=["VDC"])
    app.include_router(ownership.router, prefix="/api/v1/ownership", tags=["Ownership"])
    app.include_router(topology.router, prefix="/api/v1/topology", tags=["Topology"])

    @app.get("/api/health", tags=["Health"])
    async def legacy_health_check():
        return {"status": "ok", "service": "geosix-api"}

    @app.get("/api/v1", tags=["Root"])
    async def root():
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "redoc": "/redoc",
        }

    # ------------------------------------------------------------------
    # Standardized error responses
    # ------------------------------------------------------------------
    def _standard_error_response(
        status_code: int,
        error_code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> JSONResponse:
        # `headers` must be forwarded. Several statuses carry protocol
        # information in them rather than metadata: dropping them turns a 429
        # into one with no Retry-After and a 401 into one with no
        # WWW-Authenticate, both of which change how a client must behave.
        return JSONResponse(
            status_code=status_code,
            content={
                "error_code": error_code,
                "message": message,
                "details": details or {},
            },
            headers=dict(headers) if headers else None,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            err = exc.detail["error"]
            code = err.get("code", ERROR_CODE_NOT_FOUND)
            message = err.get("message", str(exc.detail))
            details = err.get("details", {})
        else:
            code = None
            message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            details = {}

        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return _standard_error_response(
                status.HTTP_404_NOT_FOUND,
                code or ERROR_CODE_NOT_FOUND,
                message if code else "The requested resource was not found",
                details,
                exc.headers,
            )
        if exc.status_code == status.HTTP_409_CONFLICT:
            return _standard_error_response(
                status.HTTP_409_CONFLICT,
                code or ERROR_CODE_CONFLICT,
                message,
                details,
                exc.headers,
            )
        if exc.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT and code:
            return _standard_error_response(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                code,
                message,
                details,
                exc.headers,
            )
        if code and exc.status_code not in {
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        }:
            return _standard_error_response(exc.status_code, code, message, details, exc.headers)
        # Preserve the existing legacy body for all other statuses,
        # including the authentication 401/403 responses.
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        details: dict[str, Any] = {}
        for error in exc.errors():
            location = list(error.get("loc", ()))
            if location and location[0] in ("body", "query", "path", "header", "cookie"):
                location = location[1:]
            field = ".".join(str(part) for part in location) or "request"
            details[field] = str(error.get("msg", "Invalid value"))
        return _standard_error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ERROR_CODE_VALIDATION_ERROR,
            "Request validation failed",
            details,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "Unhandled exception request_id=%s method=%s path=%s: %s",
            request_id,
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )
        response = _standard_error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            ERROR_CODE_INTERNAL_ERROR,
            "Internal server error",
        )
        response.headers["X-Request-ID"] = request_id
        return response  # ------------------------------------------------------------------

    # OpenAPI documentation for the standardized error contract
    # ------------------------------------------------------------------
    legacy_error_component = "LegacyAuthErrorResponse"
    standard_error_ref = "#/components/schemas/ErrorResponse"

    def _rewrite_schema_refs(node: Any, old_ref: str, new_ref: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "$ref" and value == old_ref:
                    node[key] = new_ref
                else:
                    _rewrite_schema_refs(value, old_ref, new_ref)
        elif isinstance(node, list):
            for item in node:
                _rewrite_schema_refs(item, old_ref, new_ref)

    def _standard_error_ref_response(description: str) -> dict[str, Any]:
        return {
            "description": description,
            "content": {
                "application/json": {
                    "schema": {"$ref": standard_error_ref},
                }
            },
        }

    def _normalize_error_docs(schema: dict[str, Any]) -> None:
        schemas = schema.setdefault("components", {}).setdefault("schemas", {})
        generated_legacy = None
        for name, component in schemas.items():
            properties = component.get("properties", {}) if isinstance(component, dict) else {}
            if (
                isinstance(properties, dict)
                and "error" in properties
                and "error_code" not in properties
            ):
                generated_legacy = name
                break
        if generated_legacy is not None and generated_legacy != legacy_error_component:
            schemas[legacy_error_component] = schemas.pop(generated_legacy)
            _rewrite_schema_refs(
                schema,
                f"#/components/schemas/{generated_legacy}",
                f"#/components/schemas/{legacy_error_component}",
            )
        schemas["ErrorResponse"] = {
            "properties": {
                "error_code": {"title": "Error Code", "type": "string"},
                "message": {"title": "Message", "type": "string"},
                "details": {"title": "Details", "type": "object"},
            },
            "required": ["error_code", "message"],
            "title": "ErrorResponse",
            "type": "object",
        }
        for path, path_item in schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if not isinstance(operation, dict):
                    continue
                responses = operation.setdefault("responses", {})
                responses.setdefault("404", _standard_error_ref_response("Not found"))
                responses.setdefault(
                    "500",
                    _standard_error_ref_response("Internal server error"),
                )
                if "409" in responses:
                    responses["409"] = _standard_error_ref_response("Conflict")
                if "requestBody" in operation or operation.get("parameters"):
                    responses["422"] = _standard_error_ref_response("Validation error")

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
            servers=app.servers,
            tags=app.openapi_tags,
        )
        _normalize_error_docs(schema)
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
    return app


app = create_app()
