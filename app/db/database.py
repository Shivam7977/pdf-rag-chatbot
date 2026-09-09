from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

# Aiven (and some other providers) give URIs starting with "postgres://",
# but SQLAlchemy 2.0+ only recognizes "postgresql://" — normalize it here
# so .env can have either form without breaking.
_db_url = DATABASE_URL.replace("postgres://", "postgresql://", 1) if DATABASE_URL else DATABASE_URL

engine = create_engine(_db_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()