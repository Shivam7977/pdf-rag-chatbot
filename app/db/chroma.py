import chromadb
from app.services.embeddings import embed_texts
from app.config import CHROMA_PATH

_client = None
_collection = None

def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _client.get_or_create_collection(name="pdf_docs")
    return _collection


def add_chunks(chunks: list):
    collection = get_collection()

    texts = [c["text"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]
    metadatas = [{"page": c["page"], "source": c["source"]} for c in chunks]

    embeddings = embed_texts(texts)

    collection.upsert(   # changed from add() — re-uploads now update, not crash
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas
    )

    return len(chunks)


def query_collection(query_text: str, top_k: int = 5, sources: list | None = None):
    """
    sources: optional list of filenames to restrict the search to (matches
    the "source" metadata field). Pass None or [] to search everything —
    but for session-scoped chat, the caller should always pass the current
    session's uploaded filenames.
    """
    collection = get_collection()
    query_embedding = embed_texts([query_text])[0]

    where_filter = {"source": {"$in": sources}} if sources else None

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where_filter
    )
    return results


if __name__ == "__main__":
    import sys
    sys.path.append(".")
    from app.services.pdf_parser import extract_text_from_pdf
    from app.services.chunker import chunk_pages

    test_file = sys.argv[1] if len(sys.argv) > 1 else None
    if not test_file:
        print("Usage: python -m app.db.chroma <path_to_pdf>")
    else:
        pages = extract_text_from_pdf(test_file)
        chunks = chunk_pages(pages)
        count = add_chunks(chunks)
        print(f"Stored {count} chunks in ChromaDB.")

        test_query = "What are global South funds?"
        results = query_collection(test_query, top_k=3)
        print(f"\n--- Top 3 results for: '{test_query}' ---")
        for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
            print(f"\n(page {meta['page']}, distance {dist:.4f})")
            print(doc[:200])