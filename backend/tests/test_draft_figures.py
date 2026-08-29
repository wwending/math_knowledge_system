"""Draft-flow figure detection & per-question figure storage (#58).

Covers: recognize masks figure regions before OCR, degrade paths keep the
pre-#58 behavior, save-to-bank crops the confirmed figure from the original
asset, and the authenticated /questions/{id}/figure endpoint.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import endpoints
from app.core.config import settings
from app.core.constants import DraftStatus
from app.core.database import get_db
from app.core.security import get_password_hash
from app.db.base import Base
from app.main import app
from app.models.draft import Draft
from app.models.question import Question
from app.models.question_figure import QuestionFigure, QuestionRevisionFigure
from app.models.question_revision import QuestionRevision
from app.models.source_asset import SourceAsset
from app.models.user import User, UserStatus
from app.services.draft_image_service import compose_bbox_to_page
from app.services.layout_service import FigureBox, LayoutResult


class DraftFigureTests(unittest.TestCase):
    TEST_PHONE = "13900000021"
    OTHER_PHONE = "13900000022"
    TEST_PASSWORD = "Secret123!"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root_dir = Path(self.temp_dir.name)
        self.static_dir = root_dir / "static"
        self.upload_dir = root_dir / "uploads"
        self.pdf_temp_dir = root_dir / "pdf_temp"
        self.static_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_temp_dir.mkdir(parents=True, exist_ok=True)

        self._old_static_dir = settings.STATIC_DIR
        self._old_upload_dir = settings.UPLOAD_DIR
        self._old_pdf_temp_dir = settings.PDF_TEMP_DIR
        self._old_layout_enabled = settings.LAYOUT_ENABLED
        self._old_min_area = settings.LAYOUT_MIN_AREA_RATIO
        settings.STATIC_DIR = str(self.static_dir)
        settings.UPLOAD_DIR = str(self.upload_dir)
        settings.PDF_TEMP_DIR = str(self.pdf_temp_dir)
        # The conftest autouse fixture disables detection for hermeticity; these
        # suites exercise the endpoint path with a patched service instead.
        settings.LAYOUT_ENABLED = True

        db_path = root_dir / "test.sqlite"
        self.engine = create_engine(
            f"sqlite:///{db_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        with self.SessionLocal() as db:
            for phone, email in (
                (self.TEST_PHONE, "figure-tester@example.com"),
                (self.OTHER_PHONE, "figure-other@example.com"),
            ):
                db.add(
                    User(
                        username=phone,
                        email=email,
                        phone=phone,
                        display_name=f"User {phone}",
                        hashed_password=get_password_hash(self.TEST_PASSWORD),
                        role="user",
                        status=UserStatus.ACTIVE.value,
                    )
                )
            db.commit()

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.auth_headers = self._login(self.TEST_PHONE)
        self.other_headers = self._login(self.OTHER_PHONE)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        settings.STATIC_DIR = self._old_static_dir
        settings.UPLOAD_DIR = self._old_upload_dir
        settings.PDF_TEMP_DIR = self._old_pdf_temp_dir
        settings.LAYOUT_ENABLED = self._old_layout_enabled
        settings.LAYOUT_MIN_AREA_RATIO = self._old_min_area
        self.temp_dir.cleanup()

    def _login(self, phone: str) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/token",
            data={"username": phone, "password": self.TEST_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def _create_image_asset(self, stored_name: str = "asset.png", width: int = 200, height: int = 100) -> int:
        Image.new("RGB", (width, height), color=(240, 240, 240)).save(
            self.upload_dir / stored_name, format="PNG"
        )
        with self.SessionLocal() as db:
            asset = SourceAsset(
                user_id=self._user_id_for(phone=self.TEST_PHONE),
                kind="image",
                original_path=stored_name,
                normalized_path=None,
                mime="image/png",
                size_bytes=(self.upload_dir / stored_name).stat().st_size,
                width=width,
                height=height,
                sha256=f"{stored_name}-draft-figure-test-sha",
            )
            db.add(asset)
            db.commit()
            db.refresh(asset)
            return asset.id

    def _user_id_for(self, phone: str) -> int:
        with self.SessionLocal() as db:
            return db.query(User).filter(User.username == phone).one().id

    def _create_draft(self, asset_id: int) -> int:
        response = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": asset_id},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    def _ready_draft_with_content(self) -> tuple[int, int]:
        asset_id = self._create_image_asset()
        draft_id = self._create_draft(asset_id)
        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            draft.status = DraftStatus.DRAFT_READY
            draft.current_content = {"text": "clean math text", "knowledge_tags": []}
            db.commit()
        return draft_id, asset_id

    @staticmethod
    def _layout_result(boxes=None, success=True, error_type=None):
        return LayoutResult(success=success, boxes=list(boxes or []), error_type=error_type)

    def _recognize(self, draft_id: int, *, detect_result, ocr_capture: dict):
        def fake_recognize(path):
            ocr_capture["path"] = path
            return {"success": True, "content": "raw math text", "cost_seconds": 0.1}

        with patch.object(
            endpoints.layout_service, "detect", return_value=detect_result
        ), patch.object(
            endpoints.draft_ocr_service, "recognize", side_effect=fake_recognize
        ), patch.object(
            endpoints.nlp_service,
            "analyze",
            return_value={"success": True, "corrected_text": "clean", "tags": [], "cost_seconds": 0.2},
        ):
            return self.client.post(f"/api/v1/drafts/{draft_id}/recognize", headers=self.auth_headers)

    # -- recognize pipeline --------------------------------------------------

    def test_recognize_masks_figure_regions_before_ocr_and_reports_detection(self):
        draft_id, asset_id = self._ready_draft_with_content()
        original_path = str(self.upload_dir / "asset.png")
        ocr_capture: dict = {}
        detect_result = self._layout_result(
            boxes=[FigureBox(bbox=[0.25, 0.25, 0.5, 0.5], label="figure", score=0.9)]
        )

        response = self._recognize(draft_id, detect_result=detect_result, ocr_capture=ocr_capture)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], DraftStatus.DRAFT_READY)
        self.assertEqual(len(payload["detected_figures"]), 1)
        self.assertEqual(payload["detected_figures"][0]["bbox"], [0.25, 0.25, 0.5, 0.5])
        self.assertEqual(payload["detected_figures"][0]["label"], "figure")
        # OCR must receive a masked temp image, not the original asset pixels.
        self.assertNotEqual(ocr_capture["path"], original_path)
        self.assertTrue(ocr_capture["path"].endswith(".jpg"))
        self.assertFalse(Path(ocr_capture["path"]).exists(), "masked temp must be cleaned up")
        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            self.assertEqual(draft.detected_figures[0]["bbox"], [0.25, 0.25, 0.5, 0.5])

    def test_recognize_without_figures_sends_original_image_to_ocr(self):
        draft_id, _ = self._ready_draft_with_content()
        original_path = str(self.upload_dir / "asset.png")
        ocr_capture: dict = {}

        response = self._recognize(draft_id, detect_result=self._layout_result([]), ocr_capture=ocr_capture)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detected_figures"], [])
        self.assertEqual(ocr_capture["path"], original_path)

    def test_recognize_degrades_when_layout_times_out(self):
        draft_id, _ = self._ready_draft_with_content()
        ocr_capture: dict = {}

        response = self._recognize(
            draft_id,
            detect_result=self._layout_result(success=False, error_type="timeout"),
            ocr_capture=ocr_capture,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], DraftStatus.DRAFT_READY)
        self.assertEqual(payload["detected_figures"], [])
        self.assertEqual(ocr_capture["path"], str(self.upload_dir / "asset.png"))

    def test_recognize_degrades_when_layout_crashes(self):
        draft_id, _ = self._ready_draft_with_content()
        ocr_capture: dict = {}

        def crashing_detect(path):
            raise RuntimeError("boom")

        with patch.object(
            endpoints.layout_service, "detect", side_effect=crashing_detect
        ), patch.object(
            endpoints.draft_ocr_service,
            "recognize",
            side_effect=lambda path: ocr_capture.update(path=path)
            or {"success": True, "content": "raw", "cost_seconds": 0.1},
        ), patch.object(
            endpoints.nlp_service,
            "analyze",
            return_value={"success": True, "corrected_text": "clean", "tags": [], "cost_seconds": 0.2},
        ):
            response = self.client.post(f"/api/v1/drafts/{draft_id}/recognize", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detected_figures"], [])
        self.assertEqual(ocr_capture["path"], str(self.upload_dir / "asset.png"))

    # -- save-to-bank figure storage ------------------------------------------

    def test_save_to_bank_crops_confirmed_figure_and_stores_per_question_asset(self):
        draft_id, _ = self._ready_draft_with_content()

        save_response = self.client.post(
            f"/api/v1/drafts/{draft_id}/save-to-bank",
            headers=self.auth_headers,
            json={"figure_bbox": [0.1, 0.2, 0.5, 0.5]},
        )
        self.assertEqual(save_response.status_code, 200)
        question_id = save_response.json()["question_id"]

        with self.SessionLocal() as db:
            question = db.query(Question).filter(Question.id == question_id).one()
            revision = db.query(QuestionRevision).filter(
                QuestionRevision.question_id == question_id
            ).one()
            self.assertEqual(question.figure_crop_bbox, [0.1, 0.2, 0.5, 0.5])
            self.assertIsNotNone(question.figure_image)
            self.assertIsNotNone(revision.figure_asset_id)
            figure_asset = db.query(SourceAsset).filter(
                SourceAsset.id == revision.figure_asset_id
            ).one()
            self.assertEqual(figure_asset.kind, "figure")
            self.assertEqual((figure_asset.width, figure_asset.height), (100, 50))
            question_figure = db.query(QuestionFigure).filter_by(question_id=question_id).one()
            revision_link = db.query(QuestionRevisionFigure).filter_by(
                question_revision_id=revision.id,
                question_figure_id=question_figure.id,
            ).one()
            self.assertEqual(revision_link.question_id, question_id)
            self.assertEqual(question_figure.source_asset_id, revision.source_asset_id)
            self.assertEqual(question_figure.figure_asset_id, figure_asset.id)
            self.assertEqual(question_figure.source_crop_bbox, [0.1, 0.2, 0.5, 0.5])
            self.assertEqual(question.section_snapshot, revision.section_snapshot)
            self.assertEqual(question.section_snapshot["schema_version"], 2)
            placement = question.section_snapshot["sections"]["stem"]["blocks"][1]["placements"][0]
            self.assertEqual(placement["figure_id"], question_figure.stable_id)
            figure_file = self.upload_dir / (figure_asset.normalized_path or figure_asset.original_path)
            self.assertTrue(figure_file.is_file())

        with Image.open(figure_file) as img:
            self.assertEqual(img.size, (100, 50))

        image_response = self.client.get(
            f"/api/v1/questions/{question_id}/figure", headers=self.auth_headers
        )
        self.assertEqual(image_response.status_code, 200)
        self.assertIn("image/", image_response.headers.get("content-type", ""))

    def test_figure_bbox_composition_does_not_apply_question_crop_minimum(self):
        self.assertEqual(
            compose_bbox_to_page([0.25, 0.2, 0.5, 0.6], [0.2, 0.25, 0.01, 0.01]),
            [0.35, 0.35, 0.005, 0.006],
        )

    def test_save_to_bank_keeps_small_figure_in_small_question_crop(self):
        # The figure occupies 4% of the crop (above LAYOUT_MIN_AREA_RATIO in
        # crop-relative space) but under 1% of the page once composed. Save must
        # validate in crop-relative space so the figure is not silently dropped.
        asset_id = self._create_image_asset(width=200, height=100)
        create_response = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": asset_id, "crop_bbox": [0.25, 0.2, 0.1, 0.1]},
        )
        self.assertEqual(create_response.status_code, 200)
        draft_id = create_response.json()["id"]
        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            draft.status = DraftStatus.DRAFT_READY
            draft.current_content = {"text": "clean math text", "knowledge_tags": []}
            db.commit()

        response = self.client.post(
            f"/api/v1/drafts/{draft_id}/save-to-bank",
            headers=self.auth_headers,
            json={"figure_bbox": [0, 0, 0.2, 0.2]},
        )
        self.assertEqual(response.status_code, 200)
        with self.SessionLocal() as db:
            question = db.query(Question).filter(Question.id == response.json()["question_id"]).one()
            self.assertEqual(question.figure_crop_bbox, [0.25, 0.2, 0.02, 0.02])
            self.assertIsNotNone(question.figure_image)
            revision = db.query(QuestionRevision).filter(
                QuestionRevision.question_id == question.id
            ).one()
            self.assertIsNotNone(revision.figure_asset_id)

    def test_save_to_bank_composes_crop_relative_figure_bbox_to_page_coordinates(self):
        asset_id = self._create_image_asset(width=200, height=100)
        create_response = self.client.post(
            "/api/v1/drafts",
            headers=self.auth_headers,
            json={"source_asset_id": asset_id, "crop_bbox": [0.25, 0.2, 0.5, 0.6]},
        )
        self.assertEqual(create_response.status_code, 200)
        draft_id = create_response.json()["id"]
        with self.SessionLocal() as db:
            draft = db.query(Draft).filter(Draft.id == draft_id).one()
            draft.status = DraftStatus.DRAFT_READY
            draft.current_content = {"text": "clean math text", "knowledge_tags": []}
            db.commit()

        response = self.client.post(
            f"/api/v1/drafts/{draft_id}/save-to-bank",
            headers=self.auth_headers,
            json={"figure_bbox": [0.2, 0.25, 0.4, 0.5]},
        )
        self.assertEqual(response.status_code, 200)
        with self.SessionLocal() as db:
            question = db.query(Question).filter(Question.id == response.json()["question_id"]).one()
            self.assertEqual(question.figure_crop_bbox, [0.35, 0.35, 0.2, 0.3])
            revision = db.query(QuestionRevision).filter(
                QuestionRevision.question_id == question.id
            ).one()
            figure_asset = db.query(SourceAsset).filter(
                SourceAsset.id == revision.figure_asset_id
            ).one()
            self.assertEqual((figure_asset.width, figure_asset.height), (40, 30))

    def test_save_to_bank_persists_all_confirmed_figures_in_one_image_area(self):
        draft_id, _ = self._ready_draft_with_content()
        response = self.client.post(
            f"/api/v1/drafts/{draft_id}/save-to-bank",
            headers=self.auth_headers,
            json={
                "figure_bboxes": [
                    [0.5, 0.0, 0.5, 0.5],
                    [0.0, 0.0, 0.5, 0.4],
                ]
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        question_id = response.json()["question_id"]

        with self.SessionLocal() as db:
            question = db.query(Question).filter_by(id=question_id).one()
            revision = db.query(QuestionRevision).filter_by(question_id=question_id).one()
            figures = sorted(
                db.query(QuestionFigure).filter_by(question_id=question_id).all(),
                key=lambda figure: (figure.source_crop_bbox[1], figure.source_crop_bbox[0]),
            )
            self.assertEqual(len(figures), 2)
            self.assertEqual(len(revision.figure_links), 2)
            self.assertIsNone(question.figure_image)
            self.assertIsNone(question.figure_crop_bbox)
            self.assertIsNone(revision.figure_asset_id)
            self.assertEqual([figure.source_crop_bbox for figure in figures], [
                [0.0, 0.0, 0.5, 0.4],
                [0.5, 0.0, 0.5, 0.5],
            ])
            blocks = question.section_snapshot["sections"]["stem"]["blocks"]
            self.assertEqual([block["kind"] for block in blocks], ["text", "image_area"])
            area = blocks[1]
            self.assertEqual(area["height_ratio"], 0.25)
            self.assertEqual([placement["figure_id"] for placement in area["placements"]], [
                figure.stable_id for figure in figures
            ])
            self.assertEqual(area["placements"][0]["width"], 0.5)
            self.assertEqual(area["placements"][0]["height"], 0.8)
            self.assertEqual(area["placements"][1]["x"], 0.5)
            self.assertEqual(area["placements"][1]["height"], 1.0)

        document = self.client.get(
            f"/api/v1/questions/{question_id}/document", headers=self.auth_headers
        )
        self.assertEqual(document.status_code, 200)
        self.assertEqual(len(document.json()["figures"]), 2)
        self.assertTrue(document.json()["has_figure"])
        self.assertEqual(
            self.client.get(
                f"/api/v1/questions/{question_id}/figure", headers=self.auth_headers
            ).status_code,
            404,
        )

    def test_save_to_bank_rejects_overlapping_figures_and_ambiguous_fields(self):
        draft_id, _ = self._ready_draft_with_content()
        overlap = self.client.post(
            f"/api/v1/drafts/{draft_id}/save-to-bank",
            headers=self.auth_headers,
            json={"figure_bboxes": [[0, 0, 0.6, 0.5], [0.5, 0, 0.5, 0.5]]},
        )
        self.assertEqual(overlap.status_code, 422)
        self.assertEqual(overlap.json()["detail"]["errors"][0]["code"], "figure_bbox_overlap")

        ambiguous = self.client.post(
            f"/api/v1/drafts/{draft_id}/save-to-bank",
            headers=self.auth_headers,
            json={"figure_bboxes": [], "figure_bbox": None},
        )
        self.assertEqual(ambiguous.status_code, 422)
        with self.SessionLocal() as db:
            self.assertEqual(db.query(Question).count(), 0)

    def test_save_to_bank_rejects_invalid_figure_bbox_atomically(self):
        draft_id, _ = self._ready_draft_with_content()

        response = self.client.post(
            f"/api/v1/drafts/{draft_id}/save-to-bank",
            headers=self.auth_headers,
            json={"figure_bboxes": [[1.5, 0.2, 0.5, 0.5]]},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["errors"][0]["code"], "invalid_figure_bbox")

        with self.SessionLocal() as db:
            self.assertEqual(db.query(Question).count(), 0)
            draft = db.query(Draft).filter_by(id=draft_id).one()
            self.assertEqual(draft.status, DraftStatus.DRAFT_READY)
        self.assertEqual(list(self.upload_dir.glob("*figure*")), [])

    def test_figure_relational_failure_rolls_back_partial_figure_state(self):
        draft_id, _ = self._ready_draft_with_content()

        with patch.object(
            endpoints, "build_draft_v2_snapshot", side_effect=RuntimeError("snapshot failure")
        ):
            with self.assertRaisesRegex(RuntimeError, "snapshot failure"):
                self.client.post(
                    f"/api/v1/drafts/{draft_id}/save-to-bank",
                    headers=self.auth_headers,
                    json={"figure_bboxes": [[0.1, 0.2, 0.5, 0.5]]},
                )

        with self.SessionLocal() as db:
            self.assertEqual(db.query(Question).count(), 0)
            self.assertEqual(db.query(QuestionRevision).count(), 0)
            self.assertEqual(db.query(QuestionFigure).count(), 0)
            self.assertEqual(db.query(QuestionRevisionFigure).count(), 0)
            draft = db.query(Draft).filter_by(id=draft_id).one()
            self.assertEqual(draft.status, DraftStatus.DRAFT_READY)
        self.assertEqual(list(self.upload_dir.glob("*figure*")), [])

    def test_save_to_bank_without_body_keeps_pre58_behavior(self):
        draft_id, _ = self._ready_draft_with_content()

        response = self.client.post(f"/api/v1/drafts/{draft_id}/save-to-bank", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        question_id = response.json()["question_id"]

        with self.SessionLocal() as db:
            question = db.query(Question).filter(Question.id == question_id).one()
            self.assertIsNone(question.figure_image)
            revision = db.query(QuestionRevision).filter(
                QuestionRevision.question_id == question_id
            ).one()
            self.assertIsNone(revision.figure_asset_id)

    def test_second_user_cannot_fetch_foreign_question_figure(self):
        draft_id, _ = self._ready_draft_with_content()
        save_response = self.client.post(
            f"/api/v1/drafts/{draft_id}/save-to-bank",
            headers=self.auth_headers,
            json={"figure_bbox": [0.1, 0.2, 0.5, 0.5]},
        )
        question_id = save_response.json()["question_id"]

        unauthenticated = self.client.get(f"/api/v1/questions/{question_id}/figure")
        self.assertEqual(unauthenticated.status_code, 401)

        foreign = self.client.get(
            f"/api/v1/questions/{question_id}/figure", headers=self.other_headers
        )
        self.assertEqual(foreign.status_code, 404)

        unknown = self.client.get("/api/v1/questions/999999/figure", headers=self.auth_headers)
        self.assertEqual(unknown.status_code, 404)


if __name__ == "__main__":
    unittest.main()
