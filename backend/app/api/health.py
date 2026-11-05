from fastapi import APIRouter

from backend.app.catalog.service import get_catalog_gateway

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health():
    catalog = get_catalog_gateway()
    return {
        "status": "ok",
        "service": "backend",
        "agent": "configured",
        "catalog": await catalog.get_data_status(),
    }
