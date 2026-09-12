import re

BROAD_PATTERNS = [
    r"\bsummar(y|ize|ise)\b",
    r"\bkey points?\b",
    r"\bmain points?\b",
    r"\boverview\b",
    r"\bwhat.*(document|pdf|this).*about\b",
    r"\bconclu(de|sion)\b",
]

COMPARISON_PATTERNS = [
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bdifference(s)? between\b",
    r"\bvs\.?\b",
    r"\bversus\b",
    r"\bsimilarit(y|ies)\b",
    r"\bcontrast\b",
]


def classify_question(question: str, document_count: int) -> str:
    q = question.lower()

    if document_count > 1 and any(re.search(p, q) for p in COMPARISON_PATTERNS):
        return "comparison"

    if any(re.search(p, q) for p in BROAD_PATTERNS):
        return "broad"

    return "specific"


def _normalize(name: str) -> str:
    name = re.sub(r"\.(pdf|PDF)$", "", name)
    name = re.sub(r"[_\-]+", " ", name)
    return name.strip().lower()


def extract_mentioned_documents(question: str, documents: list[dict]) -> list[str]:
    """
    documents: [{"filename": ..., "display_title": ...}, ...]

    Returns the filenames of documents that seem explicitly named in the
    question — matched against EITHER the filename OR its extracted
    display_title, so "compare paper1.pdf with the other one" and "compare
    the funding report with the other one" both work regardless of how
    meaningless the actual filename is. Empty list means nothing matched —
    callers should treat that as "use all documents".
    """
    q = question.lower()
    q_compact = re.sub(r"\s+", "", q)

    matched = []
    for doc in documents:
        candidates = [doc["filename"]]
        if doc.get("display_title"):
            candidates.append(doc["display_title"])

        for candidate in candidates:
            normalized = _normalize(candidate)
            normalized_compact = normalized.replace(" ", "")
            if normalized in q or normalized_compact in q_compact:
                matched.append(doc["filename"])
                break  # don't add the same filename twice if both candidates match

    return matched