from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrganizationType(str, enum.Enum):
    HOSPITAL = "HOSPITAL"
    LABORATORY = "LABORATORY"
    RESEARCH_CENTER = "RESEARCH_CENTER"


class UserRole(str, enum.Enum):
    RESEARCHER = "RESEARCHER"
    ORG_ADMIN = "ORG_ADMIN"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


class AnalysisType(str, enum.Enum):
    VARIANT_FREQUENCY = "VARIANT_FREQUENCY"
    ALLELE_FREQUENCY = "ALLELE_FREQUENCY"
    COHORT_MEAN_AGE = "COHORT_MEAN_AGE"
    THERAPY_RESPONSE_RATE = "THERAPY_RESPONSE_RATE"
    THERAPY_RESPONSE = "THERAPY_RESPONSE"
    VARIANT_DISEASE_ASSOCIATION = "VARIANT_DISEASE_ASSOCIATION"


class StudyStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    READY = "READY"
    COMPUTING = "COMPUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ParticipationStatus(str, enum.Enum):
    INVITED = "INVITED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class MPCSessionStatus(str, enum.Enum):
    CREATED = "CREATED"
    SHARING = "SHARING"
    COMPUTING = "COMPUTING"
    RECONSTRUCTING = "RECONSTRUCTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DESTROYED = "DESTROYED"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    type: Mapped[OrganizationType] = mapped_column(Enum(OrganizationType), nullable=False)
    node_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    participant_index: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization | None] = relationship(back_populates="users")


class Study(Base):
    __tablename__ = "studies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_type: Mapped[AnalysisType] = mapped_column(Enum(AnalysisType), nullable=False)
    study_mode: Mapped[str] = mapped_column(String(32), default="SECURE", nullable=False)
    status: Mapped[StudyStatus] = mapped_column(Enum(StudyStatus), default=StudyStatus.WAITING_APPROVAL)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    criteria: Mapped["StudyCohortCriteria"] = relationship(back_populates="study", uselist=False, cascade="all, delete-orphan")
    participants: Mapped[list["StudyParticipant"]] = relationship(back_populates="study", cascade="all, delete-orphan")
    results: Mapped[list["StudyResult"]] = relationship(back_populates="study", cascade="all, delete-orphan")


class StudyCohortCriteria(Base):
    __tablename__ = "study_cohort_criteria"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), unique=True, nullable=False)
    min_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(1), nullable=True)
    disease_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    variant_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    therapy_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    study: Mapped[Study] = relationship(back_populates="criteria")


class StudyParticipant(Base):
    __tablename__ = "study_participants"
    __table_args__ = (UniqueConstraint("study_id", "organization_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), nullable=False)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    participant_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ParticipationStatus] = mapped_column(Enum(ParticipationStatus), default=ParticipationStatus.INVITED)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    study: Mapped[Study] = relationship(back_populates="participants")
    organization: Mapped[Organization] = relationship()


class MPCSession(Base):
    __tablename__ = "mpc_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), nullable=False, index=True)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    field_prime: Mapped[str] = mapped_column(String(100), nullable=False)
    security_model: Mapped[str] = mapped_column(String(50), default="SEMI_HONEST", nullable=False)
    status: Mapped[MPCSessionStatus] = mapped_column(Enum(MPCSessionStatus), default=MPCSessionStatus.CREATED)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StudyResult(Base):
    __tablename__ = "study_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"), nullable=False)
    mpc_session_id: Mapped[str] = mapped_column(ForeignKey("mpc_sessions.id"), nullable=False)
    result_type: Mapped[str] = mapped_column(String(100), nullable=False)
    result_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    study: Mapped[Study] = relationship(back_populates="results")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    study_id: Mapped[str | None] = mapped_column(ForeignKey("studies.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
