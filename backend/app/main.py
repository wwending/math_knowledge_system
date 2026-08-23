from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.db.base import Base
from app.db.question_contract import ensure_legacy_question_columns
from app.models import auth_audit_log, auth_session, login_rate_limit, question, user  # noqa: F401


def create_app() -> FastAPI:
    settings.validate_security_settings()
    settings.validate_runtime_schema_settings()
    settings.validate_upload_dir_isolation()
    app = FastAPI(title=settings.PROJECT_NAME)
    settings.ensure_runtime_dirs()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS_LIST,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount(
        settings.STATIC_URL_PREFIX_NORMALIZED,
        StaticFiles(directory=str(settings.STATIC_DIR_PATH)),
        name="static",
    )

    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)

    if settings.AUTO_APPLY_LEGACY_QUESTION_COMPAT:
        ensure_legacy_question_columns(engine)

    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/")
    def root():
        return {"message": "Math Knowledge System API is running!"}

    return app


app = create_app()
