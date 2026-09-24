import re
import ollama
from groq import Groq
from app.config import LLM_PROVIDER, GROQ_API_KEY

CONFIDENCE_HIGH_THRESHOLD = 0.0
SHORT_QUERY_WORD_THRESHOLD = 4

QUESTION_WORDS = {"what", "who", "how", "why", "when", "where", "which"}
ACTION_WORDS = {
    "summarize", "summarise", "summary",
    "explain", "describe",
    "compare", "contrast",
    "list", "show",
    "tell", "give",
    "define", "definition",
    "extract", "find",
    "identify", "mention",
    "provide", "details", "overview",
}
REFERENCE_WORDS = {"it", "that", "this", "he", "she", "they", "him", "her", "them", "its", "his", "their"}

_groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Groq's currently-supported free-tier model. Check console.groq.com/docs/models
# if this ever gets deprecated — Groq rotates model availability periodically.
GROQ_MODEL = "llama-3.1-8b-instant"


def get_confidence_level(top_score: float) -> str:
    if top_score > CONFIDENCE_HIGH_THRESHOLD:
        return "high"
    return "low"


def _chat_once(prompt: str, temperature: float = 0.1) -> str:
    """Non-streaming single response — used for reference resolution and
    title extraction, where we just need the final text, not a token
    stream."""
    if LLM_PROVIDER == "ollama":
        response = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": temperature},
        )
        return response["message"]["content"].strip()
    elif LLM_PROVIDER == "groq":
        response = _groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    else:
        raise NotImplementedError(f"LLM provider '{LLM_PROVIDER}' not implemented yet")


def _normalize_words(question: str) -> list[str]:
    return [w.strip(".,!?;:\"'()[]{}").lower() for w in question.strip().split()]


def _resolve_reference(question: str, recent_history: list[dict]) -> str:
    """
    LLM call used ONLY to resolve a pronoun/reference-based follow-up
    ("what about it", "tell me more about that", "and when did that
    happen") against the recent conversation — NOT to rephrase or
    "improve" the question otherwise. Kept as its own narrow step, separate
    from the deterministic templating below, so it can never touch a
    question that doesn't actually need it.
    """
    history_text = "\n".join(f"{h['role']}: {h['content']}" for h in recent_history)

    prompt = f"""The LATEST question below uses a reference word ("it", "that",
"he", "they", etc.) that refers to something mentioned earlier in the
conversation. Rewrite ONLY to replace that reference with what it actually
refers to, based on the conversation. Do not change anything else about the
question's wording or add extra phrasing.
Return ONLY the rewritten question, nothing else — no explanation.

CONVERSATION SO FAR:
{history_text}

LATEST QUESTION: {question}

RESOLVED QUESTION:"""

    try:
        resolved = _chat_once(prompt)
        return resolved if resolved else question
    except Exception:
        return question  # fail open — never block a question over this


def build_search_query(question: str, recent_history: list[dict]) -> str:
    """
    Decides what to actually search with — NOT a general rewriter. Four
    outcomes, checked in order:
    1. Empty/whitespace question -> returned as-is (caller/validation
       handles rejecting it).
    2. Contains a reference word ("it", "that", "he"...) AND there's prior
       history -> resolve the reference via a narrow, single-purpose LLM
       call (see _resolve_reference). This is the only case that touches
       the LLM.
    3. Contains a question-word (what/who/why/how...) or an action-word
       (summarize/compare/list/tell/give...), OR is longer than
       SHORT_QUERY_WORD_THRESHOLD words -> already a natural/well-formed
       query (or an action/broad-mode query that doesn't need templating
       at all) -> returned UNCHANGED. This is deliberately conservative:
       we only transform a query when we have strong evidence doing so
       will help, never as a default.
    4. Otherwise: a short, bare noun/topic phrase ("skills", "Oracle
       Corporation", "Oracle projects") -> wrapped in a deterministic
       template so the downstream cross-encoder reranker (trained on
       question<->passage pairs, scores bare keywords poorly) has
       something to work with. No LLM call — fully predictable output,
       can never come back garbled.
    """
    question = question.strip()
    if not question:
        return question

    words = _normalize_words(question)

    if recent_history and any(w in REFERENCE_WORDS for w in words):
        return _resolve_reference(question, recent_history)

    has_question_or_action_word = any(w in QUESTION_WORDS or w in ACTION_WORDS for w in words)
    is_short = len(words) <= SHORT_QUERY_WORD_THRESHOLD

    if has_question_or_action_word or not is_short:
        return question

    return f"What does the document say about {question}?"


