from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..audit import log_event
from ..dependencies import get_current_user, get_db, get_orchestrator, require_roles
from ..models import (
    AnalysisType,
    MPCSession,
    MPCSessionStatus,
    Organization,
    ParticipationStatus,
    Study,
    StudyCohortCriteria,
    StudyParticipant,
    StudyResult,
    StudyStatus,
    User,
    UserRole,
)
from ..schemas import ApprovalRequest, HospitalAccessResponse, ParticipantResponse, RunStudyResponse, StudyCreate, StudyResponse, VerificationResponse
from ..verification.reference_analysis import compare_results
from ..security import create_hospital_access_token

router = APIRouter(prefix="/api/studies", tags=["studies"])


def _load_study(db: Session, study_id: str) -> Study:
    stmt = (
        select(Study)
        .where(Study.id == study_id)
        .options(
            selectinload(Study.criteria),
            selectinload(Study.participants).selectinload(StudyParticipant.organization),
            selectinload(Study.results),
        )
    )
    study = db.scalar(stmt)
    if not study:
        raise HTTPException(status_code=404, detail="study not found")
    return study


def _response(study: Study) -> StudyResponse:
    result = study.results[-1].result_data if study.results else None
    return StudyResponse(
        id=study.id,
        name=study.name,
        description=study.description,
        analysis_type=study.analysis_type,
        study_mode=study.study_mode,
        status=study.status,
        created_by=study.created_by,
        created_at=study.created_at,
        completed_at=study.completed_at,
        criteria=study.criteria,
        participants=[
            ParticipantResponse(
                organization_id=p.organization_id,
                organization_name=p.organization.name,
                participant_index=p.participant_index,
                status=p.status,
            )
            for p in sorted(study.participants, key=lambda p: p.participant_index)
        ],
        result=result,
    )


def _user_can_access_study(study: Study, user: User) -> bool:
    if user.role == UserRole.SYSTEM_ADMIN:
        return True
    if user.role == UserRole.RESEARCHER:
        return study.created_by == user.id
    if user.role == UserRole.ORG_ADMIN and user.organization_id:
        return any(p.organization_id == user.organization_id for p in study.participants)
    return False


def _require_study_access(study: Study, user: User) -> None:
    if not _user_can_access_study(study, user):
        raise HTTPException(status_code=403, detail="you do not have access to this study")


@router.get("", response_model=list[StudyResponse])
def list_studies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Study.id).order_by(Study.created_at.desc())
    if user.role == UserRole.RESEARCHER:
        stmt = stmt.where(Study.created_by == user.id)
    elif user.role == UserRole.ORG_ADMIN:
        if not user.organization_id:
            return []
        stmt = (
            stmt.join(StudyParticipant, StudyParticipant.study_id == Study.id)
            .where(StudyParticipant.organization_id == user.organization_id)
        )
    ids = list(db.scalars(stmt))
    return [_response(_load_study(db, sid)) for sid in ids]


@router.get("/{study_id}", response_model=StudyResponse)
def get_study(study_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    study = _load_study(db, study_id)
    _require_study_access(study, user)
    return _response(study)


@router.get("/{study_id}/local-access", response_model=HospitalAccessResponse)
def issue_study_local_access(
    study_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORG_ADMIN)),
):
    study = _load_study(db, study_id)
    _require_study_access(study, user)
    participant = next(p for p in study.participants if p.organization_id == user.organization_id)
    org = participant.organization
    settings = request.app.state.settings
    node_url = settings.hospital_public_urls.get(org.participant_index)
    if not node_url:
        raise HTTPException(status_code=409, detail="hospital public URL is not configured")
    token = create_hospital_access_token(
        user_id=user.id, organization_id=org.id, participant_id=org.participant_index,
        secret=settings.jwt_secret, algorithm=settings.jwt_algorithm,
        scope="local_study_input", study_id=study.id,
    )
    return HospitalAccessResponse(organization=org, node_url=node_url, access_token=token)


@router.post("", response_model=StudyResponse, status_code=status.HTTP_201_CREATED)
def create_study(
    payload: StudyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.RESEARCHER, UserRole.SYSTEM_ADMIN)),
):
    orgs = list(db.scalars(select(Organization).where(Organization.id.in_(payload.organization_ids))))
    if len(orgs) != len(payload.organization_ids):
        raise HTTPException(status_code=422, detail="all selected organizations must exist")
    if any(not o.is_active or not o.node_url for o in orgs):
        raise HTTPException(status_code=422, detail="all organizations must be active and have hospital node URLs")

    study = Study(
        created_by=user.id,
        name=payload.name,
        description=payload.description,
        analysis_type=payload.analysis_type,
        study_mode=payload.study_mode,
        status=StudyStatus.WAITING_APPROVAL,
    )
    study.criteria = StudyCohortCriteria(**payload.criteria.model_dump())
    by_id = {o.id: o for o in orgs}
    for participant_index, org_id in enumerate(payload.organization_ids, start=1):
        org = by_id[org_id]
        study.participants.append(StudyParticipant(
            organization_id=org.id,
            participant_index=participant_index,
            status=ParticipationStatus.INVITED,
        ))
    db.add(study)
    db.flush()
    log_event(db, event_type="STUDY_CREATED", study_id=study.id, user=user,
              metadata={"analysis_type": study.analysis_type.value, "organization_count": len(payload.organization_ids)})
    db.commit()
    return _response(_load_study(db, study.id))


