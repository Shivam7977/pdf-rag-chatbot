import os
from dotenv import load_dotenv

load_dotenv()

# --- Database (Aiven Postgres) ---
DATABASE_URL = os.getenv("DATABASE_URL")  # postgresql://user:pass@host:port/dbname?sslmode=require

# --- Auth ---
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# --- Upload limits ---
MAX_UPLOAD_BYTES_PER_SESSION = 50 * 1024 * 1024  # 50MB

# --- CORS ---
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:8000")

# --- LLM ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

# CHROMA_PATH removed — vectors now live in Postgres via pgvector.