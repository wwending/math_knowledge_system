from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# 1. 创建数据库引擎
# check_same_thread=False 是 SQLite 必须的配置
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# 2. 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. 获取数据库会话的依赖函数 (给 FastAPI 用的)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()