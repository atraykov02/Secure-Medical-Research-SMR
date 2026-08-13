from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..cohort import (calculate_allele_frequency_counts, calculate_mean_age_counts,
    calculate_response_rate_counts, calculate_therapy_response_counts,
    calculate_variant_disease_counts, calculate_variant_frequency_counts)
from ..dependencies import get_db
from ..models import Disease, GeneticVariant, Patient, PatientDisease, PatientVariant, ResponseCategory, Therapy, Treatment, TreatmentOutcome
from ..schemas import DiseaseCreate, GeneticVariantCreate, LocalMedicalCatalog, LocalPatient, LocalPatientDetail, LocalPatientsResponse, LocalPatientWrite, LocalStudyInputRequest, LocalStudyInputResponse, ResponseCategoryCreate, TherapyCreate
from ..security import verify_local_admin

router = APIRouter(prefix="/api/local", tags=["local-data"])


@router.get("/catalog", response_model=LocalMedicalCatalog)
def local_medical_catalog(claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    if claims.get("scope") != "local_patients":
        raise HTTPException(status_code=403, detail="token is not valid for local patient data")
    return LocalMedicalCatalog(
        diseases=[{"code": item.code, "name": item.name} for item in db.scalars(select(Disease).order_by(Disease.code))],
        variants=[{
            "code": item.code, "name": f"{item.gene} · chr{item.chromosome}:{item.position}",
            "gene": item.gene, "chromosome": item.chromosome, "position": item.position,
            "reference_allele": item.reference_allele, "alternate_allele": item.alternate_allele,
        } for item in db.scalars(select(GeneticVariant).order_by(GeneticVariant.code))],
        therapies=[{"code": item.code, "name": item.name} for item in db.scalars(select(Therapy).order_by(Therapy.code))],
        responses=[{"code": item.code, "name": item.name, "is_positive": bool(item.is_positive)} for item in db.scalars(select(ResponseCategory).order_by(ResponseCategory.code))],
    )


def _create_catalog_item(db: Session, item):
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="catalog code already exists") from exc
    db.refresh(item)
    return item


def _commit_catalog_update(db: Session, item):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="catalog code already exists") from exc
    db.refresh(item)
    return item


def _catalog_item(db: Session, model, code: str):
    item = db.scalar(select(model).where(model.code == code))
    if not item:
        raise HTTPException(status_code=404, detail="catalog item not found")
    return item


def _require_catalog_admin(claims: dict) -> None:
    if claims.get("scope") != "local_patients":
        raise HTTPException(status_code=403, detail="token is not valid for local medical configuration")


