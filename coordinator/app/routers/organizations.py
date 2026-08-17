from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import log_event
from ..dependencies import get_current_user, get_db, require_roles
from ..models import AuditLog, Organization, StudyParticipant, User, UserRole
from ..schemas import HospitalAccessResponse, OrganizationCreate, OrganizationResponse, OrganizationUpdate
from ..security import create_hospital_access_token

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


def _verify_node(
    node_url: str,
    participant_index: int | None,
    timeout_seconds: float,
    service_token: str,
) -> dict:
    try:
        response = httpx.get(
            f"{node_url.rstrip('/')}/api/mpc/node-info",
            headers={"X-MPC-Service-Token": service_token},
            timeout=min(timeout_seconds, 5.0),
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Болничният възел не е достъпен на въведения адрес или не връща валиден статус.",
        ) from exc
    if payload.get("status") != "ok":
        raise HTTPException(status_code=422, detail="Болничният възел не е в готово състояние.")
    if participant_index is not None and payload.get("participant_id") != participant_index:
        raise HTTPException(
            status_code=422,
            detail=f"Адресът принадлежи на участник P{payload.get('participant_id')}, а организацията е регистрирана като P{participant_index}.",
        )
    if not isinstance(payload.get("participant_id"), int) or payload["participant_id"] < 1:
        raise HTTPException(status_code=422, detail="Болничният възел не връща валиден идентификатор.")
    return payload


@router.get("/me/local-access", response_model=HospitalAccessResponse)
def issue_local_access(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ORG_ADMIN)),
):
    org = db.get(Organization, user.organization_id)
    if not org or not org.is_active or org.participant_index is None:
        raise HTTPException(status_code=409, detail="your organization has no active MPC node")
    settings = request.app.state.settings
    node_url = settings.hospital_public_urls.get(org.participant_index)
    if not node_url:
        raise HTTPException(status_code=409, detail="hospital public URL is not configured")
    token = create_hospital_access_token(
        user_id=user.id,
        organization_id=org.id,
        participant_id=org.participant_index,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        scope="local_patients",
    )
    return HospitalAccessResponse(organization=org, node_url=node_url, access_token=token)


@router.get("", response_model=list[OrganizationResponse])
def list_organizations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(Organization).order_by(Organization.participant_index, Organization.name)))


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
):
    node_info = None
    settings = request.app.state.settings
    if payload.node_url:
        node_info = _verify_node(
            payload.node_url, payload.participant_index, settings.hospital_timeout_seconds,
            settings.mpc_service_token,
        )
    values = payload.model_dump()
    if node_info and values["participant_index"] is None:
        values["participant_index"] = node_info["participant_id"]
    org = Organization(**values, is_active=False)
    db.add(org)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="organization name or participant index already exists") from exc
    db.refresh(org)
    log_event(db, event_type="ORGANIZATION_REGISTERED", user=user,
              metadata={"organization_id": org.id, "node_verified": bool(node_info)})
    db.commit()
    return org


@router.patch("/{organization_id}", response_model=OrganizationResponse)
def update_organization(
    organization_id: str,
    payload: OrganizationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
):
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="organization not found")
    settings = request.app.state.settings
    effective_url = payload.node_url if "node_url" in payload.model_fields_set else org.node_url
    requires_verification = "node_url" in payload.model_fields_set or (
        "is_active" in payload.model_fields_set and payload.is_active is True
    )
    node_info = None
    if requires_verification:
        if not effective_url:
            raise HTTPException(status_code=422, detail="Въведете адрес на болничния възел преди активиране.")
        node_info = _verify_node(
            effective_url, org.participant_index, settings.hospital_timeout_seconds,
            settings.mpc_service_token,
        )
    for field in payload.model_fields_set:
        setattr(org, field, getattr(payload, field))
    if node_info and org.participant_index is None:
        org.participant_index = node_info["participant_id"]
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="organization name already exists") from exc
    db.refresh(org)
    return org


@router.post("/{organization_id}/verify")
def verify_organization_node(
    organization_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
):
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Организацията не е намерена.")
    if not org.node_url:
        raise HTTPException(status_code=422, detail="Организацията няма зададен адрес на болничен възел.")
    settings = request.app.state.settings
    info = _verify_node(
        org.node_url, org.participant_index, settings.hospital_timeout_seconds,
        settings.mpc_service_token,
    )
    if org.participant_index is None:
        org.participant_index = info["participant_id"]
    log_event(db, event_type="HOSPITAL_NODE_VERIFIED", user=user,
              metadata={"organization_id": org.id, "participant_index": info["participant_id"]})
    db.commit()
    return {
        "status": "verified",
        "organization_id": org.id,
        "organization_name": info["organization_name"],
        "participant_index": info["participant_id"],
    }


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(
    organization_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
):
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Организацията не е намерена.")
    if db.scalar(select(User.id).where(User.organization_id == organization_id).limit(1)):
        raise HTTPException(status_code=409, detail="Организацията има регистрирани потребители и не може да бъде изтрита.")
    if db.scalar(select(StudyParticipant.id).where(StudyParticipant.organization_id == organization_id).limit(1)):
        raise HTTPException(status_code=409, detail="Организацията участва в проучване и не може да бъде изтрита.")
    if db.scalar(select(AuditLog.id).where(AuditLog.organization_id == organization_id).limit(1)):
        raise HTTPException(status_code=409, detail="Организацията присъства в историята на действията и не може да бъде изтрита.")
    db.delete(org)
    db.commit()
