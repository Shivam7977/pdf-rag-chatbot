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

# --- CORS ---
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:8000")

# --- LLM ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")