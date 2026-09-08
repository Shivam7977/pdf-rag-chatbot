from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db.database import Base, engine
from app.api.auth import router as auth_router
from app.api.chats import router as chats_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.config import FRONTEND_ORIGIN

app = FastAPI(title="PDF RAG Chatbot")

# Creates tables if they don't exist yet — fine at this scale.
# A real migration tool (Alembic) would replace this if the schema
# needs to change after data already exists.
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in FRONTEND_ORIGIN.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(chat_router)
app.include_router(documents_router)


@app.get("/health")
def health():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")