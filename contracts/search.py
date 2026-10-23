"""
Контракт фильтров поиска. SearchFilters — то, что приходит в функцию find_offers.
AI-агент (участник №2) извлекает эти поля из текста пользователя в query_parser.py и передаёт сюда.
"""
from pydantic import BaseModel, Field
from typing import Optional
class SearchFilters(BaseModel):
    """
    Параметры поиска отелей.Все поля Optional
    Функция find_offers должна корректно обрабатывать None.
    """
    city: Optional[str] = None
    """Город, например "Сочи"."""
    check_in: Optional[str] = None
    """Дата заезда (ISO или как пришло)."""
    check_out: Optional[str] = None
    """Дата выезда."""
    guests: Optional[int] = None
    """Количество гостей."""
    price_max: Optional[float] = None
    """Максимальная цена проживания (бюджет пользователя)."""
    rating_min: Optional[float] = None
    """Минимальный рейтинг отеля."""
    amenities: list[str] = Field(default_factory=list)
    """Требуемые удобства: ["бассейн", "завтрак"]."""
    query: Optional[str] = None
    """
    Свободный текстовый запрос для семантического поиска.
        """