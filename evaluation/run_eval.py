import sys
import json
sys.path.append(".")
from app.db.chroma import query_collection
from app.services.reranker import rerank_chunks
from app.services.hybrid_retriever import hybrid_search


def load_dataset():
    with open("evaluation/dataset.json", "r", encoding="utf-8") as f:
        return json.load(f)


def is_strict_match(chunk, expected_source, expected_page):
    return chunk["source"] == expected_source and chunk["page"] == expected_page


def is_keyword_match(chunk, expected_source, expected_keywords, min_ratio=0.5):
    """
    Secondary/looser check: same document, and at least half the
    expected keywords appear in the chunk text (case-insensitive).
    Used only for reporting alongside strict match, not to replace it.
    """
    if chunk["source"] != expected_source:
        return False
    text_lower = chunk["text"].lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in text_lower)
    return hits >= max(1, len(expected_keywords) * min_ratio)


def find_rank(chunks, item, match_fn):
    for i, chunk in enumerate(chunks, start=1):
        if match_fn(chunk, item):
            return i
    return None


def dense_retrieve(question, fetch_k):
    """Wraps query_collection() so it returns the same chunk shape as hybrid_search()."""
    results = query_collection(question, top_k=fetch_k)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    return [{"text": d, "page": m["page"], "source": m["source"]}
            for d, m in zip(documents, metadatas)]


def evaluate(dataset, top_k, retrieval_mode="dense", use_reranker=False, initial_k=20):
    """
    retrieval_mode: "dense" or "hybrid"
    use_reranker: whether to rerank the fetched candidates down to top_k
    """
    strict_ranks = []
    keyword_ranks = []
    strict_hits = 0
    keyword_hits = 0

    for item in dataset:
        fetch_k = initial_k if use_reranker else top_k

        if retrieval_mode == "hybrid":
            chunks = hybrid_search(item["question"], top_k=fetch_k)
        else:
            chunks = dense_retrieve(item["question"], fetch_k)

        if use_reranker:
            chunks = rerank_chunks(item["question"], chunks, top_k=top_k)
        else:
            chunks = chunks[:top_k]

        strict_rank = find_rank(
            chunks, item,
            lambda c, it: is_strict_match(c, it["expected_source"], it["expected_page"])
        )
        keyword_rank = find_rank(
            chunks, item,
            lambda c, it: is_keyword_match(c, it["expected_source"], it["expected_keywords"])
        )

        if strict_rank:
            strict_hits += 1
            strict_ranks.append(1 / strict_rank)
        else:
            strict_ranks.append(0)

        if keyword_rank:
            keyword_hits += 1
            keyword_ranks.append(1 / keyword_rank)
        else:
            keyword_ranks.append(0)

    n = len(dataset)
    return {
        "strict_recall": strict_hits / n,
        "strict_mrr": sum(strict_ranks) / n,
        "keyword_recall": keyword_hits / n,
        "keyword_mrr": sum(keyword_ranks) / n,
    }


def print_results(label, results, show_mrr):
    print(f"{label}:")
    print(f"  Strict match   -> Recall: {results['strict_recall']*100:.1f}%"
          + (f" | MRR: {results['strict_mrr']:.3f}" if show_mrr else ""))
    print(f"  Keyword-assist -> Recall: {results['keyword_recall']*100:.1f}%"
          + (f" | MRR: {results['keyword_mrr']:.3f}" if show_mrr else ""))
    print()


if __name__ == "__main__":
    dataset = load_dataset()
    print(f"Evaluating on {len(dataset)} questions...\n")

    all_results = {}

    for k in [5, 10]:
        combos = [
            ("DENSE (baseline)", "dense", False),
            ("DENSE + RERANKER", "dense", True),
            ("HYBRID (BM25 + dense, RRF)", "hybrid", False),
            ("HYBRID + RERANKER", "hybrid", True),
        ]
        for label, mode, use_reranker in combos:
            res = evaluate(dataset, top_k=k, retrieval_mode=mode, use_reranker=use_reranker)
            print_results(f"{label}, top-{k}", res, show_mrr=(k == 5))
            all_results[f"{label} | top-{k}"] = res

    with open("evaluation/results_phase7.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("Note: 'Strict match' requires exact source+page match (narrow ground truth).")
    print("'Keyword-assist' additionally counts chunks from the right document")
    print("containing most expected keywords, even if the page differs slightly.")
    print("\nFull results saved to evaluation/results_phase7.json")