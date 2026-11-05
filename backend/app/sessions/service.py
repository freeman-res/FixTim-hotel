from sqlalchemy.orm import Session as DBSession
from .models import Session, Message
from .repository import SessionLocal, create_tables
from datetime import datetime
import uuid


class SessionService:
    """Менеджер сессий, который работает с SQLite"""

    def __init__(self):

        create_tables()

    def _get_db(self) -> DBSession:
        return SessionLocal()

    def create_session(self) -> str:
        """Создаёт новую сессию и возвращает её id"""
        db = self._get_db()
        try:
            session_id = str(uuid.uuid4())
            new_session = Session(
                id=session_id,
                state_json={}
            )
            db.add(new_session)
            db.commit()
            return session_id
        finally:
            db.close()

    def get_session(self, session_id: str) -> dict | None:
        """Возвращает сессию в виде словаря или None"""
        db = self._get_db()
        try:
            session = db.query(Session).filter(Session.id == session_id).first()
            if not session:
                return None

            return {
                "id": session.id,
                "state": session.state_json or {},
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None
                    }
                    for msg in session.messages
                ],
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            }
        finally:
            db.close()

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Добавляет сообщение в историю сессии"""
        db = self._get_db()
        try:
            session = db.query(Session).filter(Session.id == session_id).first()
            if not session:
                return

            message = Message(
                session_id=session_id,
                role=role,
                content=content
            )
            db.add(message)


            session.updated_at = datetime.utcnow()
            db.commit()
        finally:
            db.close()

    def update_state(self, session_id: str, state: dict) -> None:
        """Обновляет состояние поездки"""
        db = self._get_db()
        try:
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.state_json = state
                session.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()



session_service = SessionService()