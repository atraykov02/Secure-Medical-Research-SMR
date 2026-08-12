from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hospital_node.app.cohort import (
    calculate_therapy_response_counts,
    calculate_variant_frequency_counts,
)
from hospital_node.app.db import Base
from hospital_node.app.models import (
    Disease,
    GeneticVariant,
    Patient,
    PatientDisease,
    PatientVariant,
    Therapy,
    Treatment,
    TreatmentOutcome,
)
from hospital_node.app.schemas import CohortCriteria


def make_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


def add_patient(db, sid, age, has_variant, response):
    disease = db.query(Disease).filter_by(code="DX").one()
    variant = db.query(GeneticVariant).filter_by(code="V1").one()
    therapy = db.query(Therapy).filter_by(code="T1").one()
    patient = Patient(synthetic_identifier=sid, age=age, sex="F")
    db.add(patient)
    db.flush()
    db.add(PatientDisease(patient_id=patient.id, disease_id=disease.id))
    if has_variant:
        db.add(PatientVariant(patient_id=patient.id, variant_id=variant.id, genotype="0/1"))
    treatment = Treatment(patient_id=patient.id, therapy_id=therapy.id, started_at=date(2026, 1, 1))
    db.add(treatment)
    db.flush()
    db.add(TreatmentOutcome(treatment_id=treatment.id, response=response))


def test_local_medical_aggregates():
    db = make_db()
    db.add_all([
        Disease(code="DX", name="Disease"),
        GeneticVariant(code="V1", gene="G", chromosome="1", position=1, reference_allele="A", alternate_allele="T"),
        Therapy(code="T1", name="Therapy"),
    ])
    db.commit()

    add_patient(db, "P1", 50, True, "RESPONDER")
    add_patient(db, "P2", 55, True, "NON_RESPONDER")
    add_patient(db, "P3", 60, False, "RESPONDER")
    add_patient(db, "P4", 65, False, "NON_RESPONDER")
    add_patient(db, "P5", 20, True, "RESPONDER")  # excluded by age
    db.commit()

    criteria = CohortCriteria(
        min_age=40,
        max_age=70,
        sex="F",
        disease_code="DX",
        variant_code="V1",
        therapy_code="T1",
    )
    vf = calculate_variant_frequency_counts(db, criteria)
    assert vf.variant_count == 2
    assert vf.cohort_count == 4

    tr = calculate_therapy_response_counts(db, criteria)
    assert (tr.a, tr.b, tr.c, tr.d) == (1, 1, 1, 1)
