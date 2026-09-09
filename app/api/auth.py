from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db import models
from app.schemas.auth import SignupRequest, LoginRequest, GoogleLoginRequest, SetPasswordRequest, TokenResponse
from app.services.security import hash_password, verify_password, create_access_token, verify_google_token
from app.services.cleanup import cleanup_stale_guests
from app.services.email import send_welcome_email
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user = models.User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    send_welcome_email(user.email)

    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        info = verify_google_token(payload.id_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token.")

    email, google_id = info["email"], info["sub"]
    user = db.query(models.User).filter(models.User.email == email).first()
    is_new_user = False
    if not user:
        user = models.User(email=email, google_id=google_id)
        db.add(user)
        db.commit()
        db.refresh(user)
        is_new_user = True
    elif not user.google_id:
        user.google_id = google_id
        db.commit()

    if is_new_user:
        send_welcome_email(user.email)

    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/guest")
def start_guest_session(db: Session = Depends(get_db)):
    cleanup_stale_guests(db)
    session = models.ChatSession(is_guest=True, user_id=None)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"chat_session_id": str(session.id)}


@router.post("/set-password")
def set_password(
    payload: SetPasswordRequest,
    user: models.User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user:
        raise HTTPException(status_code=401, detail="Login required.")
    if user.password_hash:
        raise HTTPException(status_code=400, detail="This account already has a password. Use the change-password flow instead.")

    user.password_hash = hash_password(payload.password)
    db.commit()
    return {"status": "password set"}


@router.get("/me")
def get_current_user_info(user: models.User | None = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Login required.")
    return {
        "email": user.email,
        "has_password": user.password_hash is not None,
        "has_google": user.google_id is not None,
    }