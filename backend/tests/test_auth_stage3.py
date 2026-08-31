from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.core.config import Settings, settings  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.auth_audit_log import AuthAuditLog  # noqa: E402
from app.models.login_rate_limit import LoginRateLimit  # noqa: E402
from app.models.user import User, UserRole, UserStatus  # noqa: E402
from tests.db_migration_helper import FreshMigratedSQLiteDatabase  # noqa: E402


class AuthStage3TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.database = FreshMigratedSQLiteDatabase()
        self.engine = self.database.engine
        self.SessionLocal = self.database.SessionLocal

        self.original_rate_limit_settings = (
            settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
            settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
            settings.LOGIN_RATE_LIMIT_BLOCK_SECONDS,
        )
        settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS = 600
        settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 2
        settings.LOGIN_RATE_LIMIT_BLOCK_SECONDS = 300

        self.app = create_app()

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        self.database.dispose()
        (
            settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
            settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
            settings.LOGIN_RATE_LIMIT_BLOCK_SECONDS,
        ) = self.original_rate_limit_settings

    def _db_session(self):
        return self.SessionLocal()

    def _create_user(
        self,
        *,
        phone: str,
        password: str,
        role: str = UserRole.USER.value,
        status: str = UserStatus.ACTIVE.value,
        must_change_password: bool = False,
        display_name: str = "Test User",
    ) -> User:
        db = self._db_session()
        try:
            user = User(
                username=phone,
                phone=phone,
                display_name=display_name,
                hashed_password=get_password_hash(password),
                role=role,
                status=status,
                must_change_password=must_change_password,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            db.expunge(user)
            return user
        finally:
            db.close()

    @staticmethod
    def _auth_headers(access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    def test_login_rate_limit_and_audit_logs(self) -> None:
        self._create_user(phone="13800000001", password="AdminPass123!", display_name="Login User")

        for attempt in range(2):
            response = self.client.post(
                "/api/v1/auth/login",
                json={"phone": "13800000001", "password": "WrongPass123!"},
            )
            self.assertEqual(response.status_code, 401, msg=f"attempt {attempt + 1} should fail with 401")

        blocked_response = self.client.post(
            "/api/v1/auth/login",
            json={"phone": "13800000001", "password": "WrongPass123!"},
        )
        self.assertEqual(blocked_response.status_code, 429)
        self.assertEqual(blocked_response.json()["detail"], "Too many failed login attempts. Please try again later")
        self.assertIn("Retry-After", blocked_response.headers)

        db = self._db_session()
        try:
            rate_limit = (
                db.query(LoginRateLimit)
                .filter(LoginRateLimit.scope_type == "phone", LoginRateLimit.scope_value == "13800000001")
                .first()
            )
            self.assertIsNotNone(rate_limit)
            self.assertEqual(rate_limit.failed_count, 2)
            self.assertIsNotNone(rate_limit.blocked_until)

            failures = (
                db.query(AuthAuditLog)
                .filter(AuthAuditLog.event_type == "auth.login.failure")
                .order_by(AuthAuditLog.id.asc())
                .all()
            )
            self.assertEqual(len(failures), 3)
            self.assertEqual(failures[-1].outcome, "rate_limited")
        finally:
            db.close()

    def test_admin_user_management_session_flow_and_audit_logs(self) -> None:
        self._create_user(
            phone="13800000000",
            password="AdminPass123!",
            role=UserRole.SUPER_ADMIN.value,
            display_name="Super Admin",
        )

        admin_login = self.client.post(
            "/api/v1/auth/login",
            json={"phone": "13800000000", "password": "AdminPass123!"},
        )
        self.assertEqual(admin_login.status_code, 200)
        admin_token = admin_login.json()["access_token"]
        admin_headers = self._auth_headers(admin_token)

        create_response = self.client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "username": "managed138",
                "display_name": "ManagedUser",
                "password": "TempPass123!",
                "role": "user",
                "must_change_password": True,
            },
        )
        self.assertEqual(create_response.status_code, 200)
        created_user_id = create_response.json()["id"]

        role_response = self.client.patch(
            f"/api/v1/admin/users/{created_user_id}/role",
            headers=admin_headers,
            json={"role": "admin"},
        )
        self.assertEqual(role_response.status_code, 200)

        disable_response = self.client.patch(
            f"/api/v1/admin/users/{created_user_id}/status",
            headers=admin_headers,
            json={"status": "disabled"},
        )
        self.assertEqual(disable_response.status_code, 200)

        disabled_login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "managed138", "password": "TempPass123!"},
        )
        self.assertEqual(disabled_login.status_code, 403)

        enable_response = self.client.patch(
            f"/api/v1/admin/users/{created_user_id}/status",
            headers=admin_headers,
            json={"status": "active"},
        )
        self.assertEqual(enable_response.status_code, 200)

        reset_response = self.client.post(
            f"/api/v1/admin/users/{created_user_id}/reset-password",
            headers=admin_headers,
            json={"new_password": "ResetPass123!", "must_change_password": True},
        )
        self.assertEqual(reset_response.status_code, 200)

        user_client = TestClient(self.app)
        try:
            user_login = user_client.post(
                "/api/v1/auth/login",
                json={"username": "managed138", "password": "ResetPass123!"},
            )
            self.assertEqual(user_login.status_code, 200)
            self.assertFalse(user_login.json()["user"]["must_change_password"])
            user_token = user_login.json()["access_token"]
            user_headers = self._auth_headers(user_token)

            me_response = user_client.get("/api/v1/auth/me", headers=user_headers)
            self.assertEqual(me_response.status_code, 200)
            self.assertFalse(me_response.json()["must_change_password"])

            change_password_response = user_client.post(
                "/api/v1/auth/change-password",
                headers=user_headers,
                json={
                    "current_password": "ResetPass123!",
                    "new_password": "FinalPass123!",
                },
            )
            self.assertEqual(change_password_response.status_code, 200)
            self.assertFalse(change_password_response.json()["user"]["must_change_password"])

            refreshed_token = change_password_response.json()["access_token"]
            refresh_response = user_client.post("/api/v1/auth/refresh")
            self.assertEqual(refresh_response.status_code, 200)
            self.assertEqual(refresh_response.json()["user"]["username"], "managed138")

            logout_response = user_client.post(
                "/api/v1/auth/logout",
                headers=self._auth_headers(refreshed_token),
            )
            self.assertEqual(logout_response.status_code, 200)
            self.assertTrue(logout_response.json()["success"])
        finally:
            user_client.close()

        db = self._db_session()
        try:
            event_types = {
                row.event_type
                for row in db.query(AuthAuditLog).all()
            }
            self.assertIn("auth.login.success", event_types)
            self.assertIn("auth.login.failure", event_types)
            self.assertIn("admin.user.created", event_types)
            self.assertIn("admin.user.disabled", event_types)
            self.assertIn("admin.user.enabled", event_types)
            self.assertIn("admin.user.role.changed", event_types)
            self.assertIn("admin.user.password.reset", event_types)
            self.assertIn("auth.password.changed", event_types)
        finally:
            db.close()

    def test_production_security_validation_rejects_insecure_defaults(self) -> None:
        insecure = Settings(
            _env_file=None,
            APP_ENV="production",
            SECRET_KEY="CHANGE_THIS_TO_A_SECURE_RANDOM_KEY",
            CORS_ALLOW_ORIGINS="*",
            REFRESH_TOKEN_COOKIE_SECURE=True,
            REFRESH_TOKEN_COOKIE_SAMESITE="lax",
            SECURE_TRANSPORT_MODE="direct_https",
        )

        with self.assertRaisesRegex(RuntimeError, "SECRET_KEY must be overridden"):
            insecure.validate_security_settings()

    def test_refresh_cookie_validation_rejects_invalid_shape_in_any_environment(self) -> None:
        invalid_same_site = Settings(
            _env_file=None,
            APP_ENV="development",
            REFRESH_TOKEN_COOKIE_SAMESITE="unsafe",
        )
        with self.assertRaisesRegex(RuntimeError, "REFRESH_TOKEN_COOKIE_SAMESITE must be one of"):
            invalid_same_site.validate_security_settings()

        invalid_path = Settings(
            _env_file=None,
            APP_ENV="development",
            REFRESH_TOKEN_COOKIE_PATH="auth",
        )
        with self.assertRaisesRegex(RuntimeError, "REFRESH_TOKEN_COOKIE_PATH must start with '/'"):
            invalid_path.validate_security_settings()

        invalid_transport = Settings(
            _env_file=None,
            APP_ENV="development",
            SECURE_TRANSPORT_MODE="https_only",
        )
        with self.assertRaisesRegex(RuntimeError, "SECURE_TRANSPORT_MODE must be one of"):
            invalid_transport.validate_security_settings()

    def test_production_security_validation_rejects_insecure_refresh_cookie_settings(self) -> None:
        insecure_cookie = Settings(
            _env_file=None,
            APP_ENV="production",
            SECRET_KEY="x" * 32,
            CORS_ALLOW_ORIGINS='["https://app.example.com"]',
            REFRESH_TOKEN_COOKIE_SECURE=False,
            REFRESH_TOKEN_COOKIE_SAMESITE="lax",
            SECURE_TRANSPORT_MODE="direct_https",
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "REFRESH_TOKEN_COOKIE_SECURE must be true when strict auth security is enabled",
        ):
            insecure_cookie.validate_security_settings()

        cross_site_cookie = Settings(
            _env_file=None,
            APP_ENV="production",
            SECRET_KEY="x" * 32,
            CORS_ALLOW_ORIGINS='["https://app.example.com"]',
            REFRESH_TOKEN_COOKIE_SECURE=True,
            REFRESH_TOKEN_COOKIE_SAMESITE="none",
            SECURE_TRANSPORT_MODE="direct_https",
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "REFRESH_TOKEN_COOKIE_SAMESITE cannot be 'none' unless ALLOW_CROSS_SITE_REFRESH_COOKIE=true",
        ):
            cross_site_cookie.validate_security_settings()

    def test_explicit_strict_mode_rejects_insecure_http_transport(self) -> None:
        strict_staging = Settings(
            _env_file=None,
            APP_ENV="staging",
            AUTH_STRICT_SECURITY=True,
            SECRET_KEY="x" * 32,
            CORS_ALLOW_ORIGINS='["https://staging.example.com"]',
            REFRESH_TOKEN_COOKIE_SECURE=True,
            REFRESH_TOKEN_COOKIE_SAMESITE="lax",
            SECURE_TRANSPORT_MODE="insecure_http",
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "SECURE_TRANSPORT_MODE cannot be insecure_http when strict auth security is enabled",
        ):
            strict_staging.validate_security_settings()

    def test_explicit_cross_site_refresh_cookie_exception_is_allowed_in_strict_mode(self) -> None:
        strict_staging = Settings(
            _env_file=None,
            APP_ENV="staging",
            AUTH_STRICT_SECURITY=True,
            SECRET_KEY="x" * 32,
            CORS_ALLOW_ORIGINS='["https://staging.example.com"]',
            REFRESH_TOKEN_COOKIE_SECURE=True,
            REFRESH_TOKEN_COOKIE_SAMESITE="NoNe",
            SECURE_TRANSPORT_MODE="TRUSTED_PROXY_TLS",
            ALLOW_CROSS_SITE_REFRESH_COOKIE=True,
        )

        strict_staging.validate_security_settings()
        self.assertTrue(strict_staging.AUTH_STRICT_SECURITY_ENABLED)
        self.assertEqual(strict_staging.REFRESH_TOKEN_COOKIE_SAMESITE_NORMALIZED, "none")
        self.assertEqual(strict_staging.SECURE_TRANSPORT_MODE_NORMALIZED, "trusted_proxy_tls")

    def test_create_app_rejects_insecure_production_cookie_settings_at_startup(self) -> None:
        original_settings = {
            "APP_ENV": settings.APP_ENV,
            "AUTH_STRICT_SECURITY": settings.AUTH_STRICT_SECURITY,
            "SECRET_KEY": settings.SECRET_KEY,
            "CORS_ALLOW_ORIGINS": settings.CORS_ALLOW_ORIGINS,
            "REFRESH_TOKEN_COOKIE_SECURE": settings.REFRESH_TOKEN_COOKIE_SECURE,
            "REFRESH_TOKEN_COOKIE_SAMESITE": settings.REFRESH_TOKEN_COOKIE_SAMESITE,
            "SECURE_TRANSPORT_MODE": settings.SECURE_TRANSPORT_MODE,
            "ALLOW_CROSS_SITE_REFRESH_COOKIE": settings.ALLOW_CROSS_SITE_REFRESH_COOKIE,
        }

        settings.APP_ENV = "production"
        settings.AUTH_STRICT_SECURITY = False
        settings.SECRET_KEY = "x" * 32
        settings.CORS_ALLOW_ORIGINS = '["https://app.example.com"]'
        settings.REFRESH_TOKEN_COOKIE_SECURE = False
        settings.REFRESH_TOKEN_COOKIE_SAMESITE = "lax"
        settings.SECURE_TRANSPORT_MODE = "direct_https"
        settings.ALLOW_CROSS_SITE_REFRESH_COOKIE = False

        try:
            with self.assertRaisesRegex(
                RuntimeError,
                "REFRESH_TOKEN_COOKIE_SECURE must be true when strict auth security is enabled",
            ):
                create_app()
        finally:
            for key, value in original_settings.items():
                setattr(settings, key, value)

    def test_create_app_rejects_insecure_transport_when_explicit_strict_mode_enabled(self) -> None:
        original_settings = {
            "APP_ENV": settings.APP_ENV,
            "AUTH_STRICT_SECURITY": settings.AUTH_STRICT_SECURITY,
            "SECRET_KEY": settings.SECRET_KEY,
            "CORS_ALLOW_ORIGINS": settings.CORS_ALLOW_ORIGINS,
            "REFRESH_TOKEN_COOKIE_SECURE": settings.REFRESH_TOKEN_COOKIE_SECURE,
            "REFRESH_TOKEN_COOKIE_SAMESITE": settings.REFRESH_TOKEN_COOKIE_SAMESITE,
            "SECURE_TRANSPORT_MODE": settings.SECURE_TRANSPORT_MODE,
            "ALLOW_CROSS_SITE_REFRESH_COOKIE": settings.ALLOW_CROSS_SITE_REFRESH_COOKIE,
        }

        settings.APP_ENV = "staging"
        settings.AUTH_STRICT_SECURITY = True
        settings.SECRET_KEY = "x" * 32
        settings.CORS_ALLOW_ORIGINS = '["https://staging.example.com"]'
        settings.REFRESH_TOKEN_COOKIE_SECURE = True
        settings.REFRESH_TOKEN_COOKIE_SAMESITE = "lax"
        settings.SECURE_TRANSPORT_MODE = "insecure_http"
        settings.ALLOW_CROSS_SITE_REFRESH_COOKIE = False

        try:
            with self.assertRaisesRegex(
                RuntimeError,
                "SECURE_TRANSPORT_MODE cannot be insecure_http when strict auth security is enabled",
            ):
                create_app()
        finally:
            for key, value in original_settings.items():
                setattr(settings, key, value)

    def test_runtime_schema_validation_rejects_production_mutations(self) -> None:
        production_compat = Settings(
            _env_file=None,
            APP_ENV="production",
            ALLOW_RUNTIME_SCHEMA_MUTATIONS=True,
            AUTO_CREATE_TABLES=True,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "Runtime schema mutations are forbidden in production",
        ):
            production_compat.validate_runtime_schema_settings()

    def test_runtime_schema_validation_requires_explicit_allow_outside_production(self) -> None:
        development_compat = Settings(
            _env_file=None,
            APP_ENV="development",
            ALLOW_RUNTIME_SCHEMA_MUTATIONS=False,
            AUTO_APPLY_LEGACY_QUESTION_COMPAT=True,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "ALLOW_RUNTIME_SCHEMA_MUTATIONS=true",
        ):
            development_compat.validate_runtime_schema_settings()

    def test_runtime_schema_validation_allows_explicit_non_production_compat_mode(self) -> None:
        development_compat = Settings(
            _env_file=None,
            APP_ENV="development",
            ALLOW_RUNTIME_SCHEMA_MUTATIONS=True,
            AUTO_CREATE_TABLES=True,
        )

        development_compat.validate_runtime_schema_settings()

    def test_create_app_rejects_runtime_schema_mutations_in_production(self) -> None:
        original_settings = {
            "APP_ENV": settings.APP_ENV,
            "SECRET_KEY": settings.SECRET_KEY,
            "CORS_ALLOW_ORIGINS": settings.CORS_ALLOW_ORIGINS,
            "REFRESH_TOKEN_COOKIE_SECURE": settings.REFRESH_TOKEN_COOKIE_SECURE,
            "REFRESH_TOKEN_COOKIE_SAMESITE": settings.REFRESH_TOKEN_COOKIE_SAMESITE,
            "SECURE_TRANSPORT_MODE": settings.SECURE_TRANSPORT_MODE,
            "ALLOW_RUNTIME_SCHEMA_MUTATIONS": settings.ALLOW_RUNTIME_SCHEMA_MUTATIONS,
            "AUTO_CREATE_TABLES": settings.AUTO_CREATE_TABLES,
            "AUTO_APPLY_LEGACY_QUESTION_COMPAT": settings.AUTO_APPLY_LEGACY_QUESTION_COMPAT,
        }

        settings.APP_ENV = "production"
        settings.SECRET_KEY = "x" * 32
        settings.CORS_ALLOW_ORIGINS = '["https://app.example.com"]'
        settings.REFRESH_TOKEN_COOKIE_SECURE = True
        settings.REFRESH_TOKEN_COOKIE_SAMESITE = "lax"
        settings.SECURE_TRANSPORT_MODE = "direct_https"
        settings.ALLOW_RUNTIME_SCHEMA_MUTATIONS = True
        settings.AUTO_CREATE_TABLES = True
        settings.AUTO_APPLY_LEGACY_QUESTION_COMPAT = False

        try:
            with self.assertRaisesRegex(
                RuntimeError,
                "Runtime schema mutations are forbidden in production",
            ):
                create_app()
        finally:
            for key, value in original_settings.items():
                setattr(settings, key, value)

    def test_create_app_rejects_runtime_schema_mutations_without_explicit_allow(self) -> None:
        original_settings = {
            "APP_ENV": settings.APP_ENV,
            "ALLOW_RUNTIME_SCHEMA_MUTATIONS": settings.ALLOW_RUNTIME_SCHEMA_MUTATIONS,
            "AUTO_CREATE_TABLES": settings.AUTO_CREATE_TABLES,
            "AUTO_APPLY_LEGACY_QUESTION_COMPAT": settings.AUTO_APPLY_LEGACY_QUESTION_COMPAT,
        }

        settings.APP_ENV = "development"
        settings.ALLOW_RUNTIME_SCHEMA_MUTATIONS = False
        settings.AUTO_CREATE_TABLES = False
        settings.AUTO_APPLY_LEGACY_QUESTION_COMPAT = True

        try:
            with self.assertRaisesRegex(
                RuntimeError,
                "ALLOW_RUNTIME_SCHEMA_MUTATIONS=true",
            ):
                create_app()
        finally:
            for key, value in original_settings.items():
                setattr(settings, key, value)


if __name__ == "__main__":
    unittest.main()
