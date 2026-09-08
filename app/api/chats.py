from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models
from app.api.deps import get_current_user

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("")
def create_chat(db: Session = Depends(get_db), user: models.User | None = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Login required to create a saved chat. Use /auth/guest for a temporary one.")
    session = models.ChatSession(is_guest=False, user_id=user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"chat_session_id": str(session.id)}


@router.get("")
def list_chats(db: Session = Depends(get_db), user: models.User | None = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Login required.")
    sessions = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.user_id == user.id)
        .order_by(models.ChatSession.last_active_at.desc())
        .all()
    )
    return [{"id": str(s.id), "title": s.title, "last_active_at": s.last_active_at.isoformat()} for s in sessions]


@router.get("/{chat_session_id}/messages")
def get_messages(chat_session_id: str, db: Session = Depends(get_db), user: models.User | None = Depends(get_current_user)):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == chat_session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat not found.")
    if session.user_id is not None and (not user or session.user_id != user.id):
        raise HTTPException(status_code=403, detail="This chat belongs to another account.")

    messages = (
        db.query(models.Message)
        .filter(models.Message.chat_session_id == chat_session_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
    return [{"role": m.role, "content": m.content, "sources": m.sources_json} for m in messages]