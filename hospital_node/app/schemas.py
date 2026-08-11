from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from bgw.field import DEFAULT_PRIME


class MPCSessionCreate(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    participant_id: int = Field(ge=1)
    participant_ids: list[int] = [1, 2, 3]
    peer_urls: dict[int, str]
    threshold: int = 1
    prime: int = DEFAULT_PRIME
    demonstration_trace: bool = False

    @model_validator(mode="after")
    def validate_participants(self):
        expected_ids = list(range(1, len(self.participant_ids) + 1))
        if not 3 <= len(self.participant_ids) <= 6 or self.participant_ids != expected_ids:
            raise ValueError("sessions require between 3 and 6 consecutive participant ids starting at 1")
        if self.threshold != (len(self.participant_ids) - 1) // 2:
            raise ValueError("threshold must be floor((participant count - 1) / 2)")
        if self.participant_id not in self.participant_ids:
            raise ValueError("participant_id must belong to participant_ids")
        if set(self.peer_urls) != set(self.participant_ids):
            raise ValueError("peer_urls must contain every session participant")
        return self


class CohortCriteria(BaseModel):
    min_age: int | None = Field(default=None, ge=0, le=130)
    max_age: int | None = Field(default=None, ge=0, le=130)
    sex: Literal["F", "M"] | None = None
    disease_code: str | None = Field(default=None, max_length=64)
    variant_code: str | None = Field(default=None, max_length=128)
    therapy_code: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_age_range(self) -> "CohortCriteria":
        if (
            self.min_age is not None
            and self.max_age is not None
            and self.min_age > self.max_age
        ):
            raise ValueError("min_age cannot be greater than max_age")
        return self


class AnalysisRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    criteria: CohortCriteria


class SessionActionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)


class NodeStatus(BaseModel):
    participant_id: int
    organization_name: str
    status: str


class SessionStatus(BaseModel):
    session_id: str
    participant_id: int
    threshold: int
    participant_ids: list[int]
    available_value_names: list[str]


class ActionResponse(BaseModel):
    session_id: str
    status: str
    detail: str
    shared_value_names: list[str] = []


class ResultShare(BaseModel):
    name: str
    x: int
    value: str


class ResultSharesResponse(BaseModel):
    session_id: str
    participant_id: int
    shares: list[ResultShare]


class LocalPatient(BaseModel):
    identifier: str
    age: int
    sex: str
    diseases: list[str]
    variants: list[str]
    therapies: list[str]
    responses: list[str]


class PatientVariantInput(BaseModel):
    code: str = Field(min_length=1, max_length=128)
    genotype: Literal["0/0", "0/1", "1/0", "1/1"] = "0/1"


class PatientTreatmentInput(BaseModel):
    therapy_code: str = Field(min_length=1, max_length=64)
    response: str = Field(min_length=1, max_length=32)


class LocalPatientWrite(BaseModel):
    identifier: str = Field(min_length=3, max_length=64)
    age: int = Field(ge=0, le=130)
    sex: Literal["F", "M"]
    disease_codes: list[str] = []
    variants: list[PatientVariantInput] = []
    treatments: list[PatientTreatmentInput] = []


class LocalPatientDetail(LocalPatientWrite):
    pass


class CatalogOption(BaseModel):
    code: str
    name: str


class ResponseCatalogOption(CatalogOption):
    is_positive: bool


class VariantCatalogOption(CatalogOption):
    gene: str
    chromosome: str
    position: int
    reference_allele: str
    alternate_allele: str


class LocalMedicalCatalog(BaseModel):
    diseases: list[CatalogOption]
    variants: list[VariantCatalogOption]
    therapies: list[CatalogOption]
    genotypes: list[str] = ["0/0", "0/1", "1/0", "1/1"]
    responses: list[ResponseCatalogOption]


class DiseaseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=255)


class GeneticVariantCreate(BaseModel):
    code: str = Field(min_length=1, max_length=128)
    gene: str = Field(min_length=1, max_length=64)
    chromosome: str = Field(min_length=1, max_length=16)
    position: int = Field(ge=1)
    reference_allele: str = Field(min_length=1, max_length=32)
    alternate_allele: str = Field(min_length=1, max_length=32)


class TherapyCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=255)


class ResponseCategoryCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=2, max_length=255)
    is_positive: bool = False


class LocalPatientsResponse(BaseModel):
    organization: str
    participant_id: int
    page: int
    page_size: int
    total: int
    items: list[LocalPatient]


AnalysisTypeName = Literal[
    "VARIANT_FREQUENCY", "ALLELE_FREQUENCY", "COHORT_MEAN_AGE",
    "THERAPY_RESPONSE_RATE", "THERAPY_RESPONSE", "VARIANT_DISEASE_ASSOCIATION",
]


class LocalStudyInputRequest(BaseModel):
    analysis_type: AnalysisTypeName
    criteria: CohortCriteria


class LocalStudyInputResponse(BaseModel):
    study_id: str
    organization: str
    participant_id: int
    analysis_type: str
    cohort_size: int
    variant_count: int | None = None
    alternative_allele_count: int | None = None
    age_sum: int | None = None
    local_mean_age: float | None = None
    treated_count: int | None = None
    responder_count: int | None = None
    a: int | None = None
    b: int | None = None
    c: int | None = None
    d: int | None = None
    local_values_status: str = "CALCULATED"
    sharing_status: str = "PRIVATE"


class VerificationInputRequest(LocalStudyInputRequest):
    data_source: Literal["SYNTHETIC"]
