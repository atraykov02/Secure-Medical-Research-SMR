from fastapi import APIRouter, Request

from ..schemas import NodeStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=NodeStatus)
def health(request: Request):
    settings = request.app.state.settings
    return NodeStatus(
        participant_id=settings.participant_id,
        organization_name=settings.organization_name,
        status="ok",
    )
