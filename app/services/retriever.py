from app.services.hybrid_retriever import hybrid_search
from app.services.reranker import rerank_chunks
from app.services.vector_store import get_spread_chunks, query_chunks_per_document, count_documents, get_documents_metadata
from app.services.query_classifier import classify_question, extract_mentioned_documents


def retrieve_chunks(question: str, chat_session_id: str, db, top_k: int = 5, initial_k: int = 20):
    document_count = count_documents(chat_session_id, db)
    mode = classify_question(question, document_count)

    if mode == "broad":
        return get_spread_chunks(chat_session_id, db, chunks_per_document=8), mode

    if mode == "comparison":
        documents = get_documents_metadata(chat_session_id, db)
        mentioned = extract_mentioned_documents(question, documents)
        target_filenames = mentioned if len(mentioned) >= 2 else None
        return query_chunks_per_document(question, chat_session_id, db, top_k_per_doc=5, filenames=target_filenames), mode

    chunks = hybrid_search(question, chat_session_id, db, top_k=initial_k)
    reranked_chunks = rerank_chunks(question, chunks, top_k=top_k)
    return reranked_chunks, mode