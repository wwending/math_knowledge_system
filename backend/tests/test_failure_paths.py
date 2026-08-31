import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import endpoints
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.main import app
from app.models.question import Question
from app.models.user import User, UserStatus


class FailurePathTests(unittest.TestCase):
    TEST_PHONE = "13800000000"
    TEST_PASSWORD = "Secret123!"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root_dir = Path(self.temp_dir.name)
        self.static_dir = root_dir / "static"
        self.upload_dir = self.static_dir / "uploads"
        self.pdf_temp_dir = self.static_dir / "pdf_temp"
        self.static_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_temp_dir.mkdir(parents=True, exist_ok=True)

        self._old_static_dir = settings.STATIC_DIR
        self._old_upload_dir = settings.UPLOAD_DIR
        self._old_pdf_temp_dir = settings.PDF_TEMP_DIR
        settings.STATIC_DIR = str(self.static_dir)
        settings.UPLOAD_DIR = str(self.upload_dir)
        settings.PDF_TEMP_DIR = str(self.pdf_temp_dir)

        db_path = root_dir / "test.sqlite"
        self.engine = create_engine(
            f"sqlite:///{db_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        with self.SessionLocal() as db:
            user = User(
                username=self.TEST_PHONE,
                email="tester@example.com",
                phone=self.TEST_PHONE,
                display_name="Tester",
                hashed_password=get_password_hash(self.TEST_PASSWORD),
                role="user",
                status=UserStatus.ACTIVE.value,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            self.user_id = user.id

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        login_response = self.client.post(
            "/api/v1/auth/token",
            data={"username": self.TEST_PHONE, "password": self.TEST_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(login_response.status_code, 200)
        self.auth_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        settings.STATIC_DIR = self._old_static_dir
        settings.UPLOAD_DIR = self._old_upload_dir
        settings.PDF_TEMP_DIR = self._old_pdf_temp_dir
        self.temp_dir.cleanup()

    def _question_count(self) -> int:
        with self.SessionLocal() as db:
            return db.query(Question).count()

    def _post_recognize(self):
        return self.client.post(
            "/api/v1/recognize",
            headers=self.auth_headers,
            files={"file": ("question.png", b"fake-image-bytes", "image/png")},
        )

    def test_login_failure_returns_clear_message(self):
        response = self.client.post(
            "/api/v1/auth/token",
            data={"username": self.TEST_PHONE, "password": "wrong-password"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid username or password")

    def test_missing_token_rejected(self):
        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Login required")

    def test_invalid_token_rejected(self):
        response = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not-a-real-token"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid login state")

    def test_expired_token_rejected(self):
        expired_token = create_access_token(
            {"sub": str(self.user_id), "sid": "expired-session", "typ": "access", "role": "user"},
            expires_delta=timedelta(minutes=-1),
        )
        response = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Login expired")

    def test_recognize_handles_ocr_exception(self):
        with patch.object(endpoints.ocr_service, "recognize", side_effect=RuntimeError("ocr boom")):
            response = self._post_recognize()

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error_type"], "service_error")
        self.assertEqual(self._question_count(), 0)

    def test_recognize_handles_ocr_empty_result(self):
        with patch.object(
            endpoints.ocr_service,
            "recognize",
            return_value={
                "success": False,
                "error_type": "empty_result",
                "error": "未能识别到可用文字，请更换更清晰的图片后重试",
                "detail": "baidu_ocr_empty_result",
                "content": "",
            },
        ):
            response = self._post_recognize()

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error_type"], "empty_result")
        self.assertEqual(self._question_count(), 0)

    def test_recognize_handles_llm_exception(self):
        with patch.object(
            endpoints.ocr_service,
            "recognize",
            return_value={"success": True, "content": "raw ocr text", "cost_seconds": 0.2},
        ), patch.object(endpoints.nlp_service, "analyze", side_effect=RuntimeError("llm boom")):
            response = self._post_recognize()

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["partial_success"])
        self.assertEqual(payload["error_type"], "llm_failed")
        self.assertEqual(payload["content"], "raw ocr text")
        self.assertEqual(self._question_count(), 1)

    def test_recognize_handles_llm_invalid_structure(self):
        with patch.object(
            endpoints.ocr_service,
            "recognize",
            return_value={"success": True, "content": "raw ocr text", "cost_seconds": 0.2},
        ), patch.object(
            endpoints.nlp_service,
            "analyze",
            return_value={
                "success": False,
                "error_type": "invalid_response",
                "error": "智能整理服务返回了异常结构",
                "detail": "deepseek_invalid_tags",
                "corrected_text": "raw ocr text",
                "tags": [],
            },
        ):
            response = self._post_recognize()

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["partial_success"])
        self.assertEqual(payload["content"], "raw ocr text")
        self.assertEqual(payload["error_type"], "llm_failed")

    def test_recognize_handles_ocr_success_but_llm_failure(self):
        with patch.object(
            endpoints.ocr_service,
            "recognize",
            return_value={"success": True, "content": "ocr only text", "cost_seconds": 0.2},
        ), patch.object(
            endpoints.nlp_service,
            "analyze",
            return_value={
                "success": False,
                "error_type": "timeout",
                "error": "智能整理超时，已保留原始识别结果",
                "detail": "deepseek_timeout",
                "corrected_text": "ocr only text",
                "tags": [],
            },
        ):
            response = self._post_recognize()

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["partial_success"])
        self.assertEqual(payload["warning"], "智能整理超时，已保留原始识别结果")
        self.assertEqual(payload["content"], "ocr only text")
        self.assertEqual(self._question_count(), 1)


if __name__ == "__main__":
    unittest.main()
