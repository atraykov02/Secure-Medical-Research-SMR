from __future__ import annotations

from sqlalchemy.orm import Session

from bgw.circuits import build_therapy_response_sums, build_variant_frequency_sums

from .cohort import (
    calculate_allele_frequency_counts, calculate_mean_age_counts,
    calculate_response_rate_counts, calculate_therapy_response_counts,
    calculate_variant_disease_counts, calculate_variant_frequency_counts,
)
from .runtime import NodeRuntime
from .schemas import CohortCriteria


def _validate_field_value(value: int, prime: int) -> None:
    if value < 0 or value >= prime:
        raise ValueError("local aggregate is outside the configured finite field")


async def share_variant_frequency_inputs(
    *, runtime: NodeRuntime, db: Session, session_id: str, criteria: CohortCriteria
) -> list[str]:
    participant = runtime.store.get(session_id)
    transport = runtime.get_transport(session_id)
    pid = participant.participant_id
    names = [f"variant_count_p{pid}", f"cohort_count_p{pid}"]
    if any(participant.has_value(name) for name in names):
        raise ValueError("local variant-frequency inputs were already shared")

    counts = calculate_variant_frequency_counts(db, criteria)
    _validate_field_value(counts.variant_count, participant.prime)
    _validate_field_value(counts.cohort_count, participant.prime)

    await participant.share_private_input(names[0], counts.variant_count, transport)
    await participant.share_private_input(names[1], counts.cohort_count, transport)
    return names


def build_variant_frequency(runtime: NodeRuntime, session_id: str) -> None:
    participant = runtime.store.get(session_id)
    if participant.has_value("variant_total") or participant.has_value("cohort_total"):
        return
    ids = participant.participant_ids
    variant_wires = [f"variant_count_p{pid}" for pid in ids]
    cohort_wires = [f"cohort_count_p{pid}" for pid in ids]
    missing = [
        name
        for name in [*variant_wires, *cohort_wires]
        if not participant.has_value(name)
    ]
    if missing:
        raise RuntimeError(f"not all hospitals have shared their inputs: {missing}")
    build_variant_frequency_sums(
        participant,
        variant_wires=variant_wires,
        cohort_wires=cohort_wires,
    )


SUM_ANALYSES = {
    "ALLELE_FREQUENCY": (calculate_allele_frequency_counts, "alternative_allele_total", "cohort_total"),
    "COHORT_MEAN_AGE": (calculate_mean_age_counts, "age_sum_total", "cohort_total"),
    "THERAPY_RESPONSE_RATE": (calculate_response_rate_counts, "responder_total", "treated_total"),
}


async def share_sum_inputs(*, runtime: NodeRuntime, db: Session, session_id: str,
                           criteria: CohortCriteria, analysis_type: str) -> list[str]:
    if analysis_type not in SUM_ANALYSES:
        raise ValueError("unsupported secure-sum analysis")
    calculator, _, _ = SUM_ANALYSES[analysis_type]
    participant = runtime.store.get(session_id)
    pid = participant.participant_id
    names = [f"metric_p{pid}", f"denominator_p{pid}"]
    if any(participant.has_value(name) for name in names):
        raise ValueError("local secure-sum inputs were already shared")
    counts = calculator(db, criteria)
    for value in (counts.value, counts.cohort_count):
        _validate_field_value(value, participant.prime)
    transport = runtime.get_transport(session_id)
    await participant.share_private_input(names[0], counts.value, transport)
    await participant.share_private_input(names[1], counts.cohort_count, transport)
    return names


def build_sum_analysis(runtime: NodeRuntime, session_id: str, analysis_type: str) -> None:
    if analysis_type not in SUM_ANALYSES:
        raise ValueError("unsupported secure-sum analysis")
    participant = runtime.store.get(session_id)
    _, metric_out, denominator_out = SUM_ANALYSES[analysis_type]
    ids = participant.participant_ids
    build_variant_frequency_sums(
        participant,
        variant_wires=[f"metric_p{pid}" for pid in ids],
        cohort_wires=[f"denominator_p{pid}" for pid in ids],
        variant_total_out=metric_out,
        cohort_total_out=denominator_out,
    )


async def share_therapy_response_inputs(
    *, runtime: NodeRuntime, db: Session, session_id: str, criteria: CohortCriteria
) -> list[str]:
    participant = runtime.store.get(session_id)
    transport = runtime.get_transport(session_id)
    pid = participant.participant_id
    labels = ["a", "b", "c", "d"]
    names = [f"{label}_p{pid}" for label in labels]
    if any(participant.has_value(name) for name in names):
        raise ValueError("local therapy-response inputs were already shared")

    counts = calculate_therapy_response_counts(db, criteria)
    values = [counts.a, counts.b, counts.c, counts.d]
    for value in values:
        _validate_field_value(value, participant.prime)

    for name, value in zip(names, values):
        await participant.share_private_input(name, value, transport)
    return names


async def share_association_inputs(*, runtime: NodeRuntime, db: Session, session_id: str,
                                   criteria: CohortCriteria, analysis_type: str) -> list[str]:
    calculator = calculate_therapy_response_counts if analysis_type == "THERAPY_RESPONSE" else calculate_variant_disease_counts
    participant = runtime.store.get(session_id)
    pid = participant.participant_id
    names = [f"{label}_p{pid}" for label in ("a", "b", "c", "d")]
    if any(participant.has_value(name) for name in names):
        raise ValueError("local association inputs were already shared")
    counts = calculator(db, criteria)
    values = [counts.a, counts.b, counts.c, counts.d]
    transport = runtime.get_transport(session_id)
    for name, value in zip(names, values):
        _validate_field_value(value, participant.prime)
        await participant.share_private_input(name, value, transport)
    return names


def build_therapy_response(runtime: NodeRuntime, session_id: str) -> None:
    participant = runtime.store.get(session_id)
    if all(participant.has_value(name) for name in ["A", "B", "C", "D"]):
        return
    ids = participant.participant_ids
    groups = {
        label: [f"{label}_p{pid}" for pid in ids]
        for label in ["a", "b", "c", "d"]
    }
    missing = [
        name
        for names in groups.values()
        for name in names
        if not participant.has_value(name)
    ]
    if missing:
        raise RuntimeError(f"not all hospitals have shared their inputs: {missing}")
    build_therapy_response_sums(
        participant,
        a_wires=groups["a"],
        b_wires=groups["b"],
        c_wires=groups["c"],
        d_wires=groups["d"],
    )


async def start_therapy_multiplications(runtime: NodeRuntime, session_id: str) -> None:
    participant = runtime.store.get(session_id)
    transport = runtime.get_transport(session_id)
    for name in ["A", "B", "C", "D"]:
        if not participant.has_value(name):
            raise RuntimeError("therapy-response sums must be built before multiplication")

    await participant.begin_multiplication(
        operation_id="therapy:AD",
        out="AD",
        a="A",
        b="D",
        transport=transport,
    )
    await participant.begin_multiplication(
        operation_id="therapy:BC",
        out="BC",
        a="B",
        b="C",
        transport=transport,
    )


def finalize_therapy_multiplications(runtime: NodeRuntime, session_id: str) -> None:
    participant = runtime.store.get(session_id)
    operations = [("therapy:AD", "AD"), ("therapy:BC", "BC")]
    incomplete = [op for op, _ in operations if not participant.can_finalize_multiplication(op)]
    if incomplete:
        raise RuntimeError(f"multiplication messages are still missing: {incomplete}")
    for operation_id, out in operations:
        participant.finalize_multiplication(operation_id=operation_id, out=out)
