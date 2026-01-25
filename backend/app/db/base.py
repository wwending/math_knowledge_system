from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Ensure model modules are imported so metadata is populated for create_all.
import app.models  # noqa: F401