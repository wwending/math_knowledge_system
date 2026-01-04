import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware  # <--- 1. 导入这个
from loguru import logger

from app.api.endpoints import router as api_router
from app.services.ocr_engine import ocr_service
from app.services.nlp_engine import nlp_service
from app.core.database import engine, Base
from app.models import question 

from app.api.auth import router as auth_router # <--- 引入

# 自动创建表结构
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🔥 系统正在启动，正在预加载 AI 模型...")
    try:
        ocr_service.initialize() 
        nlp_service.initialize() 
        logger.success("✅ 所有 AI 模型加载完毕！")
    except Exception as e:
        logger.error(f"❌ 模型加载失败: {e}")
    yield
    logger.info("👋 系统正在关闭...")

app = FastAPI(
    title="Math OCR API",
    version="1.0",
    lifespan=lifespan
)

# -----------------------------------------------------------
# ⚡️ 核心修复：配置 CORS (跨域资源共享)
# -----------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    # 允许的来源列表。为了方便开发，我们允许所有 ("*")
    # 生产环境建议改为 ["http://localhost:5173"]
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法 (GET, POST...)
    allow_headers=["*"],  # 允许所有 Header
)
# -----------------------------------------------------------

# 挂载静态文件 (图片)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 注册路由
app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


app.include_router(api_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1/auth") # <--- 注册 /register 和 /token