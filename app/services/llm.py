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


MODE_INSTRUCTIONS = {
    "specific": "",
    "broad": """This is a SUMMARY/OVERVIEW request. The context below is a
representative sample spread across the whole document(s), not just the
most similar passages to the question — synthesize it into a coherent
summary or set of key points, covering the range of what's included rather
than focusing on only one part.""",
    "comparison": """This is a COMPARISON request. The context below is
grouped by source document (see the [Source: ...] labels). Structure your
answer to explicitly compare/contrast across the documents — call out
where they agree, differ, or where one covers something the other doesn't.""",
}


def generate_answer(question: str, context_chunks: list, mode: str = "specific"):
    context_text = "\n\n".join(
        f"[Source: {c['source']}, Page {c['page']}]\n{c['text']}"
        for c in context_chunks
    )

    mode_instruction = MODE_INSTRUCTIONS.get(mode, "")

    prompt = f"""Answer the question using ONLY the context below.
Use ONLY the information explicitly supported by the CONTEXT.
Do not add assumptions, recommendations, opinions, or outside knowledge.
If the answer is not present in the context, say
"I couldn't find this in the uploaded documents."

Do NOT include inline citations, source filenames, or page numbers in your
answer text. The sources are already shown separately in the interface, so
just answer naturally without mentioning where the information came from.

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