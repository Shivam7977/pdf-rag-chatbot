import ollama
from app.config import LLM_PROVIDER

def generate_answer(question: str, context_chunks: list):
    context_text = "\n\n".join(
        f"[Source: {c['source']}, Page {c['page']}]\n{c['text']}"
        for c in context_chunks
    )

    prompt = f"""Answer the question using ONLY the context below.
Use ONLY the information explicitly supported by the CONTEXT.
Do not add assumptions, recommendations, opinions, or outside knowledge.
If the answer is not present in the context, say
"I couldn't find this in the uploaded documents."

Do NOT include inline citations, source filenames, or page numbers in your
answer text. The sources are already shown separately in the interface, so
just answer naturally without mentioning where the information came from.

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
            # Low temperature — this is a fact-retrieval tool, not a creative
            # writer. High randomness was causing the same question to get
            # differently-phrased (and sometimes garbled) answers each time.
            options={"temperature": 0.1}
        )
        for chunk in stream:
            content = chunk["message"]["content"]
            if content:
                yield content
    else:
        raise NotImplementedError(f"LLM provider '{LLM_PROVIDER}' not implemented yet")