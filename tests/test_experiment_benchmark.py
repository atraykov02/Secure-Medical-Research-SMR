from __future__ import annotations

import asyncio

import pytest

from coordinator.app.verification.reference_analysis import compare_results
from experiments.run_benchmarks import (
    ANALYSES,
    _collect_local_inputs,
    _open_sessions,
    _run_bgw,
    _seed_database,
)


@pytest.fixture(scope="module")
def synthetic_sessions(tmp_path_factory):
    root = tmp_path_factory.mktemp("experiment-databases")
    paths = []
    for node_id in range(1, 7):
        path = root / f"hospital-{node_id}.sqlite3"
        _seed_database(path, count=50, seed=20260911, node_id=node_id)
        paths.append(path)

    engines, sessions = _open_sessions(paths)
    yield sessions
    for session in sessions:
        session.close()
    for engine in engines:
        engine.dispose()


@pytest.mark.parametrize("participant_count", [3, 4, 5, 6])
@pytest.mark.parametrize("analysis", ANALYSES)
def test_benchmark_scenario_matches_reference(
    analysis, participant_count, synthetic_sessions
):
    sessions = synthetic_sessions[:participant_count]
    local_inputs = _collect_local_inputs(analysis, sessions)
    bgw_result = asyncio.run(
        _run_bgw(
            analysis,
            local_inputs,
            run_id=1,
            participant_count=participant_count,
        )
    )
    _, differences, verified = compare_results(analysis, local_inputs, bgw_result)

    assert verified
    assert all(difference == 0 for difference in differences.values())
