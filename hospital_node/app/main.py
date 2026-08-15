from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 - registers SQLAlchemy metadata
from .config import HospitalSettings, get_settings
from .db import Base, create_database_engine, create_session_factory
from .routers.analyses import router as analyses_router
from .routers.health import router as health_router
from .routers.mpc import router as mpc_router
from .routers.local_data import router as local_data_router
from .routers.verification import router as verification_router
from .runtime import NodeRuntime
from .seed import seed_synthetic_data


def create_app(settings: HospitalSettings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.auto_create_schema:
            Base.metadata.create_all(engine)
        if settings.auto_seed:
            with session_factory() as db:
                seed_synthetic_data(
                    db,
                    count=settings.synthetic_patient_count,
                    seed=settings.synthetic_seed,
                    node_id=settings.participant_id,
                )
        yield
        # Session shares are ephemeral; clear them on process shutdown.
        for session_id in list(app.state.runtime.store.sessions):
            app.state.runtime.destroy_session(session_id)
        engine.dispose()

    app = FastAPI(
        title=f"PrecisionMPC Hospital Node - {settings.organization_name}",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.runtime = NodeRuntime(settings=settings)

    app.include_router(health_router)
    app.include_router(mpc_router)
    app.include_router(analyses_router)
    app.include_router(local_data_router)
    app.include_router(verification_router)
    return app
