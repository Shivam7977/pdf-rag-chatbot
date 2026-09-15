"""
Temporary debug script — runs the "specific" mode retrieval pipeline
(hybrid_search -> rerank_chunks) for one question against one chat session,
and prints what came back at EACH stage, including element_type, so we can
see whether the image/table chunk is being retrieved at all and where it
ranks. Not part of the production pipeline; delete after use.

Usage:
    python debug_retrieval.py <chat_session_id> "your question here"

Find your chat_session_id by running this in PG Studio:
    SELECT id, title, last_active_at FROM chat_sessions ORDER BY last_active_at DESC LIMIT 5;
"""
import sys
from app.db.database import get_db
from app.services.hybrid_retriever import hybrid_search
from app.services.reranker import rerank_chunks

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: python debug_retrieval.py <chat_session_id> "your question"')
        sys.exit(1)

    chat_session_id = sys.argv[1]
    question = sys.argv[2]

    db = next(get_db())
    try:
        hybrid_results = hybrid_search(question, chat_session_id, db, top_k=20)
        print(f"--- hybrid_search returned {len(hybrid_results)} chunk(s) ---")
        for i, c in enumerate(hybrid_results, start=1):
            etype = c.get("element_type", "?")
            print(f"{i}. type={etype} page={c['page']} text={c['text'][:70]!r}")

        reranked = rerank_chunks(question, hybrid_results, top_k=5)
        print(f"\n--- rerank_chunks (top 5) returned {len(reranked)} chunk(s) ---")
        for i, c in enumerate(reranked, start=1):
            score = c.get("rerank_score", "N/A")
            etype = c.get("element_type", "?")
            print(f"{i}. score={score} type={etype} page={c['page']} text={c['text'][:70]!r}")
    finally:
        db.close()