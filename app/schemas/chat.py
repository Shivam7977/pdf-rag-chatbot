from uuid import UUID
from pydantic import BaseModel


class ChatRequest(BaseModel):
    # UUID (not str) — Pydantic validates the format before this ever
    # reaches a query, so a malformed ID gets a clean 422 instead of a raw
    # DB-level exception (this is exactly the failure mode we saw firsthand
    # debugging retrieval earlier: a malformed chat_session_id string
    # reached Postgres directly and leaked a raw SQL error).
    chat_session_id: UUID
    question: str
    # "sources" (filenames) removed — chat_session_id alone now scopes
    # retrieval, since every chunk is tagged with the session that uploaded it.


class SourceChunk(BaseModel):
    page: int
    source: str
    text: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]