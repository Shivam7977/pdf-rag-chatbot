from pydantic import BaseModel


class ChatRequest(BaseModel):
    chat_session_id: str
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