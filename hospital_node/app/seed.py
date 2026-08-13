from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    Disease,
    GeneticVariant,
    Patient,
    PatientDisease,
    PatientVariant,
    Therapy,
    Treatment,
    TreatmentOutcome,
    ResponseCategory,
)


def seed_synthetic_data(db: Session, *, count: int, seed: int, node_id: int) -> int:
    for code, name, is_positive in (
        ("RESPONDER", "Положителен терапевтичен отговор", 1),
        ("NON_RESPONDER", "Без положителен терапевтичен отговор", 0),
    ):
        if not db.scalar(select(ResponseCategory.id).where(ResponseCategory.code == code)):
            db.add(ResponseCategory(code=code, name=name, is_positive=is_positive))
    db.commit()
    existing = int(db.scalar(select(func.count(Patient.id))) or 0)
    if existing:
        return 0

    rng = random.Random(seed + node_id * 10_000)

    diseases = [
        Disease(code="DX-LUNG", name="Synthetic lung disease cohort"),
        Disease(code="DX-BREAST", name="Synthetic breast disease cohort"),
    ]
    variants = [
        GeneticVariant(
            code="VAR-A",
            gene="GENE-A",
            chromosome="7",
            position=140453136,
            reference_allele="A",
            alternate_allele="T",
        ),
        GeneticVariant(
            code="VAR-B",
            gene="GENE-B",
            chromosome="17",
            position=43071077,
            reference_allele="G",
            alternate_allele="A",
        ),
    ]
    therapies = [
        Therapy(code="THERAPY-A", name="Synthetic targeted therapy A"),
        Therapy(code="THERAPY-B", name="Synthetic targeted therapy B"),
    ]
    db.add_all([*diseases, *variants, *therapies])
    db.flush()

    today = date.today()
    for index in range(1, count + 1):
        patient = Patient(
            synthetic_identifier=f"H{node_id}-SYN-{index:06d}",
            age=rng.randint(25, 85),
            sex=rng.choice(["F", "M"]),
        )
        db.add(patient)
        db.flush()

        disease = diseases[0] if rng.random() < 0.68 else diseases[1]
        db.add(PatientDisease(patient_id=patient.id, disease_id=disease.id))

        # Different nodes get slightly different variant prevalences, which makes
        # the multicenter MPC result more interesting without using real patients.
        variant_a_probability = 0.16 + (node_id - 1) * 0.025
        has_variant_a = rng.random() < variant_a_probability
        if has_variant_a:
            db.add(
                PatientVariant(
                    patient_id=patient.id,
                    variant_id=variants[0].id,
                    genotype=rng.choice(["0/1", "1/1"]),
                )
            )
        if rng.random() < 0.12:
            db.add(
                PatientVariant(
                    patient_id=patient.id,
                    variant_id=variants[1].id,
                    genotype="0/1",
                )
            )

        therapy = therapies[0] if rng.random() < 0.72 else therapies[1]
        started = today - timedelta(days=rng.randint(60, 720))
        treatment = Treatment(
            patient_id=patient.id,
            therapy_id=therapy.id,
            started_at=started,
            completed_at=started + timedelta(days=rng.randint(30, 120)),
        )
        db.add(treatment)
        db.flush()

        if therapy.code == "THERAPY-A":
            # Create a synthetic association between VAR-A and response so the
            # secure odds-ratio analysis has a visible signal in the demo.
            response_probability = 0.72 if has_variant_a else 0.48
        else:
            response_probability = 0.55
        response = "RESPONDER" if rng.random() < response_probability else "NON_RESPONDER"
        db.add(
            TreatmentOutcome(
                treatment_id=treatment.id,
                response=response,
                evaluated_at=treatment.completed_at,
            )
        )

    db.commit()
    return count
