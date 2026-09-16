from sentence_transformers import CrossEncoder

_reranker_model = None

# SECURITY: pin to a specific commit rather than "main" (the implicit
# default) — an unpinned model pull is a supply-chain risk: if the repo
# owner (or anyone with write access) ever pushes a different/malicious
# model to "main", the next server restart would silently pull it in.
# Pinning to a known-good commit means the model can only ever change when
# this hash is deliberately updated. Current HEAD of main as of this pin:
# https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2/commit/b2cfda5
_RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_RERANKER_MODEL_REVISION = "b2cfda50a1a9fc7919e7444afbb52610d268af92"


def get_reranker_model():
    global _reranker_model
    if _reranker_model is None:
        # ye ek chhota, fast cross-encoder model hai — 
        # specifically relevance scoring ke liye train kiya gaya hai
        _reranker_model = CrossEncoder(_RERANKER_MODEL_NAME, revision=_RERANKER_MODEL_REVISION)
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