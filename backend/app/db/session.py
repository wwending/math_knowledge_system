from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


sqlite_connect_args = {}
if settings.DATABASE_URL_RESOLVED.startswith("sqlite"):
    sqlite_connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL_RESOLVED,
    connect_args=sqlite_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
