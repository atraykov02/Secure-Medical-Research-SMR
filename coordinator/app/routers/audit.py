from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import AuditLog, Organization, Study, StudyParticipant, User, UserRole
from ..schemas import AuditResponse

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditResponse])
def list_audit(
    study_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)

    if user.role == UserRole.RESEARCHER:
        allowed = select(Study.id).where(Study.created_by == user.id)
        stmt = stmt.where(AuditLog.study_id.in_(allowed))
    elif user.role == UserRole.ORG_ADMIN:
        if not user.organization_id:
            return []
        allowed = select(StudyParticipant.study_id).where(
            StudyParticipant.organization_id == user.organization_id
        )
        stmt = stmt.where(AuditLog.study_id.in_(allowed))

    if study_id:
        # The role filter above deliberately turns inaccessible study IDs into an
        # empty result rather than leaking whether another study exists.
        stmt = stmt.where(AuditLog.study_id == study_id)

    rows = list(db.scalars(stmt))
    organization_ids = {row.organization_id for row in rows if row.organization_id}
    organization_names = {
        organization.id: organization.name
        for organization in db.scalars(
            select(Organization).where(Organization.id.in_(organization_ids))
        )
    } if organization_ids else {}
    user_ids = {row.user_id for row in rows if row.user_id}
    users = {
        audit_user.id: audit_user
        for audit_user in db.scalars(select(User).where(User.id.in_(user_ids)))
    } if user_ids else {}
    return [
        AuditResponse(
            id=r.id,
            study_id=r.study_id,
            user_id=r.user_id,
            organization_id=r.organization_id,
            organization_name=organization_names.get(r.organization_id),
            actor_name=(f"{users[r.user_id].first_name} {users[r.user_id].last_name}" if r.user_id in users else None),
            actor_role=(users[r.user_id].role if r.user_id in users else None),
            event_type=r.event_type,
            metadata=r.metadata_json,
            created_at=r.created_at,
        )
        for r in rows
    ]
