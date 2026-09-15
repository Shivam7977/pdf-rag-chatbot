import uuid
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models
from app.services.pdf_parser import extract_text_from_pdf
from app.services.table_extractor import extract_tables_from_pdf
from app.services.visual_extractor import extract_visuals_from_pdf
from app.services.chunker import chunk_pages
from app.services.vector_store import add_chunks
from app.services.bm25_retriever import invalidate_bm25_index
from app.services.cleanup import cleanup_stale_guests
from app.services.title_extractor import extract_display_title
from app.config import MAX_UPLOAD_BYTES_PER_SESSION, MAX_SINGLE_UPLOAD_BYTES
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

    # Validate BEFORE the DB query — an invalid UUID string reaching
    # Postgres as a query parameter raises a raw DataError (we saw this
    # exact failure mode ourselves debugging retrieval earlier), which
    # would otherwise surface as an unhandled 500 with internal details.
    try:
        uuid.UUID(chat_session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat session ID.")

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

    if file_size > MAX_SINGLE_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="This file exceeds the 20MB per-file limit.")

    if session.total_upload_bytes + file_size > MAX_UPLOAD_BYTES_PER_SESSION:
        raise HTTPException(status_code=413, detail="This chat has hit its 50MB storage limit. Start a new chat to upload more.")

    file_bytes = file.file.read()
    file.file.seek(0)

    # SECURITY: file.content_type is a client-supplied header and can be
    # spoofed trivially — it doesn't guarantee the bytes are actually a PDF.
    # Check the real file signature (PDFs start with "%PDF-") before doing
    # any further work, so a mislabeled non-PDF is rejected immediately
    # instead of relying solely on fitz.open() failing later.
    if not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="This file doesn't look like a valid PDF.")

    # SECURITY: never build the on-disk path from the client-supplied
    # filename — it's attacker-controlled and could contain path-traversal
    # sequences (e.g. "../../evil"). Generate a random, server-controlled
    # name for the actual file on disk; the original filename is still used
    # everywhere else below (display_name, DB storage, API response) since
    # none of those ever touch a filesystem path.
    save_path = UPLOAD_DIR / f"{chat_session_id}_{uuid.uuid4().hex}.pdf"
    with open(save_path, "wb") as f:
        f.write(file_bytes)

    try:
        from app.services.pdf_parser import PasswordProtectedPDFError, CorruptPDFError
        try:
            pages = extract_text_from_pdf(str(save_path), display_name=file.filename)
        except PasswordProtectedPDFError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except CorruptPDFError as e:
            raise HTTPException(status_code=422, detail=str(e))

        if not pages:
            raise HTTPException(status_code=422, detail="No extractable text found in this PDF.")

        # Best-effort: a PDF with no tables just yields an empty list here,
        # never blocks the upload on its own.
        table_chunks = extract_tables_from_pdf(str(save_path), display_name=file.filename)

        # Best-effort: unlike table extraction, this calls out to an
        # external vision model (Ollama locally, or Mistral in production)
        # — that call can genuinely fail for reasons outside our control
        # (Ollama not running, Mistral API/key issues, rate limits). A
        # figure/chart failing to describe itself should never block the
        # whole upload; the document is still useful without it.
        try:
            visual_chunks = extract_visuals_from_pdf(str(save_path), display_name=file.filename)
        except Exception as e:
            print(f"[visual_extractor] Failed for {file.filename}: {e}")
            visual_chunks = []

        chunks = chunk_pages(pages, table_chunks=table_chunks, visual_chunks=visual_chunks)
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
    except HTTPException:
        raise  # intended errors (422/413/etc. above) pass through unchanged
    except Exception as e:
        # Anything else is unexpected (a malformed PDF confusing pdfplumber,
        # a DB-write failure, etc.) — never leak the raw exception to the
        # client; log it server-side and return a clean, generic message.
        print(f"[documents.upload] Unexpected error processing {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong while processing this document. Please try again.")
    finally:
        save_path.unlink(missing_ok=True)

    return {"filename": file.filename, "display_title": display_title, "chunks_indexed": chunk_count}