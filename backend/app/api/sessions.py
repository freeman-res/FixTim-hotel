from fastapi import APIRouter
from ..sessions.service import session_service
from ..core.errors import AppError

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    """
    Возвращает историю сообщений сессии.
    """
    session = session_service.get_session(session_id)

    if not session:
        raise AppError(
            code="session_not_found",
            message="Сессия не найдена",
            status_code=404
        )

    return {
        "session_id": session_id,
        "messages": session["messages"]
    }