from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Report that the API process is serving requests.

    CORS is *not* hardcoded here. The response deliberately carries no
    ``Access-Control-Allow-Origin`` of its own: the application's
    ``CORSMiddleware`` (configured through ``CORS_ORIGINS``) is the single source
    of truth, and an endpoint that pinned ``http://localhost:5173`` would keep
    advertising a development origin from inside a production deployment.
    """
    return {"status": "ok", "service": "geosix-api"}
