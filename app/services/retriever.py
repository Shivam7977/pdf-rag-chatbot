from app.services.hybrid_retriever import hybrid_search
from app.services.reranker import rerank_chunks
from app.services.vector_store import get_spread_chunks, query_chunks_per_document, count_documents, get_documents_metadata
from app.services.query_classifier import classify_question, extract_mentioned_documents


def retrieve_chunks(search_query: str, original_question: str, chat_session_id: str, db, top_k: int = 5, initial_k: int = 20):
    """
    search_query: the (possibly LLM-rewritten) query used for actual
        retrieval — better phrased for the cross-encoder/embedding search.
    original_question: the user's raw, unmodified question — used ONLY for
        mode classification and document-mention matching. Rewritten
        phrasing (e.g. "What does the document say about X?") can
        accidentally match BROAD_PATTERNS even for a simple lookup, so
        classification must never run on the rewritten text.

    Returns (chunks, mode).
    - "specific": flat list of chunks with rerank_score.
    - "broad": list of {"filename", "chunks"} GROUPED per document.
    - "comparison": flat list of chunks (each carries its own "source").
    """
    document_count = count_documents(chat_session_id, db)
    mode = classify_question(original_question, document_count)

    if mode == "broad":
        return get_spread_chunks(chat_session_id, db, chunks_per_document=8), mode

    if mode == "comparison":
        documents = get_documents_metadata(chat_session_id, db)
        mentioned = extract_mentioned_documents(original_question, documents)
        target_filenames = mentioned if len(mentioned) >= 2 else None
        return query_chunks_per_document(search_query, chat_session_id, db, top_k_per_doc=5, filenames=target_filenames), mode

    chunks = hybrid_search(search_query, chat_session_id, db, top_k=initial_k)
    reranked_chunks = rerank_chunks(search_query, chunks, top_k=top_k)
    return reranked_chunks, mode