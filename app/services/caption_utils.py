"""
Shared heuristic for finding a caption near a visual element (table, figure,
or chart) on a page. Used by table_extractor.py (pdfplumber pages) and
visual_extractor.py (PyMuPDF pages) — since those two libraries expose word
positions differently, this function takes an already-normalized word list
rather than a page object, so each caller adapts its own library's output
once and shares this same matching logic.
"""

CAPTION_SEARCH_DISTANCE = 60  # points; how far above/below the element to look


def find_nearby_caption(words: list[dict], bbox, prefixes: tuple[str, ...], max_words: int = 20) -> str | None:
    """
    words: list of {"text": str, "top": float} — "top" is the distance from
    the top of the page, in points, for each word (pdfplumber gives this
    directly; PyMuPDF's page.get_text("words") gives y0 which serves the
    same purpose).

    Looks at text lines immediately above and below the given bounding box
    for a line that starts with one of `prefixes` (case-insensitive) and is
    short enough to plausibly be a caption rather than a body paragraph.
    Prefers the line above (captions are more commonly placed above a
    table/figure than below it).
    """
    x0, top, x1, bottom = bbox

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

    def _looks_like_caption(text: str) -> bool:
        stripped = text.strip().lower()
        if not stripped or len(stripped.split()) > max_words:
            return False
        return stripped.startswith(prefixes)

    for _, text in sorted(above_candidates):
        if _looks_like_caption(text):
            return text.strip()
    for _, text in sorted(below_candidates):
        if _looks_like_caption(text):
            return text.strip()

    return None