import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash, utcnow
from app.db.migrations import upgrade_database
from app.models.auth_audit_log import AuthAuditLog
from app.models.auth_setting import AuthSetting
from app.models.signup_rate_limit import SignupRateLimit
from app.models.user import User


class UsernamePublicSignupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_url = f"sqlite:///{os.path.join(self.temp_dir.name, 'issue147.db')}"
        upgrade_database(self.db_url)
        self.engine = create_engine(self.db_url, connect_args={"check_same_thread": False})
        self.Session = sessionmaker(bind=self.engine)
        self.app = FastAPI()
        self.app.include_router(api_router, prefix=settings.API_V1_STR)

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        self.app.dependency_overrides[get_db] = override_db
        self.client = TestClient(self.app)
        with self.Session() as db:
            db.add_all([
                User(username="13800000000", phone="13800000000", display_name="超级一", hashed_password=get_password_hash("123456"), role="super_admin", status="active", must_change_password=False),
                User(username="admin_old", phone="13900000000", display_name="管理一", hashed_password=get_password_hash("123456"), role="admin", status="active", must_change_password=False),
            ])
            db.commit()

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def login(self, identifier, password="123456"):
        response = self.client.post(f"{settings.API_V1_STR}/auth/login", json={"username": identifier, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def test_public_registration_username_rules_and_legacy_phone_login(self):
        response = self.client.post(f"{settings.API_V1_STR}/auth/register", json={"username": "  测试_1  ", "password": "abc123"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["username"], "测试_1")
        self.assertEqual(response.json()["display_name"], "测试_1")
        self.assertIsNone(response.json()["phone"])
        self.login("测试_1", "abc123")
        self.login("13800000000")
        self.login("138-0000-0000")

        for invalid in ("___", "root", "has space", "emoji😀", "a" * 33):
            rejected = self.client.post(f"{settings.API_V1_STR}/auth/register", json={"username": invalid, "password": "abc123"})
            self.assertEqual(rejected.status_code, 422, (invalid, rejected.text))

    def test_username_nfc_case_sensitivity_nickname_and_legacy_phone_namespace(self):
        response = self.client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={"username": "CaseName", "display_name": "昵称一", "password": "abc123"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        cases = [
            ({"username": "CaseName", "password": "abc123"}, 409),
            ({"username": "casename", "password": "abc123"}, 200),
            ({"username": "Cafe\u0301", "password": "abc123"}, 422),
            ({"username": "13800000000", "password": "abc123"}, 409),
            ({"username": "another", "display_name": "昵称一", "password": "abc123"}, 409),
            ({"username": "valid_name", "display_name": "ADMIN", "password": "abc123"}, 422),
        ]
        for payload, expected_status in cases:
            result = self.client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
            self.assertEqual(result.status_code, expected_status, (payload, result.text))

    def test_super_admin_exclusive_management_and_persistent_switch(self):
        admin_headers = self.login("13900000000")
        endpoints = [
            ("get", "/admin/users", None),
            ("post", "/admin/users", {"username": "blocked", "password": "abc123", "role": "user"}),
            ("get", "/admin/users/settings/public-signup", None),
            ("put", "/admin/users/settings/public-signup", {"public_signup_enabled": False}),
            ("get", "/admin/users/1", None),
            ("patch", "/admin/users/1/status", {"status": "disabled"}),
            ("patch", "/admin/users/1/role", {"role": "admin"}),
            ("post", "/admin/users/1/reset-password", {"new_password": "abc123"}),
        ]
        for method, path, payload in endpoints:
            kwargs = {"headers": admin_headers}
            if payload is not None:
                kwargs["json"] = payload
            result = getattr(self.client, method)(f"{settings.API_V1_STR}{path}", **kwargs)
            self.assertEqual(result.status_code, 403, (method, path, result.text))

        super_headers = self.login("13800000000")
        disabled = self.client.put(f"{settings.API_V1_STR}/admin/users/settings/public-signup", headers=super_headers, json={"public_signup_enabled": False})
        self.assertEqual(disabled.status_code, 200, disabled.text)
        self.assertFalse(self.client.get(f"{settings.API_V1_STR}/auth/capabilities").json()["public_signup_enabled"])
        self.assertEqual(self.client.post(f"{settings.API_V1_STR}/auth/register", json={"username": "new_user", "password": "abc123"}).status_code, 403)
        with self.Session() as db:
            self.assertFalse(db.query(AuthSetting).one().public_signup_enabled)
            self.assertIsNotNone(db.query(AuthAuditLog).filter(AuthAuditLog.event_type == "admin.public_signup.disabled").first())
        enabled = self.client.put(
            f"{settings.API_V1_STR}/admin/users/settings/public-signup",
            headers=super_headers,
            json={"public_signup_enabled": True},
        )
        self.assertEqual(enabled.status_code, 200, enabled.text)
        self.assertTrue(self.client.get(f"{settings.API_V1_STR}/auth/capabilities").json()["public_signup_enabled"])

    def test_database_prevents_removing_last_active_super_admin(self):
        with self.Session() as db:
            super_admin = db.query(User).filter(User.role == "super_admin").one()
            super_admin.role = "admin"
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()

    def test_password_policy_allows_simple_printable_ascii_and_rejects_controls(self):
        for password in ("123456", "abcdef", "!!!!!!", "a b c "):
            name = f"u{abs(hash(password)) % 1000000}"
            response = self.client.post(f"{settings.API_V1_STR}/auth/register", json={"username": name, "password": password})
            self.assertEqual(response.status_code, 200, (password, response.text))
        for password in ("12345", "      ", "abc\t123", "中文123"):
            response = self.client.post(f"{settings.API_V1_STR}/auth/register", json={"username": f"bad{len(password)}x", "password": password})
            self.assertEqual(response.status_code, 422, (password, response.text))

    def test_signup_success_limit_audit_and_window_recovery(self):
        for index in range(5):
            response = self.client.post(
                f"{settings.API_V1_STR}/auth/register",
                json={"username": f"quota{index}", "password": "abc123"},
            )
            self.assertEqual(response.status_code, 200, response.text)
        limited = self.client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={"username": "quota5", "password": "abc123"},
        )
        self.assertEqual(limited.status_code, 429, limited.text)
        with self.Session() as db:
            events = db.query(AuthAuditLog).filter(AuthAuditLog.event_type.in_(["auth.signup.success", "auth.signup.rate_limited"])).all()
            self.assertEqual(sum(event.event_type == "auth.signup.success" for event in events), 5)
            self.assertTrue(any(event.event_type == "auth.signup.rate_limited" for event in events))
            self.assertTrue(all(event.target_user_id is not None for event in events if event.event_type == "auth.signup.success"))
            self.assertNotIn("abc123", repr([event.details for event in events]))
            record = db.query(SignupRateLimit).one()
            record.success_window_started_at = utcnow() - timedelta(hours=1, seconds=1)
            db.commit()
        recovered = self.client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={"username": "quota5", "password": "abc123"},
        )
        self.assertEqual(recovered.status_code, 200, recovered.text)

    def test_failed_signup_limit_recovers_and_untrusted_forwarded_header_is_ignored(self):
        for _ in range(20):
            response = self.client.post(
                f"{settings.API_V1_STR}/auth/register",
                headers={"X-Forwarded-For": "203.0.113.10"},
                json={"username": "bad name", "password": "abc123"},
            )
            self.assertEqual(response.status_code, 422, response.text)
        limited = self.client.post(
            f"{settings.API_V1_STR}/auth/register",
            headers={"X-Forwarded-For": "198.51.100.20"},
            json={"username": "after_failures", "password": "abc123"},
        )
        self.assertEqual(limited.status_code, 429, limited.text)
        with self.Session() as db:
            record = db.query(SignupRateLimit).one()
            self.assertNotEqual(record.ip_address, "203.0.113.10")
            record.failure_window_started_at = utcnow() - timedelta(minutes=10, seconds=1)
            db.commit()
        recovered = self.client.post(
            f"{settings.API_V1_STR}/auth/register",
            json={"username": "after_failures", "password": "abc123"},
        )
        self.assertEqual(recovered.status_code, 200, recovered.text)

    def test_concurrent_duplicate_username_and_success_quota_are_stable(self):
        def register(username):
            with TestClient(self.app) as client:
                response = client.post(
                    f"{settings.API_V1_STR}/auth/register",
                    json={"username": username, "password": "abc123"},
                )
                return response.status_code, response.json().get("detail")

        with ThreadPoolExecutor(max_workers=2) as pool:
            duplicate_results = list(pool.map(register, ["same_name", "same_name"]))
        self.assertEqual(sorted(status for status, _ in duplicate_results), [200, 409], duplicate_results)
        self.assertEqual(next(detail for status, detail in duplicate_results if status == 409), "Username already exists")

        with self.Session() as db:
            db.query(SignupRateLimit).delete()
            db.commit()
        with ThreadPoolExecutor(max_workers=6) as pool:
            quota_results = list(pool.map(register, [f"parallel{index}" for index in range(6)]))
        self.assertEqual(sum(status == 200 for status, _ in quota_results), 5, quota_results)
        self.assertEqual(sum(status == 429 for status, _ in quota_results), 1, quota_results)


if __name__ == "__main__":
    unittest.main()
