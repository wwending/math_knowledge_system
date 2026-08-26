import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from loguru import logger
from PIL import Image
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
from app.services import question_metadata


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

    def _create_source_asset(
        self,
        *,
        stored_name: str = "asset.png",
        kind: str = "image",
        mime: str = "image/png",
        width: int | None = 100,
        height: int | None = 80,
    ) -> int:
        if mime.startswith("image/"):
            Image.new("RGB", (width or 100, height or 80), color="white").save(self.upload_dir / stored_name)
        else:
            (self.upload_dir / stored_name).write_bytes(b"fake-image-bytes")
        with self.SessionLocal() as db:
            asset = SourceAsset(
                user_id=self.user_id,
                kind=kind,
                original_path=stored_name,
                normalized_path=None,
                mime=mime,
                size_bytes=16,
                width=width,
                height=height,
                sha256=f"{stored_name}-{mime}-draft-pipeline-test-sha",
            )
            db.add(asset)
            db.commit()
            db.refresh(asset)
            return asset.id

    def _create_draft(self, asset_id: int) -> int:
        response = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": asset_id},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    def _set_draft_state(self, draft_id: int, status: str, current_content: dict | None = None) -> None:
        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            draft.status = status
            if current_content is not None:
                draft.current_content = current_content
            db.commit()

    def _tiny_png_bytes(self) -> bytes:
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
            b"\x02\xfeA\xe2!\xbc\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    def test_repeated_asset_upload_reuses_existing_asset_and_allows_new_draft(self):
        image_bytes = self._tiny_png_bytes()

        first_response = self.client.post(
            "/api/v1/assets",
            headers=self.auth_headers,
            files={"file": ("smoke.png", image_bytes, "image/png")},
        )
        self.assertEqual(first_response.status_code, 200)
        first_payload = first_response.json()
        first_asset_id = first_payload["asset_id"]
        self.assertFalse(first_payload.get("deduplicated", False))

        second_response = self.client.post(
            "/api/v1/assets",
            headers=self.auth_headers,
            files={"file": ("smoke.png", image_bytes, "image/png")},
        )
        self.assertEqual(second_response.status_code, 200)
        second_payload = second_response.json()
        self.assertEqual(second_payload["asset_id"], first_asset_id)
        self.assertTrue(second_payload["deduplicated"])
        self.assertEqual(second_payload["existing_asset_id"], first_asset_id)
        self.assertIn("using existing asset", second_payload["message"])

        first_draft = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": first_asset_id},
        )
        second_draft = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": second_payload["asset_id"]},
        )
        self.assertEqual(first_draft.status_code, 200)
        self.assertEqual(second_draft.status_code, 200)
        self.assertNotEqual(first_draft.json()["id"], second_draft.json()["id"])

        with self.SessionLocal() as db:
            self.assertEqual(db.query(SourceAsset).count(), 1)
            self.assertEqual(db.query(Draft).filter(Draft.source_asset_id == first_asset_id).count(), 2)

    def _recognize_draft_successfully(self, draft_id: int):
        with patch.object(
            endpoints.draft_ocr_service,
            "recognize",
            return_value={"success": True, "content": "raw math text", "cost_seconds": 0.1},
        ), patch.object(
            endpoints.nlp_service,
            "analyze",
            return_value={
                "success": True,
                "corrected_text": "clean math text",
                "tags": ["函数"],
                "cost_seconds": 0.2,
            },
        ):
            response = self.client.post(f"/api/v1/drafts/{draft_id}/recognize", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DraftStatus.DRAFT_READY)
        return response

    def test_manual_edit_preserves_recognition_context_rechecks_warnings_and_saves_updated_content(self):
        asset_id = self._create_source_asset()
        draft_id = self._create_draft(asset_id)
        self._recognize_draft_successfully(draft_id)
        initial_content = "题干：请选择正确答案。\nA. 选项一\nB. 选项二"
        manual_content = "题干：请选择正确答案。\nA. 选项一\nB. 选项二\nC. 选项三\nD. 选项四"

        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            last_ocr_run_id = draft.last_ocr_run_id
            last_llm_run_id = draft.last_llm_run_id
            draft.current_content = {
                "text": initial_content,
                "ocr_text": "raw math text",
                "knowledge_tags": [{"label": "函数", "score": 1.0}],
                "partial_success": False,
                "warning": None,
                "recognition_debug": {"pipeline": "original"},
            }
            db.commit()

        initial_response = self.client.get(f"/api/v1/drafts/{draft_id}", headers=self.auth_headers)
        self.assertEqual(initial_response.status_code, 200)
        self.assertIn(
            "choice_options_incomplete",
            {warning["code"] for warning in initial_response.json()["quality_warnings"]},
        )

        update_response = self.client.patch(
            f"/api/v1/drafts/{draft_id}",
            headers=self.auth_headers,
            json={"content": f"  {manual_content}  "},
        )
        self.assertEqual(update_response.status_code, 200)
        update_payload = update_response.json()
        self.assertEqual(update_payload["status"], DraftStatus.DRAFT_READY)
        self.assertEqual(update_payload["content"], manual_content)
        self.assertEqual(update_payload["current_content"]["text"], manual_content)
        self.assertEqual(update_payload["current_content"]["ocr_text"], "raw math text")
        self.assertEqual(update_payload["current_content"]["knowledge_tags"], [{"label": "函数", "score": 1.0}])
        self.assertEqual(update_payload["current_content"]["recognition_debug"], {"pipeline": "original"})
        self.assertEqual(update_payload["last_ocr_run_id"], last_ocr_run_id)
        self.assertEqual(update_payload["last_llm_run_id"], last_llm_run_id)
        self.assertEqual(update_payload["recognition_debug"]["ocr_raw_text"], "raw math text")
        self.assertEqual(update_payload["recognition_debug"]["llm_cleaned_text"], "clean math text")
        self.assertNotIn(
            "choice_options_incomplete",
            {warning["code"] for warning in update_payload["quality_warnings"]},
        )

        detail_response = self.client.get(f"/api/v1/drafts/{draft_id}", headers=self.auth_headers)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["content"], manual_content)

        with self.SessionLocal() as db:
            edit_events = db.query(DraftEvent).filter(DraftEvent.event_type == DraftEventType.EDIT).all()
            self.assertEqual(len(edit_events), 1)
            edit_event = edit_events[0]
            self.assertEqual(edit_event.draft_id, draft_id)
            self.assertEqual(edit_event.from_status, DraftStatus.DRAFT_READY)
            self.assertEqual(edit_event.to_status, DraftStatus.DRAFT_READY)
            self.assertEqual(edit_event.metadata_["source"], "manual_review")
            self.assertEqual(edit_event.metadata_["previous_length"], len(initial_content))
            self.assertEqual(edit_event.metadata_["new_length"], len(manual_content))
            self.assertEqual(len(edit_event.metadata_["previous_sha256"]), 64)
            self.assertEqual(len(edit_event.metadata_["new_sha256"]), 64)
            self.assertNotIn(initial_content, edit_event.metadata_.values())
            self.assertNotIn(manual_content, edit_event.metadata_.values())

        unchanged_response = self.client.patch(
            f"/api/v1/drafts/{draft_id}",
            headers=self.auth_headers,
            json={"content": manual_content},
        )
        self.assertEqual(unchanged_response.status_code, 200)
        with self.SessionLocal() as db:
            self.assertEqual(db.query(DraftEvent).filter(DraftEvent.event_type == DraftEventType.EDIT).count(), 1)

        with patch.object(endpoints, "evaluate_question_metadata_task", return_value=None):
            save_response = self.client.post(
                f"/api/v1/drafts/{draft_id}/save-to-bank",
                headers=self.auth_headers,
            )
        self.assertEqual(save_response.status_code, 200)
        with self.SessionLocal() as db:
            question = db.query(Question).one()
            revision = db.query(QuestionRevision).one()
            self.assertEqual(question.content, manual_content)
            self.assertEqual(revision.content["text"], manual_content)
            self.assertEqual(revision.content["ocr_text"], "raw math text")

    def test_manual_edit_rejects_empty_and_whitespace_only_content(self):
        asset_id = self._create_source_asset()
        draft_id = self._create_draft(asset_id)
        self._set_draft_state(draft_id, DraftStatus.DRAFT_READY, {"text": "原题目内容"})

        for content in ("", "   \r\n\t"):
            with self.subTest(content=repr(content)):
                response = self.client.patch(
                    f"/api/v1/drafts/{draft_id}",
                    headers=self.auth_headers,
                    json={"content": content},
                )
                self.assertEqual(response.status_code, 422)

    def test_manual_edit_rejects_non_owner(self):
        asset_id = self._create_source_asset()
        draft_id = self._create_draft(asset_id)
        self._set_draft_state(draft_id, DraftStatus.DRAFT_READY, {"text": "原题目内容"})

        other_phone = "13900000001"
        with self.SessionLocal() as db:
            db.add(
                User(
                    username=other_phone,
                    email="other-draft-editor@example.com",
                    phone=other_phone,
                    display_name="Other Draft Editor",
                    hashed_password=get_password_hash(self.TEST_PASSWORD),
                    role="user",
                    status=UserStatus.ACTIVE.value,
                )
            )
            db.commit()
        login_response = self.client.post(
            "/api/v1/auth/token",
            data={"username": other_phone, "password": self.TEST_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(login_response.status_code, 200)
        other_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        response = self.client.patch(
            f"/api/v1/drafts/{draft_id}",
            headers=other_headers,
            json={"content": "越权修改"},
        )
        self.assertEqual(response.status_code, 403)

    def test_manual_edit_rejects_every_non_ready_status(self):
        asset_id = self._create_source_asset()
        forbidden_statuses = (
            DraftStatus.DRAFT_CREATED,
            DraftStatus.RECOGNIZING,
            DraftStatus.FAILED,
            DraftStatus.SUPERSEDED,
            DraftStatus.SAVED_TO_BANK,
        )

        for status in forbidden_statuses:
            with self.subTest(status=status):
                draft_id = self._create_draft(asset_id)
                self._set_draft_state(draft_id, status, {"text": "原题目内容"})
                response = self.client.patch(
                    f"/api/v1/drafts/{draft_id}",
                    headers=self.auth_headers,
                    json={"content": "人工修改内容"},
                )
                self.assertEqual(response.status_code, 409)

    def test_draft_pipeline_recognize_is_lightweight_and_save_to_bank_sets_metadata_pending(self):
        asset_id = self._create_source_asset()

        create_response = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": asset_id, "crop_bbox": [0.1, 0.2, 0.6, 0.5]},
        )
        self.assertEqual(create_response.status_code, 200)
        draft_payload = create_response.json()
        self.assertEqual(draft_payload["status"], DraftStatus.DRAFT_CREATED)
        draft_id = draft_payload["id"]

        with patch.object(
            endpoints.draft_ocr_service,
            "recognize",
            return_value={"success": True, "content": "raw math text", "cost_seconds": 0.1},
        ), patch.object(
            endpoints.nlp_service,
            "analyze",
            return_value={
                "success": True,
                "corrected_text": "clean math text",
                "tags": ["函数", "代数"],
                "knowledge_tags": ["函数", "代数"],
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
        self.assertEqual(recognize_payload["recognition_debug"]["ocr_provider"], "baidu")
        self.assertEqual(recognize_payload["recognition_debug"]["ocr_raw_text"], "raw math text")
        self.assertEqual(recognize_payload["recognition_debug"]["llm_cleaned_text"], "clean math text")
        self.assertEqual(recognize_payload["quality_warnings"], [{"code": "recognized_text_too_short", "level": "warning", "message": "识别文本较短，可能存在漏识别，请核对原图和原始 OCR 文本。"}])
        self.assertIsNone(recognize_payload["recognition_debug"]["ocr_error"])
        self.assertIsNone(recognize_payload["recognition_debug"]["llm_error"])
        self.assertIsNone(recognize_payload["question_type"])
        self.assertIsNone(recognize_payload["difficulty_level"])
        self.assertIsNone(recognize_payload["difficulty_label"])
        self.assertIsNone(recognize_payload["difficulty_confidence"])
        self.assertIsNone(recognize_payload["difficulty_reason"])

        detail_response = self.client.get(f"/api/v1/drafts/{draft_id}", headers=self.auth_headers)
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload["recognition_debug"]["ocr_raw_text"], "raw math text")
        self.assertEqual(detail_payload["recognition_debug"]["llm_cleaned_text"], "clean math text")
        self.assertEqual(detail_payload["quality_warnings"], recognize_payload["quality_warnings"])

        with patch.object(endpoints, "evaluate_question_metadata_task", return_value=None) as metadata_task:
            save_response = self.client.post(
                f"/api/v1/drafts/{draft_id}/save-to-bank",
                headers=self.auth_headers,
            )
        self.assertEqual(save_response.status_code, 200)
        metadata_task.assert_called_once()
        save_payload = save_response.json()
        self.assertEqual(save_payload["status"], DraftStatus.SAVED_TO_BANK)
        self.assertEqual(save_payload["rev_no"], 1)

        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            self.assertEqual(draft.status, DraftStatus.SAVED_TO_BANK)
            self.assertIsNone(draft.question_type)
            self.assertIsNone(draft.difficulty_level)
            self.assertEqual(db.query(OCRRun).filter(OCRRun.draft_id == draft_id).count(), 1)
            self.assertEqual(db.query(OCRRun).filter(OCRRun.draft_id == draft_id).one().provider, "baidu")
            self.assertEqual(db.query(LLMRun).filter(LLMRun.draft_id == draft_id).count(), 1)
            self.assertEqual(db.query(Question).count(), 1)
            question = db.query(Question).one()
            self.assertIsNone(question.question_type)
            self.assertIsNone(question.difficulty_level)
            self.assertIsNone(question.difficulty_label)
            self.assertIsNone(question.difficulty_confidence)
            self.assertIsNone(question.difficulty_reason)
            self.assertIsNone(question.difficulty_model)
            self.assertIsNone(question.difficulty_evaluated_at)
            self.assertEqual(question.metadata_status, "pending")
            self.assertIsNone(question.metadata_error)
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

    def test_question_metadata_task_updates_question_on_success(self):
        with self.SessionLocal() as db:
            question = Question(
                user_id=self.user_id,
                content="clean math text",
                knowledge_tags=[{"label": "函数", "score": 1.0}],
                metadata_status="pending",
            )
            db.add(question)
            db.commit()
            question_id = question.id

        with patch.object(question_metadata, "SessionLocal", self.SessionLocal), patch.object(
            question_metadata.nlp_service,
            "evaluate_question_metadata",
            return_value={
                "success": True,
                "question_type": "solution",
                "difficulty": {
                    "level": 3,
                    "label": "中等",
                    "confidence": 0.81,
                    "reason": "需要函数性质和代数变形。",
                },
                "cost_seconds": 0.2,
            },
        ):
            question_metadata.evaluate_question_metadata_task(question_id)

        with self.SessionLocal() as db:
            question = db.query(Question).filter(Question.id == question_id).one()
            self.assertEqual(question.metadata_status, "ready")
            self.assertIsNone(question.metadata_error)
            self.assertEqual(question.question_type, "solution")
            self.assertEqual(question.difficulty_level, 3)
            self.assertEqual(question.difficulty_label, "中等")
            self.assertAlmostEqual(question.difficulty_confidence, 0.81)
            self.assertEqual(question.difficulty_reason, "需要函数性质和代数变形。")
            self.assertEqual(question.difficulty_model, settings.DEEPSEEK_MODEL)
            self.assertIsNotNone(question.difficulty_evaluated_at)
            self.assertIsNotNone(question.metadata_started_at)
            self.assertIsNotNone(question.metadata_finished_at)

    def test_question_metadata_perf_log_contains_stage_timings(self):
        with self.SessionLocal() as db:
            question = Question(
                user_id=self.user_id,
                content="clean math text",
                knowledge_tags=[],
                metadata_status="pending",
            )
            db.add(question)
            db.commit()
            question_id = question.id

        log_output = StringIO()
        sink_id = logger.add(log_output, level="INFO")
        try:
            with patch.object(question_metadata, "SessionLocal", self.SessionLocal), patch.object(
                question_metadata.nlp_service,
                "evaluate_question_metadata",
                return_value={
                    "success": True,
                    "question_type": "fill_blank",
                    "difficulty": {
                        "level": 3,
                        "label": "中等",
                        "confidence": 0.8,
                        "reason": "两步推理。",
                    },
                    "_perf": {"prompt_ms": 2, "api_ms": 8, "parse_ms": 4},
                },
            ):
                question_metadata.evaluate_question_metadata_task(question_id)
        finally:
            logger.remove(sink_id)

        perf_log = log_output.getvalue()
        self.assertIn("[QuestionMetadataPerf]", perf_log)
        self.assertIn("load_ms=", perf_log)
        self.assertIn("prompt_ms=2", perf_log)
        self.assertIn("api_ms=8", perf_log)
        self.assertIn("parse_ms=4", perf_log)
        self.assertIn("db_ms=", perf_log)
        self.assertIn("total_ms=", perf_log)

    def test_question_metadata_task_marks_question_failed_without_raising(self):
        with self.SessionLocal() as db:
            question = Question(
                user_id=self.user_id,
                content="clean math text",
                knowledge_tags=[],
                metadata_status="pending",
            )
            db.add(question)
            db.commit()
            question_id = question.id

        with patch.object(question_metadata, "SessionLocal", self.SessionLocal), patch.object(
            question_metadata.nlp_service,
            "evaluate_question_metadata",
            return_value={
                "success": False,
                "error_type": "timeout",
                "error": "metadata timeout",
                "detail": "deepseek_timeout",
                "cost_seconds": 0.2,
            },
        ):
            question_metadata.evaluate_question_metadata_task(question_id)

        with self.SessionLocal() as db:
            question = db.query(Question).filter(Question.id == question_id).one()
            self.assertEqual(question.metadata_status, "failed")
            self.assertEqual(question.metadata_error, "timeout")
            self.assertIsNone(question.question_type)
            self.assertIsNone(question.difficulty_level)
            self.assertIsNotNone(question.metadata_finished_at)

    def test_save_to_bank_succeeds_when_background_metadata_evaluation_fails(self):
        asset_id = self._create_source_asset()
        draft_id = self._create_draft(asset_id)
        self._recognize_draft_successfully(draft_id)

        with patch.object(question_metadata, "SessionLocal", self.SessionLocal), patch.object(
            question_metadata.nlp_service,
            "evaluate_question_metadata",
            return_value={
                "success": False,
                "error_type": "timeout",
                "error": "metadata timeout",
                "detail": "deepseek_timeout",
                "cost_seconds": 0.2,
            },
        ):
            response = self.client.post(f"/api/v1/drafts/{draft_id}/save-to-bank", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        with self.SessionLocal() as db:
            question = db.query(Question).one()
            self.assertEqual(question.metadata_status, "failed")
            self.assertEqual(question.metadata_error, "timeout")

    def test_draft_recognize_allows_llm_partial_success(self):
        asset_id = self._create_source_asset()
        create_response = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": asset_id},
        )
        draft_id = create_response.json()["id"]

        with patch.object(
            endpoints.draft_ocr_service,
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

    def test_draft_recognize_records_empty_content_invalid_response(self):
        asset_id = self._create_source_asset()
        draft_id = self._create_draft(asset_id)
        log_output = StringIO()
        sink_id = logger.add(log_output, level="INFO")
        try:
            with patch.object(
                endpoints.draft_ocr_service,
                "recognize",
                return_value={"success": True, "content": "complex ellipse ocr text", "cost_seconds": 0.1},
            ), patch.object(
                endpoints.nlp_service,
                "analyze",
                return_value={
                    "success": False,
                    "error_type": "invalid_response",
                    "error": "智能整理服务返回了空数据",
                    "detail": (
                        "deepseek_length_exhausted_empty_content: choices_count=1 finish_reason=length "
                        "content_len=0 completion_tokens=22"
                    ),
                    "corrected_text": "complex ellipse ocr text",
                    "knowledge_tags": [],
                    "cost_seconds": 0.2,
                },
            ):
                response = self.client.post(f"/api/v1/drafts/{draft_id}/recognize", headers=self.auth_headers)
        finally:
            logger.remove(sink_id)

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["partial_success"])
        self.assertEqual(payload["warning"], "智能整理服务返回了空数据")
        self.assertEqual(payload["error_type"], "llm_failed")
        self.assertEqual(payload["status"], DraftStatus.DRAFT_READY)

        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            self.assertTrue(draft.current_content["partial_success"])
            self.assertEqual(draft.current_content["warning"], "智能整理服务返回了空数据")
            llm_run = db.query(LLMRun).filter(LLMRun.draft_id == draft_id).one()
            self.assertEqual(llm_run.error_code, "invalid_response")
            self.assertIn("deepseek_length_exhausted_empty_content", llm_run.error_message)
            self.assertIn("finish_reason=length", llm_run.error_message)
            self.assertTrue(llm_run.fallback_used)

        perf_log = log_output.getvalue()
        self.assertIn("[DraftRecognizePerf]", perf_log)
        self.assertIn("llm_fallback=True", perf_log)
        self.assertIn("fallback_reason=invalid_response", perf_log)
        self.assertIn("failure_stage=llm", perf_log)

    def test_draft_recognize_logs_perf_when_ocr_fails(self):
        asset_id = self._create_source_asset()
        draft_id = self._create_draft(asset_id)
        log_output = StringIO()
        sink_id = logger.add(log_output, level="INFO")
        try:
            with patch.object(
                endpoints.draft_ocr_service,
                "recognize",
                return_value={
                    "success": False,
                    "content": "",
                    "cost_seconds": 0.1,
                    "error_type": "timeout",
                    "error": "ocr timeout",
                    "detail": "baidu_ocr_timeout",
                },
            ):
                response = self.client.post(f"/api/v1/drafts/{draft_id}/recognize", headers=self.auth_headers)
        finally:
            logger.remove(sink_id)

        self.assertEqual(response.status_code, 200)
        perf_log = log_output.getvalue()
        self.assertIn("[DraftRecognizePerf]", perf_log)
        self.assertIn(f"draft_id={draft_id}", perf_log)
        self.assertIn(f"asset_id={asset_id}", perf_log)
        self.assertIn("ocr_ms=", perf_log)
        self.assertIn("llm_text_ms=0", perf_log)
        self.assertIn("total_ms=", perf_log)
        self.assertIn("llm_fallback=True", perf_log)
        self.assertIn("fallback_reason=timeout", perf_log)
        self.assertIn("failure_stage=ocr", perf_log)

    def test_create_draft_validates_normalized_bbox_and_preserves_full_image_compatibility(self):
        asset_id = self._create_source_asset()
        for body in (
            {"source_asset_id": asset_id},
            {"source_asset_id": asset_id, "crop_bbox": None},
            {"source_asset_id": asset_id, "crop_bbox": {}},
        ):
            with self.subTest(body=body):
                response = self.client.post("/api/v1/drafts", headers=self.auth_headers, json=body)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["crop_bbox"], {})

        valid = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": asset_id, "crop_bbox": [0.1, 0.2, 0.6, 0.5]},
        )
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()["crop_bbox"], [0.1, 0.2, 0.6, 0.5])

        invalid_values = (
            [0, 0, 0, 1],
            [0, 0, 0.01, 0.01],
            [0.8, 0, 0.3, 1],
            [-0.1, 0, 0.5, 0.5],
            [0, 0, 1],
            {"x": 0, "y": 0, "w": 1, "h": 1},
            [True, 0, 0.5, 0.5],
            ["0", 0, 0.5, 0.5],
        )
        for bbox in invalid_values:
            with self.subTest(bbox=bbox):
                response = self.client.post(
                    "/api/v1/drafts",
                    headers=self.auth_headers,
                    json={"source_asset_id": asset_id, "crop_bbox": bbox},
                )
                self.assertEqual(response.status_code, 422)

    def test_recognize_rejects_too_small_bbox_already_stored_in_database(self):
        asset_id = self._create_source_asset()
        draft_id = self._create_draft(asset_id)
        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            draft.crop_bbox = [0, 0, 0.01, 0.01]
            db.commit()

        response = self.client.post(
            f"/api/v1/drafts/{draft_id}/recognize", headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 400)
        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            self.assertEqual(draft.status, DraftStatus.FAILED)
            event = db.query(DraftEvent).filter(
                DraftEvent.draft_id == draft_id,
                DraftEvent.event_type == DraftEventType.RECOGNIZE_FAIL,
            ).one()
            self.assertEqual(event.metadata_["failure_stage"], "crop")

    def test_recognize_rejects_duplicate_in_flight_but_allows_failed_retry(self):
        asset_id = self._create_source_asset()
        draft_id = self._create_draft(asset_id)
        self._set_draft_state(draft_id, DraftStatus.RECOGNIZING)

        duplicate = self.client.post(f"/api/v1/drafts/{draft_id}/recognize", headers=self.auth_headers)
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("正在识别", duplicate.json()["detail"])

        self._set_draft_state(draft_id, DraftStatus.FAILED)
        retried = self._recognize_draft_successfully(draft_id)
        self.assertTrue(retried.json()["success"])
        with self.SessionLocal() as db:
            events = db.query(DraftEvent).filter(DraftEvent.draft_id == draft_id).all()
            self.assertEqual(
                [event.event_type for event in events],
                [DraftEventType.CREATE, DraftEventType.START_RECOGNIZE, DraftEventType.RECOGNIZE_SUCCESS],
            )

    def test_recognition_uses_crop_for_layout_and_ocr_and_cleans_all_temps(self):
        asset_id = self._create_source_asset(width=200, height=100)
        response = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": asset_id, "crop_bbox": [0.25, 0.2, 0.5, 0.6]},
        )
        draft_id = response.json()["id"]
        seen: dict[str, str] = {}

        from app.services.layout_service import FigureBox, LayoutResult

        with patch.object(
            endpoints.layout_service,
            "detect",
            side_effect=lambda path: seen.update(layout=path)
            or LayoutResult(
                success=True,
                boxes=[FigureBox(bbox=[0.1, 0.1, 0.2, 0.2], label="figure", score=0.9)],
            ),
        ), patch.object(
            endpoints.draft_ocr_service,
            "recognize",
            side_effect=lambda path: seen.update(ocr=path)
            or {"success": True, "content": "raw", "cost_seconds": 0.1},
        ), patch.object(
            endpoints.nlp_service,
            "analyze",
            return_value={"success": True, "corrected_text": "clean", "tags": [], "cost_seconds": 0.1},
        ):
            recognized = self.client.post(
                f"/api/v1/drafts/{draft_id}/recognize", headers=self.auth_headers
            )

        self.assertEqual(recognized.status_code, 200)
        self.assertIn("tmp_draft_crop_", seen["layout"])
        self.assertIn("tmp_masked_", seen["ocr"])
        self.assertFalse(Path(seen["layout"]).exists())
        self.assertFalse(Path(seen["ocr"]).exists())

    def test_create_draft_returns_404_when_source_asset_missing(self):
        response = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": 999999},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("资源不存在", response.json()["detail"])

    def test_recognize_returns_404_when_draft_missing(self):
        response = self.client.post("/api/v1/drafts/999999/recognize", headers=self.auth_headers)

        self.assertEqual(response.status_code, 404)
        self.assertIn("资源不存在", response.json()["detail"])

    def test_save_to_bank_returns_404_when_draft_missing(self):
        response = self.client.post("/api/v1/drafts/999999/save-to-bank", headers=self.auth_headers)

        self.assertEqual(response.status_code, 404)
        self.assertIn("资源不存在", response.json()["detail"])

    def test_recognize_returns_400_for_non_image_asset(self):
        asset_id = self._create_source_asset(
            stored_name="asset.pdf",
            kind="pdf",
            mime="application/pdf",
            width=None,
            height=None,
        )
        draft_id = self._create_draft(asset_id)

        response = self.client.post(f"/api/v1/drafts/{draft_id}/recognize", headers=self.auth_headers)

        self.assertEqual(response.status_code, 400)
        self.assertIn("image assets only", response.json()["detail"])

    def test_save_to_bank_returns_409_when_draft_not_ready(self):
        asset_id = self._create_source_asset()
        draft_id = self._create_draft(asset_id)

        response = self.client.post(f"/api/v1/drafts/{draft_id}/save-to-bank", headers=self.auth_headers)

        self.assertEqual(response.status_code, 409)
        self.assertIn("已识别完成", response.json()["detail"])

    def test_repeated_save_to_bank_returns_409_without_duplicate_question_or_revision(self):
        asset_id = self._create_source_asset()
        draft_id = self._create_draft(asset_id)
        self._recognize_draft_successfully(draft_id)

        with patch.object(endpoints, "evaluate_question_metadata_task", return_value=None):
            first_response = self.client.post(f"/api/v1/drafts/{draft_id}/save-to-bank", headers=self.auth_headers)
        self.assertEqual(first_response.status_code, 200)
        second_response = self.client.post(f"/api/v1/drafts/{draft_id}/save-to-bank", headers=self.auth_headers)

        self.assertEqual(second_response.status_code, 409)
        self.assertIn("不能重复保存", second_response.json()["detail"])
        with self.SessionLocal() as db:
            self.assertEqual(db.query(Question).count(), 1)
            self.assertEqual(db.query(QuestionRevision).count(), 1)
            self.assertEqual(
                db.query(DraftEvent).filter(DraftEvent.event_type == DraftEventType.SAVE_TO_BANK).count(),
                1,
            )

    def test_saved_to_bank_draft_cannot_be_recognized_again(self):
        asset_id = self._create_source_asset()
        draft_id = self._create_draft(asset_id)
        self._recognize_draft_successfully(draft_id)
        with patch.object(endpoints, "evaluate_question_metadata_task", return_value=None):
            save_response = self.client.post(f"/api/v1/drafts/{draft_id}/save-to-bank", headers=self.auth_headers)
        self.assertEqual(save_response.status_code, 200)

        response = self.client.post(f"/api/v1/drafts/{draft_id}/recognize", headers=self.auth_headers)

        self.assertEqual(response.status_code, 409)
        self.assertIn("不能再次识别", response.json()["detail"])
        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            self.assertEqual(draft.status, DraftStatus.SAVED_TO_BANK)
            self.assertEqual(db.query(OCRRun).filter(OCRRun.draft_id == draft_id).count(), 1)
            self.assertEqual(db.query(LLMRun).filter(LLMRun.draft_id == draft_id).count(), 1)

    def test_question_list_and_detail_include_metadata_for_current_user_only(self):
        with self.SessionLocal() as db:
            own_question = Question(
                user_id=self.user_id,
                content="own metadata question",
                knowledge_tags=[{"label": "函数", "score": 1.0}],
                question_type="fill_blank",
                difficulty_level=2,
                difficulty_label="较易",
                difficulty_confidence=0.67,
                difficulty_reason="单一知识点基础应用。",
                metadata_status="ready",
            )
            other_user = User(
                username="13900000001",
                email="other-draft@example.com",
                phone="13900000001",
                display_name="Other Draft Tester",
                hashed_password=get_password_hash(self.TEST_PASSWORD),
                role="user",
                status=UserStatus.ACTIVE.value,
            )
            db.add_all([own_question, other_user])
            db.flush()
            db.add(
                Question(
                    user_id=other_user.id,
                    content="hidden metadata question",
                    knowledge_tags=[],
                    question_type="solution",
                    difficulty_level=5,
                    difficulty_label="压轴",
                    metadata_status="ready",
                )
            )
            db.commit()
            own_question_id = own_question.id

        list_response = self.client.get("/api/v1/questions", headers=self.auth_headers)
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], own_question_id)
        self.assertEqual(payload[0]["question_type"], "fill_blank")
        self.assertEqual(payload[0]["difficulty_level"], 2)
        self.assertEqual(payload[0]["metadata_status"], "ready")
        self.assertIsNone(payload[0]["metadata_error"])

        detail_response = self.client.get(f"/api/v1/questions/{own_question_id}", headers=self.auth_headers)
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload["difficulty_label"], "较易")
        self.assertEqual(detail_payload["difficulty_reason"], "单一知识点基础应用。")
        self.assertEqual(detail_payload["metadata_status"], "ready")


if __name__ == "__main__":
    unittest.main()
