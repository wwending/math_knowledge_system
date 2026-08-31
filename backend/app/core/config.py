from __future__ import annotations

import json
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


CONFIG_DIR = Path(__file__).resolve().parent
APP_DIR = CONFIG_DIR.parent
BACKEND_DIR = APP_DIR.parent
REPO_ROOT_DIR = BACKEND_DIR.parent
ENV_FILE_PATH = BACKEND_DIR / ".env"
DEFAULT_DEV_CORS_ALLOW_ORIGINS = (
    '["http://localhost:5173","http://127.0.0.1:5173",'
    '"http://localhost:4173","http://127.0.0.1:4173",'
    '"http://localhost:3000","http://127.0.0.1:3000"]'
)
ALLOWED_COOKIE_SAMESITE_VALUES = {"lax", "strict", "none"}
ALLOWED_SECURE_TRANSPORT_MODES = {"direct_https", "trusted_proxy_tls", "insecure_http"}
ALLOWED_LOG_LEVELS = {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}


def _resolve_path(value: str | Path, *, base_dir: Path) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    return candidate.resolve()


def _resolve_sqlite_url(url: str, *, base_dir: Path) -> str:
    if ":///" not in url:
        return url

    scheme, db_path = url.split(":///", 1)
    if not scheme.startswith("sqlite") or db_path == ":memory:":
        return url

    raw_path, has_query, query = db_path.partition("?")
    resolved_path = _resolve_path(raw_path, base_dir=base_dir).as_posix()
    suffix = f"?{query}" if has_query else ""
    return f"{scheme}:///{resolved_path}{suffix}"


def _normalize_url_prefix(value: str) -> str:
    prefix = value.strip() or "/"
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    if len(prefix) > 1:
        prefix = prefix.rstrip("/")
    return prefix


def _parse_cors_origins(value: str) -> list[str]:
    raw_value = value.strip()
    if not raw_value:
        return []
    if raw_value == "*":
        return ["*"]
    if raw_value.startswith("["):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in raw_value.split(",") if item.strip()]


