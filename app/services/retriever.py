from app.services.hybrid_retriever import hybrid_search
from app.services.reranker import rerank_chunks


def retrieve_chunks(question: str, chat_session_id: str, db, top_k: int = 5, initial_k: int = 20):
    chunks = hybrid_search(question, chat_session_id, db, top_k=initial_k)
    reranked_chunks = rerank_chunks(question, chunks, top_k=top_k)
    return reranked_chunks