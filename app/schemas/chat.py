from pydantic import BaseModel

class ChatRequest(BaseModel):
    question: str

class SourceChunk(BaseModel):
    page: int
    source: str
    text: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]