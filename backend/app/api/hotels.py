from fastapi import APIRouter, HTTPException
from backend.app.catalog.service import get_catalog_gateway

router = APIRouter(prefix="/api/v1", tags=["hotels"])


@router.get("/hotels/{hotel_id}")
async def get_hotel(hotel_id: str):
    """Return a catalog record without inventing offer or booking details."""
    hotel = await get_catalog_gateway().get_hotel(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=404, detail="Отель не найден")
    return hotel