def _delete_catalog_item(db: Session, item, is_used: bool):
    if is_used:
        raise HTTPException(
            status_code=409,
            detail="Стойността се използва от един или повече пациенти и не може да бъде изтрита.",
        )
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/catalog/diseases", status_code=status.HTTP_201_CREATED)
def create_disease(payload: DiseaseCreate, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    if claims.get("scope") != "local_patients":
        raise HTTPException(status_code=403, detail="token is not valid for local patient data")
    return _create_catalog_item(db, Disease(code=payload.code.strip().upper(), name=payload.name.strip()))


@router.post("/catalog/variants", status_code=status.HTTP_201_CREATED)
def create_variant(payload: GeneticVariantCreate, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    if claims.get("scope") != "local_patients":
        raise HTTPException(status_code=403, detail="token is not valid for local patient data")
    return _create_catalog_item(db, GeneticVariant(**payload.model_dump()))


@router.post("/catalog/therapies", status_code=status.HTTP_201_CREATED)
def create_therapy(payload: TherapyCreate, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    if claims.get("scope") != "local_patients":
        raise HTTPException(status_code=403, detail="token is not valid for local patient data")
    return _create_catalog_item(db, Therapy(code=payload.code.strip().upper(), name=payload.name.strip()))


@router.post("/catalog/responses", status_code=status.HTTP_201_CREATED)
def create_response_category(payload: ResponseCategoryCreate, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    if claims.get("scope") != "local_patients":
        raise HTTPException(status_code=403, detail="token is not valid for local patient data")
    return _create_catalog_item(db, ResponseCategory(code=payload.code.strip().upper(), name=payload.name.strip(), is_positive=int(payload.is_positive)))


@router.put("/catalog/diseases/{code}")
def update_disease(code: str, payload: DiseaseCreate, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    _require_catalog_admin(claims)
    item = _catalog_item(db, Disease, code)
    item.code, item.name = payload.code.strip().upper(), payload.name.strip()
    return _commit_catalog_update(db, item)


@router.delete("/catalog/diseases/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_disease(code: str, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    _require_catalog_admin(claims)
    item = _catalog_item(db, Disease, code)
    used = db.scalar(select(PatientDisease.id).where(PatientDisease.disease_id == item.id).limit(1)) is not None
    return _delete_catalog_item(db, item, used)


@router.put("/catalog/variants/{code}")
def update_variant(code: str, payload: GeneticVariantCreate, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    _require_catalog_admin(claims)
    item = _catalog_item(db, GeneticVariant, code)
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    return _commit_catalog_update(db, item)


@router.delete("/catalog/variants/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(code: str, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    _require_catalog_admin(claims)
    item = _catalog_item(db, GeneticVariant, code)
    used = db.scalar(select(PatientVariant.id).where(PatientVariant.variant_id == item.id).limit(1)) is not None
    return _delete_catalog_item(db, item, used)


@router.put("/catalog/therapies/{code}")
def update_therapy(code: str, payload: TherapyCreate, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    _require_catalog_admin(claims)
    item = _catalog_item(db, Therapy, code)
    item.code, item.name = payload.code.strip().upper(), payload.name.strip()
    return _commit_catalog_update(db, item)


@router.delete("/catalog/therapies/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_therapy(code: str, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    _require_catalog_admin(claims)
    item = _catalog_item(db, Therapy, code)
    used = db.scalar(select(Treatment.id).where(Treatment.therapy_id == item.id).limit(1)) is not None
    return _delete_catalog_item(db, item, used)


@router.put("/catalog/responses/{code}")
def update_response_category(code: str, payload: ResponseCategoryCreate, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    _require_catalog_admin(claims)
    item = _catalog_item(db, ResponseCategory, code)
    item.code, item.name, item.is_positive = payload.code.strip().upper(), payload.name.strip(), int(payload.is_positive)
    return _commit_catalog_update(db, item)


@router.delete("/catalog/responses/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_response_category(code: str, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    _require_catalog_admin(claims)
    item = _catalog_item(db, ResponseCategory, code)
    used = db.scalar(select(TreatmentOutcome.id).where(TreatmentOutcome.response == item.code).limit(1)) is not None
    return _delete_catalog_item(db, item, used)


def _load_patient(db: Session, identifier: str) -> Patient:
    patient = db.scalar(
        select(Patient)
        .where(Patient.synthetic_identifier == identifier)
        .options(
            selectinload(Patient.diseases).selectinload(PatientDisease.disease),
            selectinload(Patient.variants).selectinload(PatientVariant.variant),
            selectinload(Patient.treatments).selectinload(Treatment.therapy),
            selectinload(Patient.treatments).selectinload(Treatment.outcome),
        )
    )
    if not patient:
        raise HTTPException(status_code=404, detail="patient not found")
    return patient


def _patient_detail(patient: Patient) -> LocalPatientDetail:
    return LocalPatientDetail(
        identifier=patient.synthetic_identifier,
        age=patient.age,
        sex=patient.sex,
        disease_codes=[item.disease.code for item in patient.diseases],
        variants=[{"code": item.variant.code, "genotype": item.genotype} for item in patient.variants],
        treatments=[
            {"therapy_code": item.therapy.code, "response": item.outcome.response}
            for item in patient.treatments if item.outcome
        ],
    )


def _replace_medical_relations(db: Session, patient: Patient, payload: LocalPatientWrite) -> None:
    disease_codes = list(dict.fromkeys(code.strip() for code in payload.disease_codes if code.strip()))
    variant_inputs = {item.code.strip(): item.genotype for item in payload.variants}
    treatment_inputs = {item.therapy_code.strip(): item.response for item in payload.treatments}

    diseases = list(db.scalars(select(Disease).where(Disease.code.in_(disease_codes)))) if disease_codes else []
    variants = list(db.scalars(select(GeneticVariant).where(GeneticVariant.code.in_(variant_inputs)))) if variant_inputs else []
    therapies = list(db.scalars(select(Therapy).where(Therapy.code.in_(treatment_inputs)))) if treatment_inputs else []
    response_codes = set(treatment_inputs.values())
    existing_responses = set(db.scalars(select(ResponseCategory.code).where(ResponseCategory.code.in_(response_codes)))) if response_codes else set()
    if {item.code for item in diseases} != set(disease_codes):
        raise HTTPException(status_code=422, detail="one or more disease codes do not exist in this hospital")
    if {item.code for item in variants} != set(variant_inputs):
        raise HTTPException(status_code=422, detail="one or more variant codes do not exist in this hospital")
    if {item.code for item in therapies} != set(treatment_inputs):
        raise HTTPException(status_code=422, detail="one or more therapy codes do not exist in this hospital")
    if existing_responses != response_codes:
        raise HTTPException(status_code=422, detail="one or more response codes do not exist in this hospital")

    patient.diseases.clear()
    patient.variants.clear()
    patient.treatments.clear()
    db.flush()
    patient.diseases.extend(PatientDisease(disease_id=item.id) for item in diseases)
    patient.variants.extend(
        PatientVariant(variant_id=item.id, genotype=variant_inputs[item.code]) for item in variants
    )
    for therapy in therapies:
        treatment = Treatment(therapy_id=therapy.id)
        treatment.outcome = TreatmentOutcome(response=treatment_inputs[therapy.code])
        patient.treatments.append(treatment)


@router.get("/patients/{identifier}", response_model=LocalPatientDetail)
def patient_detail(identifier: str, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    if claims.get("scope") != "local_patients":
        raise HTTPException(status_code=403, detail="token is not valid for local patient data")
    return _patient_detail(_load_patient(db, identifier))


@router.post("/patients", response_model=LocalPatientDetail, status_code=status.HTTP_201_CREATED)
def create_patient(payload: LocalPatientWrite, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    if claims.get("scope") != "local_patients":
        raise HTTPException(status_code=403, detail="token is not valid for local patient data")
    if db.scalar(select(Patient.id).where(Patient.synthetic_identifier == payload.identifier.strip())):
        raise HTTPException(status_code=409, detail="patient identifier already exists")
    patient = Patient(synthetic_identifier=payload.identifier.strip(), age=payload.age, sex=payload.sex)
    db.add(patient)
    db.flush()
    _replace_medical_relations(db, patient, payload)
    db.commit()
    return _patient_detail(_load_patient(db, patient.synthetic_identifier))


@router.put("/patients/{identifier}", response_model=LocalPatientDetail)
def update_patient(identifier: str, payload: LocalPatientWrite, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    if claims.get("scope") != "local_patients":
        raise HTTPException(status_code=403, detail="token is not valid for local patient data")
    patient = _load_patient(db, identifier)
    new_identifier = payload.identifier.strip()
    duplicate = db.scalar(select(Patient.id).where(Patient.synthetic_identifier == new_identifier, Patient.id != patient.id))
    if duplicate:
        raise HTTPException(status_code=409, detail="patient identifier already exists")
    patient.synthetic_identifier = new_identifier
    patient.age = payload.age
    patient.sex = payload.sex
    _replace_medical_relations(db, patient, payload)
    db.commit()
    return _patient_detail(_load_patient(db, new_identifier))


@router.delete("/patients/{identifier}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(identifier: str, claims: dict = Depends(verify_local_admin), db: Session = Depends(get_db)):
    if claims.get("scope") != "local_patients":
        raise HTTPException(status_code=403, detail="token is not valid for local patient data")
    patient = _load_patient(db, identifier)
    db.delete(patient)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/patients", response_model=LocalPatientsResponse)
def local_patients(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=64),
    min_age: int | None = Query(default=None, ge=0, le=130),
    max_age: int | None = Query(default=None, ge=0, le=130),
    sex: str | None = Query(default=None, pattern="^(F|M)$"),
    disease: str | None = Query(default=None, max_length=64),
    variant: str | None = Query(default=None, max_length=128),
    therapy: str | None = Query(default=None, max_length=64),
    response: str | None = Query(default=None, max_length=32),
    claims: dict = Depends(verify_local_admin),
    db: Session = Depends(get_db),
):
    if claims.get("scope") != "local_patients":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="token is not valid for local patient data")
    stmt = select(Patient)
    if search:
        stmt = stmt.where(Patient.synthetic_identifier.ilike(f"%{search.strip()}%"))
    if min_age is not None:
        stmt = stmt.where(Patient.age >= min_age)
    if max_age is not None:
        stmt = stmt.where(Patient.age <= max_age)
    if sex:
        stmt = stmt.where(Patient.sex == sex)
    if disease:
        stmt = stmt.where(Patient.diseases.any(PatientDisease.disease.has(Disease.code.ilike(disease.strip()))))
    if variant:
        stmt = stmt.where(Patient.variants.any(PatientVariant.variant.has(GeneticVariant.code.ilike(variant.strip()))))
    if therapy:
        stmt = stmt.where(Patient.treatments.any(Treatment.therapy.has(Therapy.code.ilike(therapy.strip()))))
    if response:
        stmt = stmt.where(Patient.treatments.any(Treatment.outcome.has(TreatmentOutcome.response.ilike(response.strip()))))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    patients = list(db.scalars(
        stmt
        .options(
            selectinload(Patient.diseases).selectinload(PatientDisease.disease),
            selectinload(Patient.variants).selectinload(PatientVariant.variant),
            selectinload(Patient.treatments).selectinload(Treatment.therapy),
            selectinload(Patient.treatments).selectinload(Treatment.outcome),
        )
        .order_by(Patient.synthetic_identifier)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ))
    items = [
        LocalPatient(
            identifier=p.synthetic_identifier,
            age=p.age,
            sex=p.sex,
            diseases=[x.disease.code for x in p.diseases],
            variants=[x.variant.code for x in p.variants],
            therapies=[x.therapy.code for x in p.treatments],
            responses=[x.outcome.response for x in p.treatments if x.outcome],
        )
        for p in patients
    ]
    settings = request.app.state.settings
    return LocalPatientsResponse(
        organization=settings.organization_name,
        participant_id=settings.participant_id,
        page=page,
        page_size=page_size,
        total=total,
        items=items,
    )


@router.post("/studies/{study_id}/input", response_model=LocalStudyInputResponse)
def local_study_input(
    study_id: str,
    payload: LocalStudyInputRequest,
    request: Request,
    claims: dict = Depends(verify_local_admin),
    db: Session = Depends(get_db),
):
    if claims.get("scope") != "local_study_input" or claims.get("study_id") != study_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="token is not valid for this study")
    settings = request.app.state.settings
    common = dict(
        study_id=study_id,
        organization=settings.organization_name,
        participant_id=settings.participant_id,
        analysis_type=payload.analysis_type,
    )
    if payload.analysis_type == "VARIANT_FREQUENCY":
        counts = calculate_variant_frequency_counts(db, payload.criteria)
        return LocalStudyInputResponse(
            **common, cohort_size=counts.cohort_count, variant_count=counts.variant_count
        )
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
        **common,
        cohort_size=counts.a + counts.b + counts.c + counts.d,
        a=counts.a, b=counts.b, c=counts.c, d=counts.d,
    )
