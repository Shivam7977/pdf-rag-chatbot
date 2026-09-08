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
    """Dense retrieval via pgvector's <-> (L2 distance) operator, replacing
    ChromaDB's query_collection(). Scoped to one chat_session_id, so this
    also fixes the old cross-user filename-collision bug."""
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
    """Used by bm25_retriever.py to build a per-session BM25 index."""
    rows = (
        db.query(models.DocumentChunk)
        .filter(models.DocumentChunk.chat_session_id == chat_session_id)
        .all()
    )
    return [{"text": r.text, "page": r.page, "source": r.filename, "chunk_id": str(r.id)} for r in rows]