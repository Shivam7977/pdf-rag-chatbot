"""
Table extraction: finds tables on each page via pdfplumber, converts each to
a Markdown table, and prefixes it with the nearest caption-like text (e.g.
"Table 1: Revenue by Year") so the chunk carries context on its own instead
of being a bare grid of numbers.
"""
import pdfplumber

# A caption line is usually short and starts with a recognizable label —
# this keeps the heuristic cheap and avoids grabbing an unrelated paragraph
# that merely happens to be near the table.
CAPTION_PREFIXES = ("table", "tab.", "tbl")
CAPTION_MAX_WORDS = 20
CAPTION_SEARCH_DISTANCE = 60  # points; how far above/below the table to look


def _looks_like_caption(text: str) -> bool:
    stripped = text.strip().lower()
    if not stripped:
        return False
    if len(stripped.split()) > CAPTION_MAX_WORDS:
        return False
    return stripped.startswith(CAPTION_PREFIXES)


def _find_caption(page, table_bbox) -> str | None:
    """
    Looks at text lines immediately above and below the table's bounding box
    for something that reads like a caption. Prefers the line above (captions
    are more commonly placed above a table than below it).
    """
    x0, top, x1, bottom = table_bbox
    words = page.extract_words()

    lines_by_top = {}
    for w in words:
        lines_by_top.setdefault(round(w["top"]), []).append(w["text"])

    above_candidates = []
    below_candidates = []
    for line_top, line_words in lines_by_top.items():
        line_text = " ".join(line_words)
        if top - CAPTION_SEARCH_DISTANCE <= line_top < top:
            above_candidates.append((top - line_top, line_text))
        elif bottom < line_top <= bottom + CAPTION_SEARCH_DISTANCE:
            below_candidates.append((line_top - bottom, line_text))

    for distance, text in sorted(above_candidates):
        if _looks_like_caption(text):
            return text.strip()
    for distance, text in sorted(below_candidates):
        if _looks_like_caption(text):
            return text.strip()

    return None


def _rows_to_markdown(rows: list[list[str | None]]) -> str:
    """
    Converts pdfplumber's row-of-cells output into a Markdown table.
    Empty/None cells become blank cells rather than the literal "None".
    """
    cleaned_rows = [
        [(cell or "").strip().replace("\n", " ") for cell in row]
        for row in rows
        if row and any((cell or "").strip() for cell in row)
    ]
    if not cleaned_rows:
        return ""

    header, *body_rows = cleaned_rows
    col_count = len(header)

    lines = ["| " + " | ".join(header) + " |"]
    lines.append("| " + " | ".join(["---"] * col_count) + " |")
    for row in body_rows:
        # pdfplumber sometimes returns rows with a different cell count than
        # the header (merged cells, ragged tables) — pad/truncate to keep the
        # Markdown well-formed rather than emitting a broken row.
        row = (row + [""] * col_count)[:col_count]
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def extract_tables_from_page(page, page_number: int, filename: str) -> list[dict]:
    """
    Returns a list of table entries for one page, each ready to become its
    own chunk: {"text": <caption + markdown>, "page": ..., "source": ...,
    "element_type": "table"}.
    """
    results = []
    found_tables = page.find_tables()

    for table in found_tables:
        rows = table.extract()
        markdown = _rows_to_markdown(rows)
        if not markdown:
            continue

        caption = _find_caption(page, table.bbox)
        text = f"{caption}\n\n{markdown}" if caption else markdown

        results.append({
            "text": text,
            "page": page_number,
            "source": filename,
            "element_type": "table",
        })

    return results


def extract_tables_from_pdf(file_path: str, display_name: str | None = None) -> list[dict]:
    filename = display_name or file_path.split("\\")[-1].split("/")[-1]

    table_chunks = []
    with pdfplumber.open(file_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            table_chunks.extend(extract_tables_from_page(page, page_number, filename))

    return table_chunks


if __name__ == "__main__":
    import sys
    test_file = sys.argv[1] if len(sys.argv) > 1 else None
    if not test_file:
        print("Usage: python table_extractor.py <path_to_pdf>")
    else:
        tables = extract_tables_from_pdf(test_file)
        print(f"Found {len(tables)} table(s).")
        for i, t in enumerate(tables, start=1):
            print(f"\n--- Table {i} (page {t['page']}) ---")
            print(t["text"])