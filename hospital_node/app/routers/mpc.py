from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from bgw.models import MPCMessage

from ..dependencies import get_runtime
from ..schemas import ActionResponse, MPCSessionCreate, NodeStatus, SessionStatus
from ..security import verify_service_token

router = APIRouter(
    prefix="/api/mpc",
    tags=["mpc"],
    dependencies=[Depends(verify_service_token)],
)


@router.get("/node-info", response_model=NodeStatus)
def node_info(request: Request):
    settings = request.app.state.settings
    return NodeStatus(
        participant_id=settings.participant_id,
        organization_name=settings.organization_name,
        status="ok",
    )


@router.post("/sessions", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
def create_session(payload: MPCSessionCreate, runtime=Depends(get_runtime)):
    try:
        runtime.create_session(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ActionResponse(
        session_id=payload.session_id,
        status="created",
        detail="MPC session created in ephemeral memory",
    )


@router.get("/sessions/{session_id}", response_model=SessionStatus)
def session_status(session_id: str, runtime=Depends(get_runtime)):
    try:
        participant = runtime.store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionStatus(
        session_id=session_id,
        participant_id=participant.participant_id,
        threshold=participant.threshold,
        participant_ids=participant.participant_ids,
        available_value_names=sorted(participant.values),
    )


@router.get("/sessions/{session_id}/demonstration-trace")
def demonstration_trace(session_id: str, runtime=Depends(get_runtime)):
    try:
        participant = runtime.store.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not participant.trace_enabled:
        raise HTTPException(status_code=403, detail="trace is disabled for secure sessions")
    return {"session_id": session_id, "participant_id": participant.participant_id,
            "prime": str(participant.prime), "threshold": participant.threshold, "events": participant.trace}


@router.delete("/sessions/{session_id}", response_model=ActionResponse)
def destroy_session(session_id: str, runtime=Depends(get_runtime)):
    runtime.destroy_session(session_id)
    return ActionResponse(
        session_id=session_id,
        status="destroyed",
        detail="MPC session state and shares were removed from application memory",
    )


@router.post("/messages", response_model=ActionResponse)
async def receive_message(request: Request, runtime=Depends(get_runtime)):
    payload = await request.json()
    try:
        message = MPCMessage.from_payload(payload)
        participant = runtime.store.get(message.session_id)
        await participant.handle_message(message)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ActionResponse(
        session_id=message.session_id,
        status="accepted",
        detail=f"{message.message_type.value} accepted",
    )
