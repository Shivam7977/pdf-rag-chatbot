from langchain_text_splitters import RecursiveCharacterTextSplitter
import hashlib

def _get_document_id(source: str):
    """Creates a short, stable ID for a document based on its filename."""
    return hashlib.md5(source.encode()).hexdigest()[:8]

def chunk_pages(pages: list, chunk_size: int = 512, chunk_overlap: int = 100):
    """
    Takes the output of extract_text_from_pdf() and splits each page's
    text into smaller overlapping chunks.

    NOTE: chunk_size/chunk_overlap are measured in CHARACTERS, not tokens.
    We'll revisit sizing once we have an evaluation harness (Phase 6).

    Returns a list of chunks, each tagged with a stable chunk_id
    (based on document + page + position) plus page/source metadata.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    all_chunks = []

    for page in pages:
        if not page["text"].strip():  # skip empty/blank pages
            continue

        doc_id = _get_document_id(page["source"])
        page_chunks = splitter.split_text(page["text"])

        for i, chunk_text in enumerate(page_chunks, start=1):
            all_chunks.append({
                "chunk_id": f"{doc_id}_p{page['page']}_c{i}",
                "text": chunk_text,
                "page": page["page"],
                "source": page["source"]
            })

    return all_chunks


if __name__ == "__main__":
    import sys
    sys.path.append(".")
    from pdf_parser import extract_text_from_pdf

    test_file = sys.argv[1] if len(sys.argv) > 1 else None
    if not test_file:
        print("Usage: python chunker.py <path_to_pdf>")
    else:
        pages = extract_text_from_pdf(test_file)
        chunks = chunk_pages(pages)
        print(f"Total chunks created: {len(chunks)}")
        print("--- Preview of first 2 chunks ---")
        for c in chunks[:2]:
            print(f"\n[{c['chunk_id']}] (page {c['page']}, {len(c['text'])} chars)")
            print(c["text"])