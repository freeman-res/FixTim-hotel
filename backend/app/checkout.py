from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import uuid4

from backend.app.sessions.service import session_service

router = APIRouter(prefix="/api/v1/checkout", tags=["checkout"])


class CheckoutRequest(BaseModel):
    session_id: str


class CheckoutResponse(BaseModel):
    status: str
    message: str
    is_demo: bool = True
    booking_id: str


@router.post("/confirm", response_model=CheckoutResponse)
async def confirm_checkout(request: CheckoutRequest):
    """
    Демо-подтверждение заказа.
    Никакой реальной оплаты нет.
    """
    session = session_service.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")


    state = session.get("state", {})
    cart = state.get("cart") or {}
    if not cart.get("items") or not cart.get("is_demo") or state.get("needs_replan"):
        raise HTTPException(status_code=409, detail="Нет актуальной корзины для подтверждения")
    booking_id = "DEMO-" + uuid4().hex[:8].upper()
    state["demo_booked"] = True
    state["booking_status"] = "confirmed"
    state["demo_booking_id"] = booking_id
    session_service.update_state(request.session_id, state)

    return CheckoutResponse(
        status="ok",
        message="Демо-заказ успешно подтверждён. Это учебное бронирование.",
        is_demo=True,
        booking_id=booking_id,
    )
