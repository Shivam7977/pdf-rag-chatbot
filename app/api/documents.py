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
from app.config import MAX_UPLOAD_BYTES_PER_SESSION

router = APIRouter()

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/api/documents/upload")
def upload_document(
    chat_session_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    cleanup_stale_guests(db)

    session = db.query(models.ChatSession).filter(models.ChatSession.id == chat_session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found. Start one via /auth/guest or /chats.")

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if session.total_upload_bytes + file_size > MAX_UPLOAD_BYTES_PER_SESSION:
        raise HTTPException(status_code=413, detail="This chat has hit its 50MB storage limit. Start a new chat to upload more.")

    save_path = UPLOAD_DIR / f"{chat_session_id}_{file.filename}"
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        pages = extract_text_from_pdf(str(save_path))
        if not pages:
            raise HTTPException(status_code=422, detail="No extractable text found in this PDF.")

        chunks = chunk_pages(pages)
        # NOTE: confirm chunk_pages() tags each chunk's "source" as file.filename
        # (the original name), not the on-disk save_path — check chunker.py.
        chunk_count = add_chunks(chunks, chat_session_id=chat_session_id, db=db)
        invalidate_bm25_index(chat_session_id)

        session.total_upload_bytes += file_size
        session.last_active_at = datetime.utcnow()
        db.commit()
    finally:
        save_path.unlink(missing_ok=True)  # only needed transiently for text extraction

    return {"filename": file.filename, "chunks_indexed": chunk_count}