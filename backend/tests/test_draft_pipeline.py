import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import endpoints
from app.core.config import settings
from app.core.constants import DraftEventType, DraftStatus
from app.core.database import get_db
from app.core.security import get_password_hash
from app.db.base import Base
from app.main import app
from app.models.draft import Draft
from app.models.draft_event import DraftEvent
from app.models.llm_run import LLMRun
from app.models.ocr_run import OCRRun
from app.models.question import Question
from app.models.question_revision import QuestionRevision
from app.models.source_asset import SourceAsset
from app.models.user import User, UserStatus


class DraftPipelineTests(unittest.TestCase):
    TEST_PHONE = "13900000000"
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
                email="draft-tester@example.com",
                phone=self.TEST_PHONE,
                display_name="Draft Tester",
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

    def _create_source_asset(self) -> int:
        stored_name = "asset.png"
        (self.upload_dir / stored_name).write_bytes(b"fake-image-bytes")
        with self.SessionLocal() as db:
            asset = SourceAsset(
                user_id=self.user_id,
                kind="image",
                original_path=stored_name,
                normalized_path=None,
                mime="image/png",
                size_bytes=16,
                width=100,
                height=80,
                sha256="draft-pipeline-test-sha",
            )
            db.add(asset)
            db.commit()
            db.refresh(asset)
            return asset.id

    def test_draft_pipeline_recognize_and_save_to_bank(self):
        asset_id = self._create_source_asset()

        create_response = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": asset_id, "crop_bbox": {"x": 1, "y": 2, "w": 30, "h": 40}},
        )
        self.assertEqual(create_response.status_code, 200)
        draft_payload = create_response.json()
        self.assertEqual(draft_payload["status"], DraftStatus.DRAFT_CREATED)
        draft_id = draft_payload["id"]

        with patch.object(
            endpoints.ocr_service,
            "recognize",
            return_value={"success": True, "content": "raw math text", "cost_seconds": 0.1},
        ), patch.object(
            endpoints.nlp_service,
            "analyze",
            return_value={
                "success": True,
                "corrected_text": "clean math text",
                "tags": ["函数", "代数"],
                "cost_seconds": 0.2,
            },
        ):
            recognize_response = self.client.post(
                f"/api/v1/drafts/{draft_id}/recognize",
                headers=self.auth_headers,
            )

        self.assertEqual(recognize_response.status_code, 200)
        recognize_payload = recognize_response.json()
        self.assertTrue(recognize_payload["success"])
        self.assertFalse(recognize_payload["partial_success"])
        self.assertEqual(recognize_payload["status"], DraftStatus.DRAFT_READY)
        self.assertEqual(recognize_payload["content"], "clean math text")
        self.assertEqual([tag["label"] for tag in recognize_payload["knowledge_tags"]], ["函数", "代数"])

        save_response = self.client.post(
            f"/api/v1/drafts/{draft_id}/save-to-bank",
            headers=self.auth_headers,
        )
        self.assertEqual(save_response.status_code, 200)
        save_payload = save_response.json()
        self.assertEqual(save_payload["status"], DraftStatus.SAVED_TO_BANK)
        self.assertEqual(save_payload["rev_no"], 1)

        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            self.assertEqual(draft.status, DraftStatus.SAVED_TO_BANK)
            self.assertEqual(db.query(OCRRun).filter(OCRRun.draft_id == draft_id).count(), 1)
            self.assertEqual(db.query(LLMRun).filter(LLMRun.draft_id == draft_id).count(), 1)
            self.assertEqual(db.query(Question).count(), 1)
            revision = db.query(QuestionRevision).one()
            self.assertEqual(revision.rev_no, 1)
            self.assertEqual(revision.source_asset_id, asset_id)
            event_types = [event.event_type for event in db.query(DraftEvent).order_by(DraftEvent.id.asc()).all()]
            self.assertEqual(
                event_types,
                [
                    DraftEventType.CREATE,
                    DraftEventType.START_RECOGNIZE,
                    DraftEventType.RECOGNIZE_SUCCESS,
                    DraftEventType.SAVE_TO_BANK,
                ],
            )

    def test_draft_recognize_allows_llm_partial_success(self):
        asset_id = self._create_source_asset()
        create_response = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": asset_id},
        )
        draft_id = create_response.json()["id"]

        with patch.object(
            endpoints.ocr_service,
            "recognize",
            return_value={"success": True, "content": "ocr only text", "cost_seconds": 0.1},
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
                "cost_seconds": 0.2,
            },
        ):
            response = self.client.post(f"/api/v1/drafts/{draft_id}/recognize", headers=self.auth_headers)

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["partial_success"])
        self.assertEqual(payload["error_type"], "llm_failed")
        self.assertEqual(payload["status"], DraftStatus.DRAFT_READY)

        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            self.assertEqual(draft.current_content["text"], "ocr only text")
            llm_run = db.query(LLMRun).filter(LLMRun.draft_id == draft_id).one()
            self.assertEqual(llm_run.error_code, "timeout")
            self.assertTrue(llm_run.fallback_used)


if __name__ == "__main__":
    unittest.main()
