from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from .models import (
    Disease,
    GeneticVariant,
    Patient,
    PatientDisease,
    PatientVariant,
    ResponseCategory,
    Therapy,
    Treatment,
    TreatmentOutcome,
)
from .schemas import CohortCriteria


@dataclass(frozen=True)
class VariantFrequencyCounts:
    variant_count: int
    cohort_count: int


@dataclass(frozen=True)
class TherapyResponseCounts:
    a: int  # variant + responder
    b: int  # variant + non-responder
    c: int  # no variant + responder
    d: int  # no variant + non-responder


@dataclass(frozen=True)
class SumCounts:
    value: int
    cohort_count: int


def _base_patient_conditions(criteria: CohortCriteria):
    conditions = []
    if criteria.min_age is not None:
        conditions.append(Patient.age >= criteria.min_age)
    if criteria.max_age is not None:
        conditions.append(Patient.age <= criteria.max_age)
    if criteria.sex is not None:
        conditions.append(Patient.sex == criteria.sex)

    if criteria.disease_code:
        conditions.append(
            exists(
                select(1)
                .select_from(PatientDisease)
                .join(Disease, Disease.id == PatientDisease.disease_id)
                .where(
                    PatientDisease.patient_id == Patient.id,
                    Disease.code == criteria.disease_code,
                )
            )
        )
    return conditions


def _has_variant(variant_code: str):
    return exists(
        select(1)
        .select_from(PatientVariant)
        .join(GeneticVariant, GeneticVariant.id == PatientVariant.variant_id)
        .where(
            PatientVariant.patient_id == Patient.id,
            GeneticVariant.code == variant_code,
        )
    )


def _require_variant(criteria: CohortCriteria) -> str:
    if not criteria.variant_code:
        raise ValueError("variant_code is required for this analysis")
    return criteria.variant_code


def _has_therapy(therapy_code: str):
    return exists(
        select(1)
        .select_from(Treatment)
        .join(Therapy, Therapy.id == Treatment.therapy_id)
        .where(Treatment.patient_id == Patient.id, Therapy.code == therapy_code)
    )


def _has_therapy_response(therapy_code: str, responses: list[str]):
    return exists(
        select(1)
        .select_from(Treatment)
        .join(Therapy, Therapy.id == Treatment.therapy_id)
        .join(TreatmentOutcome, TreatmentOutcome.treatment_id == Treatment.id)
        .where(
            Treatment.patient_id == Patient.id,
            Therapy.code == therapy_code,
            TreatmentOutcome.response.in_(responses),
        )
    )


def _response_codes(db: Session, *, positive: bool) -> list[str]:
    codes = list(db.scalars(
        select(ResponseCategory.code).where(ResponseCategory.is_positive == int(positive))
    ))
    if not codes:
        return ["RESPONDER" if positive else "NON_RESPONDER"]
    return codes


def _count_patients(db: Session, *conditions) -> int:
    stmt = select(func.count(Patient.id)).where(and_(*conditions))
    return int(db.scalar(stmt) or 0)


def calculate_variant_frequency_counts(
    db: Session, criteria: CohortCriteria
) -> VariantFrequencyCounts:
    base = _base_patient_conditions(criteria)
    if criteria.therapy_code:
        base.append(_has_therapy(criteria.therapy_code))

    cohort_count = _count_patients(db, *base)
    variant_count = _count_patients(db, *base, _has_variant(_require_variant(criteria)))
    return VariantFrequencyCounts(variant_count=variant_count, cohort_count=cohort_count)


def calculate_therapy_response_counts(
    db: Session, criteria: CohortCriteria
) -> TherapyResponseCounts:
    if not criteria.therapy_code:
        raise ValueError("therapy_code is required for therapy-response analysis")

    base = _base_patient_conditions(criteria)
    variant = _has_variant(_require_variant(criteria))
    responder_codes = _response_codes(db, positive=True)
    non_responder_codes = _response_codes(db, positive=False)
    responder = _has_therapy_response(criteria.therapy_code, responder_codes)
    non_responder = _has_therapy_response(criteria.therapy_code, non_responder_codes)

    return TherapyResponseCounts(
        a=_count_patients(db, *base, variant, responder),
        b=_count_patients(db, *base, variant, non_responder),
        c=_count_patients(db, *base, ~variant, responder),
        d=_count_patients(db, *base, ~variant, non_responder),
    )


def calculate_allele_frequency_counts(db: Session, criteria: CohortCriteria) -> SumCounts:
    base = _base_patient_conditions(criteria)
    if criteria.therapy_code:
        base.append(_has_therapy(criteria.therapy_code))
    cohort_count = _count_patients(db, *base)
    variant_code = _require_variant(criteria)
    rows = db.execute(
        select(PatientVariant.genotype, func.count(PatientVariant.id))
        .join(Patient, Patient.id == PatientVariant.patient_id)
        .join(GeneticVariant, GeneticVariant.id == PatientVariant.variant_id)
        .where(and_(*base), GeneticVariant.code == variant_code)
        .group_by(PatientVariant.genotype)
    ).all()
    dosage = {"0/0": 0, "0|0": 0, "0/1": 1, "1/0": 1, "0|1": 1, "1|0": 1, "1/1": 2, "1|1": 2}
    try:
        alleles = sum(dosage[genotype.strip()] * int(count) for genotype, count in rows)
    except KeyError as exc:
        raise ValueError(f"unsupported genotype: {exc.args[0]}") from exc
    return SumCounts(value=alleles, cohort_count=cohort_count)


def calculate_mean_age_counts(db: Session, criteria: CohortCriteria) -> SumCounts:
    base = _base_patient_conditions(criteria)
    if criteria.variant_code:
        base.append(_has_variant(criteria.variant_code))
    if criteria.therapy_code:
        base.append(_has_therapy(criteria.therapy_code))
    count, age_sum = db.execute(
        select(func.count(Patient.id), func.coalesce(func.sum(Patient.age), 0)).where(and_(*base))
    ).one()
    return SumCounts(value=int(age_sum), cohort_count=int(count))


def calculate_response_rate_counts(db: Session, criteria: CohortCriteria) -> SumCounts:
    if not criteria.therapy_code:
        raise ValueError("therapy_code is required for therapy response rate")
    base = _base_patient_conditions(criteria)
    if criteria.variant_code:
        base.append(_has_variant(criteria.variant_code))
    treated = _count_patients(db, *base, _has_therapy(criteria.therapy_code))
    responder_codes = _response_codes(db, positive=True)
    responders = _count_patients(db, *base, _has_therapy_response(criteria.therapy_code, responder_codes))
    return SumCounts(value=responders, cohort_count=treated)


def calculate_variant_disease_counts(db: Session, criteria: CohortCriteria) -> TherapyResponseCounts:
    if not criteria.disease_code:
        raise ValueError("disease_code is required for variant-disease association")
    # Disease is the outcome here, so omit it from the base cohort filters.
    base_criteria = criteria.model_copy(update={"disease_code": None})
    base = _base_patient_conditions(base_criteria)
    variant = _has_variant(_require_variant(criteria))
    disease = exists(
        select(1).select_from(PatientDisease).join(Disease).where(
            PatientDisease.patient_id == Patient.id, Disease.code == criteria.disease_code
        )
    )
    return TherapyResponseCounts(
        a=_count_patients(db, *base, variant, disease),
        b=_count_patients(db, *base, variant, ~disease),
        c=_count_patients(db, *base, ~variant, disease),
        d=_count_patients(db, *base, ~variant, ~disease),
    )
