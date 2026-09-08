import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.pdf_parser import extract_text_from_pdf
from app.services.chunker import chunk_pages, _get_document_id
from app.db.chroma import add_chunks
from app.services.bm25_retriever import build_bm25_index

router = APIRouter()

# NOTE: if app/config.py already defines an upload path, use that instead
# of hardcoding this — keeping it here for now since config.py wasn't shared.
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/api/documents/upload")
def upload_document(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # pdf_parser needs a real file path on disk, so save it first.
    save_path = UPLOAD_DIR / file.filename
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Same pipeline as evaluation/ingest_all.py, just for one file at a time.
    pages = extract_text_from_pdf(str(save_path))
    if not pages:
        raise HTTPException(status_code=422, detail="No extractable text found in this PDF.")

    chunks = chunk_pages(pages)
    chunk_count = add_chunks(chunks)

    # Keep BM25 in sync with what's now in ChromaDB. This re-tokenizes the
    # WHOLE collection (not just the new file) — fine at this scale, but
    # will get slower as more PDFs pile up.
    build_bm25_index(force_rebuild=True)

    # NOTE: _get_document_id is a "private" (underscore-prefixed) helper in
    # chunker.py. Importing it works fine in Python, but if you want this to
    # look less like reaching into internals, rename it to get_document_id
    # in chunker.py (no functional change, just drops the leading underscore).
    document_id = _get_document_id(file.filename)

    return {
        "document_id": document_id,
        "filename": file.filename,
        "chunks_indexed": chunk_count,
    }