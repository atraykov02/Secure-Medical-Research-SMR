from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import platform
import random
import sqlite3
import statistics
import tempfile
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter_ns

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from bgw.circuits import build_therapy_response_sums, build_variant_frequency_sums
from bgw.field import DEFAULT_PRIME
from bgw.participant import BGWParticipant
from bgw.reconstruction import reconstruct_result
from bgw.transport.memory import InMemoryTransport
from coordinator.app.verification.reference_analysis import compare_results
from hospital_node.app.cohort import (
    calculate_allele_frequency_counts,
    calculate_mean_age_counts,
    calculate_response_rate_counts,
    calculate_therapy_response_counts,
    calculate_variant_disease_counts,
    calculate_variant_frequency_counts,
)
from hospital_node.app.db import Base
from hospital_node.app.models import (
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
from hospital_node.app.schemas import CohortCriteria


DEFAULT_PARTICIPANT_COUNTS = [3, 4, 5, 6]
DATASET_SCALING_PARTICIPANTS = 3
ANALYSES = [
    "VARIANT_FREQUENCY",
    "ALLELE_FREQUENCY",
    "COHORT_MEAN_AGE",
    "THERAPY_RESPONSE_RATE",
    "THERAPY_RESPONSE",
    "VARIANT_DISEASE_ASSOCIATION",
]
ANALYSIS_LABELS = {
    "VARIANT_FREQUENCY": "Variant Frequency",
    "ALLELE_FREQUENCY": "Allele Frequency",
    "COHORT_MEAN_AGE": "Cohort Mean Age",
    "THERAPY_RESPONSE_RATE": "Therapy Response Rate",
    "THERAPY_RESPONSE": "Therapy Response",
    "VARIANT_DISEASE_ASSOCIATION": "Variant-Disease Association",
}
RESULT_FIELDS = {
    "VARIANT_FREQUENCY": ("frequency_percent", "%"),
    "ALLELE_FREQUENCY": ("allele_frequency_percent", "%"),
    "COHORT_MEAN_AGE": ("mean_age", "years"),
    "THERAPY_RESPONSE_RATE": ("response_rate_percent", "%"),
    "THERAPY_RESPONSE": ("odds_ratio", "OR"),
    "VARIANT_DISEASE_ASSOCIATION": ("odds_ratio", "OR"),
}
PROTOCOL_PROFILE = {
    "VARIANT_FREQUENCY": ("addition", 0),
    "ALLELE_FREQUENCY": ("addition", 0),
    "COHORT_MEAN_AGE": ("addition", 0),
    "THERAPY_RESPONSE_RATE": ("addition", 0),
    "THERAPY_RESPONSE": ("addition and multiplication", 2),
    "VARIANT_DISEASE_ASSOCIATION": ("addition and multiplication", 2),
}


def _threshold_for(participant_count: int) -> int:
    if not 3 <= participant_count <= 6:
        raise ValueError("participant count must be between 3 and 6")
    return (participant_count - 1) // 2


def _remote_message_count(analysis: str, participant_count: int) -> int:
    """Count deliveries that cross participant/process boundaries.

    Secure-sum analyses share two local aggregates. Association analyses share
    four inputs and reshare two products during degree reduction.
    """
    values_shared_per_owner = 2 if PROTOCOL_PROFILE[analysis][1] == 0 else 6
    return values_shared_per_owner * participant_count * (participant_count - 1)


@dataclass(frozen=True)
class TimingSummary:
    median_ms: float
    min_ms: float
    max_ms: float
    p95_ms: float
    samples_ms: list[float]


def _timing_summary(samples: list[float]) -> TimingSummary:
    ordered = sorted(samples)
    p95_index = max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999999) - 1))
    return TimingSummary(
        median_ms=round(statistics.median(samples), 6),
        min_ms=round(ordered[0], 6),
        max_ms=round(ordered[-1], 6),
        p95_ms=round(ordered[p95_index], 6),
        samples_ms=[round(value, 6) for value in samples],
    )


def _elapsed_ms(start_ns: int) -> float:
    return (perf_counter_ns() - start_ns) / 1_000_000


