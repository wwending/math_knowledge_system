"""
兼容层：统一使用 app.db.session 的 engine / SessionLocal / get_db
后续可以把所有 import 改为 from app.db.session import get_db
再删除这个文件。
"""
from app.db.session import engine, SessionLocal, get_db
from app.db.base import Base  # noqa: F401
