from fastapi import Depends, Header
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models
from app.services.security import decode_access_token


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User | None:
    """Returns the logged-in User, or None (guests simply send no
    Authorization header at all)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    user_id = decode_access_token(authorization.removeprefix("Bearer ").strip())
    if not user_id:
        return None
    return db.query(models.User).filter(models.User.id == user_id).first()