import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash
from app.db.base import Base
from app.main import app
from app.models.question import Question
from app.models.question_figure import QuestionFigure, QuestionRevisionFigure
from app.models.question_revision import QuestionRevision
from app.models.source_asset import SourceAsset
from app.models.user import User, UserStatus
from app.services.question_content import build_legacy_v2_snapshot


class QuestionDocumentApiTests(unittest.TestCase):
    PHONE = "13900000128"
    OTHER_PHONE = "13900000129"
    PASSWORD = "Secret123!"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.upload_dir = root / "uploads"
        self.upload_dir.mkdir()
        self.old_upload_dir = settings.UPLOAD_DIR
        settings.UPLOAD_DIR = str(self.upload_dir)
        self.engine = create_engine(
            f"sqlite:///{(root / 'test.sqlite').as_posix()}",
            connect_args={"check_same_thread": False},
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(self.engine)
        with self.SessionLocal() as db:
            for phone in (self.PHONE, self.OTHER_PHONE):
                db.add(
                    User(
                        username=phone,
                        email=f"{phone}@example.com",
                        phone=phone,
                        display_name=phone,
                        hashed_password=get_password_hash(self.PASSWORD),
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
        self.headers = self._login(self.PHONE)
        self.other_headers = self._login(self.OTHER_PHONE)
        self.question_id = self._create_question()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        settings.UPLOAD_DIR = self.old_upload_dir
        self.temp_dir.cleanup()

    def _login(self, phone):
        response = self.client.post(
            "/api/v1/auth/token",
            data={"username": phone, "password": self.PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def _user_id(self, phone):
        with self.SessionLocal() as db:
            return db.query(User).filter(User.username == phone).one().id

    def _create_question(self):
        source_path = self.upload_dir / "source.png"
        Image.new("RGB", (400, 200), color=(245, 245, 245)).save(source_path)
        with self.SessionLocal() as db:
            asset = SourceAsset(
                user_id=self._user_id(self.PHONE),
                kind="image",
                original_path=source_path.name,
                mime="image/png",
                size_bytes=source_path.stat().st_size,
                width=400,
                height=200,
                sha256="question-document-source",
            )
            db.add(asset)
            db.flush()
            question = Question(
                user_id=asset.user_id,
                content="old stem",
                answer=None,
                analysis=None,
                knowledge_tags=[],
                question_type="solution",
            )
            db.add(question)
            db.flush()
            snapshot = build_legacy_v2_snapshot(content="old stem", seed=f"question:{question.id}")
            question.section_snapshot = snapshot
            revision = QuestionRevision(
                question_id=question.id,
                rev_no=1,
                content={"text": "old stem", "knowledge_tags": [], "question_type": "solution"},
                section_snapshot=snapshot,
                crop_bbox=[0.25, 0.0, 0.5, 1.0],
                source_asset_id=asset.id,
                change_reason="create",
            )
            db.add(revision)
            db.commit()
            return question.id

    @staticmethod
    def _payload(*, figure_id=None, crop_bbox=None, expected_revision_no=1):
        text_id = str(uuid.uuid4())
        blocks = [{"id": text_id, "kind": "text", "markdown": "new stem"}]
        figures = []
        if figure_id:
            area_id = str(uuid.uuid4())
            blocks.append(
                {
                    "id": area_id,
                    "kind": "image_area",
                    "height_ratio": 2.0,
                    "placements": [
                        {
                            "figure_id": figure_id,
                            "x": 0.0,
                            "y": 0.0,
                            "width": 1.0,
                            "height": 1.0,
                        }
                    ],
                }
            )
            figures.append({"id": figure_id, "kind": "crop", "crop_bbox": crop_bbox})
        return {
            "schema_version": 2,
            "expected_revision_no": expected_revision_no,
            "sections": {
                "stem": {"blocks": blocks},
                "answer": {"blocks": []},
                "analysis": {"blocks": []},
            },
            "figures": figures,
            "metadata": {
                "knowledge_tags": [{"label": "圆", "score": 1.0}],
                "question_type": "solution",
                "difficulty_level": 3,
            },
        }

    def test_atomic_document_save_creates_one_revision_and_high_resolution_crop(self):
        figure_id = str(uuid.uuid4())
        response = self.client.put(
            f"/api/v1/questions/{self.question_id}/document",
            headers=self.headers,
            json=self._payload(figure_id=figure_id, crop_bbox=[0.0, 0.0, 0.5, 1.0]),
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["revision_created"])
        self.assertEqual(body["current_revision_no"], 2)
        self.assertEqual(body["question"]["content"], "new stem")
        self.assertTrue(body["question"]["has_figure"])
        self.assertEqual(body["question"]["figures"][0]["id"], figure_id)

        with self.SessionLocal() as db:
            self.assertEqual(db.query(QuestionRevision).filter_by(question_id=self.question_id).count(), 2)
            figure = db.query(QuestionFigure).filter_by(stable_id=figure_id).one()
            self.assertEqual(figure.source_crop_bbox, [0.25, 0.0, 0.25, 1.0])
            self.assertEqual((figure.figure_asset.width, figure.figure_asset.height), (100, 200))
            latest = db.query(QuestionRevision).filter_by(question_id=self.question_id, rev_no=2).one()
            self.assertEqual(len(latest.figure_links), 1)
            self.assertEqual(latest.figure_asset_id, figure.figure_asset_id)
            question = db.get(Question, self.question_id)
            self.assertEqual(question.figure_image, figure.figure_asset.original_path)

    def test_post_commit_response_failure_keeps_committed_figure_file(self):
        figure_id = str(uuid.uuid4())
        from app.services import question_document_service

        original_build_detail = question_document_service._build_detail
        call_count = 0

        def fail_after_commit(question, revision):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("response construction failed")
            return original_build_detail(question, revision)

        with patch.object(question_document_service, "_build_detail", side_effect=fail_after_commit):
            with self.assertRaisesRegex(RuntimeError, "response construction failed"):
                self.client.put(
                    f"/api/v1/questions/{self.question_id}/document",
                    headers=self.headers,
                    json=self._payload(
                        figure_id=figure_id,
                        crop_bbox=[0.0, 0.0, 0.5, 1.0],
                    ),
                )

        with self.SessionLocal() as db:
            revision = db.query(QuestionRevision).filter_by(
                question_id=self.question_id, rev_no=2
            ).one()
            figure = db.query(QuestionFigure).filter_by(stable_id=figure_id).one()
            figure_path = self.upload_dir / figure.figure_asset.original_path
            self.assertEqual(len(revision.figure_links), 1)
            self.assertTrue(figure_path.is_file())

    def test_document_validation_error_is_structured_and_atomic(self):
        figure_a = str(uuid.uuid4())
        figure_b = str(uuid.uuid4())
        payload = self._payload(figure_id=figure_a, crop_bbox=[0.0, 0.0, 0.6, 1.0])
        area = payload["sections"]["stem"]["blocks"][1]
        area["placements"].append(
            {"figure_id": figure_b, "x": 0.5, "y": 0.0, "width": 0.5, "height": 1.0}
        )
        payload["figures"].append(
            {"id": figure_b, "kind": "crop", "crop_bbox": [0.5, 0.0, 0.5, 1.0]}
        )
        response = self.client.put(
            f"/api/v1/questions/{self.question_id}/document",
            headers=self.headers,
            json=payload,
        )
        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "question_document_invalid")
        self.assertEqual(detail["errors"][0]["code"], "placement_overlap")
        self.assertIn("block_id", detail["errors"][0])
        with self.SessionLocal() as db:
            self.assertEqual(db.query(QuestionRevision).filter_by(question_id=self.question_id).count(), 1)
            self.assertEqual(db.query(QuestionFigure).filter_by(question_id=self.question_id).count(), 0)
        self.assertEqual(list(self.upload_dir.glob("*figure*")), [])

    def test_stale_revision_returns_409_without_cropping(self):
        response = self.client.put(
            f"/api/v1/questions/{self.question_id}/document",
            headers=self.headers,
            json=self._payload(
                figure_id=str(uuid.uuid4()), crop_bbox=[0, 0, 0.5, 1], expected_revision_no=99
            ),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(list(self.upload_dir.glob("*figure*")), [])

    def test_plural_figure_blob_enforces_question_ownership(self):
        figure_id = str(uuid.uuid4())
        save = self.client.put(
            f"/api/v1/questions/{self.question_id}/document",
            headers=self.headers,
            json=self._payload(figure_id=figure_id, crop_bbox=[0.0, 0.0, 0.5, 1.0]),
        )
        self.assertEqual(save.status_code, 200, save.text)
        url = f"/api/v1/questions/{self.question_id}/figures/{figure_id}"
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url, headers=self.other_headers).status_code, 404)
        owner = self.client.get(url, headers=self.headers)
        self.assertEqual(owner.status_code, 200)
        self.assertEqual(owner.headers["content-type"], "image/jpeg")
        self.assertEqual(owner.headers["cache-control"], "private, no-store")

    def test_list_and_detail_expose_image_indicators(self):
        listing = self.client.get("/api/v1/questions", headers=self.headers)
        self.assertEqual(listing.status_code, 200)
        item = listing.json()[0]
        self.assertEqual(item["schema_version"], 2)
        self.assertTrue(item["has_question_image"])
        self.assertFalse(item["has_figure"])
        detail = self.client.get(f"/api/v1/questions/{self.question_id}", headers=self.headers)
        self.assertTrue(detail.json()["has_question_image"])

    def test_get_document_adapts_latest_snapshot_and_exact_noop_creates_no_revision(self):
        with self.SessionLocal() as db:
            question = db.get(Question, self.question_id)
            question.question_type = None
            revision = db.query(QuestionRevision).filter_by(question_id=self.question_id).one()
            revision.content = {**revision.content, "question_type": None}
            db.commit()
        detail = self.client.get(
            f"/api/v1/questions/{self.question_id}/document", headers=self.headers
        )
        self.assertEqual(detail.status_code, 200)
        document = detail.json()
        payload = {
            "schema_version": 2,
            "expected_revision_no": 1,
            "sections": document["sections"],
            "figures": [],
            "metadata": {
                "knowledge_tags": document["knowledge_tags"],
                "question_type": document["question_type"],
                "difficulty_level": document["difficulty_level"],
            },
        }
        response = self.client.put(
            f"/api/v1/questions/{self.question_id}/document",
            headers=self.headers,
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["revision_created"])
        self.assertEqual(response.json()["current_revision_no"], 1)
        with self.SessionLocal() as db:
            self.assertEqual(db.query(QuestionRevision).filter_by(question_id=self.question_id).count(), 1)

    def test_crop_overlap_is_rejected_before_files_are_created(self):
        first = str(uuid.uuid4())
        second = str(uuid.uuid4())
        payload = self._payload(figure_id=first, crop_bbox=[0.0, 0.0, 0.6, 1.0])
        area = payload["sections"]["stem"]["blocks"][1]
        area["placements"] = [
            {"figure_id": first, "x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0},
            {"figure_id": second, "x": 0.5, "y": 0.0, "width": 0.5, "height": 1.0},
        ]
        payload["figures"].append(
            {"id": second, "kind": "crop", "crop_bbox": [0.5, 0.0, 0.5, 1.0]}
        )
        response = self.client.put(
            f"/api/v1/questions/{self.question_id}/document",
            headers=self.headers,
            json=payload,
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["errors"][0]["code"], "crop_overlap")
        self.assertEqual(list(self.upload_dir.glob("*figure*")), [])

    def test_more_than_fifty_blocks_is_rejected_with_section_location(self):
        payload = self._payload()
        payload["sections"]["stem"]["blocks"] = [
            {"id": str(uuid.uuid4()), "kind": "text", "markdown": f"block {index}"}
            for index in range(51)
        ]
        response = self.client.put(
            f"/api/v1/questions/{self.question_id}/document",
            headers=self.headers,
            json=payload,
        )
        self.assertEqual(response.status_code, 422)
        error = response.json()["detail"]["errors"][0]
        self.assertEqual(error["code"], "too_many_blocks")
        self.assertEqual(error["section"], "stem")


if __name__ == "__main__":
    unittest.main()
