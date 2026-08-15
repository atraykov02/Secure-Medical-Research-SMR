from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..cohort import (calculate_allele_frequency_counts, calculate_mean_age_counts,
    calculate_response_rate_counts, calculate_therapy_response_counts,
    calculate_variant_disease_counts, calculate_variant_frequency_counts)
from ..dependencies import get_db
from ..schemas import LocalStudyInputResponse, VerificationInputRequest
from ..security import verify_service_token

router = APIRouter(
    prefix="/api/verification", tags=["verification"],
    dependencies=[Depends(verify_service_token)],
)


@router.post("/studies/{study_id}/local-input", response_model=LocalStudyInputResponse)
def verification_input(study_id: str, payload: VerificationInputRequest, request: Request, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    common = dict(
        study_id=study_id, organization=settings.organization_name,
        participant_id=settings.participant_id, analysis_type=payload.analysis_type,
    )
    if payload.analysis_type == "VARIANT_FREQUENCY":
        counts = calculate_variant_frequency_counts(db, payload.criteria)
        return LocalStudyInputResponse(**common, cohort_size=counts.cohort_count, variant_count=counts.variant_count)
    if payload.analysis_type == "ALLELE_FREQUENCY":
        counts = calculate_allele_frequency_counts(db, payload.criteria)
        return LocalStudyInputResponse(**common, cohort_size=counts.cohort_count, alternative_allele_count=counts.value)
    if payload.analysis_type == "COHORT_MEAN_AGE":
        counts = calculate_mean_age_counts(db, payload.criteria)
        return LocalStudyInputResponse(**common, cohort_size=counts.cohort_count, age_sum=counts.value,
            local_mean_age=round(counts.value / counts.cohort_count, 2) if counts.cohort_count else None)
    if payload.analysis_type == "THERAPY_RESPONSE_RATE":
        counts = calculate_response_rate_counts(db, payload.criteria)
        return LocalStudyInputResponse(**common, cohort_size=counts.cohort_count, treated_count=counts.cohort_count,
                                       responder_count=counts.value)
    calculator = calculate_variant_disease_counts if payload.analysis_type == "VARIANT_DISEASE_ASSOCIATION" else calculate_therapy_response_counts
    counts = calculator(db, payload.criteria)
    return LocalStudyInputResponse(
        **common, cohort_size=counts.a + counts.b + counts.c + counts.d,
        a=counts.a, b=counts.b, c=counts.c, d=counts.d,
    )