@router.post("/{study_id}/approval", response_model=StudyResponse)
def approve_study(
    study_id: str,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORG_ADMIN)),
):
    study = _load_study(db, study_id)
    if study.status not in (StudyStatus.WAITING_APPROVAL, StudyStatus.READY):
        raise HTTPException(status_code=409, detail="study is no longer awaiting approvals")
    participant = next((p for p in study.participants if p.organization_id == user.organization_id), None)
    if not participant:
        raise HTTPException(status_code=403, detail="your organization is not part of this study")

    participant.status = ParticipationStatus.APPROVED if payload.approve else ParticipationStatus.REJECTED
    participant.approved_by = user.id
    participant.approved_at = datetime.now(timezone.utc)
    if not payload.approve:
        study.status = StudyStatus.FAILED
    elif all(p.status == ParticipationStatus.APPROVED for p in study.participants):
        study.status = StudyStatus.READY
    else:
        study.status = StudyStatus.WAITING_APPROVAL
    log_event(db, event_type="PARTICIPATION_APPROVED" if payload.approve else "PARTICIPATION_REJECTED",
              study_id=study.id, user=user, metadata={"organization_id": participant.organization_id})
    db.commit()
    return _response(_load_study(db, study.id))


@router.post("/{study_id}/run", response_model=RunStudyResponse)
async def run_study(
    study_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.RESEARCHER, UserRole.SYSTEM_ADMIN)),
    orchestrator=Depends(get_orchestrator),
):
    study = _load_study(db, study_id)
    _require_study_access(study, user)
    retrying_failed_execution = (
        study.status == StudyStatus.FAILED
        and all(p.status == ParticipationStatus.APPROVED for p in study.participants)
    )
    if study.status != StudyStatus.READY and not retrying_failed_execution:
        raise HTTPException(status_code=409, detail="all participating organizations must approve before computation")

    session = MPCSession(
        study_id=study.id,
        threshold=orchestrator.threshold_for_participant_count(len(study.participants)),
        field_prime=str(orchestrator.prime),
        security_model="SEMI_HONEST",
        status=MPCSessionStatus.CREATED,
    )
    db.add(session)
    study.status = StudyStatus.COMPUTING
    db.flush()
    log_event(db, event_type="MPC_STARTED", study_id=study.id, user=user, metadata={"session_id": session.id})
    db.commit()

    targets = orchestrator.targets_for_study(study)
    try:
        session.status = MPCSessionStatus.SHARING
        db.commit()
        result_data = await orchestrator.run(study, session.id)
        demonstration_trace = result_data.pop("_demonstration_trace", None)
        if demonstration_trace is not None:
            request.app.state.demonstration_traces[study.id] = demonstration_trace

        minimum = request.app.state.settings.minimum_cohort_size
        cohort_size = result_data.get("cohort_size")
        if cohort_size is not None and cohort_size < minimum:
            result_data = {
                "suppressed": True,
                "reason": "cohort_below_privacy_threshold",
                "minimum_cohort_size": minimum,
            }

        session.status = MPCSessionStatus.COMPLETED
        session.completed_at = datetime.now(timezone.utc)
        study.status = StudyStatus.COMPLETED
        study.completed_at = session.completed_at
        for participant in study.participants:
            participant.status = ParticipationStatus.COMPLETED
        db.add(StudyResult(
            study_id=study.id,
            mpc_session_id=session.id,
            result_type=study.analysis_type.value,
            result_data=result_data,
        ))
        log_event(db, event_type="RESULT_RECONSTRUCTED", study_id=study.id, user=user,
                  metadata={"session_id": session.id, "result_type": study.analysis_type.value})
        db.commit()
        return RunStudyResponse(study_id=study.id, session_id=session.id, status="COMPLETED", result=result_data)
    except Exception as exc:
        session.status = MPCSessionStatus.FAILED
        session.error_message = str(exc)[:2000]
        session.completed_at = datetime.now(timezone.utc)
        study.status = StudyStatus.FAILED
        log_event(db, event_type="MPC_FAILED", study_id=study.id, user=user,
                  metadata={"session_id": session.id, "error_type": type(exc).__name__})
        db.commit()
        raise HTTPException(status_code=502, detail=f"MPC execution failed: {exc}") from exc
    finally:
        await orchestrator.destroy_sessions(session.id, targets)


@router.post("/{study_id}/verify", response_model=VerificationResponse)
async def verify_demonstration_study(
    study_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.RESEARCHER, UserRole.SYSTEM_ADMIN)),
    orchestrator=Depends(get_orchestrator),
):
    study = _load_study(db, study_id)
    _require_study_access(study, user)
    if study.study_mode != "DEMONSTRATION":
        raise HTTPException(status_code=403, detail="plaintext verification is disabled for secure studies")
    if study.status != StudyStatus.COMPLETED or not study.results:
        raise HTTPException(status_code=409, detail="the demonstration study must be completed first")
    bgw = study.results[-1].result_data
    if bgw.get("suppressed"):
        raise HTTPException(status_code=409, detail="a privacy-suppressed result cannot be verified")
    local_values = await orchestrator.collect_demo_plaintext_inputs(study)
    reference, differences, verified = compare_results(study.analysis_type.value, local_values, bgw)
    return VerificationResponse(
        study_id=study.id,
        analysis_type=study.analysis_type,
        reference=reference,
        bgw=bgw,
        differences=differences,
        verified=verified,
        tolerance=1e-9,
        local_breakdown=local_values,
        protocol_trace=request.app.state.demonstration_traces.get(study.id, []),
    )
