from sentence_transformers import CrossEncoder

_reranker_model = None

def get_reranker_model():
    global _reranker_model
    if _reranker_model is None:
        # ye ek chhota, fast cross-encoder model hai — 
        # specifically relevance scoring ke liye train kiya gaya hai
        _reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker_model


def rerank_chunks(question: str, chunks: list, top_k: int = 5):
    """
    Har chunk ko question ke saath pair banake cross-encoder ko dete hain.
    Model ek relevance score deta hai har pair ke liye.
    Phir hum sabse high-score wale top_k chunks return karte hain.
    """
    if not chunks:
        return []

    model = get_reranker_model()

    # Cross-encoder ko [question, chunk_text] pairs chahiye
    pairs = [[question, chunk["text"]] for chunk in chunks]

    scores = model.predict(pairs)

    # Har chunk ke saath uska score attach karo
    for chunk, score in zip(chunks, scores):
        chunk["rerank_score"] = float(score)

    # Highest score wale sabse pehle aane chahiye
    reranked = sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)

    return reranked[:top_k]