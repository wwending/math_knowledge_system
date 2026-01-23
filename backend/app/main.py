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

    # CORS：正式版后续要收紧；先保证开发可用
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 静态文件（你的 endpoints 会返回 image_url）
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # 数据库建表（正式版会换成 Alembic；先保持 MVP 可跑）
    Base.metadata.create_all(bind=engine)

    # 路由
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/")
    def root():
        return {"message": "Math Knowledge System API is running!"}

    return app


app = create_app()
