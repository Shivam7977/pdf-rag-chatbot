import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.chat import ChatRequest
from app.services.retriever import retrieve_chunks
from app.services.llm import generate_answer

router = APIRouter()

# Same guardrail threshold and message as the non-streaming version (Phase 8).
# Cross-encoder scores are unbounded logits — roughly: >0 relevant, <0 not.
RERANK_CONFIDENCE_THRESHOLD = -3.0
NO_ANSWER_MESSAGE = "I couldn't find this in the uploaded documents."


def sse_event(event: str, data: dict) -> str:
    """Formats one Server-Sent Event block: 'event: X\\ndata: {...}\\n\\n'."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def stream_chat_response(question: str):
    chunks = retrieve_chunks(question, top_k=5)

    # Guardrail: same logic as Phase 8, but now the "not found" message is
    # streamed word-by-word too, so the frontend UX stays consistent whether
    # the answer came from the LLM or from the guardrail short-circuit.
    if not chunks or chunks[0]["rerank_score"] < RERANK_CONFIDENCE_THRESHOLD:
        for word in NO_ANSWER_MESSAGE.split(" "):
            yield sse_event("token", {"content": word + " "})
        yield sse_event("done", {})
        yield sse_event("sources", {"sources": []})
        return

    try:
        for token in generate_answer(question, chunks):
            yield sse_event("token", {"content": token})

        yield sse_event("done", {})

        # Sources are sent only at the end — retrieval already finished
        # before generation started, so there's no reason to send them early.
        # Dedupe by (source, page): multiple retrieved chunks can come from
        # the same page, but the UI only needs to show each page once.
        seen = set()
        sources = []
        for c in chunks:
            key = (c["source"], c["page"])
            if key in seen:
                continue
            seen.add(key)
            sources.append({"page": c["page"], "source": c["source"], "text": c["text"][:200]})

        yield sse_event("sources", {"sources": sources})

    except Exception as e:
        yield sse_event("error", {"message": str(e)})


@router.post("/chat")
def chat(request: ChatRequest):
    return StreamingResponse(
        stream_chat_response(request.question),
        media_type="text/event-stream"
    )