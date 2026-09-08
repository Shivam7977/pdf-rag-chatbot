"""
BM25 (lexical/keyword) retrieval — now scoped PER CHAT SESSION instead of the
whole app. Each session is capped at 50MB, so rebuilding its BM25 index from
scratch is fast enough that the old disk cache (data/bm25_index.pkl) and
"rebuild whole collection" approach are no longer needed. Cached in memory
per chat_session_id, invalidated on new upload.
"""

from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session
from app.services.vector_store import get_all_chunks

_index_cache: dict[str, dict] = {}


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def invalidate_bm25_index(chat_session_id: str):
    """Call this after any new upload to a session — forces a fresh index
    next time bm25_search() runs for it."""
    _index_cache.pop(chat_session_id, None)


def build_bm25_index(chat_session_id: str, db: Session, force_rebuild: bool = False):
    if not force_rebuild and chat_session_id in _index_cache:
        return _index_cache[chat_session_id]

    chunks = get_all_chunks(chat_session_id, db)
    tokenized_corpus = [_tokenize(c["text"]) for c in chunks]

    index_data = {
        "bm25": BM25Okapi(tokenized_corpus) if tokenized_corpus else None,
        "chunks": chunks,
    }
    _index_cache[chat_session_id] = index_data
    return index_data


def bm25_search(query: str, chat_session_id: str, db: Session, top_k: int = 20):
    index_data = build_bm25_index(chat_session_id, db)
    if index_data["bm25"] is None:
        return []

    scores = index_data["bm25"].get_scores(_tokenize(query))
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    results = []
    for rank, idx in enumerate(ranked_indices):
        c = index_data["chunks"][idx]
        results.append({
            "text": c["text"],
            "page": c["page"],
            "source": c["source"],
            "chunk_id": c["chunk_id"],
            "bm25_rank": rank + 1,
        })
    return results