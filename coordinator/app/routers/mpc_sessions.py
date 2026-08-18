from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import MPCSession, Study, StudyParticipant, User, UserRole
from ..schemas import MPCSessionResponse

router = APIRouter(prefix="/api/mpc-sessions", tags=["mpc-sessions"])


def _response(session: MPCSession, study_name: str, participant_count: int) -> dict:
    return {
        "id": session.id, "study_id": session.study_id, "study_name": study_name,
        "participant_count": participant_count,
        "threshold": session.threshold, "field_prime": session.field_prime,
        "security_model": session.security_model, "status": session.status,
        "error_message": session.error_message, "started_at": session.started_at,
        "completed_at": session.completed_at,
    }


def _allowed_study_ids(user: User):
    if user.role == UserRole.RESEARCHER:
        return select(Study.id).where(Study.created_by == user.id)
    if user.role == UserRole.ORG_ADMIN:
        if not user.organization_id:
            return select(Study.id).where(False)
        return select(StudyParticipant.study_id).where(
            StudyParticipant.organization_id == user.organization_id
        )
    return None


@router.get("", response_model=list[MPCSessionResponse])
def list_mpc_sessions(
    study_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    participant_count = (
        select(StudyParticipant.study_id, func.count().label("participant_count"))
        .group_by(StudyParticipant.study_id)
        .subquery()
    )
    stmt = (
        select(MPCSession, Study.name, participant_count.c.participant_count)
        .join(Study, Study.id == MPCSession.study_id)
        .join(participant_count, participant_count.c.study_id == Study.id)
        .order_by(MPCSession.started_at.desc())
    )
    allowed = _allowed_study_ids(user)
    if allowed is not None:
        stmt = stmt.where(MPCSession.study_id.in_(allowed))
    if study_id:
        stmt = stmt.where(MPCSession.study_id == study_id)
    return [_response(session, study_name, count) for session, study_name, count in db.execute(stmt).all()]


@router.get("/{session_id}", response_model=MPCSessionResponse)
def get_mpc_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    participant_count = (
        select(func.count())
        .select_from(StudyParticipant)
        .where(StudyParticipant.study_id == MPCSession.study_id)
        .scalar_subquery()
    )
    row = db.execute(select(MPCSession, Study.name, participant_count).join(Study, Study.id == MPCSession.study_id).where(MPCSession.id == session_id)).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="MPC session not found")
    session, study_name, count = row
    allowed = _allowed_study_ids(user)
    if allowed is not None:
        allowed_ids = set(db.scalars(allowed))
        if session.study_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="you do not have access to this MPC session")
    return _response(session, study_name, count)
