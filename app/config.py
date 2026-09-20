import os
from dotenv import load_dotenv

load_dotenv()

# --- Database (Aiven Postgres) ---
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Auth ---
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# --- Email (Resend) ---
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")

# --- Upload limits ---
MAX_UPLOAD_BYTES_PER_SESSION = 50 * 1024 * 1024
# Per-file cap, checked in addition to the per-session cumulative cap above.
# The frontend dropzone has always advertised "Max 20 MB" (see app.html) but
# the backend never actually enforced a per-file limit — only the 50MB
# session-total. Adding this closes that gap and matches what's promised.
MAX_SINGLE_UPLOAD_BYTES = 20 * 1024 * 1024

# --- CORS ---
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:8000")

# --- LLM ---
# "ollama" for local dev, "groq" for production (Render can't run Ollama).
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")