def _criteria(analysis: str) -> CohortCriteria:
    common = {"min_age": 18, "max_age": 100}
    if analysis in ("VARIANT_FREQUENCY", "ALLELE_FREQUENCY"):
        return CohortCriteria(**common, variant_code="VAR-A")
    if analysis == "COHORT_MEAN_AGE":
        return CohortCriteria(**common)
    if analysis == "THERAPY_RESPONSE_RATE":
        return CohortCriteria(**common, therapy_code="THERAPY-A")
    if analysis == "THERAPY_RESPONSE":
        return CohortCriteria(
            **common, variant_code="VAR-A", therapy_code="THERAPY-A"
        )
    if analysis == "VARIANT_DISEASE_ASSOCIATION":
        return CohortCriteria(
            **common, variant_code="VAR-A", disease_code="DX-LUNG"
        )
    raise ValueError(f"unsupported analysis: {analysis}")


def _insert_catalog(connection) -> None:
    connection.execute(
        ResponseCategory.__table__.insert(),
        [
            {"id": 1, "code": "RESPONDER", "name": "Responder", "is_positive": 1},
            {
                "id": 2,
                "code": "NON_RESPONDER",
                "name": "Non-responder",
                "is_positive": 0,
            },
        ],
    )
    connection.execute(
        Disease.__table__.insert(),
        [
            {"id": 1, "code": "DX-LUNG", "name": "Synthetic lung disease"},
            {"id": 2, "code": "DX-BREAST", "name": "Synthetic breast disease"},
        ],
    )
    connection.execute(
        GeneticVariant.__table__.insert(),
        [
            {
                "id": 1,
                "code": "VAR-A",
                "gene": "GENE-A",
                "chromosome": "7",
                "position": 140453136,
                "reference_allele": "A",
                "alternate_allele": "T",
            },
            {
                "id": 2,
                "code": "VAR-B",
                "gene": "GENE-B",
                "chromosome": "17",
                "position": 43071077,
                "reference_allele": "G",
                "alternate_allele": "A",
            },
        ],
    )
    connection.execute(
        Therapy.__table__.insert(),
        [
            {"id": 1, "code": "THERAPY-A", "name": "Synthetic therapy A"},
            {"id": 2, "code": "THERAPY-B", "name": "Synthetic therapy B"},
        ],
    )


