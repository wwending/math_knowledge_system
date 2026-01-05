from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 使用 SQLite，文件会生成在 backend 目录下，叫 math.db
SQLALCHEMY_DATABASE_URL = "sqlite:///./math_knowledge.db"
# 如果你想用 PostgreSQL，改这里: "postgresql://user:password@localhost/dbname"

# check_same_thread=False 是 SQLite 必需的，PostgreSQL 不需要
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 依赖注入函数：用于在 API 中获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()