# Import model modules so SQLAlchemy metadata is populated.
from app.models import auth_audit_log  # noqa: F401
from app.models import auth_session  # noqa: F401
from app.models import user  # noqa: F401
from app.models import login_rate_limit  # noqa: F401
from app.models import question  # noqa: F401
from app.models import source_asset  # noqa: F401
from app.models import draft  # noqa: F401
from app.models import draft_event  # noqa: F401
from app.models import ocr_run  # noqa: F401
from app.models import llm_run  # noqa: F401
from app.models import question_revision  # noqa: F401
from app.models import paper  # noqa: F401
from app.models import feedback  # noqa: F401
