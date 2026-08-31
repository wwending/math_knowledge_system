import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash, utcnow
from app.db.migrations import upgrade_database
from app.models.user import User, UserRole, UserStatus


class AuthSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "auth-system.db")
        self.database_url = f"sqlite:///{self.database_path}"

        upgrade_database(self.database_url)

        self.engine = create_engine(
            self.database_url,
            connect_args={"check_same_thread": False},
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        self.app = FastAPI()
        self.app.include_router(api_router, prefix=settings.API_V1_STR)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

        self.super_admin = self._create_user(
            phone="13800000000",
            display_name="Super Admin",
            password="AdminPass123!",
            role=UserRole.SUPER_ADMIN.value,
            status=UserStatus.ACTIVE.value,
            must_change_password=False,
        )
        self.normal_user = self._create_user(
            phone="13900000000",
            display_name="Normal User",
            password="UserPass123!",
            role=UserRole.USER.value,
            status=UserStatus.ACTIVE.value,
            must_change_password=False,
        )

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _create_user(self, *, phone: str, display_name: str, password: str, role: str, status: str, must_change_password: bool):
        db = self.SessionLocal()
        try:
            user = User(
                username=phone,
                phone=phone,
                display_name=display_name,
                hashed_password=get_password_hash(password),
                role=role,
                status=status,
                must_change_password=must_change_password,
                password_changed_at=utcnow(),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
        finally:
            db.close()

    def _login(self, phone: str, password: str) -> dict:
        response = self.client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={"phone": phone, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _login_with_client(self, client: TestClient, phone: str, password: str) -> dict:
        response = client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={"phone": phone, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _auth_headers(self, access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    def test_migration_creates_required_tables_and_columns(self):
        inspector = inspect(self.engine)
        self.assertIn("auth_sessions", inspector.get_table_names())

        user_columns = {column["name"] for column in inspector.get_columns("users")}
        self.assertTrue(
            {
                "phone",
                "display_name",
                "role",
                "status",
                "must_change_password",
                "last_login_at",
                "password_changed_at",
                "created_by",
                "created_at",
                "updated_at",
            }.issubset(user_columns)
        )

    def test_migration_tightens_legacy_users_constraints(self):
        legacy_db_path = os.path.join(self.temp_dir.name, "legacy-auth.db")
        legacy_database_url = f"sqlite:///{legacy_db_path}"
        legacy_engine = create_engine(
            legacy_database_url,
            connect_args={"check_same_thread": False},
        )
        try:
            with legacy_engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TABLE users (
                            id INTEGER PRIMARY KEY,
                            username VARCHAR NOT NULL UNIQUE,
                            email VARCHAR UNIQUE,
                            hashed_password VARCHAR NOT NULL,
                            is_active BOOLEAN,
                            role VARCHAR
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO users (id, username, email, hashed_password, is_active, role)
                        VALUES (1, '13800138000', 'legacy@example.com', 'legacy_hash', 1, 'user')
                        """
                    )
                )

            upgrade_database(legacy_database_url)

            inspector = inspect(legacy_engine)
            columns = {column["name"]: column for column in inspector.get_columns("users")}
            self.assertFalse(columns["display_name"]["nullable"])
            self.assertFalse(columns["status"]["nullable"])
            self.assertFalse(columns["must_change_password"]["nullable"])
            self.assertIn("active", str(columns["status"]["default"]))

            foreign_keys = inspector.get_foreign_keys("users")
            self.assertTrue(
                any(
                    foreign_key.get("referred_table") == "users"
                    and foreign_key.get("constrained_columns") == ["created_by"]
                    for foreign_key in foreign_keys
                )
            )

            with legacy_engine.connect() as connection:
                row = connection.execute(
                    text(
                        "SELECT phone, display_name, status, must_change_password "
                        "FROM users WHERE id = 1"
                    )
                ).mappings().one()
            self.assertEqual(row["phone"], "13800138000")
            self.assertEqual(row["display_name"], "13800138000")
            self.assertEqual(row["status"], "active")
            self.assertIn(row["must_change_password"], (0, False))
        finally:
            legacy_engine.dispose()

    def test_phone_login_refresh_and_logout_revoke_refresh_token(self):
        login_payload = self._login("13800000000", "AdminPass123!")
        self.assertEqual(login_payload["user"]["phone"], "13800000000")

        refresh_response = self.client.post(f"{settings.API_V1_STR}/auth/refresh")
        self.assertEqual(refresh_response.status_code, 200, refresh_response.text)
        self.assertEqual(refresh_response.json()["user"]["phone"], "13800000000")

        logout_response = self.client.post(
            f"{settings.API_V1_STR}/auth/logout",
            headers=self._auth_headers(login_payload["access_token"]),
        )
        self.assertEqual(logout_response.status_code, 200, logout_response.text)

        refresh_after_logout = self.client.post(f"{settings.API_V1_STR}/auth/refresh")
        self.assertEqual(refresh_after_logout.status_code, 401, refresh_after_logout.text)

    def test_admin_can_create_list_get_update_role_status_and_reset_password(self):
        admin_login = self._login("13800000000", "AdminPass123!")
        headers = self._auth_headers(admin_login["access_token"])

        create_response = self.client.post(
            f"{settings.API_V1_STR}/admin/users",
            headers=headers,
            json={
                "username": "managed137",
                "display_name": "ManagedUser",
                "password": "ManagedPass123!",
                "role": "user",
                "must_change_password": True,
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        managed_user = create_response.json()
        self.assertEqual(managed_user["status"], "active")

        list_response = self.client.get(f"{settings.API_V1_STR}/admin/users", headers=headers)
        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertGreaterEqual(list_response.json()["total"], 3)

        detail_response = self.client.get(f"{settings.API_V1_STR}/admin/users/{managed_user['id']}", headers=headers)
        self.assertEqual(detail_response.status_code, 200, detail_response.text)
        self.assertEqual(detail_response.json()["username"], "managed137")

        role_response = self.client.patch(
            f"{settings.API_V1_STR}/admin/users/{managed_user['id']}/role",
            headers=headers,
            json={"role": "admin"},
        )
        self.assertEqual(role_response.status_code, 200, role_response.text)
        self.assertEqual(role_response.json()["user"]["role"], "admin")

        status_response = self.client.patch(
            f"{settings.API_V1_STR}/admin/users/{managed_user['id']}/status",
            headers=headers,
            json={"status": "disabled"},
        )
        self.assertEqual(status_response.status_code, 200, status_response.text)
        self.assertEqual(status_response.json()["user"]["status"], "disabled")

        enable_response = self.client.patch(
            f"{settings.API_V1_STR}/admin/users/{managed_user['id']}/status",
            headers=headers,
            json={"status": "active"},
        )
        self.assertEqual(enable_response.status_code, 200, enable_response.text)
        self.assertEqual(enable_response.json()["user"]["status"], "active")

        reset_response = self.client.post(
            f"{settings.API_V1_STR}/admin/users/{managed_user['id']}/reset-password",
            headers=headers,
            json={"new_password": "ResetPass123!", "must_change_password": True},
        )
        self.assertEqual(reset_response.status_code, 200, reset_response.text)
        self.assertFalse(reset_response.json()["user"]["must_change_password"])
        self.assertEqual(reset_response.json()["user"]["status"], "active")

    def test_non_admin_cannot_access_admin_routes(self):
        user_login = self._login("13900000000", "UserPass123!")
        response = self.client.get(
            f"{settings.API_V1_STR}/admin/users",
            headers=self._auth_headers(user_login["access_token"]),
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_only_super_admin_cannot_be_disabled_or_downgraded_when_unique(self):
        admin_login = self._login("13800000000", "AdminPass123!")
        headers = self._auth_headers(admin_login["access_token"])

        downgrade_response = self.client.patch(
            f"{settings.API_V1_STR}/admin/users/{self.super_admin.id}/role",
            headers=headers,
            json={"role": "admin"},
        )
        self.assertEqual(downgrade_response.status_code, 409, downgrade_response.text)

        disable_response = self.client.patch(
            f"{settings.API_V1_STR}/admin/users/{self.super_admin.id}/status",
            headers=headers,
            json={"status": "disabled"},
        )
        self.assertEqual(disable_response.status_code, 409, disable_response.text)

    def test_admin_reset_password_invalidates_existing_sessions_and_new_password_can_login(self):
        admin_login = self._login("13800000000", "AdminPass123!")
        headers = self._auth_headers(admin_login["access_token"])

        create_response = self.client.post(
            f"{settings.API_V1_STR}/admin/users",
            headers=headers,
            json={
                "username": "reset136",
                "display_name": "ResetTarget",
                "password": "ManagedPass123!",
                "role": "user",
                "must_change_password": True,
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        managed_user = create_response.json()

        managed_client = TestClient(self.app)
        try:
            managed_login = self._login_with_client(managed_client, "reset136", "ManagedPass123!")

            reset_response = self.client.post(
                f"{settings.API_V1_STR}/admin/users/{managed_user['id']}/reset-password",
                headers=headers,
                json={"new_password": "ResetPass123!", "must_change_password": True},
            )
            self.assertEqual(reset_response.status_code, 200, reset_response.text)

            old_session_me = managed_client.get(
                f"{settings.API_V1_STR}/auth/me",
                headers=self._auth_headers(managed_login["access_token"]),
            )
            self.assertEqual(old_session_me.status_code, 401, old_session_me.text)

            relogin = self._login_with_client(managed_client, "reset136", "ResetPass123!")
            self.assertFalse(relogin["user"]["must_change_password"])

            blocked_business_response = managed_client.get(
                f"{settings.API_V1_STR}/questions",
                headers=self._auth_headers(relogin["access_token"]),
            )
            self.assertEqual(blocked_business_response.status_code, 200, blocked_business_response.text)

            change_password_response = managed_client.post(
                f"{settings.API_V1_STR}/auth/change-password",
                headers=self._auth_headers(relogin["access_token"]),
                json={"current_password": "ResetPass123!", "new_password": "ResetPass456!"},
            )
            self.assertEqual(change_password_response.status_code, 200, change_password_response.text)

            allowed_business_response = managed_client.get(
                f"{settings.API_V1_STR}/questions",
                headers=self._auth_headers(change_password_response.json()["access_token"]),
            )
            self.assertEqual(allowed_business_response.status_code, 200, allowed_business_response.text)
        finally:
            managed_client.close()

    def test_must_change_password_user_is_blocked_until_password_is_changed(self):
        admin_login = self._login("13800000000", "AdminPass123!")
        headers = self._auth_headers(admin_login["access_token"])
        create_response = self.client.post(
            f"{settings.API_V1_STR}/admin/users",
            headers=headers,
            json={
                "username": "first135",
                "display_name": "FirstLoginUser",
                "password": "FirstPass123!",
                "role": "user",
                "must_change_password": True,
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)

        with TestClient(self.app) as managed_client:
            login_payload = self._login_with_client(managed_client, "first135", "FirstPass123!")
            me_response = managed_client.get(
                f"{settings.API_V1_STR}/auth/me",
                headers=self._auth_headers(login_payload["access_token"]),
            )
            self.assertEqual(me_response.status_code, 200, me_response.text)

            blocked_questions_response = managed_client.get(
                f"{settings.API_V1_STR}/questions",
                headers=self._auth_headers(login_payload["access_token"]),
            )
            self.assertEqual(blocked_questions_response.status_code, 200, blocked_questions_response.text)

            change_password_response = managed_client.post(
                f"{settings.API_V1_STR}/auth/change-password",
                headers=self._auth_headers(login_payload["access_token"]),
                json={"current_password": "FirstPass123!", "new_password": "FirstPass456!"},
            )
            self.assertEqual(change_password_response.status_code, 200, change_password_response.text)

            recovered_questions_response = managed_client.get(
                f"{settings.API_V1_STR}/questions",
                headers=self._auth_headers(change_password_response.json()["access_token"]),
            )
            self.assertEqual(recovered_questions_response.status_code, 200, recovered_questions_response.text)

    def test_pending_password_change_admin_cannot_access_admin_routes(self):
        admin_login = self._login("13800000000", "AdminPass123!")
        headers = self._auth_headers(admin_login["access_token"])
        create_response = self.client.post(
            f"{settings.API_V1_STR}/admin/users",
            headers=headers,
            json={
                "username": "pending134",
                "display_name": "PendingAdmin",
                "password": "PendingPass123!",
                "role": "admin",
                "must_change_password": True,
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)

        with TestClient(self.app) as pending_admin_client:
            pending_login = self._login_with_client(pending_admin_client, "pending134", "PendingPass123!")
            response = pending_admin_client.get(
                f"{settings.API_V1_STR}/admin/users",
                headers=self._auth_headers(pending_login["access_token"]),
            )
            self.assertEqual(response.status_code, 403, response.text)

    def test_admin_cannot_disable_or_change_own_role(self):
        admin_login = self._login("13800000000", "AdminPass123!")
        headers = self._auth_headers(admin_login["access_token"])

        disable_response = self.client.patch(
            f"{settings.API_V1_STR}/admin/users/{self.super_admin.id}/status",
            headers=headers,
            json={"status": "disabled"},
        )
        self.assertEqual(disable_response.status_code, 409, disable_response.text)

        role_response = self.client.patch(
            f"{settings.API_V1_STR}/admin/users/{self.super_admin.id}/role",
            headers=headers,
            json={"role": "admin"},
        )
        self.assertEqual(role_response.status_code, 409, role_response.text)

        reset_response = self.client.post(
            f"{settings.API_V1_STR}/admin/users/{self.super_admin.id}/reset-password",
            headers=headers,
            json={"new_password": "AdminPass456!", "must_change_password": True},
        )
        self.assertEqual(reset_response.status_code, 409, reset_response.text)

    def test_admin_role_user_cannot_disable_self_or_change_own_role(self):
        bootstrap_login = self._login("13800000000", "AdminPass123!")
        headers = self._auth_headers(bootstrap_login["access_token"])
        create_response = self.client.post(
            f"{settings.API_V1_STR}/admin/users",
            headers=headers,
            json={
                "username": "admin133",
                "display_name": "ManagedAdmin",
                "password": "OpsPassword123!",
                "role": "admin",
                "must_change_password": False,
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        managed_admin = create_response.json()

        with TestClient(self.app) as admin_client:
            admin_login = self._login_with_client(admin_client, "admin133", "OpsPassword123!")
            admin_headers = self._auth_headers(admin_login["access_token"])

            disable_response = admin_client.patch(
                f"{settings.API_V1_STR}/admin/users/{managed_admin['id']}/status",
                headers=admin_headers,
                json={"status": "disabled"},
            )
            self.assertEqual(disable_response.status_code, 403, disable_response.text)

            role_response = admin_client.patch(
                f"{settings.API_V1_STR}/admin/users/{managed_admin['id']}/role",
                headers=admin_headers,
                json={"role": "user"},
            )
            self.assertEqual(role_response.status_code, 403, role_response.text)

    def test_user_can_change_password(self):
        login_payload = self._login("13900000000", "UserPass123!")
        change_response = self.client.post(
            f"{settings.API_V1_STR}/auth/change-password",
            headers=self._auth_headers(login_payload["access_token"]),
            json={"current_password": "UserPass123!", "new_password": "UserPass456!"},
        )
        self.assertEqual(change_response.status_code, 200, change_response.text)
        self.assertTrue(change_response.json()["success"])

        old_password_response = self.client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={"phone": "13900000000", "password": "UserPass123!"},
        )
        self.assertEqual(old_password_response.status_code, 401, old_password_response.text)

        new_password_response = self.client.post(
            f"{settings.API_V1_STR}/auth/login",
            json={"phone": "13900000000", "password": "UserPass456!"},
        )
        self.assertEqual(new_password_response.status_code, 200, new_password_response.text)

    def test_disabled_user_sessions_are_invalidated(self):
        user_login = self._login("13900000000", "UserPass123!")
        with TestClient(self.app) as admin_client:
            admin_login = admin_client.post(
                f"{settings.API_V1_STR}/auth/login",
                json={"phone": "13800000000", "password": "AdminPass123!"},
            )
            self.assertEqual(admin_login.status_code, 200, admin_login.text)
            disable_response = admin_client.patch(
                f"{settings.API_V1_STR}/admin/users/{self.normal_user.id}/status",
                headers=self._auth_headers(admin_login.json()["access_token"]),
                json={"status": "disabled"},
            )
            self.assertEqual(disable_response.status_code, 200, disable_response.text)

        me_response = self.client.get(
            f"{settings.API_V1_STR}/auth/me",
            headers=self._auth_headers(user_login["access_token"]),
        )
        self.assertEqual(me_response.status_code, 401, me_response.text)

        refresh_response = self.client.post(f"{settings.API_V1_STR}/auth/refresh")
        self.assertEqual(refresh_response.status_code, 401, refresh_response.text)


if __name__ == "__main__":
    unittest.main()
