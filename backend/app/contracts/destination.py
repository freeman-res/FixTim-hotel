from pydantic import BaseModel, Field
from typing import Optional

class DestinationOption(BaseModel):
    destination_id: str
    name: str
    country: Optional[str] = None
    vibe_tags: list[str] = Field(default_factory=list)
    flight_time_hours: Optional[float] = None
    # По ТЗ (п. 3): обязательно указываем источник и тип данных
    source_type: str = "demo" 
    source_name: Optional[str] = None