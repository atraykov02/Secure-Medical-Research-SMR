from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..dependencies import get_db, require_roles
from ..models import AuditLog, Organization, Study, StudyParticipant, User, UserRole
from ..schemas import UserCreate, UserResponse, UserUpdate
from ..security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
):
    return list(db.scalars(select(User).order_by(User.email)))


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
):
    if payload.organization_id and not db.get(Organization, payload.organization_id):
        raise HTTPException(status_code=404, detail="organization not found")
    if payload.role == UserRole.ORG_ADMIN and not payload.organization_id:
        raise HTTPException(status_code=422, detail="Администраторът на организация трябва да бъде свързан с организация.")
    user = User(
        organization_id=payload.organization_id,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=payload.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="email already exists") from exc
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if actor.id == user.id and payload.role is not None and payload.role != UserRole.SYSTEM_ADMIN:
        raise HTTPException(status_code=409, detail="Не можете да промените ролята на собствения си системен акаунт.")
    if payload.organization_id is not None and not db.get(Organization, payload.organization_id):
        raise HTTPException(status_code=404, detail="organization not found")
    resulting_role = payload.role or user.role
    resulting_organization = payload.organization_id if "organization_id" in payload.model_fields_set else user.organization_id
    if resulting_role == UserRole.ORG_ADMIN and not resulting_organization:
        raise HTTPException(status_code=422, detail="Администраторът на организация трябва да бъде свързан с организация.")
    if payload.email is not None:
        user.email = payload.email.lower()
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.first_name is not None:
        user.first_name = payload.first_name
    if payload.last_name is not None:
        user.last_name = payload.last_name
    if payload.role is not None:
        user.role = payload.role
    if "organization_id" in payload.model_fields_set:
        user.organization_id = payload.organization_id
    if payload.is_active is not None:
        if user.id == actor.id and not payload.is_active:
            raise HTTPException(status_code=409, detail="you cannot deactivate your own account")
        user.is_active = payload.is_active
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Вече съществува потребител с този имейл.") from exc
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SYSTEM_ADMIN)),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Потребителят не е намерен.")
    if user.id == actor.id:
        raise HTTPException(status_code=409, detail="Не можете да изтриете собствения си акаунт.")
    if db.scalar(select(Study.id).where(Study.created_by == user_id).limit(1)):
        raise HTTPException(status_code=409, detail="Потребителят е създал проучвания и не може да бъде изтрит.")
    if db.scalar(select(StudyParticipant.id).where(StudyParticipant.approved_by == user_id).limit(1)):
        raise HTTPException(status_code=409, detail="Потребителят е одобрявал участия и не може да бъде изтрит.")
    if db.scalar(select(AuditLog.id).where(AuditLog.user_id == user_id).limit(1)):
        raise HTTPException(status_code=409, detail="Потребителят присъства в историята на действията и не може да бъде изтрит.")
    db.delete(user)
    db.commit()
