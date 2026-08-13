from __future__ import annotations

from fastapi import Request


def get_runtime(request: Request):
    return request.app.state.runtime


def get_db(request: Request):
    session_factory = request.app.state.session_factory
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
