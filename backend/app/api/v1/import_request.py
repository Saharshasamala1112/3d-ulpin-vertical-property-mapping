from __future__ import annotations

from fastapi import HTTPException, Request, status
from pydantic import ValidationError

from app.schemas.geojson_import import MAX_IMPORT_BYTES, GeoJSONFeatureCollection


async def read_feature_collection(request: Request) -> GeoJSONFeatureCollection:
    """Read a GeoJSON body with a hard byte limit before decoding it."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"application/json", "application/geo+json"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error": {
                    "code": "UNSUPPORTED_MEDIA_TYPE",
                    "message": "Send a GeoJSON JSON body.",
                }
            },
        )

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_CONTENT_LENGTH",
                        "message": "Invalid Content-Length header.",
                    }
                },
            ) from None
        if declared_size < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_CONTENT_LENGTH",
                        "message": "Content-Length cannot be negative.",
                    }
                },
            )
        if declared_size > MAX_IMPORT_BYTES:
            raise _too_large()

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_IMPORT_BYTES:
            raise _too_large()
        body.extend(chunk)

    try:
        return GeoJSONFeatureCollection.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Expected a GeoJSON FeatureCollection with 1 to 500 features.",
                }
            },
        ) from exc


def _too_large() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        detail={
            "error": {
                "code": "IMPORT_TOO_LARGE",
                "message": (
                    f"GeoJSON request exceeds the {MAX_IMPORT_BYTES // (1024 * 1024)} MiB limit."
                ),
            }
        },
    )
