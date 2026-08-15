from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..dependencies import get_db, get_runtime
from ..schemas import (
    ActionResponse,
    AnalysisRequest,
    ResultShare,
    ResultSharesResponse,
    SessionActionRequest,
)
from ..security import verify_service_token
from ..services import (
    build_therapy_response,
    build_sum_analysis,
    build_variant_frequency,
    finalize_therapy_multiplications,
    share_therapy_response_inputs,
    share_association_inputs,
    share_sum_inputs,
    share_variant_frequency_inputs,
    start_therapy_multiplications,
)

router = APIRouter(
    prefix="/api/analyses",
    tags=["analyses"],
    dependencies=[Depends(verify_service_token)],
)


@router.post("/secure-sum/{analysis_type}/share-local-inputs", response_model=ActionResponse)
async def sum_share_local_inputs(analysis_type: str, payload: AnalysisRequest, runtime=Depends(get_runtime), db: Session = Depends(get_db)):
    try:
        names = await share_sum_inputs(runtime=runtime, db=db, session_id=payload.session_id,
                                       criteria=payload.criteria, analysis_type=analysis_type)
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ActionResponse(session_id=payload.session_id, status="shared",
                          detail="Local aggregates were secret-shared", shared_value_names=names)


@router.post("/secure-sum/{analysis_type}/build", response_model=ActionResponse)
def sum_build(analysis_type: str, payload: SessionActionRequest, runtime=Depends(get_runtime)):
    try:
        build_sum_analysis(runtime, payload.session_id, analysis_type)
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ActionResponse(session_id=payload.session_id, status="computed", detail="Global totals remain shared")


@router.get("/secure-sum/{analysis_type}/{session_id}/result-share", response_model=ResultSharesResponse)
def sum_result_share(analysis_type: str, session_id: str, runtime=Depends(get_runtime)):
    from ..services import SUM_ANALYSES
    if analysis_type not in SUM_ANALYSES:
        raise HTTPException(status_code=404, detail="unsupported secure-sum analysis")
    _, metric, denominator = SUM_ANALYSES[analysis_type]
    return _shares_response(runtime, session_id, [metric, denominator])


@router.post("/association/{analysis_type}/share-local-inputs", response_model=ActionResponse)
async def association_share(analysis_type: str, payload: AnalysisRequest, runtime=Depends(get_runtime), db: Session = Depends(get_db)):
    if analysis_type not in ("THERAPY_RESPONSE", "VARIANT_DISEASE_ASSOCIATION"):
        raise HTTPException(status_code=404, detail="unsupported association analysis")
    try:
        names = await share_association_inputs(runtime=runtime, db=db, session_id=payload.session_id,
                                                criteria=payload.criteria, analysis_type=analysis_type)
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ActionResponse(session_id=payload.session_id, status="shared", detail="Local 2x2 cells were secret-shared", shared_value_names=names)


def _shares_response(runtime, session_id: str, names: list[str]) -> ResultSharesResponse:
    try:
        participant = runtime.store.get(session_id)
        shares = [participant.get_share(name) for name in names]
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ResultSharesResponse(
        session_id=session_id,
        participant_id=participant.participant_id,
        shares=[ResultShare(name=name, x=share.x, value=str(share.y)) for name, share in zip(names, shares)],
    )


@router.post("/variant-frequency/share-local-inputs", response_model=ActionResponse)
async def variant_share_local_inputs(
    payload: AnalysisRequest,
    runtime=Depends(get_runtime),
    db: Session = Depends(get_db),
):
    try:
        names = await share_variant_frequency_inputs(
            runtime=runtime,
            db=db,
            session_id=payload.session_id,
            criteria=payload.criteria,
        )
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ActionResponse(
        session_id=payload.session_id,
        status="shared",
        detail="Local cohort aggregates were secret-shared; plaintext counts were not persisted",
        shared_value_names=names,
    )


@router.post("/variant-frequency/build", response_model=ActionResponse)
def variant_build(payload: SessionActionRequest, runtime=Depends(get_runtime)):
    try:
        build_variant_frequency(runtime, payload.session_id)
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ActionResponse(
        session_id=payload.session_id,
        status="computed",
        detail="Global variant and cohort totals are available only as local BGW shares",
    )


@router.get("/variant-frequency/{session_id}/result-share", response_model=ResultSharesResponse)
def variant_result_share(session_id: str, runtime=Depends(get_runtime)):
    return _shares_response(runtime, session_id, ["variant_total", "cohort_total"])


@router.post("/therapy-response/share-local-inputs", response_model=ActionResponse)
async def therapy_share_local_inputs(
    payload: AnalysisRequest,
    runtime=Depends(get_runtime),
    db: Session = Depends(get_db),
):
    try:
        names = await share_therapy_response_inputs(
            runtime=runtime,
            db=db,
            session_id=payload.session_id,
            criteria=payload.criteria,
        )
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ActionResponse(
        session_id=payload.session_id,
        status="shared",
        detail="Local 2x2 therapy-response aggregates were secret-shared",
        shared_value_names=names,
    )


@router.post("/therapy-response/build", response_model=ActionResponse)
def therapy_build(payload: SessionActionRequest, runtime=Depends(get_runtime)):
    try:
        build_therapy_response(runtime, payload.session_id)
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ActionResponse(
        session_id=payload.session_id,
        status="computed",
        detail="A, B, C and D are available only as local BGW shares",
    )


@router.post("/therapy-response/start-multiplication", response_model=ActionResponse)
async def therapy_start_multiplication(
    payload: SessionActionRequest, runtime=Depends(get_runtime)
):
    try:
        await start_therapy_multiplications(runtime, payload.session_id)
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ActionResponse(
        session_id=payload.session_id,
        status="started",
        detail="BGW multiplication/degree-reduction rounds for AD and BC were started",
    )


@router.post("/therapy-response/finalize-multiplication", response_model=ActionResponse)
def therapy_finalize_multiplication(
    payload: SessionActionRequest, runtime=Depends(get_runtime)
):
    try:
        finalize_therapy_multiplications(runtime, payload.session_id)
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ActionResponse(
        session_id=payload.session_id,
        status="computed",
        detail="AD and BC are available as degree-reduced BGW shares",
    )


@router.get("/therapy-response/{session_id}/result-share", response_model=ResultSharesResponse)
def therapy_result_share(session_id: str, runtime=Depends(get_runtime)):
    return _shares_response(runtime, session_id, ["AD", "BC", "therapy_cohort_total"])
