import ollama
from app.config import LLM_PROVIDER

CONFIDENCE_HIGH_THRESHOLD = 0.0


def get_confidence_level(top_score: float) -> str:
    if top_score > CONFIDENCE_HIGH_THRESHOLD:
        return "high"
    return "low"


def rewrite_query(question: str, recent_history: list[dict]) -> str:
    if not recent_history:
        return question

    history_text = "\n".join(f"{h['role']}: {h['content']}" for h in recent_history)

    prompt = f"""Given this recent conversation, rewrite the LATEST question so it can
be understood on its own, without needing the earlier messages for context.
Only rewrite if the question actually depends on prior context (e.g. uses
"it", "that", "the decoder" referring to something mentioned earlier).
If the question is already standalone, return it UNCHANGED.
Return ONLY the rewritten question, nothing else — no explanation.

CONVERSATION SO FAR:
{history_text}

LATEST QUESTION: {question}

STANDALONE QUESTION:"""

    if LLM_PROVIDER == "ollama":
        response = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1},
        )
        rewritten = response["message"]["content"].strip()
        return rewritten if rewritten else question
    else:
        return question


def _stream_llm(prompt: str):
    if LLM_PROVIDER == "ollama":
        stream = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            options={"temperature": 0.1}
        )
        for chunk in stream:
            content = chunk["message"]["content"]
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