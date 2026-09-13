import re
import hashlib
from langchain_text_splitters import RecursiveCharacterTextSplitter

HEADING_PATTERN = re.compile(r"^# (.+)$", re.MULTILINE)


def _get_document_id(source: str):
    """Creates a short, stable ID for a document based on its filename."""
    return hashlib.md5(source.encode()).hexdigest()[:8]


def _split_into_sections(text: str):
    """
    Splits a page's text into (section_title, section_text) pieces based on
    the '# heading' lines produced by pdf_parser's heading detection. This
    is what lets chunking respect section boundaries instead of the
    character-based splitter cutting straight through a heading.

    Text before the first heading on a page has section_title=None — the
    caller carries forward whatever section title was active from the
    previous page, since a page doesn't always start with a new heading.
    """
    matches = list(HEADING_PATTERN.finditer(text))
    if not matches:
        return [(None, text)]

    sections = []
    if matches[0].start() > 0:
        sections.append((None, text[:matches[0].start()]))

    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((title, text[start:end]))

    return sections


def chunk_pages(pages: list, table_chunks: list | None = None, chunk_size: int = 512, chunk_overlap: int = 100):
    """
    Takes the output of extract_text_from_pdf() (and optionally
    extract_tables_from_pdf()) and produces the final list of chunks to
    embed and store.

    Text chunks: split heading-aware (section boundaries are respected, a
    chunk never straddles two sections) and tagged with section_title.

    Table chunks: passed through UNCHANGED — never run through the
    character splitter, since breaking a table across chunks would corrupt
    its structure. Each keeps its own element_type="table".

    NOTE: chunk_size/chunk_overlap are measured in CHARACTERS, not tokens.
    We'll revisit sizing once we have an evaluation harness (Phase 6).
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    all_chunks = []
    current_section = None  # carries across pages until a new heading appears

    for page in pages:
        if not page["text"].strip():  # skip empty/blank pages
            continue

        doc_id = _get_document_id(page["source"])
        sections = _split_into_sections(page["text"])
        chunk_index = 1

        for title, section_text in sections:
            if title is not None:
                current_section = title

            if not section_text.strip():
                continue

            for chunk_text in splitter.split_text(section_text):
                all_chunks.append({
                    "chunk_id": f"{doc_id}_p{page['page']}_c{chunk_index}",
                    "text": chunk_text,
                    "page": page["page"],
                    "source": page["source"],
                    "section_title": current_section,
                    "element_type": "text",
                })
                chunk_index += 1

    if table_chunks:
        for i, t in enumerate(table_chunks, start=1):
            doc_id = _get_document_id(t["source"])
            all_chunks.append({
                "chunk_id": f"{doc_id}_p{t['page']}_tbl{i}",
                "text": t["text"],
                "page": t["page"],
                "source": t["source"],
                # Not inheriting the nearest heading here yet — table captions
                # already carry their own context (see table_extractor.py).
                # Could attach the surrounding section_title too if retrieval
                # testing later shows it's needed.
                "section_title": None,
                "element_type": "table",
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
            print(f"\n[{c['chunk_id']}] (page {c['page']}, section={c['section_title']!r}, {len(c['text'])} chars)")
            print(c["text"])