class Settings(BaseSettings):
    PROJECT_NAME: str = "Math Knowledge System"
    API_V1_STR: str = "/api/v1"
    APP_ENV: str = "development"

    STATIC_URL_PREFIX: str = "/static"
    STATIC_DIR: str = "static"
    # Uploads must live outside the publicly mounted static dir (#44): question images
    # are served only through the authenticated /questions/{id}/image endpoint.
    UPLOAD_DIR: str = "uploads"
    # Legacy upload_pdf page renders also stay off the public /static mount (#103):
    # production already points PDF_TEMP_DIR at /data/pdf_temp; nothing serves these
    # files publicly anymore.
    PDF_TEMP_DIR: str = "pdf_temp"

    DATABASE_URL: str = "sqlite:///./math_knowledge.db"
    CORS_ALLOW_ORIGINS: str = DEFAULT_DEV_CORS_ALLOW_ORIGINS

    SECRET_KEY: str = "CHANGE_THIS_TO_A_SECURE_RANDOM_KEY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    REFRESH_TOKEN_COOKIE_PATH: str = "/"
    REFRESH_TOKEN_COOKIE_SECURE: bool = False
    REFRESH_TOKEN_COOKIE_SAMESITE: str = "lax"
    AUTH_STRICT_SECURITY: bool = False
    SECURE_TRANSPORT_MODE: str = "insecure_http"
    ALLOW_CROSS_SITE_REFRESH_COOKIE: bool = False
    ALLOW_RUNTIME_SCHEMA_MUTATIONS: bool = False
    AUTO_CREATE_TABLES: bool = False
    AUTO_APPLY_LEGACY_QUESTION_COMPAT: bool = False
    PUBLIC_SIGNUP_ENABLED: bool = True
    SMS_CODE_LOGIN_ENABLED: bool = False
    SMS_PASSWORD_RECOVERY_ENABLED: bool = False
    PASSWORD_RECOVERY_MODE: str = "admin_contact"
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 900
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_BLOCK_SECONDS: int = 1800

    BAIDU_API_KEY: str = ""
    BAIDU_SECRET_KEY: str = ""
    OCR_PROVIDER: str = "baidu"
    OCR_FALLBACK_PROVIDER: str = ""
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_TIMEOUT_SECONDS: int = 30
    DEEPSEEK_METADATA_TIMEOUT_SECONDS: int = 45
    PDF_SERVICE_URL: str = "http://gotenberg:3000"
    PDF_SERVICE_CONNECT_TIMEOUT_SECONDS: float = 5
    PDF_SERVICE_READ_TIMEOUT_SECONDS: float = 60

    # Layout analysis (#58): figure-region detection on question crops. Failure,
    # timeout, or a missing model must degrade to the pre-#58 no-figure flow.
    LAYOUT_ENABLED: bool = True
    LAYOUT_MODEL_TYPE: str = "doclayout_docstructbench"
    LAYOUT_MODEL_DIR: str = "weights"
    LAYOUT_MODEL_PATH: str = ""
    LAYOUT_TIMEOUT_SECONDS: float = 15
    LAYOUT_CONF_THRESHOLD: float = 0.4
    LAYOUT_MIN_AREA_RATIO: float = 0.01
    LAYOUT_FIGURE_LABELS: str = "figure"

    # Schema-v2 current-document cumulative figure budget (#128).
    QUESTION_MAX_TOTAL_FIGURE_BYTES: int = 24 * 1024 * 1024

    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    GIT_SHA: str = "unknown"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def BASE_DIR(self) -> Path:
        return BACKEND_DIR

    @property
    def REPO_ROOT(self) -> Path:
        return REPO_ROOT_DIR

    @property
    def STATIC_URL_PREFIX_NORMALIZED(self) -> str:
        return _normalize_url_prefix(self.STATIC_URL_PREFIX)

    @property
    def STATIC_DIR_PATH(self) -> Path:
        return _resolve_path(self.STATIC_DIR, base_dir=self.BASE_DIR)

    @property
    def UPLOAD_DIR_PATH(self) -> Path:
        return _resolve_path(self.UPLOAD_DIR, base_dir=self.BASE_DIR)

    @property
    def PDF_TEMP_DIR_PATH(self) -> Path:
        return _resolve_path(self.PDF_TEMP_DIR, base_dir=self.BASE_DIR)

    @property
    def LOG_DIR_PATH(self) -> Path:
        return _resolve_path(self.LOG_DIR, base_dir=self.BASE_DIR)

    @property
    def LAYOUT_MODEL_DIR_PATH(self) -> Path:
        return _resolve_path(self.LAYOUT_MODEL_DIR, base_dir=self.BASE_DIR)

    @property
    def LAYOUT_FIGURE_LABELS_SET(self) -> set[str]:
        return {label.strip().lower() for label in self.LAYOUT_FIGURE_LABELS.split(",") if label.strip()}

    @property
    def DATABASE_URL_RESOLVED(self) -> str:
        return _resolve_sqlite_url(self.DATABASE_URL, base_dir=self.BASE_DIR)

    @property
    def CORS_ALLOW_ORIGINS_LIST(self) -> list[str]:
        return _parse_cors_origins(self.CORS_ALLOW_ORIGINS)

    @property
    def APP_ENV_NORMALIZED(self) -> str:
        return self.APP_ENV.strip().lower()

    @property
    def LOG_LEVEL_NORMALIZED(self) -> str:
        candidate = self.LOG_LEVEL.strip().upper()
        return candidate if candidate in ALLOWED_LOG_LEVELS else "INFO"

    @property
    def IS_PRODUCTION(self) -> bool:
        return self.APP_ENV_NORMALIZED in {"prod", "production"}

    @property
    def AUTH_STRICT_SECURITY_ENABLED(self) -> bool:
        return self.IS_PRODUCTION or self.AUTH_STRICT_SECURITY

    @property
    def RUNTIME_SCHEMA_MUTATIONS_REQUESTED(self) -> bool:
        return self.AUTO_CREATE_TABLES or self.AUTO_APPLY_LEGACY_QUESTION_COMPAT

    @property
    def REFRESH_TOKEN_COOKIE_NAME_NORMALIZED(self) -> str:
        return self.REFRESH_TOKEN_COOKIE_NAME.strip()

    @property
    def REFRESH_TOKEN_COOKIE_PATH_NORMALIZED(self) -> str:
        return self.REFRESH_TOKEN_COOKIE_PATH.strip()

    @property
    def REFRESH_TOKEN_COOKIE_SAMESITE_NORMALIZED(self) -> str:
        return self.REFRESH_TOKEN_COOKIE_SAMESITE.strip().lower()

    @property
    def SECURE_TRANSPORT_MODE_NORMALIZED(self) -> str:
        return self.SECURE_TRANSPORT_MODE.strip().lower()

    def validate_refresh_cookie_settings(self) -> None:
        if not self.REFRESH_TOKEN_COOKIE_NAME_NORMALIZED:
            raise RuntimeError("REFRESH_TOKEN_COOKIE_NAME cannot be empty")

        if not self.REFRESH_TOKEN_COOKIE_PATH_NORMALIZED:
            raise RuntimeError("REFRESH_TOKEN_COOKIE_PATH cannot be empty")

        if not self.REFRESH_TOKEN_COOKIE_PATH_NORMALIZED.startswith("/"):
            raise RuntimeError("REFRESH_TOKEN_COOKIE_PATH must start with '/'")

        if self.REFRESH_TOKEN_COOKIE_SAMESITE_NORMALIZED not in ALLOWED_COOKIE_SAMESITE_VALUES:
            raise RuntimeError("REFRESH_TOKEN_COOKIE_SAMESITE must be one of: lax, strict, none")

        if self.SECURE_TRANSPORT_MODE_NORMALIZED not in ALLOWED_SECURE_TRANSPORT_MODES:
            raise RuntimeError(
                "SECURE_TRANSPORT_MODE must be one of: direct_https, trusted_proxy_tls, insecure_http"
            )

        if not self.AUTH_STRICT_SECURITY_ENABLED:
            return

        if not self.REFRESH_TOKEN_COOKIE_SECURE:
            raise RuntimeError("REFRESH_TOKEN_COOKIE_SECURE must be true when strict auth security is enabled")

        if self.SECURE_TRANSPORT_MODE_NORMALIZED == "insecure_http":
            raise RuntimeError(
                "SECURE_TRANSPORT_MODE cannot be insecure_http when strict auth security is enabled"
            )

        if (
            self.REFRESH_TOKEN_COOKIE_SAMESITE_NORMALIZED == "none"
            and not self.ALLOW_CROSS_SITE_REFRESH_COOKIE
        ):
            raise RuntimeError(
                "REFRESH_TOKEN_COOKIE_SAMESITE cannot be 'none' unless "
                "ALLOW_CROSS_SITE_REFRESH_COOKIE=true when strict auth security is enabled"
            )

    def validate_security_settings(self) -> None:
        self.validate_refresh_cookie_settings()

        if not self.AUTH_STRICT_SECURITY_ENABLED:
            return

        if self.SECRET_KEY == "CHANGE_THIS_TO_A_SECURE_RANDOM_KEY":
            raise RuntimeError("SECRET_KEY must be overridden when strict auth security is enabled")

        if len(self.SECRET_KEY.strip()) < 32:
            raise RuntimeError("SECRET_KEY must be at least 32 characters when strict auth security is enabled")

        if "*" in self.CORS_ALLOW_ORIGINS_LIST:
            raise RuntimeError("CORS_ALLOW_ORIGINS cannot be '*' when strict auth security is enabled")

    def validate_runtime_schema_settings(self) -> None:
        if not self.RUNTIME_SCHEMA_MUTATIONS_REQUESTED:
            return

        if self.IS_PRODUCTION:
            raise RuntimeError(
                "Runtime schema mutations are forbidden in production; run Alembic migrations before startup"
            )

        if not self.ALLOW_RUNTIME_SCHEMA_MUTATIONS:
            raise RuntimeError(
                "Runtime schema mutations require ALLOW_RUNTIME_SCHEMA_MUTATIONS=true outside production"
            )

    def validate_upload_dir_isolation(self) -> None:
        # Fail closed on misconfiguration: an uploads directory inside the mounted
        # static tree would re-expose question image bytes without authentication.
        upload_dir = self.UPLOAD_DIR_PATH
        static_dir = self.STATIC_DIR_PATH
        if upload_dir == static_dir or static_dir in upload_dir.parents:
            raise RuntimeError(
                "UPLOAD_DIR must live outside STATIC_DIR so uploads stay off the public "
                f"/static mount (got UPLOAD_DIR={self.UPLOAD_DIR!r}, STATIC_DIR={self.STATIC_DIR!r}). "
                "Move existing upload files out of the static dir once and update UPLOAD_DIR."
            )

    def validate_pdf_temp_dir_isolation(self) -> None:
        # Fail closed like uploads (#44): a pdf_temp inside the mounted static tree
        # would re-expose legacy PDF page renders without authentication (#103).
        pdf_temp_dir = self.PDF_TEMP_DIR_PATH
        static_dir = self.STATIC_DIR_PATH
        if pdf_temp_dir == static_dir or static_dir in pdf_temp_dir.parents:
            raise RuntimeError(
                "PDF_TEMP_DIR must live outside STATIC_DIR so legacy PDF renders stay off "
                f"the public /static mount (got PDF_TEMP_DIR={self.PDF_TEMP_DIR!r}, "
                f"STATIC_DIR={self.STATIC_DIR!r}). Move existing pdf_temp files out of the "
                "static dir once and update PDF_TEMP_DIR."
            )

    def ensure_runtime_dirs(self) -> None:
        for path in (self.STATIC_DIR_PATH, self.UPLOAD_DIR_PATH, self.PDF_TEMP_DIR_PATH, self.LAYOUT_MODEL_DIR_PATH):
            path.mkdir(parents=True, exist_ok=True)
        try:
            self.LAYOUT_MODEL_DIR_PATH.mkdir(parents=True, exist_ok=True)
        except OSError:
            # #58: an unwritable model dir (e.g. default weights/ inside the
            # read-only container image) must not take the whole backend down;
            # layout detection degrades to the no-figure flow instead.
            pass


settings = Settings()
settings.ensure_runtime_dirs()
