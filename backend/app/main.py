import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.db.base import Base

# 重要：确保模型被导入，create_all 才知道有哪些表
from app.models import user, question  # noqa: F401

from app.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(title=settings.PROJECT_NAME)

    # -----------------------------
    # 0) 目录保障（部署环境经常缺目录）
    # -----------------------------
    os.makedirs("static", exist_ok=True)
    os.makedirs(getattr(settings, "UPLOAD_DIR", "static/uploads"), exist_ok=True)

    # -----------------------------
    # 1) CORS（开发先放开；正式版务必收紧）
    # -----------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: 生产环境改成你的前端域名列表
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -----------------------------
    # 2) 静态文件（你的 endpoints 会返回 image_url）
    # -----------------------------
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # -----------------------------
    # 3) 数据库建表（正式版换 Alembic；先保留但加开关）
    # -----------------------------
    # 默认开发环境 True；生产环境可在 settings 里加 AUTO_CREATE_TABLES=False
    if getattr(settings, "AUTO_CREATE_TABLES", True):
        Base.metadata.create_all(bind=engine)

    # -----------------------------
    # 4) 路由
    # -----------------------------
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # -----------------------------
    # 5) 健康检查 / 根路由
    # -----------------------------
    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/")
    def root():
        return {"message": "Math Knowledge System API is running!"}

    return app


app = create_app()
