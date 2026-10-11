from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
def liveness():
    """Liveness probe: process is up. Deliberately does not touch the DB, so a DB outage
    does not make the platform restart healthy containers."""
    return {"status": "alive"}


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Readiness / startup probe — verifies app and DB connectivity."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB unavailable: {e}")
