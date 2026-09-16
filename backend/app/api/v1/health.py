from fastapi import APIRouter, Response

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health")
async def health_check(response: Response):
    response.headers["Access-Control-Allow-Origin"] = "http://localhost:5173"
    return {"status": "ok", "service": "geosix-api"}
