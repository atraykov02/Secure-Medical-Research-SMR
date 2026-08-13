from __future__ import annotations

import secrets
import jwt

from fastapi import Header, HTTPException, Request, status


def verify_service_token(
    request: Request,
    x_mpc_service_token: str | None = Header(default=None),
) -> None:
    expected = request.app.state.settings.service_token
    if not x_mpc_service_token or not secrets.compare_digest(x_mpc_service_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid MPC service token",
        )


def verify_local_admin(request: Request, authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="hospital access token required")
    settings = request.app.state.settings
    try:
        claims = jwt.decode(
            authorization[7:],
            settings.local_access_secret,
            algorithms=[settings.local_access_algorithm],
            audience="hospital-local-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid hospital access token") from exc
    if (
        claims.get("type") != "hospital_local_access"
        or claims.get("role") != "ORG_ADMIN"
        or claims.get("participant_id") != settings.participant_id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="token does not belong to this hospital")
    return claims
