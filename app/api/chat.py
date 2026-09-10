import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import get_db, SessionLocal
from app.db import models
from app.schemas.chat import ChatRequest
from app.services.retriever import retrieve_chunks
from app.services.llm import generate_answer
from app.api.deps import get_current_user

router = APIRouter()

RERANK_CONFIDENCE_THRESHOLD = -3.0
NO_ANSWER_MESSAGE = "I couldn't find this in the uploaded documents."


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def stream_chat_response(question: str, chat_session_id: str):
    # Own DB session — the one injected into the route function closes as
    # soon as the route returns the StreamingResponse object, before this
    # generator has actually finished streaming.
    db = SessionLocal()
    try:
        chunks = retrieve_chunks(question, chat_session_id, db, top_k=5)

        def save_message(role: str, content: str, sources_json: str):
            db.add(models.Message(chat_session_id=chat_session_id, role=role, content=content, sources_json=sources_json))
            session = db.query(models.ChatSession).filter(models.ChatSession.id == chat_session_id).first()
            if session:
                session.last_active_at = datetime.utcnow()
            db.commit()

        save_message("user", question, "[]")

        if not chunks or chunks[0]["rerank_score"] < RERANK_CONFIDENCE_THRESHOLD:
            for word in NO_ANSWER_MESSAGE.split(" "):
                yield sse_event("token", {"content": word + " "})
            yield sse_event("done", {})
            yield sse_event("sources", {"sources": []})
            save_message("assistant", NO_ANSWER_MESSAGE, "[]")
            return

        answer_text = ""
        try:
            for token in generate_answer(question, chunks):
                answer_text += token
                yield sse_event("token", {"content": token})

            yield sse_event("done", {})

            seen = set()
            sources_out = []
            for c in chunks:
                key = (c["source"], c["page"])
                if key in seen:
                    continue
                seen.add(key)
                sources_out.append({"page": c["page"], "source": c["source"], "text": c["text"][:200]})

            yield sse_event("sources", {"sources": sources_out})
            save_message("assistant", answer_text, json.dumps(sources_out))

        except Exception as e:
            yield sse_event("error", {"message": str(e)})
            save_message("assistant", f"[error] {str(e)}", "[]")
    finally:
        db.close()


@router.post("/chat")
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_current_user),
):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == request.chat_session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found. Start one via /auth/guest or /chats.")

    # A chat owned by a registered user can only be used by that same user.
    # A guest chat (user_id is None) has no owner to check against — the
    # unguessable chat_session_id itself is what scopes access to it.
    if session.user_id is not None and (not user or session.user_id != user.id):
        raise HTTPException(status_code=403, detail="This chat belongs to another account.")

    return StreamingResponse(
        stream_chat_response(request.question, request.chat_session_id),
        media_type="text/event-stream",
    )