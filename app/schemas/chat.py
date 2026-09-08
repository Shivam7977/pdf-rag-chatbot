from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    # Filenames (matching the "source" metadata field on each chunk) that this
    # chat session has uploaded so far. Retrieval is restricted to only these
    # documents — this is what gives each session its own scoped context,
    # instead of searching every PDF ever uploaded to the app.
    sources: list[str] = []


class SourceChunk(BaseModel):
    page: int
    source: str
    text: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]