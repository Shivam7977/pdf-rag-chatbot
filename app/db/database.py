from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — fine for normal request/response routes.
    Do NOT use this for StreamingResponse generators; see chat.py's own
    SessionLocal() usage for why."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()