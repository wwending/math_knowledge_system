from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router

# 👇 1. 引入数据库基础配置
from app.db.base import Base
from app.db.session import engine, SessionLocal

# 👇👇👇 2. 关键！必须在这里显式导入模型，否则建表时会报错找不到表 👇👇👇
from app.models.user import User       # <--- 必须导入这个！
from app.models.question import Question # <--- 还有这个！

# 3. 创建数据库表 (因为上面导入了 User，这里就不会报找不到 users 表了)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Math Knowledge System")

# 4. 配置跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. 挂载静态文件 (图片上传目录)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 6. 注册路由
app.include_router(api_router, prefix="/api/v1")

# 7. 启动时自动检查管理员
@app.on_event("startup")
def init_data():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            print("⚠️ 检测到管理员缺失，正在自动创建...")
            try:
                from passlib.context import CryptContext
                pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
                hashed_pw = pwd_context.hash("123456")
            except:
                hashed_pw = "123456"

            new_user = User(
                id=1, 
                username="admin",
                email="admin@example.com",
                hashed_password=hashed_pw,
                is_active=True,
                role="admin"
            )
            db.add(new_user)
            db.commit()
            print("✅ 管理员 (ID:1) 已自动恢复！")
    except Exception as e:
        print(f"❌ 初始化数据失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)