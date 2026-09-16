from fastapi import FastAPI, Request
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


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Baseline security headers on every response — API and the
    StaticFiles-served frontend alike. None of these require any
    request-specific logic, so a single blanket middleware covers both.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"  # stop browsers from MIME-sniffing a response into executing as something it isn't
    response.headers["X-Frame-Options"] = "DENY"  # this app is never meant to be iframed elsewhere — blocks clickjacking
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"  # limits what leaks to third-party referrers on outbound links/requests
    return response


app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(chat_router)
app.include_router(documents_router)


@app.get("/health")
def health():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")