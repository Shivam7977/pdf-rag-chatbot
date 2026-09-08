"""
BM25 (lexical/keyword) retrieval, used alongside dense retrieval for hybrid search.

BM25 does not live in ChromaDB — it needs the full tokenized corpus in memory.
So this module builds an index once from whatever's in Chroma, and caches it
to disk (data/bm25_index.pkl) so we don't re-tokenize 600+ chunks every query.

IMPORTANT: rebuild this manually after ingesting new docs, by calling
build_bm25_index(force_rebuild=True) — e.g. at the end of evaluation/ingest_all.py
and now also inside app/api/documents.py after each upload.
It does NOT auto-rebuild on server startup (kept explicit on purpose, see
Phase 7 notes: avoids slow reloads during `uvicorn --reload` dev loop).
"""

import pickle
from pathlib import Path
from rank_bm25 import BM25Okapi

# NOTE: adjust this import to match your actual app/db/chroma.py.
# It needs to return the raw Chroma collection object (so we can call .get()
# on it) — if your chroma.py only exposes query_collection(), add a small
# get_collection() helper there that returns the underlying collection.
from app.db.chroma import get_collection

BM25_CACHE_PATH = Path("data/bm25_index.pkl")


def _tokenize(text: str) -> list[str]:
    # Simple whitespace + lowercase tokenizer — sufficient for BM25.
    return text.lower().split()


def build_bm25_index(force_rebuild: bool = False):
    """
    Fetches all chunks from ChromaDB and builds a BM25 index over them.
    Cached to disk; pass force_rebuild=True after re-ingesting documents.
    """
    if BM25_CACHE_PATH.exists() and not force_rebuild:
        with open(BM25_CACHE_PATH, "rb") as f:
            return pickle.load(f)

    collection = get_collection()
    all_data = collection.get(include=["documents", "metadatas"])

    chunk_ids = all_data["ids"]
    documents = all_data["documents"]
    metadatas = all_data["metadatas"]

    tokenized_corpus = [_tokenize(doc) for doc in documents]
    bm25 = BM25Okapi(tokenized_corpus)

    index_data = {
        "bm25": bm25,
        "chunk_ids": chunk_ids,
        "documents": documents,
        "metadatas": metadatas,
    }

    BM25_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BM25_CACHE_PATH, "wb") as f:
        pickle.dump(index_data, f)

    return index_data


def bm25_search(query: str, top_k: int = 20, sources: list | None = None):
    """
    Returns top_k chunks as dicts shaped like the rest of the pipeline expects:
    {"text": ..., "page": ..., "source": ..., "chunk_id": ..., "bm25_rank": ...}

    sources: optional list of filenames to restrict results to. The BM25 index
    itself still covers the whole corpus (rebuilding it per-query would be slow),
    but we skip any ranked result whose "source" isn't in this list — so a
    session only ever sees chunks from documents it uploaded.
    """
    index_data = build_bm25_index()  # served from cache unless force_rebuild was called elsewhere
    bm25 = index_data["bm25"]
    tokenized_query = _tokenize(query)

    scores = bm25.get_scores(tokenized_query)
    # Rank the FULL corpus first, then filter — slicing top_k before filtering
    # would risk returning fewer than top_k (or zero) results once restricted
    # to a small session's documents.
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    allowed = set(sources) if sources else None

    results = []
    for idx in ranked_indices:
        meta = index_data["metadatas"][idx]
        if allowed is not None and meta["source"] not in allowed:
            continue

        results.append({
            "text": index_data["documents"][idx],
            "page": meta["page"],
            "source": meta["source"],
            "chunk_id": index_data["chunk_ids"][idx],
            "bm25_rank": len(results) + 1,
        })

        if len(results) >= top_k:
            break

    return results