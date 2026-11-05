
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class ChatRequest(BaseModel):
    """Проверяет сообщение, которое присылает frontend."""

    model_config = ConfigDict(str_strip_whitespace=True)

    session_id: Optional[str] = Field(
        default=None,
        description="ID существующей сессии или null для новой",
    )
    message: str = Field(
        min_length=1,
        max_length=4000,
        description="Новое сообщение пользователя",
    )
    action: Optional[Literal["select_destination", "select_hotel", "select_transport",
                             "search_return_transport", "select_return_transport"]] = None
    target_id: Optional[str] = Field(default=None, min_length=1, max_length=128)


class HotelCard(BaseModel):
    """Публичная карточка; optional facts stay optional when source lacks them."""

    model_config = ConfigDict(extra="allow")

    hotel_id: str
    name: str
    price: Optional[float] = None
    currency: Optional[str] = None
    total_price: Optional[float] = None
    city: Optional[str] = None
    address: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    stars: Optional[int] = None
    rating: Optional[float] = None
    amenities: List[str] = Field(default_factory=list)
    amenities_data: Dict[str, Any] = Field(default_factory=dict)
    price_details: Optional[Dict[str, Any]] = None
    availability: Dict[str, Any] = Field(default_factory=lambda: {"status": "unknown"})
    source: Optional[Dict[str, Any]] = None
    is_demo: bool = False
    reason: Optional[str] = None
    match_score: Optional[float] = None


class ChatResponse(BaseModel):
    """Публичный ответ backend."""

    session_id: str
    status: Literal[
        "clarification",
        "results",
        "no_results",
        "error",
    ]
    reply: str
    hotels: List[HotelCard] = Field(default_factory=list)


    state: Dict[str, Any] = Field(default_factory=dict)


    stage: Optional[str] = None
    destinations: List[Dict[str, Any]] = Field(default_factory=list)
    transport_options: List[Dict[str, Any]] = Field(default_factory=list)
    weather: Optional[Dict[str, Any]] = None
    itinerary: Optional[Dict[str, Any]] = None
    cart: Optional[Dict[str, Any]] = None
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    is_demo: bool = False
