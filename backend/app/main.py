import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 1. 导入数据库引擎 (Engine) 和 Session
# 假设你的 engine 和 SessionLocal 还在 core.database 里
from app.core.database import engine, SessionLocal
from app.core.security import get_password_hash

# 2. 🔥🔥🔥 导入统一的 Base 🔥🔥🔥
from app.db.base import Base

# 3. 🔥🔥🔥 显式导入所有模型 (触发注册) 🔥🔥🔥
# 即使下面代码没直接用到 Question，也必须导入，否则 create_all 不会创建 questions 表
from app.models.user import User
from app.models.question import Question
from app.api.endpoints import router as api_router

# 4. 创建所有表
# 因为上面导入了 User 和 Question，Base 现在知道要创建这两个表了
Base.metadata.create_all(bind=engine)

app = FastAPI(title="错题本 AI", version="1.0")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent
STATIC_DIR = BACKEND_DIR / "static"
os.makedirs(STATIC_DIR / "uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 自动创建管理员
def create_admin():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            print("⚠️ 管理员缺失，正在创建...")
            admin = User(
                id=1,
                username="admin",
                hashed_password=get_password_hash("123456"),
                role="admin"
            )
            db.add(admin)
            db.commit()
            print("✅ 管理员 (ID:1) 已恢复！")
    except Exception as e:
        print(f"初始化管理员失败: {e}")
    finally:
        db.close()

create_admin()

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "Math Knowledge System API is running!"}