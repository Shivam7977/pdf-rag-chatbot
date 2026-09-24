import re
import hashlib
from langchain_text_splitters import RecursiveCharacterTextSplitter

HEADING_PATTERN = re.compile(r"^# (.+)$", re.MULTILINE)

ELEMENT_TYPE_LABELS = {
    "table": "Table",
    "image": "Image",
    "chart": "Chart",
    "figure": "Figure",
}


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


def _prefix_with_context(chunk_text: str, section_title: str | None, element_type: str = "text") -> str:
    """
    Prepends the chunk's section heading (and, for table/image/chart
    chunks, a type label) directly onto its stored text — the same text
    field that gets tokenized for BM25 and embedded for dense search.

    Without this, section_title and element_type only ever existed as DB
    metadata columns that neither retrieval path ever looked at — a query
    like "projects" or "skills" had no way to match a chunk whose heading
    matched but whose BODY text never repeated that word (e.g. a resume's
    "Projects" section entries never say the word "projects" anywhere in
    their own text). Prepending makes the heading part of the searchable
    surface itself, for both lexical (BM25) and semantic (embedding)
    matching — and gives the LLM the same context when it later reads
    this chunk.
    """
    lines = []
    if section_title:
        lines.append(f"[Section: {section_title}]")
    if element_type in ELEMENT_TYPE_LABELS:
        lines.append(f"[{ELEMENT_TYPE_LABELS[element_type]}]")

    if not lines:
        return chunk_text

    return "\n".join(lines) + "\n\n" + chunk_text


def chunk_pages(pages: list, table_chunks: list | None = None, visual_chunks: list | None = None, chunk_size: int = 512, chunk_overlap: int = 100):
    """
    Takes the output of extract_text_from_pdf() (and optionally
    extract_tables_from_pdf() / extract_visuals_from_pdf()) and produces the
    final list of chunks to embed and store.

    Text chunks: split heading-aware (section boundaries are respected, a
    chunk never straddles two sections) and tagged with section_title.

    Table chunks and visual chunks: passed through UNCHANGED content-wise
    (never run through the character splitter — breaking a table or a
    figure's description across chunks would corrupt it), but now also
    inherit whatever section_title was active on their page, instead of
    always being None.

    Every chunk's final "text" is prefixed with its section heading (and
    element type, for table/image/chart) via _prefix_with_context() — see
    that function's docstring for why.

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
    page_section_map = {}   # page number -> section_title active by end of that page

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
                    "text": _prefix_with_context(chunk_text, current_section, "text"),
                    "page": page["page"],
                    "source": page["source"],
                    "section_title": current_section,
                    "element_type": "text",
                })
                chunk_index += 1

        # Record the section active by the time we're done with this page —
        # used below so table/visual chunks on this page can inherit it.
        page_section_map[page["page"]] = current_section

    # Table and visual (image/chart) chunks: content stays unmodified, but
    # each now inherits the section_title active on its page (falling back
    # to the last known section overall if its page had no heading of its
    # own) instead of always being None.
    for id_suffix, extra_chunks, default_type in (("tbl", table_chunks, "table"), ("vis", visual_chunks, "figure")):
        if not extra_chunks:
            continue
        for i, c in enumerate(extra_chunks, start=1):
            doc_id = _get_document_id(c["source"])
            section = page_section_map.get(c["page"], current_section)
            element_type = c.get("element_type", default_type)
            all_chunks.append({
                "chunk_id": f"{doc_id}_p{c['page']}_{id_suffix}{i}",
                "text": _prefix_with_context(c["text"], section, element_type),
                "page": c["page"],
                "source": c["source"],
                "section_title": section,
                "element_type": element_type,
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