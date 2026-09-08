"""
Hybrid search: combines dense (semantic) retrieval from ChromaDB with BM25
(lexical/keyword) retrieval, merged using Reciprocal Rank Fusion (RRF).

Dense catches semantic similarity; BM25 catches exact term/acronym overlap
that dense embeddings sometimes wash out. RRF just needs each list's RANKS,
not raw scores, which sidesteps the "scores aren't on the same scale" problem.
"""

from app.db.chroma import query_collection
from app.services.bm25_retriever import bm25_search

RRF_K = 60  # standard constant from the RRF literature; tweak if needed


def _chunk_key(source: str, page, text: str) -> str:
    """
    Stable-ish key to match the same chunk across dense and BM25 result lists.
    Prefers a real chunk_id when available (BM25 side has it); dense side
    falls back to (source, page, text-prefix) since query_collection() in
    this project doesn't currently surface chunk ids in its return dict.
    """
    return f"{source}|{page}|{text[:80]}"


def _dense_search(query: str, top_k: int = 20, sources: list | None = None):
    results = query_collection(query, top_k=top_k, sources=sources)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    chunks = []
    for doc, meta in zip(documents, metadatas):
        chunks.append({
            "text": doc,
            "page": meta["page"],
            "source": meta["source"],
        })
    return chunks


def reciprocal_rank_fusion(dense_results, bm25_results, top_k: int = 20):
    fused_scores = {}
    chunk_lookup = {}

    for rank, chunk in enumerate(dense_results):
        key = _chunk_key(chunk["source"], chunk["page"], chunk["text"])
        chunk_lookup.setdefault(key, chunk)
        fused_scores[key] = fused_scores.get(key, 0) + 1 / (RRF_K + rank + 1)

    for rank, chunk in enumerate(bm25_results):
        key = _chunk_key(chunk["source"], chunk["page"], chunk["text"])
        chunk_lookup.setdefault(key, chunk)
        fused_scores[key] = fused_scores.get(key, 0) + 1 / (RRF_K + rank + 1)

    ranked = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [chunk_lookup[key] for key, _ in ranked]


def hybrid_search(query: str, top_k: int = 20, sources: list | None = None):
    dense_results = _dense_search(query, top_k=20, sources=sources)
    bm25_results = bm25_search(query, top_k=20, sources=sources)
    return reciprocal_rank_fusion(dense_results, bm25_results, top_k=top_k)