def _seed_database(path: Path, *, count: int, seed: int, node_id: int) -> None:
    """Create deterministic synthetic records using efficient batched inserts.

    The probability model mirrors ``hospital_node.app.seed.seed_synthetic_data``.
    Database creation is setup work and is deliberately outside timed sections.
    """
    engine = create_engine(f"sqlite+pysqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    rng = random.Random(seed + node_id * 10_000)
    variant_row_id = 1
    batch_size = 2_000

    with engine.begin() as connection:
        _insert_catalog(connection)
        for batch_start in range(1, count + 1, batch_size):
            batch_end = min(count + 1, batch_start + batch_size)
            patients: list[dict] = []
            diseases: list[dict] = []
            variants: list[dict] = []
            treatments: list[dict] = []
            outcomes: list[dict] = []

            for index in range(batch_start, batch_end):
                age = rng.randint(25, 85)
                sex = rng.choice(["F", "M"])
                disease_id = 1 if rng.random() < 0.68 else 2
                variant_a_probability = 0.16 + (node_id - 1) * 0.025
                has_variant_a = rng.random() < variant_a_probability

                patients.append(
                    {
                        "id": index,
                        "synthetic_identifier": f"H{node_id}-SYN-{index:06d}",
                        "age": age,
                        "sex": sex,
                    }
                )
                diseases.append(
                    {"id": index, "patient_id": index, "disease_id": disease_id}
                )
                if has_variant_a:
                    variants.append(
                        {
                            "id": variant_row_id,
                            "patient_id": index,
                            "variant_id": 1,
                            "genotype": rng.choice(["0/1", "1/1"]),
                        }
                    )
                    variant_row_id += 1
                if rng.random() < 0.12:
                    variants.append(
                        {
                            "id": variant_row_id,
                            "patient_id": index,
                            "variant_id": 2,
                            "genotype": "0/1",
                        }
                    )
                    variant_row_id += 1

                therapy_id = 1 if rng.random() < 0.72 else 2
                treatments.append(
                    {
                        "id": index,
                        "patient_id": index,
                        "therapy_id": therapy_id,
                    }
                )
                if therapy_id == 1:
                    response_probability = 0.72 if has_variant_a else 0.48
                else:
                    response_probability = 0.55
                response = (
                    "RESPONDER"
                    if rng.random() < response_probability
                    else "NON_RESPONDER"
                )
                outcomes.append(
                    {"id": index, "treatment_id": index, "response": response}
                )

            connection.execute(Patient.__table__.insert(), patients)
            connection.execute(PatientDisease.__table__.insert(), diseases)
            if variants:
                connection.execute(PatientVariant.__table__.insert(), variants)
            connection.execute(Treatment.__table__.insert(), treatments)
            connection.execute(TreatmentOutcome.__table__.insert(), outcomes)
    engine.dispose()


def _open_sessions(paths: list[Path]) -> tuple[list, list[Session]]:
    engines = [
        create_engine(
            f"sqlite+pysqlite:///{path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        for path in paths
    ]
    sessions = [
        sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
        for engine in engines
    ]
    return engines, sessions


def _collect_local_inputs(analysis: str, sessions: list[Session]) -> list[dict]:
    criteria = _criteria(analysis)
    values: list[dict] = []
    for db in sessions:
        if analysis == "VARIANT_FREQUENCY":
            counts = calculate_variant_frequency_counts(db, criteria)
            values.append(
                {"cohort_size": counts.cohort_count, "variant_count": counts.variant_count}
            )
        elif analysis == "ALLELE_FREQUENCY":
            counts = calculate_allele_frequency_counts(db, criteria)
            values.append(
                {
                    "cohort_size": counts.cohort_count,
                    "alternative_allele_count": counts.value,
                }
            )
        elif analysis == "COHORT_MEAN_AGE":
            counts = calculate_mean_age_counts(db, criteria)
            values.append({"cohort_size": counts.cohort_count, "age_sum": counts.value})
        elif analysis == "THERAPY_RESPONSE_RATE":
            counts = calculate_response_rate_counts(db, criteria)
            values.append(
                {"cohort_size": counts.cohort_count, "responder_count": counts.value}
            )
        else:
            calculator = (
                calculate_therapy_response_counts
                if analysis == "THERAPY_RESPONSE"
                else calculate_variant_disease_counts
            )
            counts = calculator(db, criteria)
            values.append(
                {
                    "cohort_size": counts.a + counts.b + counts.c + counts.d,
                    "a": counts.a,
                    "b": counts.b,
                    "c": counts.c,
                    "d": counts.d,
                }
            )
    return values


def _participants(session_id: str, participant_ids: list[int], threshold: int):
    transport = InMemoryTransport()
    parties = {
        participant_id: BGWParticipant(
            session_id=session_id,
            participant_id=participant_id,
            participant_ids=participant_ids,
            threshold=threshold,
        )
        for participant_id in participant_ids
    }
    for participant_id, participant in parties.items():
        transport.register(participant_id, participant.handle_message)
    return parties, transport


def _reveal(
    parties: dict[int, BGWParticipant],
    name: str,
    participant_ids: list[int],
    threshold: int,
) -> int:
    return reconstruct_result(
        prime=DEFAULT_PRIME,
        threshold=threshold,
        shares=[parties[participant_id].get_share(name) for participant_id in participant_ids],
    )


async def _run_bgw(
    analysis: str,
    local_values: list[dict],
    run_id: int,
    participant_count: int = DATASET_SCALING_PARTICIPANTS,
) -> dict:
    participant_ids = list(range(1, participant_count + 1))
    threshold = _threshold_for(participant_count)
    if len(local_values) != participant_count:
        raise ValueError(
            f"expected {participant_count} local inputs, got {len(local_values)}"
        )
    parties, transport = _participants(
        f"benchmark-{analysis}-n{participant_count}-{run_id}",
        participant_ids,
        threshold,
    )

    def verified_result(result: dict) -> dict:
        remote_messages = sum(
            message.sender_id != message.recipient_id
            for message in transport.sent_messages
        )
        expected_messages = _remote_message_count(analysis, participant_count)
        if remote_messages != expected_messages:
            raise RuntimeError(
                f"protocol profile for {analysis} expected {expected_messages} "
                f"remote messages, observed {remote_messages}"
            )
        return result

    if analysis == "VARIANT_FREQUENCY":
        input_fields = ("variant_count", "cohort_size")
        wire_prefixes = ("variant", "cohort")
    elif analysis == "ALLELE_FREQUENCY":
        input_fields = ("alternative_allele_count", "cohort_size")
        wire_prefixes = ("metric", "denominator")
    elif analysis == "COHORT_MEAN_AGE":
        input_fields = ("age_sum", "cohort_size")
        wire_prefixes = ("metric", "denominator")
    elif analysis == "THERAPY_RESPONSE_RATE":
        input_fields = ("responder_count", "cohort_size")
        wire_prefixes = ("metric", "denominator")
    else:
        input_fields = ("a", "b", "c", "d")
        wire_prefixes = input_fields

    for owner_id, local in zip(participant_ids, local_values):
        for field_name, prefix in zip(input_fields, wire_prefixes):
            await parties[owner_id].share_private_input(
                f"{prefix}_p{owner_id}", int(local[field_name]), transport
            )

    if analysis == "VARIANT_FREQUENCY":
        for participant in parties.values():
            build_variant_frequency_sums(
                participant,
                variant_wires=[f"variant_p{pid}" for pid in participant_ids],
                cohort_wires=[f"cohort_p{pid}" for pid in participant_ids],
            )
        variant_total = _reveal(parties, "variant_total", participant_ids, threshold)
        cohort_total = _reveal(parties, "cohort_total", participant_ids, threshold)
        return verified_result({
            "cohort_size": cohort_total,
            "variant_count": variant_total,
            "frequency_percent": round(variant_total / cohort_total * 100, 4)
            if cohort_total
            else None,
        })

    if analysis in (
        "ALLELE_FREQUENCY",
        "COHORT_MEAN_AGE",
        "THERAPY_RESPONSE_RATE",
    ):
        outputs = {
            "ALLELE_FREQUENCY": ("alternative_allele_total", "cohort_total"),
            "COHORT_MEAN_AGE": ("age_sum_total", "cohort_total"),
            "THERAPY_RESPONSE_RATE": ("responder_total", "treated_total"),
        }[analysis]
        for participant in parties.values():
            build_variant_frequency_sums(
                participant,
                variant_wires=[f"metric_p{pid}" for pid in participant_ids],
                cohort_wires=[f"denominator_p{pid}" for pid in participant_ids],
                variant_total_out=outputs[0],
                cohort_total_out=outputs[1],
            )
        value = _reveal(parties, outputs[0], participant_ids, threshold)
        count = _reveal(parties, outputs[1], participant_ids, threshold)
        if analysis == "ALLELE_FREQUENCY":
            return verified_result({
                "cohort_size": count,
                "alternative_allele_count": value,
                "allele_frequency_percent": round(value / (2 * count) * 100, 4)
                if count
                else None,
            })
        if analysis == "COHORT_MEAN_AGE":
            return verified_result({
                "cohort_size": count,
                "mean_age": round(value / count, 4) if count else None,
            })
        return verified_result({
            "cohort_size": count,
            "treated_count": count,
            "responder_count": value,
            "response_rate_percent": round(value / count * 100, 4)
            if count
            else None,
        })

    for participant in parties.values():
        build_therapy_response_sums(
            participant,
            a_wires=[f"a_p{pid}" for pid in participant_ids],
            b_wires=[f"b_p{pid}" for pid in participant_ids],
            c_wires=[f"c_p{pid}" for pid in participant_ids],
            d_wires=[f"d_p{pid}" for pid in participant_ids],
        )
    for participant in parties.values():
        await participant.begin_multiplication(
            operation_id="benchmark:AD",
            out="AD",
            a="A",
            b="D",
            transport=transport,
        )
        await participant.begin_multiplication(
            operation_id="benchmark:BC",
            out="BC",
            a="B",
            b="C",
            transport=transport,
        )
    for participant in parties.values():
        participant.finalize_multiplication(operation_id="benchmark:AD", out="AD")
        participant.finalize_multiplication(operation_id="benchmark:BC", out="BC")

    ad = _reveal(parties, "AD", participant_ids, threshold)
    bc = _reveal(parties, "BC", participant_ids, threshold)
    count = _reveal(parties, "therapy_cohort_total", participant_ids, threshold)
    return verified_result({
        "cohort_size": count,
        "odds_ratio": round(ad / bc, 6) if bc else None,
    })


async def _benchmark_case(
    analysis: str,
    sessions: list[Session],
    *,
    warmups: int,
    repetitions: int,
    mpc_iterations: int,
    run_id_start: int,
    participant_count: int = DATASET_SCALING_PARTICIPANTS,
) -> dict:
    for offset in range(warmups):
        local = _collect_local_inputs(analysis, sessions)
        await _run_bgw(
            analysis,
            local,
            run_id_start + offset,
            participant_count=participant_count,
        )

    local_samples: list[float] = []
    mpc_samples: list[float] = []
    total_samples: list[float] = []
    last_local: list[dict] | None = None
    last_bgw: dict | None = None

    for offset in range(repetitions):
        local_start = perf_counter_ns()
        last_local = _collect_local_inputs(analysis, sessions)
        local_samples.append(_elapsed_ms(local_start))

        mpc_start = perf_counter_ns()
        for inner in range(mpc_iterations):
            last_bgw = await _run_bgw(
                analysis,
                last_local,
                run_id_start + warmups + offset * mpc_iterations + inner,
                participant_count=participant_count,
            )
        normalized_mpc_ms = _elapsed_ms(mpc_start) / mpc_iterations
        mpc_samples.append(normalized_mpc_ms)
        # MPC is repeated to stabilize the sub-millisecond measurement. The
        # reported total represents one local phase plus one normalized MPC run.
        total_samples.append(local_samples[-1] + normalized_mpc_ms)

    assert last_local is not None and last_bgw is not None
    reference, differences, verified = compare_results(analysis, last_local, last_bgw)
    return {
        "local": asdict(_timing_summary(local_samples)),
        "mpc": asdict(_timing_summary(mpc_samples)),
        "total": asdict(_timing_summary(total_samples)),
        "local_inputs": last_local,
        "reference": reference,
        "bgw": last_bgw,
        "differences": differences,
        "verified": verified,
    }


async def _benchmark_mpc_only(
    analysis: str,
    local_inputs: list[dict],
    *,
    participant_count: int,
    warmups: int,
    repetitions: int,
    mpc_iterations: int,
    run_id_start: int,
) -> dict:
    for offset in range(warmups):
        await _run_bgw(
            analysis,
            local_inputs,
            run_id_start + offset,
            participant_count=participant_count,
        )

    samples: list[float] = []
    bgw_result: dict | None = None
    for offset in range(repetitions):
        start = perf_counter_ns()
        for inner in range(mpc_iterations):
            bgw_result = await _run_bgw(
                analysis,
                local_inputs,
                run_id_start + warmups + offset * mpc_iterations + inner,
                participant_count=participant_count,
            )
        samples.append(_elapsed_ms(start) / mpc_iterations)

    assert bgw_result is not None
    reference, differences, verified = compare_results(
        analysis, local_inputs, bgw_result
    )
    return {
        "mpc": asdict(_timing_summary(samples)),
        "local_inputs": local_inputs,
        "reference": reference,
        "bgw": bgw_result,
        "differences": differences,
        "verified": verified,
    }


def _environment(
    repetitions: int,
    warmups: int,
    mpc_iterations: int,
    seed: int,
    participant_counts: list[int],
) -> dict:
    return {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": os.environ.get("PROCESSOR_IDENTIFIER") or platform.processor() or "unknown",
        "logical_processors": int(os.environ.get("NUMBER_OF_PROCESSORS", "0")) or None,
        "python": platform.python_version(),
        "sqlalchemy": sqlalchemy.__version__,
        "sqlite": sqlite3.sqlite_version,
        "participant_counts": participant_counts,
        "thresholds": {
            str(count): _threshold_for(count) for count in participant_counts
        },
        "dataset_scaling_participants": DATASET_SCALING_PARTICIPANTS,
        "prime": DEFAULT_PRIME,
        "transport": "InMemoryTransport (HTTP/network excluded)",
        "database": "file-backed SQLite",
        "repetitions": repetitions,
        "warmups": warmups,
        "mpc_iterations_per_sample": mpc_iterations,
        "synthetic_seed": seed,
        "timing_statistic": "median; min, max and p95 retained in JSON",
    }


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)




async def _run_all(args, work_dir: Path) -> dict:
    metadata = _environment(
        args.repetitions,
        args.warmups,
        args.mpc_iterations,
        args.seed,
        args.participant_counts,
    )
    scaling: list[dict] = []
    comparison: list[dict] = []
    correctness: list[dict] = []
    participant_scaling: list[dict] = []
    participant_correctness: list[dict] = []
    raw_cases: dict[str, dict] = {}
    run_id = 0

    for size in args.sizes:
        size_dir = work_dir / f"size-{size}"
        size_dir.mkdir(parents=True, exist_ok=True)
        database_count = (
            max(args.participant_counts)
            if size == args.participant_size
            else DATASET_SCALING_PARTICIPANTS
        )
        node_ids = list(range(1, database_count + 1))
        paths = [size_dir / f"hospital-{node_id}.sqlite3" for node_id in node_ids]
        for node_id, path in zip(node_ids, paths):
            print(f"Seeding hospital {node_id}: {size:,} records ...", flush=True)
            _seed_database(path, count=size, seed=args.seed, node_id=node_id)

        engines, sessions = _open_sessions(paths)
        try:
            print(f"Benchmarking Variant Frequency at {size:,} records ...", flush=True)
            case = await _benchmark_case(
                "VARIANT_FREQUENCY",
                sessions[:DATASET_SCALING_PARTICIPANTS],
                warmups=args.warmups,
                repetitions=args.repetitions,
                mpc_iterations=args.mpc_iterations,
                run_id_start=run_id,
                participant_count=DATASET_SCALING_PARTICIPANTS,
            )
            run_id += args.warmups + args.repetitions * args.mpc_iterations
            raw_cases[f"scaling:{size}"] = case
            scaling.append(
                {
                    "records_per_database": size,
                    "local_median_ms": case["local"]["median_ms"],
                    "mpc_median_ms": case["mpc"]["median_ms"],
                    "total_median_ms": case["total"]["median_ms"],
                }
            )

            if size == args.analysis_size:
                for analysis in ANALYSES:
                    print(f"Benchmarking {ANALYSIS_LABELS[analysis]} ...", flush=True)
                    analysis_case = await _benchmark_case(
                        analysis,
                        sessions[:DATASET_SCALING_PARTICIPANTS],
                        warmups=args.warmups,
                        repetitions=args.repetitions,
                        mpc_iterations=args.mpc_iterations,
                        run_id_start=run_id,
                        participant_count=DATASET_SCALING_PARTICIPANTS,
                    )
                    run_id += args.warmups + args.repetitions * args.mpc_iterations
                    raw_cases[f"analysis:{analysis}"] = analysis_case
                    operations, multiplications = PROTOCOL_PROFILE[analysis]
                    comparison.append(
                        {
                            "analysis": analysis,
                            "label": ANALYSIS_LABELS[analysis],
                            "operations": operations,
                            "secure_multiplications": multiplications,
                            "protocol_messages": _remote_message_count(
                                analysis, DATASET_SCALING_PARTICIPANTS
                            ),
                            "local_median_ms": analysis_case["local"]["median_ms"],
                            "mpc_median_ms": analysis_case["mpc"]["median_ms"],
                            "total_median_ms": analysis_case["total"]["median_ms"],
                        }
                    )

            if size == args.participant_size:
                for participant_count in args.participant_counts:
                    threshold = _threshold_for(participant_count)
                    participant_sessions = sessions[:participant_count]
                    verified_analyses = 0
                    observed_differences: list[float] = []
                    detailed_correctness: list[dict] = []
                    measured_cases: dict[str, dict] = {}

                    print(
                        f"Benchmarking participant configuration n={participant_count}, "
                        f"t={threshold} ...",
                        flush=True,
                    )
                    for analysis in ANALYSES:
                        local_inputs = _collect_local_inputs(
                            analysis, participant_sessions
                        )
                        if analysis in ("VARIANT_FREQUENCY", "THERAPY_RESPONSE"):
                            participant_case = await _benchmark_mpc_only(
                                analysis,
                                local_inputs,
                                participant_count=participant_count,
                                warmups=args.warmups,
                                repetitions=args.repetitions,
                                mpc_iterations=args.mpc_iterations,
                                run_id_start=run_id,
                            )
                            run_id += (
                                args.warmups
                                + args.repetitions * args.mpc_iterations
                            )
                            measured_cases[analysis] = participant_case
                            raw_cases[
                                f"participants:n{participant_count}:{analysis}"
                            ] = participant_case
                        else:
                            bgw_result = await _run_bgw(
                                analysis,
                                local_inputs,
                                run_id,
                                participant_count=participant_count,
                            )
                            run_id += 1
                            reference, differences, verified = compare_results(
                                analysis, local_inputs, bgw_result
                            )
                            participant_case = {
                                "reference": reference,
                                "bgw": bgw_result,
                                "differences": differences,
                                "verified": verified,
                            }

                        verified_analyses += int(participant_case["verified"])
                        observed_differences.extend(
                            float(value)
                            for value in participant_case["differences"].values()
                            if value is not None
                        )
                        result_field, unit = RESULT_FIELDS[analysis]
                        detailed_correctness.append(
                            {
                                "analysis": analysis,
                                "label": ANALYSIS_LABELS[analysis],
                                "result_field": result_field,
                                "unit": unit,
                                "reference_value": participant_case["reference"][result_field],
                                "bgw_value": participant_case["bgw"][result_field],
                                "absolute_difference": participant_case["differences"][result_field],
                                "verified": participant_case["verified"],
                            }
                        )

                    participant_correctness.append(
                        {
                            "participant_count": participant_count,
                            "threshold": threshold,
                            "verified_analyses": verified_analyses,
                            "total_analyses": len(ANALYSES),
                            "max_absolute_difference": max(
                                observed_differences, default=0.0
                            ),
                        }
                    )
                    participant_scaling.append(
                        {
                            "participant_count": participant_count,
                            "threshold": threshold,
                            "records_per_database": size,
                            "variant_frequency_messages": _remote_message_count(
                                "VARIANT_FREQUENCY", participant_count
                            ),
                            "variant_frequency_mpc_median_ms": measured_cases[
                                "VARIANT_FREQUENCY"
                            ]["mpc"]["median_ms"],
                            "therapy_response_messages": _remote_message_count(
                                "THERAPY_RESPONSE", participant_count
                            ),
                            "therapy_response_mpc_median_ms": measured_cases[
                                "THERAPY_RESPONSE"
                            ]["mpc"]["median_ms"],
                        }
                    )
                    if participant_count == max(args.participant_counts):
                        correctness = detailed_correctness
        finally:
            for session in sessions:
                session.close()
            for engine in engines:
                engine.dispose()

    if len(comparison) != len(ANALYSES):
        raise RuntimeError("analysis-size must be one of the requested sizes")
    if len(participant_scaling) != len(args.participant_counts):
        raise RuntimeError("participant-size must be one of the requested sizes")
    if not all(row["verified"] for row in correctness) or not all(
        row["verified_analyses"] == len(ANALYSES)
        for row in participant_correctness
    ):
        raise RuntimeError("BGW correctness comparison failed")

    return {
        "metadata": metadata,
        "analysis_records_per_database": args.analysis_size,
        "analysis_participant_count": DATASET_SCALING_PARTICIPANTS,
        "participant_records_per_database": args.participant_size,
        "correctness": correctness,
        "size_scaling": scaling,
        "analysis_comparison": comparison,
        "participant_scaling": participant_scaling,
        "participant_correctness": participant_correctness,
        "raw_cases": raw_cases,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run reproducible local-data and BGW experiments."
    )
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=[1_000, 5_000, 10_000, 25_000],
        help="patient records in each local database",
    )
    parser.add_argument(
        "--analysis-size",
        type=int,
        default=1_000,
        help="one of --sizes used to compare all six analyses",
    )
    parser.add_argument(
        "--participant-counts",
        type=int,
        nargs="+",
        default=DEFAULT_PARTICIPANT_COUNTS,
        help="BGW participant configurations to compare (supported range: 3..6)",
    )
    parser.add_argument(
        "--participant-size",
        type=int,
        default=1_000,
        help="one of --sizes used to compare participant counts",
    )
    parser.add_argument("--repetitions", type=int, default=9)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument(
        "--mpc-iterations",
        type=int,
        default=100,
        help="independent BGW runs averaged into each sub-millisecond timing sample",
    )
    parser.add_argument("--seed", type=int, default=20260911)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "results",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="keep generated SQLite databases here; default uses a temporary directory",
    )
    args = parser.parse_args()
    if any(size <= 0 for size in args.sizes):
        parser.error("all sizes must be positive")
    if len(set(args.sizes)) != len(args.sizes):
        parser.error("sizes must be unique")
    args.sizes = sorted(args.sizes)
    if args.analysis_size not in args.sizes:
        parser.error("analysis-size must be included in sizes")
    if args.participant_size not in args.sizes:
        parser.error("participant-size must be included in sizes")
    if len(set(args.participant_counts)) != len(args.participant_counts):
        parser.error("participant-counts must be unique")
    args.participant_counts = sorted(args.participant_counts)
    if any(count < 3 or count > 6 for count in args.participant_counts):
        parser.error("participant-counts must be between 3 and 6")
    if args.repetitions < 1 or args.warmups < 0 or args.mpc_iterations < 1:
        parser.error(
            "repetitions and mpc-iterations must be >= 1; warmups must be >= 0"
        )
    return args


