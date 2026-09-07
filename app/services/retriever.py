from app.services.hybrid_retriever import hybrid_search
from app.services.reranker import rerank_chunks

def retrieve_chunks(question: str, top_k: int = 5, initial_k: int = 20):
    """
    Step 1: Hybrid search (BM25 + dense, fused via RRF) se top-20 (initial_k) candidates lao
    Step 2: Cross-encoder se unhe rerank karo, sirf top-5 (top_k) rakho

    Phase 7 mein isse pehle sirf dense (query_collection) tha — ab hybrid use
    ho raha hai kyunki eval mein Hybrid+Reranker best result de raha tha
    (strict Recall@5: 90.0% vs Dense+Reranker ka 86.7%).
    """
    chunks = hybrid_search(question, top_k=initial_k)

    # Reranking step
    reranked_chunks = rerank_chunks(question, chunks, top_k=top_k)

    return reranked_chunks