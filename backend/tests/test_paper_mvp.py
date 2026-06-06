import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash
from app.db.base import Base
from app.main import app
from app.models.paper import Paper
from app.models.question import Question
from app.models.question_revision import QuestionRevision
from app.models.user import User, UserStatus


class PaperMvpTests(unittest.TestCase):
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
            self.user_id = self._create_user_in_db(db, "13700000001", "paper-user@example.com")
            self.other_user_id = self._create_user_in_db(db, "13700000002", "other-paper-user@example.com")

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.auth_headers = self._login("13700000001")
        self.other_auth_headers = self._login("13700000002")

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        settings.STATIC_DIR = self._old_static_dir
        settings.UPLOAD_DIR = self._old_upload_dir
        settings.PDF_TEMP_DIR = self._old_pdf_temp_dir
        self.temp_dir.cleanup()

    def _create_user_in_db(self, db, phone: str, email: str) -> int:
        user = User(
            username=phone,
            email=email,
            phone=phone,
            display_name=f"User {phone}",
            hashed_password=get_password_hash(self.TEST_PASSWORD),
            role="user",
            status=UserStatus.ACTIVE.value,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id

    def _login(self, phone: str) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/token",
            data={"username": phone, "password": self.TEST_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def _create_question(
        self,
        *,
        user_id: int | None = None,
        content: str = "question content",
        tags: list[dict] | None = None,
        revision_content: dict | None = None,
        question_type: str | None = None,
        difficulty_level: int | None = None,
        difficulty_label: str | None = None,
        metadata_status: str | None = None,
    ) -> int:
        with self.SessionLocal() as db:
            question = Question(
                user_id=user_id or self.user_id,
                content=content,
                knowledge_tags=tags or [{"label": "algebra", "score": 1.0}],
                origin_image="question.png",
                question_type=question_type,
                difficulty_level=difficulty_level,
                difficulty_label=difficulty_label,
                metadata_status=metadata_status,
            )
            db.add(question)
            db.flush()
            if revision_content is not None:
                db.add(
                    QuestionRevision(
                        question_id=question.id,
                        rev_no=1,
                        content=revision_content,
                        change_reason="test_seed",
                    )
                )
            db.commit()
            db.refresh(question)
            return question.id

    def _create_paper(self, question_ids: list[int], headers: dict[str, str] | None = None):
        return self.client.post(
            "/api/v1/papers",
            headers=headers or self.auth_headers,
            json={
                "title": "Unit Test Paper",
                "description": "manual selection",
                "items": [
                    {"question_id": question_id, "score": index + 1}
                    for index, question_id in enumerate(question_ids)
                ],
            },
        )

    def test_login_user_can_create_paper_with_own_questions(self):
        question_id = self._create_question(content="own question")

        response = self._create_paper([question_id])

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["title"], "Unit Test Paper")
        self.assertEqual(payload["status"], "draft")
        self.assertEqual(payload["item_count"], 1)
        self.assertEqual(payload["total_score"], 1.0)
        self.assertEqual(payload["items"][0]["question_id"], question_id)
        self.assertEqual(payload["items"][0]["content_snapshot"], "own question")

    def test_created_paper_can_be_fetched_by_id(self):
        question_id = self._create_question(content="detail question")
        create_response = self._create_paper([question_id])
        self.assertEqual(create_response.status_code, 200)
        paper_id = create_response.json()["id"]

        response = self.client.get(f"/api/v1/papers/{paper_id}", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], paper_id)
        self.assertEqual(payload["items"][0]["content_snapshot"], "detail question")

    def test_list_papers_only_returns_current_user_papers(self):
        own_question_id = self._create_question(content="own list question")
        other_question_id = self._create_question(user_id=self.other_user_id, content="other list question")
        own_response = self._create_paper([own_question_id])
        other_response = self._create_paper([other_question_id], headers=self.other_auth_headers)
        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(other_response.status_code, 200)

        response = self.client.get("/api/v1/papers", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        paper_ids = [item["id"] for item in response.json()]
        self.assertIn(own_response.json()["id"], paper_ids)
        self.assertNotIn(other_response.json()["id"], paper_ids)

    def test_create_paper_rejects_missing_question_id(self):
        response = self._create_paper([999999])

        self.assertEqual(response.status_code, 404)

    def test_create_paper_rejects_duplicate_question_id(self):
        question_id = self._create_question()

        response = self._create_paper([question_id, question_id])

        self.assertEqual(response.status_code, 409)

    def test_paper_item_position_follows_request_order(self):
        first_question_id = self._create_question(content="first")
        second_question_id = self._create_question(content="second")
        third_question_id = self._create_question(content="third")

        response = self._create_paper([second_question_id, first_question_id, third_question_id])

        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(
            [(item["question_id"], item["position"]) for item in items],
            [(second_question_id, 1), (first_question_id, 2), (third_question_id, 3)],
        )

    def test_content_snapshot_does_not_change_when_question_content_changes(self):
        question_id = self._create_question(content="snapshot before edit")
        create_response = self._create_paper([question_id])
        self.assertEqual(create_response.status_code, 200)
        paper_id = create_response.json()["id"]

        update_response = self.client.put(
            f"/api/v1/questions/{question_id}",
            headers=self.auth_headers,
            json={"content": "snapshot after edit"},
        )
        self.assertEqual(update_response.status_code, 200)

        response = self.client.get(f"/api/v1/papers/{paper_id}", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["content_snapshot"], "snapshot before edit")

    def test_paper_item_prefers_question_revision_snapshot(self):
        question_id = self._create_question(
            content="question table content",
            revision_content={
                "text": "revision content",
                "answer": "revision answer",
                "analysis": "revision analysis",
                "knowledge_tags": [{"label": "function", "score": 1.0}],
            },
        )

        response = self._create_paper([question_id])

        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["content_snapshot"], "revision content")
        self.assertEqual(item["answer_snapshot"], "revision answer")
        self.assertEqual(item["analysis_snapshot"], "revision analysis")
        self.assertEqual(item["knowledge_tags_snapshot"], [{"label": "function", "score": 1.0}])

    def test_paper_item_snapshots_question_metadata(self):
        question_id = self._create_question(
            content="metadata question",
            question_type="single_choice",
            difficulty_level=4,
            difficulty_label="较难",
            metadata_status="ready",
        )

        response = self._create_paper([question_id])

        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["question_type_snapshot"], "single_choice")
        self.assertEqual(item["difficulty_level_snapshot"], 4)
        self.assertEqual(item["difficulty_label_snapshot"], "较难")

    def test_paper_item_allows_pending_question_metadata_with_empty_difficulty_snapshot(self):
        question_id = self._create_question(
            content="pending metadata question",
            question_type="single_choice",
            difficulty_level=4,
            difficulty_label="较难",
            metadata_status="pending",
        )

        response = self._create_paper([question_id])

        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertIsNone(item["question_type_snapshot"])
        self.assertIsNone(item["difficulty_level_snapshot"])
        self.assertIsNone(item["difficulty_label_snapshot"])

    def test_other_user_question_is_hidden_as_not_found(self):
        other_question_id = self._create_question(user_id=self.other_user_id, content="hidden")

        response = self._create_paper([other_question_id])

        self.assertEqual(response.status_code, 404)

        with self.SessionLocal() as db:
            self.assertEqual(db.query(Paper).count(), 0)
