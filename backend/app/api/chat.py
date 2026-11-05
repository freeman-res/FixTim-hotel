from fastapi import APIRouter, HTTPException
from ..contracts.chat import ChatRequest, ChatResponse, HotelCard
from ..sessions.service import session_service
from ..services.agent_service import handle_action, handle_message
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])

_PUBLIC_TRIP_FIELDS = {
    "city", "destination_id", "origin_city", "check_in", "check_out", "return_date",
    "nights", "travel_month", "travel_year", "flexible_dates", "guests",
    "adults", "children", "pets", "max_total_price", "max_total_budget",
    "currency", "transport_mode", "required_amenities", "preferences",
}
_PUBLIC_SELECTION_FIELDS = {
    "hotel_offer_id", "hotel_name", "outbound_transport_id",
    "return_transport_id", "transfer_id",
}


def _public_state(state: dict) -> dict:
    """Expose UI progress without provider payloads or internal message history."""
    trip = state.get("trip") if isinstance(state.get("trip"), dict) else {}
    selected = state.get("selected") if isinstance(state.get("selected"), dict) else {}
    return {
        "trip": {key: value for key, value in trip.items() if key in _PUBLIC_TRIP_FIELDS},
        "selected": {key: value for key, value in selected.items()
                     if key in _PUBLIC_SELECTION_FIELDS},
        "last_intent": state.get("last_intent"),
        "changed_fields": state.get("changed_fields") or [],
        "needs_replan": bool(state.get("needs_replan")),
        "demo_booking_id": state.get("demo_booking_id"),
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Главный эндпоинт.
    Принимает сообщение → вызывает агента → сохраняет всё → отдаёт ответ.
    """

    if request.action and (not request.session_id or not request.target_id):
        raise HTTPException(status_code=400, detail="Для выбора карточки нужны session_id и target_id")


    if request.session_id:
        session = session_service.get_session(request.session_id)
        if not session:
            if request.action:
                raise HTTPException(status_code=404, detail="Сессия не найдена")
            session_id = session_service.create_session()
            state = {}
        else:
            session_id = request.session_id
            state = session.get("state", {})
    else:
        session_id = session_service.create_session()
        state = {}


    session_service.add_message(
        session_id=session_id,
        role="user",
        content=request.message
    )


    try:
        if request.action:
            agent_response = await handle_action(
                request.action, request.target_id, state, request.message)
        else:
            agent_response = await handle_message(
                session_id=session_id,
                message=request.message,
                state=state,
            )
    except Exception:


        logger.exception(
            "Agent call failed for session_id=%s",
            session_id,
        )

        error_reply = (
            "Не удалось обработать сообщение. "
            "Попробуйте ещё раз."
        )

        session_service.add_message(
            session_id=session_id,
            role="assistant",
            content=error_reply,
        )

        return ChatResponse(
            session_id=session_id,
            status="error",
            reply=error_reply,
            hotels=[],
            state=_public_state(state),
        )



    session_service.add_message(
        session_id=session_id,
        role="assistant",
        content=agent_response.reply
    )
    session_service.update_state(session_id, agent_response.updated_state)


    hotels = []
    for hotel in agent_response.hotels:
        item = dict(hotel)
        item.pop("catalog_city_filter_applied", None)
        item["price_details"] = item.get("price") if isinstance(item.get("price"), dict) else None
        item["price"] = item.get("total_price")
        hotels.append(HotelCard.model_validate(item))

    transport_options = [item for item in agent_response.transport_options if isinstance(item, dict)]
    is_demo = bool(agent_response.cart and agent_response.cart.get("is_demo")) or any(item.is_demo for item in hotels) or any(
        bool(item.get("is_demo", False)) for item in transport_options
    )

    if agent_response.cart and agent_response.cart.get("items"):
        stage = "checkout"
    elif agent_response.itinerary and agent_response.itinerary.get("legs"):
        stage = "itinerary"
    elif transport_options:
        stage = "itinerary"
    elif hotels:
        stage = "hotels"
    elif agent_response.destinations:
        stage = "destinations"
    else:
        stage = agent_response.stage if agent_response.stage in {"inspiration", "checkout"} else None

    return ChatResponse(
    session_id=session_id,
    status=agent_response.status,
    reply=agent_response.reply,
    hotels=hotels,
    state=_public_state(agent_response.updated_state),
    stage=stage,
    destinations=agent_response.destinations,
    itinerary=agent_response.itinerary,
    cart=agent_response.cart,
    transport_options=transport_options,
    weather=agent_response.weather,
    warnings=[{"level": "info", "text": warning} for warning in agent_response.warnings],
    is_demo=is_demo,
)
