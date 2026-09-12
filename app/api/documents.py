import shutil
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models
from app.services.pdf_parser import extract_text_from_pdf
from app.services.chunker import chunk_pages
from app.services.vector_store import add_chunks
from app.services.bm25_retriever import invalidate_bm25_index
from app.services.cleanup import cleanup_stale_guests
from app.services.title_extractor import extract_display_title
from app.config import MAX_UPLOAD_BYTES_PER_SESSION
from app.api.deps import get_current_user

router = APIRouter()

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/api/documents/upload")
def upload_document(
    chat_session_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_current_user),
):
    cleanup_stale_guests(db)

    session = db.query(models.ChatSession).filter(models.ChatSession.id == chat_session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found. Start one via /auth/guest or /chats.")

    if session.user_id is not None and (not user or session.user_id != user.id):
        raise HTTPException(status_code=403, detail="This chat belongs to another account.")

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if session.total_upload_bytes + file_size > MAX_UPLOAD_BYTES_PER_SESSION:
        raise HTTPException(status_code=413, detail="This chat has hit its 50MB storage limit. Start a new chat to upload more.")

    file_bytes = file.file.read()
    file.file.seek(0)

    save_path = UPLOAD_DIR / f"{chat_session_id}_{file.filename}"
    with open(save_path, "wb") as f:
        f.write(file_bytes)

    try:
        pages = extract_text_from_pdf(str(save_path), display_name=file.filename)
        if not pages:
            raise HTTPException(status_code=422, detail="No extractable text found in this PDF.")

        chunks = chunk_pages(pages)
        chunk_count = add_chunks(chunks, chat_session_id=chat_session_id, db=db)
        invalidate_bm25_index(chat_session_id)

        # Best-effort natural-language title, so the document can be
        # referred to by topic ("the funding report") and not just by its
        # (possibly meaningless) filename. Never blocks upload on failure.
        display_title = extract_display_title(pages[0]["text"], fallback_filename=file.filename)

        db.add(models.Document(
            chat_session_id=chat_session_id,
            filename=file.filename,
            display_title=display_title,
            content_type=file.content_type,
            data=file_bytes,
        ))

        session.total_upload_bytes += file_size
        session.last_active_at = datetime.utcnow()
        db.commit()
    finally:
        save_path.unlink(missing_ok=True)

    return {"filename": file.filename, "display_title": display_title, "chunks_indexed": chunk_count}