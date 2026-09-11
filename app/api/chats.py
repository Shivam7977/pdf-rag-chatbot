import json
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db import models
from app.api.deps import get_current_user

router = APIRouter(prefix="/chats", tags=["chats"])


class RenameChatRequest(BaseModel):
    title: str


def _check_ownership(session: models.ChatSession, user: models.User | None):
    if not session:
        raise HTTPException(status_code=404, detail="Chat not found.")
    if session.user_id is not None and (not user or session.user_id != user.id):
        raise HTTPException(status_code=403, detail="This chat belongs to another account.")


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
    return [
        {
            "id": str(s.id),
            "title": s.title,
            "created_at": s.created_at.isoformat() + "Z",
            "last_active_at": s.last_active_at.isoformat() + "Z",
        }
        for s in sessions
    ]


@router.get("/{chat_session_id}")
def get_chat(chat_session_id: str, db: Session = Depends(get_db), user: models.User | None = Depends(get_current_user)):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == chat_session_id).first()
    _check_ownership(session, user)

    messages = (
        db.query(models.Message)
        .filter(models.Message.chat_session_id == chat_session_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )

    doc_rows = (
        db.query(models.DocumentChunk.filename)
        .filter(models.DocumentChunk.chat_session_id == chat_session_id)
        .distinct()
        .all()
    )
    documents = [row[0] for row in doc_rows]

    return {
        "id": str(session.id),
        "title": session.title,
        "created_at": session.created_at.isoformat() + "Z",
        "has_documents": len(documents) > 0,
        "documents": documents,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "sources": json.loads(m.sources_json) if m.sources_json else [],
                "created_at": m.created_at.isoformat() + "Z",
            }
            for m in messages
        ],
    }


@router.patch("/{chat_session_id}")
def rename_chat(chat_session_id: str, payload: RenameChatRequest, db: Session = Depends(get_db), user: models.User | None = Depends(get_current_user)):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == chat_session_id).first()
    _check_ownership(session, user)

    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title can't be empty.")

    session.title = title[:100]
    db.commit()
    return {"title": session.title}


@router.get("/{chat_session_id}/documents/{filename}")
def get_document_file(chat_session_id: str, filename: str, db: Session = Depends(get_db), user: models.User | None = Depends(get_current_user)):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == chat_session_id).first()
    _check_ownership(session, user)

    doc = (
        db.query(models.Document)
        .filter(models.Document.chat_session_id == chat_session_id, models.Document.filename == filename)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in this chat.")

    return Response(content=doc.data, media_type=doc.content_type)


@router.delete("/{chat_session_id}")
def delete_chat(chat_session_id: str, db: Session = Depends(get_db), user: models.User | None = Depends(get_current_user)):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == chat_session_id).first()
    _check_ownership(session, user)

    db.delete(session)
    db.commit()
    return {"status": "deleted"}