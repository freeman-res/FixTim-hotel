from typing import Any, Literal
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator

Intent = Literal[
    "inspiration", "hotel_search", "trip_search", "details", "compare",
    "replan", "itinerary", "checkout", "weather", "chat"
]


ClearableField = Literal[
    "city", "destination_id", "origin_city", "check_in", "check_out", "return_date",
    "nights", "travel_month", "travel_year", "flexible_dates",
    "guests", "adults", "children", "pets", "max_total_price",
    "max_total_budget", "currency", "transport_mode", "max_travel_hours",
]


class TripPatch(BaseModel):
    """Частичное изменение параметров: отсутствие поля означает «не трогать»."""
    model_config = ConfigDict(extra="forbid")
    new_trip: bool = False
    intent: Intent | None = None

    city: str | None = None
    check_in: str | None = None
    check_out: str | None = None
    return_date: str | None = None
    nights: int | None = Field(default=None, ge=1, le=365)
    guests: int | None = Field(default=None, ge=1, le=30)
    max_total_price: float | None = Field(default=None, gt=0)
    currency: str | None = None
    required_amenities: list[str] | None = None
    preferences: list[str] | None = None
    remove_required_amenities: list[str] = Field(default_factory=list)
    remove_preferences: list[str] = Field(default_factory=list)
    reject_hotel_ids: list[str] = Field(default_factory=list)
    reject_result_numbers: list[int] = Field(default_factory=list)

    origin_city: str | None = None
    destination_id: str | None = None
    travel_month: int | None = Field(default=None, ge=1, le=12)
    travel_year: int | None = Field(default=None, ge=2020, le=2100)
    flexible_dates: str | None = None
    adults: int | None = Field(default=None, ge=1, le=30)
    children: int | None = Field(default=None, ge=0, le=20)
    pets: bool | None = None
    max_total_budget: float | None = Field(default=None, gt=0)
    transport_mode: Literal["flight", "train", "bus", "any"] | None = None
    max_travel_hours: float | None = Field(default=None, gt=0, le=120)
    shift_days: int | None = Field(default=None, ge=-365, le=365)
    clear_fields: list[ClearableField] = Field(default_factory=list)

    @field_validator("check_in", "check_out", "return_date")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        if value:
            date.fromisoformat(value)
        return value


class AgentResponse(BaseModel):
    status: Literal["clarification", "results", "no_results", "error"]
    reply: str
    hotels: list[dict[str, Any]] = Field(default_factory=list)
    updated_state: dict[str, Any] = Field(default_factory=dict)

    stage: str | None = None
    destinations: list[dict[str, Any]] = Field(default_factory=list)
    transport_options: list[dict[str, Any]] = Field(default_factory=list)
    weather: dict[str, Any] | None = None
    itinerary: dict[str, Any] | None = None
    cart: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


class SearchFilters(BaseModel):
    """Фильтры гостиниц; бюджет поездки сюда НЕ передаём как бюджет отеля."""
    model_config = ConfigDict(extra="forbid")
    city: str | None = None
    check_in: str | None = None
    check_out: str | None = None
    guests: int | None = Field(default=None, ge=1)
    max_total_price: float | None = Field(default=None, gt=0)
    currency: str | None = None
    required_amenities: list[str] = Field(default_factory=list)


class SearchHotelsArgs(BaseModel):
    filters: SearchFilters
    preferences: list[str] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=10)


class HotelDetailsArgs(BaseModel):
    hotel_id: str

    @field_validator("hotel_id", mode="before")
    @classmethod
    def normalize_id(cls, value):
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value)
        raise ValueError("Не задан идентификатор отеля")


class SearchReviewsArgs(BaseModel):
    hotel_ids: list[str] = Field(min_length=1, max_length=10)
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("hotel_ids", mode="before")
    @classmethod
    def normalize_ids(cls, values):
        if isinstance(values, list):
            return [str(v) for v in values if isinstance(v, (str, int))]
        return values


class SearchTransportArgs(BaseModel):
    from_city: str | None = None
    to_city: str | None = None
    type: Literal["plane", "flight", "bus", "train", "any"] | None = None
    date_from: str | None = None
    date_to: str | None = None
    max_price: float | None = Field(default=None, gt=0)
    limit: int = Field(default=10, ge=1, le=30)


class WeatherArgs(BaseModel):
    city: str | None = None
    destination_id: str | None = None
    target_date: str | None = None
    month: int | None = Field(default=None, ge=1, le=12)

    @field_validator("target_date")
    @classmethod
    def validate_target_date(cls, value: str | None) -> str | None:
        if value:
            date.fromisoformat(value)
        return value


class SearchHotelDescriptionsArgs(BaseModel):
    query: str = Field(min_length=1)
    hotel_ids: list[str] = Field(default_factory=list, max_length=100)
    top_k: int = Field(default=5, ge=1, le=20)


class CompareHotelsArgs(BaseModel):
    hotel_ids: list[str] = Field(min_length=2, max_length=5)
    preferences: list[str] = Field(default_factory=list)

    @field_validator("hotel_ids", mode="before")
    @classmethod
    def normalize_ids(cls, values):
        if isinstance(values, list):
            return [str(v) for v in values if isinstance(v, (str, int))]
        return values
