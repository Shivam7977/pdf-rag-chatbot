from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db import models
from app.services.bm25_retriever import invalidate_bm25_index

GUEST_TTL_HOURS = 24


def cleanup_stale_guests(db: Session):
    """Deletes guest chat sessions (and their messages/chunks, via cascade)
    inactive for more than GUEST_TTL_HOURS. Called lazily at the start of
    a couple of endpoints instead of a background scheduler — Render's free
    tier sleeps the whole process on inactivity, which would silently kill
    an in-process scheduler too."""
    cutoff = datetime.utcnow() - timedelta(hours=GUEST_TTL_HOURS)
    stale = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.is_guest == True, models.ChatSession.last_active_at < cutoff)
        .all()
    )
    stale_ids = [str(session.id) for session in stale]  # captured before delete
    for session in stale:
        db.delete(session)
    if stale:
        db.commit()
        # Was missing before — each deleted guest session's in-memory BM25
        # index would otherwise outlive its (now-deleted) data until server
        # restart, wasting memory indefinitely on a long-running server.
        for session_id in stale_ids:
            invalidate_bm25_index(session_id)