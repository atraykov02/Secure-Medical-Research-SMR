from __future__ import annotations

from sqlalchemy.orm import Session

from .models import AuditLog, User


def log_event(
    db: Session,
    *,
    event_type: str,
    study_id: str | None = None,
    user: User | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    # Privacy rule: callers must never pass patient-level data or local plaintext aggregates.
    entry = AuditLog(
        event_type=event_type,
        study_id=study_id,
        user_id=user.id if user else None,
        organization_id=user.organization_id if user else None,
        metadata_json=metadata or {},
    )
    db.add(entry)
    db.flush()
    return entry
