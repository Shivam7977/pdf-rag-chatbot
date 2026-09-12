from collections import defaultdict
from sqlalchemy.orm import Session
from app.db import models
from app.services.embeddings import embed_texts


def add_chunks(chunks: list, chat_session_id: str, db: Session) -> int:
    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)

    rows = [
        models.DocumentChunk(
            chat_session_id=chat_session_id,
            filename=c["source"],
            page=c["page"],
            text=c["text"],
            embedding=emb,
        )
        for c, emb in zip(chunks, embeddings)
    ]
    db.add_all(rows)
    db.commit()
    return len(rows)


def query_chunks(query_text: str, chat_session_id: str, top_k: int, db: Session):
    query_embedding = embed_texts([query_text])[0]

    rows = (
        db.query(models.DocumentChunk)
        .filter(models.DocumentChunk.chat_session_id == chat_session_id)
        .order_by(models.DocumentChunk.embedding.l2_distance(query_embedding))
        .limit(top_k)
        .all()
    )
    return [{"text": r.text, "page": r.page, "source": r.filename} for r in rows]


def get_all_chunks(chat_session_id: str, db: Session):
    rows = (
        db.query(models.DocumentChunk)
        .filter(models.DocumentChunk.chat_session_id == chat_session_id)
        .all()
    )
    return [{"text": r.text, "page": r.page, "source": r.filename, "chunk_id": str(r.id)} for r in rows]


def get_document_filenames(chat_session_id: str, db: Session) -> list[str]:
    rows = (
        db.query(models.DocumentChunk.filename)
        .filter(models.DocumentChunk.chat_session_id == chat_session_id)
        .distinct()
        .all()
    )
    return [row[0] for row in rows]


def get_documents_metadata(chat_session_id: str, db: Session) -> list[dict]:
    """Filename + display_title for every document uploaded in this chat —
    used for natural-language document matching in comparison questions."""
    rows = (
        db.query(models.Document)
        .filter(models.Document.chat_session_id == chat_session_id)
        .all()
    )
    return [{"filename": r.filename, "display_title": r.display_title} for r in rows]


def count_documents(chat_session_id: str, db: Session) -> int:
    return len(get_document_filenames(chat_session_id, db))


def get_spread_chunks(chat_session_id: str, db: Session, chunks_per_document: int = 8):
    rows = (
        db.query(models.DocumentChunk)
        .filter(models.DocumentChunk.chat_session_id == chat_session_id)
        .order_by(models.DocumentChunk.filename, models.DocumentChunk.page)
        .all()
    )
    if not rows:
        return []

    by_file = defaultdict(list)
    for r in rows:
        by_file[r.filename].append(r)

    sampled = []
    for file_rows in by_file.values():
        n = len(file_rows)
        take = min(chunks_per_document, n)
        step = max(1, n // take)
        for i in range(0, n, step):
            if len(sampled) < chunks_per_document * len(by_file):
                sampled.append(file_rows[i])

    return [{"text": r.text, "page": r.page, "source": r.filename} for r in sampled]


def query_chunks_per_document(query_text: str, chat_session_id: str, db: Session, top_k_per_doc: int = 5, filenames: list[str] | None = None):
    target_filenames = filenames if filenames else get_document_filenames(chat_session_id, db)

    query_embedding = embed_texts([query_text])[0]
    results = []
    for filename in target_filenames:
        rows = (
            db.query(models.DocumentChunk)
            .filter(
                models.DocumentChunk.chat_session_id == chat_session_id,
                models.DocumentChunk.filename == filename,
            )
            .order_by(models.DocumentChunk.embedding.l2_distance(query_embedding))
            .limit(top_k_per_doc)
            .all()
        )
        results.extend([{"text": r.text, "page": r.page, "source": r.filename} for r in rows])

    return results