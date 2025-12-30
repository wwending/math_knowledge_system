from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger

from app.services.nlp_engine import nlp_service

# 导入我们写的路由
from app.api.endpoints import router as api_router
# 导入 OCR 服务实例
from app.services.ocr_engine import ocr_service

# --- 生命周期 (Lifespan) ---
# FastAPI 推荐的新写法，替代旧版的 on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 启动前：加载 AI 模型
    logger.info("🔥 系统正在启动，正在预加载 AI 模型...")
    try:
        ocr_service.initialize() # 这一步会把模型加载到 RTX 2060
        logger.success("✅ 模型加载完毕，服务就绪！")
    except Exception as e:
        logger.error(f"❌ 模型加载失败: {e}")
    
    yield # 服务运行中...
    
    # 2. 关闭后：清理资源 (可选)
    logger.info("👋 系统正在关闭...")

# --- App 实例化 ---
app = FastAPI(
    title="Math Knowledge OCR API",
    version="1.0.0",
    lifespan=lifespan 
)

# --- 跨域配置 (CORS) ---
# 允许前端 (Vue/React) 本地开发时的 8080/3000 端口访问这里
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 注册路由 ---
# 所有的 API 都会加上 /api/v1 前缀
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "Math OCR Backend is Running!", "docs_url": "http://localhost:8000/docs"}

if __name__ == "__main__":
    import uvicorn
    # 启动服务器
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)