def main() -> int:
    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with ExitStack() as stack:
        if args.work_dir:
            work_dir = args.work_dir.resolve()
            work_dir.mkdir(parents=True, exist_ok=True)
        else:
            work_dir = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="smr-benchmark-")))
        results = asyncio.run(_run_all(args, work_dir))

    json_path = args.output_dir / "benchmark_results.json"
    json_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_csv(
        args.output_dir / "correctness.csv",
        [
            "analysis",
            "label",
            "result_field",
            "unit",
            "reference_value",
            "bgw_value",
            "absolute_difference",
            "verified",
        ],
        results["correctness"],
    )
    _write_csv(
        args.output_dir / "size_scaling.csv",
        [
            "records_per_database",
            "local_median_ms",
            "mpc_median_ms",
            "total_median_ms",
        ],
        results["size_scaling"],
    )
    _write_csv(
        args.output_dir / "analysis_comparison.csv",
        [
            "analysis",
            "label",
            "operations",
            "secure_multiplications",
            "protocol_messages",
            "local_median_ms",
            "mpc_median_ms",
            "total_median_ms",
        ],
        results["analysis_comparison"],
    )
    _write_csv(
        args.output_dir / "participant_scaling.csv",
        [
            "participant_count",
            "threshold",
            "records_per_database",
            "variant_frequency_messages",
            "variant_frequency_mpc_median_ms",
            "therapy_response_messages",
            "therapy_response_mpc_median_ms",
        ],
        results["participant_scaling"],
    )
    _write_csv(
        args.output_dir / "participant_correctness.csv",
        [
            "participant_count",
            "threshold",
            "verified_analyses",
            "total_analyses",
            "max_absolute_difference",
        ],
        results["participant_correctness"],
    )
    verified_total = sum(
        row["verified_analyses"] for row in results["participant_correctness"]
    )
    expected_total = sum(
        row["total_analyses"] for row in results["participant_correctness"]
    )
    print(f"\nCorrectness: {verified_total}/{expected_total}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