def _stream_llm(prompt: str, temperature: float = 0.1):
    if LLM_PROVIDER == "ollama":
        stream = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            options={"temperature": temperature},
        )
        for chunk in stream:
            content = chunk["message"]["content"]
            if content:
                yield content
    elif LLM_PROVIDER == "groq":
        stream = _groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    else:
        raise NotImplementedError(f"LLM provider '{LLM_PROVIDER}' not implemented yet")


def _build_prompt(question: str, context_text: str, mode_instruction: str) -> str:
    return f"""Answer the question using ONLY the context below.
Use ONLY the information explicitly supported by the CONTEXT.
Do not add assumptions, recommendations, opinions, or outside knowledge.
If the answer is not present in the context, say
"I couldn't find this in the uploaded documents."

The context below may include multiple sections from the document, not all
of which are relevant to the question. Identify and use ONLY the part(s)
that actually answer the question; ignore unrelated sections rather than
treating their presence as reason to say the answer wasn't found.

Do NOT include inline citations, source filenames, or page numbers in your
answer text — the sources are already shown separately in the interface.
Do NOT add your own headings, document names, or "===" style markers —
just write the answer content itself.

{mode_instruction}

IMPORTANT:
- Answer in the same language/style the question was asked in.
- Use the context to understand what technical terms actually mean.
- Do NOT translate domain-specific terms or proper nouns word-by-word
  (for example, keep "Global South funds" as a concept rather than
  translating each word separately).
- Explain the meaning naturally in the target language, rather than
  doing a literal word-for-word translation.


CONTEXT:
{context_text}

QUESTION:
{question}

ANSWER:"""


def _flat_context_text(chunks) -> str:
    return "\n\n".join(
        f"[Source: {c['source']}, Page {c['page']}]\n{c['text']}"
        for c in chunks
    )


MODE_INSTRUCTIONS = {
    "specific": "",
    "broad": """This is a SUMMARY/OVERVIEW request. The context below is a
representative sample spread across the whole document, not just the
most similar passages to the question — synthesize it into a coherent
summary or set of key points, covering the range of what's included rather
than focusing on only one part.""",
    "comparison": """This is a COMPARISON request. The context below is
grouped by source document (see the [Source: ...] labels). Structure your
answer to explicitly compare/contrast across the documents — call out
where they agree, differ, or where one covers something the other doesn't.""",
}


def generate_answer(question: str, context_chunks, mode: str = "specific"):
    """
    context_chunks is either:
    - a flat list of chunk dicts (specific/comparison modes, and single-
      document broad mode), or
    - a GROUPED list of {"filename", "chunks"} (multi-document broad mode
      only — see vector_store.get_spread_chunks()).

    For grouped multi-document summaries, this makes ONE SEPARATE LLM call
    PER DOCUMENT instead of asking one call to cover all documents in a
    single structured response — small models are unreliable at fully
    following a "write N labeled sections" instruction over a long
    response and tend to only complete the first section. A bold heading
    is inserted by CODE between each document's summary, not by the model,
    so it can never be skipped or malformed.
    """
    is_multi_doc_broad = (
        mode == "broad"
        and isinstance(context_chunks, list)
        and context_chunks
        and isinstance(context_chunks[0], dict)
        and "chunks" in context_chunks[0]
    )

    if is_multi_doc_broad:
        for i, group in enumerate(context_chunks):
            if i > 0:
                yield "\n\n"
            yield f"**{group['filename']}**\n\n"

            context_text = _flat_context_text(group["chunks"])
            prompt = _build_prompt(question, context_text, MODE_INSTRUCTIONS["broad"])
            yield from _stream_llm(prompt)
        return

    context_text = _flat_context_text(context_chunks)
    mode_instruction = MODE_INSTRUCTIONS.get(mode, "")
    prompt = _build_prompt(question, context_text, mode_instruction)
    yield from _stream_llm(prompt)