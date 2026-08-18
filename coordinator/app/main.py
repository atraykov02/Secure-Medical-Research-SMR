from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models  # noqa: F401
from .config import CoordinatorSettings, get_settings
from .db import Base, create_database_engine, create_session_factory
from .orchestrator import MPCOrchestrator
from .routers.audit import router as audit_router
from .routers.auth import router as auth_router
from .routers.health import router as health_router
from .routers.organizations import router as organizations_router
from .routers.mpc_sessions import router as mpc_sessions_router
from .routers.studies import router as studies_router
from .routers.users import router as users_router
from .seed import seed_demo_data


def create_app(settings: CoordinatorSettings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.auto_create_schema:
            Base.metadata.create_all(engine)
            if engine.dialect.name == "postgresql":
                # Lightweight compatibility migration for existing demonstrator databases.
                # PostgreSQL native enum values must be added before new studies can use them.
                with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                    for value in ("ALLELE_FREQUENCY", "COHORT_MEAN_AGE", "THERAPY_RESPONSE_RATE", "VARIANT_DISEASE_ASSOCIATION"):
                        connection.execute(text(f"ALTER TYPE analysistype ADD VALUE IF NOT EXISTS '{value}'"))
                with engine.begin() as connection:
                    connection.execute(text("ALTER TABLE study_cohort_criteria ALTER COLUMN variant_code DROP NOT NULL"))
            if "study_mode" not in {c["name"] for c in inspect(engine).get_columns("studies")}:
                with engine.begin() as connection:
                    connection.execute(text("ALTER TABLE studies ADD COLUMN study_mode VARCHAR(32) NOT NULL DEFAULT 'SECURE'"))
        if settings.auto_seed:
            with session_factory() as db:
                seed_demo_data(db)
        yield
        engine.dispose()

    app = FastAPI(title="PrecisionMPC Coordinator", version="0.3.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.orchestrator = MPCOrchestrator(
        service_token=settings.mpc_service_token,
        timeout_seconds=settings.hospital_timeout_seconds,
        prime=settings.prime,
        threshold=settings.threshold,
    )
    # Synthetic protocol traces are intentionally ephemeral and never stored in the database.
    app.state.demonstration_traces = {}

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(organizations_router)
    app.include_router(users_router)
    app.include_router(studies_router)
    app.include_router(mpc_sessions_router)
    app.include_router(audit_router)
    return app
