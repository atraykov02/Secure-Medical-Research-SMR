from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from .models import AnalysisType, MPCSessionStatus, OrganizationType, ParticipationStatus, StudyStatus, UserRole


def _validate_node_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Портът на болничния възел трябва да бъде между 1 и 65535.") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Въведете валиден HTTP или HTTPS адрес на организацията (node).")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Портът на болничния възел трябва да бъде между 1 и 65535.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Адресът трябва да съдържа само протокол, име на хост и порт.")
    return value


class TokenRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: UserRole | None = None
    organization_id: str | None = None
    is_active: bool | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: UserRole
    organization_id: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: UserRole
    organization_id: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    type: OrganizationType = OrganizationType.HOSPITAL
    node_url: str | None = Field(default=None, max_length=500)
    participant_index: int | None = Field(default=None, ge=1)

    @field_validator("node_url")
    @classmethod
    def validate_node_url(cls, value: str | None):
        return _validate_node_url(value)


class OrganizationResponse(BaseModel):
    id: str
    name: str
    type: OrganizationType
    node_url: str | None
    participant_index: int | None
    is_active: bool

    model_config = {"from_attributes": True}


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    type: OrganizationType | None = None
    node_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @field_validator("node_url")
    @classmethod
    def validate_node_url(cls, value: str | None):
        return _validate_node_url(value)


class HospitalAccessResponse(BaseModel):
    organization: OrganizationResponse
    node_url: str
    access_token: str
    expires_in_seconds: int = 300


class CohortCriteriaInput(BaseModel):
    min_age: int | None = Field(default=None, ge=0, le=130)
    max_age: int | None = Field(default=None, ge=0, le=130)
    sex: Literal["F", "M"] | None = None
    disease_code: str | None = Field(default=None, max_length=64)
    variant_code: str | None = Field(default=None, max_length=128)
    therapy_code: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_values(self):
        if self.min_age is not None and self.max_age is not None and self.min_age > self.max_age:
            raise ValueError("min_age cannot be greater than max_age")
        return self


class StudyCreate(BaseModel):
    name: str = Field(min_length=3, max_length=250)
    description: str | None = None
    analysis_type: AnalysisType
    study_mode: Literal["SECURE", "DEMONSTRATION"] = "SECURE"
    organization_ids: list[str] = Field(min_length=3, max_length=6)
    criteria: CohortCriteriaInput

    @model_validator(mode="after")
    def validate_analysis(self):
        if len(set(self.organization_ids)) != len(self.organization_ids):
            raise ValueError("all participating organizations must be different")
        variant_required = {
            AnalysisType.VARIANT_FREQUENCY, AnalysisType.ALLELE_FREQUENCY,
            AnalysisType.THERAPY_RESPONSE, AnalysisType.VARIANT_DISEASE_ASSOCIATION,
        }
        therapy_required = {AnalysisType.THERAPY_RESPONSE_RATE, AnalysisType.THERAPY_RESPONSE}
        if self.analysis_type in variant_required and not self.criteria.variant_code:
            raise ValueError(f"variant_code is required for {self.analysis_type.value}")
        if self.analysis_type in therapy_required and not self.criteria.therapy_code:
            raise ValueError(f"therapy_code is required for {self.analysis_type.value}")
        if self.analysis_type == AnalysisType.VARIANT_DISEASE_ASSOCIATION and not self.criteria.disease_code:
            raise ValueError("disease_code is required for VARIANT_DISEASE_ASSOCIATION")
        return self


class ParticipantResponse(BaseModel):
    organization_id: str
    organization_name: str
    participant_index: int
    status: ParticipationStatus


class CriteriaResponse(BaseModel):
    min_age: int | None
    max_age: int | None
    sex: str | None
    disease_code: str | None
    variant_code: str | None
    therapy_code: str | None

    model_config = {"from_attributes": True}


class StudyResponse(BaseModel):
    id: str
    name: str
    description: str | None
    analysis_type: AnalysisType
    study_mode: str
    status: StudyStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    criteria: CriteriaResponse
    participants: list[ParticipantResponse]
    result: dict | None = None


class ApprovalRequest(BaseModel):
    approve: bool = True


class RunStudyResponse(BaseModel):
    study_id: str
    session_id: str
    status: str
    result: dict


class VerificationResponse(BaseModel):
    study_id: str
    analysis_type: AnalysisType
    reference: dict
    bgw: dict
    differences: dict
    verified: bool
    tolerance: float
    local_breakdown: list[dict]
    protocol_trace: list[dict] = []


class MPCSessionResponse(BaseModel):
    id: str
    study_id: str
    study_name: str
    participant_count: int
    threshold: int
    field_prime: str
    security_model: str
    status: MPCSessionStatus
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class AuditResponse(BaseModel):
    id: str
    study_id: str | None
    user_id: str | None
    organization_id: str | None
    organization_name: str | None
    actor_name: str | None
    actor_role: UserRole | None
    event_type: str
    metadata: dict
    created_at: datetime
