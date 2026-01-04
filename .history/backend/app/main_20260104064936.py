from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# --- 内部模块 ---
from app.core.database import Base, engine
from app.api.endpoints import router as api_router

# =======================================================
# 关键修改：引用名必须是 ocr_engine 和 nlp_engine
# =======================================================
from app.services.ocr_engine import ocr_engine
from app.services.nlp_engine import nlp_engine

# 生命周期管理 (替代旧版的 on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 启动时：创建数据库表
    Base.metadata.create_all(bind=engine)
    print("🔥 系统正在启动，正在预加载 AI 模型...")
    
    # 这里不需要显式调用 initialize，因为我们在 import 时已经实例化了
    # 但可以打印一下状态确保加载成功
    if ocr_engine:
        print("✅ OCR 引擎已就绪")
    if nlp_engine:
        print("✅ NLP 引擎已就绪")
        
    yield
    # 2. 关闭时
    print("👋 系统正在关闭...")

app = FastAPI(
    title="Math Knowledge System",
    description="基于 OCR 和 LLM 的高中数学知识库系统",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS (允许前端访问)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议改为具体的 ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录 (用于访问上传的图片)
# 确保 app/static 目录存在
import os
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 注册路由
app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)