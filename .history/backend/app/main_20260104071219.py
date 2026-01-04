from fastapi import FastAPI
from fastapi.responses import RedirectResponse  # 👈 引入跳转功能
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

# --- 内部模块 ---
from app.core.database import Base, engine
from app.api.endpoints import router as api_router

# 引擎引用
from app.services.ocr_engine import ocr_engine
from app.services.nlp_engine import nlp_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    Base.metadata.create_all(bind=engine)
    print("🔥 系统启动成功！")
    if ocr_engine: print("✅ OCR 引擎就绪")
    if nlp_engine: print("✅ NLP 引擎就绪")
    yield
    # 关闭时
    print("👋 系统关闭")

app = FastAPI(
    title="Math Knowledge System",
    description="高中数学知识库 API",
    version="1.0.0",
    lifespan=lifespan
)

# 1. 配置 CORS (允许前端访问)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 挂载静态图片目录
os.makedirs("app/static/images", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 3. 注册核心 API 路由
app.include_router(api_router, prefix="/api/v1")

# =========================================================
# 👇👇👇 关键修改：首页自动跳转到文档页 👇👇👇
# =========================================================
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    # 允许局域网访问 (0.0.0.0)
    uvicorn.run(app, host="0.0.0.0", port=8000)