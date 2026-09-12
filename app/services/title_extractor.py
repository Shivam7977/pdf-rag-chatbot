import ollama
from app.config import LLM_PROVIDER


def extract_display_title(first_page_text: str, fallback_filename: str) -> str:
    """
    Generates a short, natural-language title/topic for a document from its
    first page — used so a user can refer to it in conversation ("the
    Global South funds report") even when the filename itself is
    meaningless (e.g. "22744iied.pdf"). Falls back to the filename on any
    failure, since this is a nice-to-have, not something that should ever
    block an upload from succeeding.
    """
    snippet = first_page_text[:1500]  # first page is plenty for a title

    prompt = f"""Give this document a short, descriptive title (5-8 words) based on
its actual topic/content. Return ONLY the title, nothing else — no quotes,
no explanation.

DOCUMENT TEXT:
{snippet}

TITLE:"""

    try:
        if LLM_PROVIDER == "ollama":
            response = ollama.chat(
                model="llama3.2",
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.2},
            )
            title = response["message"]["content"].strip().strip('"')
            return title if title else fallback_filename
        else:
            return fallback_filename
    except Exception:
        return fallback_filename