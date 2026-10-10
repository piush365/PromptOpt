"""Retention policy in the web app: prompts past their `expires_at` (RETENTION_DAYS after they were stored) are
deleted, with everything derived from them (ON DELETE CASCADE), before an endpoint stores, reads or lists prompts.
So the UI never shows a prompt past its expiry date, and expired data does not wait for a manual purge.

    @app.get("/api/history", dependencies=[Depends(enforce_retention)])

FastAPI caches dependencies per request, so this runs on the same session as the endpoint's own `Depends(get_db)`.
`python -m app.init_db --purge` does the same from the command line (e.g. a daily cron job).
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.repository import purge_expired


def enforce_retention(db: Session = Depends(get_db)) -> None:
    purge_expired(db)
