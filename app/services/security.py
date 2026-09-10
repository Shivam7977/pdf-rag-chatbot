import secrets
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from app.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, GOOGLE_CLIENT_ID

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

VERIFICATION_CODE_TTL_MINUTES = 15


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def verify_google_token(token: str) -> dict:
    return google_id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)


def generate_verification_code() -> tuple[str, "datetime"]:
    """Returns a 6-digit numeric code and its expiry timestamp."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.utcnow() + timedelta(minutes=VERIFICATION_CODE_TTL_MINUTES)
    return code, expires_at