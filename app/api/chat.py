import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import get_db, SessionLocal
from app.db import models
from app.schemas.chat import ChatRequest
from app.services.retriever import retrieve_chunks
from app.services.llm import generate_answer, rewrite_query, get_confidence_level
from app.api.deps import get_current_user

router = APIRouter()

RERANK_CONFIDENCE_THRESHOLD = -3.0
NO_ANSWER_MESSAGE = "I couldn't find this in the uploaded documents."
GENERATION_ERROR_MESSAGE = "Something went wrong while generating a response. Please try again."
HISTORY_LOOKBACK = 4


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _make_title_from_question(question: str) -> str:
    q = question.strip()
    return (q[:47] + "...") if len(q) > 50 else q


def _flatten_for_sources(chunks) -> list:
    """chunks can be a flat list (specific/comparison modes) or a grouped
    list of {"filename","chunks"} (broad mode) — normalize to flat for
    building the source-chips list either way."""
    if chunks and isinstance(chunks[0], dict) and "chunks" in chunks[0]:
        flat = []
        for group in chunks:
            flat.extend(group["chunks"])
        return flat
    return chunks


def stream_chat_response(question: str, chat_session_id):
    db = SessionLocal()
    try:
        recent_messages = (
            db.query(models.Message)
            .filter(models.Message.chat_session_id == chat_session_id)
            .order_by(models.Message.created_at.desc())
            .limit(HISTORY_LOOKBACK)
            .all()
        )
        recent_history = [
            {"role": m.role, "content": m.content}
            for m in reversed(recent_messages)
        ]

        search_query = rewrite_query(question, recent_history)
        print(f"[DEBUG] original={question!r} rewritten={search_query!r}")
        chunks, mode = retrieve_chunks(search_query, question, chat_session_id, db, top_k=5)
        print(f"[DEBUG] mode={mode} top_score={chunks[0].get('rerank_score', 'N/A') if chunks else 'NO CHUNKS'} retrieved_section={chunks[0].get('section_title', 'N/A') if chunks else 'N/A'}")
        print(f"[DEBUG] chunk_text={chunks[0].get('text', '')[:200]!r}" if chunks else "")

        def save_message(role: str, content: str, sources_json: str):
            db.add(models.Message(chat_session_id=chat_session_id, role=role, content=content, sources_json=sources_json))
            session = db.query(models.ChatSession).filter(models.ChatSession.id == chat_session_id).first()
            if session:
                session.last_active_at = datetime.utcnow()
                if role == "user" and session.title in (None, "New chat"):
                    session.title = _make_title_from_question(content)
            db.commit()

        save_message("user", question, "[]")

        no_content = not chunks or (mode == "specific" and chunks[0]["rerank_score"] < RERANK_CONFIDENCE_THRESHOLD)

        if no_content:
            for word in NO_ANSWER_MESSAGE.split(" "):
                yield sse_event("token", {"content": word + " "})
            yield sse_event("done", {})
            yield sse_event("sources", {"sources": []})
            save_message("assistant", NO_ANSWER_MESSAGE, "[]")
            return

        confidence = get_confidence_level(chunks[0]["rerank_score"]) if mode == "specific" else None

        # Drop weak-scoring chunks before they ever reach the LLM. A small
        # local/free-tier model can get confused and hedge into "couldn't
        # find this" when it sees several unrelated sections mixed into the
        # same context, even if the top chunk clearly answers the question —
        # telling it via prompt instruction to "ignore irrelevant sections"
        # wasn't reliable enough on its own, so filter at the source instead.
        if mode == "specific":
            filtered_chunks = [c for c in chunks if c["rerank_score"] >= RERANK_CONFIDENCE_THRESHOLD]
        else:
            filtered_chunks = chunks

        print(f"[DEBUG] num_chunks_sent_to_llm={len(filtered_chunks)} sections={[c.get('section_title') for c in filtered_chunks]}")

        answer_text = ""
        try:
            for token in generate_answer(search_query, filtered_chunks, mode=mode):
                answer_text += token
                yield sse_event("token", {"content": token})

            yield sse_event("done", {})

            flat_chunks = _flatten_for_sources(filtered_chunks)
            seen = set()
            sources_out = []
            for c in flat_chunks:
                key = (c["source"], c["page"])
                if key in seen:
                    continue
                seen.add(key)
                sources_out.append({"page": c["page"], "source": c["source"], "text": c["text"][:200]})

            sources_payload = {"sources": sources_out}
            if confidence:
                sources_payload["confidence"] = confidence
            yield sse_event("sources", sources_payload)
            save_message("assistant", answer_text, json.dumps(sources_out))

        except Exception as e:
            # SECURITY: never leak the raw exception to the client — it can
            # contain internal details (file paths, DB/library internals,
            # provider error bodies). Log the real error server-side for
            # debugging; the client only ever sees a generic message.
            print(f"[chat.stream_chat_response] Unexpected error for session {chat_session_id}: {e}")
            yield sse_event("error", {"message": GENERATION_ERROR_MESSAGE})
            save_message("assistant", GENERATION_ERROR_MESSAGE, "[]")
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

    if session.user_id is not None and (not user or session.user_id != user.id):
        raise HTTPException(status_code=403, detail="This chat belongs to another account.")

    return StreamingResponse(
        # Validated as UUID by Pydantic above (malformed input already
        # rejected with a clean 422) — converted back to str here so it
        # stays consistent with documents.py's string-typed chat_session_id
        # (Form field), since bm25_retriever's in-memory cache is keyed by
        # plain strings. A UUID object and its string form don't hash equal
        # in Python, so mixing the two types across entry points would
        # silently break cache invalidation.
        stream_chat_response(request.question, str(request.chat_session_id)),
        media_type="text/event-stream",
    )