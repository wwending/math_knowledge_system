from __future__ import annotations

import json
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


CONFIG_DIR = Path(__file__).resolve().parent
APP_DIR = CONFIG_DIR.parent
BACKEND_DIR = APP_DIR.parent
REPO_ROOT_DIR = BACKEND_DIR.parent
ENV_FILE_PATH = BACKEND_DIR / ".env"


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

    STATIC_URL_PREFIX: str = "/static"
    STATIC_DIR: str = "static"
    UPLOAD_DIR: str = "static/uploads"
    PDF_TEMP_DIR: str = "static/pdf_temp"

    DATABASE_URL: str = "sqlite:///./math_knowledge.db"
    CORS_ALLOW_ORIGINS: str = "*"

    SECRET_KEY: str = "CHANGE_THIS_TO_A_SECURE_RANDOM_KEY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    AUTO_CREATE_TABLES: bool = True

    BAIDU_API_KEY: str = ""
    BAIDU_SECRET_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

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
    def DATABASE_URL_RESOLVED(self) -> str:
        return _resolve_sqlite_url(self.DATABASE_URL, base_dir=self.BASE_DIR)

    @property
    def CORS_ALLOW_ORIGINS_LIST(self) -> list[str]:
        return _parse_cors_origins(self.CORS_ALLOW_ORIGINS)

    def ensure_runtime_dirs(self) -> None:
        for path in (self.STATIC_DIR_PATH, self.UPLOAD_DIR_PATH, self.PDF_TEMP_DIR_PATH):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_runtime_dirs()
