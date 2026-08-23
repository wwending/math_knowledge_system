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
from app.models.question import Question
from app.models.user import User, UserStatus

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-image-bytes"
IMAGE_FILENAME = "sample-image.png"


class QuestionImageAccessTests(unittest.TestCase):
    """Regression coverage for authenticated question image access (#44).

    Ownership is asserted on the Question row: SourceAsset rows are globally
    deduplicated by sha256, so different users may legitimately reference the
    same stored bytes through their own questions.
    """

    TEST_PASSWORD = "Secret123!"
    IMAGE_URL_PREFIX = "/api/v1/questions"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root_dir = Path(self.temp_dir.name)
        self.static_dir = root_dir / "static"
        # New layout (#44): uploads live outside the publicly mounted static dir.
        self.upload_dir = root_dir / "uploads"
        self.pdf_temp_dir = root_dir / "pdf_temp"
        self.static_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_temp_dir.mkdir(parents=True, exist_ok=True)
        (self.upload_dir / IMAGE_FILENAME).write_bytes(PNG_BYTES)

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
            self.owner_user_id = self._create_user_in_db(db, "13700000011", "image-owner@example.com")
            self.other_user_id = self._create_user_in_db(db, "13700000012", "image-other@example.com")
            self.owner_question_id = self._create_question_in_db(
                db,
                user_id=self.owner_user_id,
                origin_image=IMAGE_FILENAME,
                content="owner question",
            )
            # Same stored filename as the owner's image: models what the sha256
            # dedup path produces when a second user's crop resolves to an
            # existing asset row owned by someone else.
            self.shared_question_id = self._create_question_in_db(
                db,
                user_id=self.other_user_id,
                origin_image=IMAGE_FILENAME,
                content="other-user question sharing the same asset bytes",
            )
            self.imageless_question_id = self._create_question_in_db(
                db,
                user_id=self.owner_user_id,
                origin_image=None,
                content="question without image",
            )

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.owner_headers = self._login("13700000011")
        self.other_headers = self._login("13700000012")

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

    def _create_question_in_db(self, db, *, user_id: int, origin_image, content: str) -> int:
        question = Question(user_id=user_id, origin_image=origin_image, content=content)
        db.add(question)
        db.commit()
        db.refresh(question)
        return question.id

    def _login(self, phone: str) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/token",
            data={"username": phone, "password": self.TEST_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def test_unauthenticated_request_cannot_fetch_question_image(self):
        response = self.client.get(f"{self.IMAGE_URL_PREFIX}/{self.owner_question_id}/image")
        self.assertEqual(response.status_code, 401)

    def test_non_owner_receives_403_for_foreign_question_image(self):
        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{self.owner_question_id}/image",
            headers=self.other_headers,
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_receives_image_bytes(self):
        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{self.owner_question_id}/image",
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PNG_BYTES)
        self.assertTrue(response.headers["content-type"].startswith("image/"))

    def test_shared_asset_bytes_stay_readable_via_own_question(self):
        # The second user owns the referencing question even though the underlying
        # asset/file originated from the first user (sha256 dedup).
        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{self.shared_question_id}/image",
            headers=self.other_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PNG_BYTES)

    def test_missing_image_returns_404(self):
        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{self.imageless_question_id}/image",
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_path_traversal_outside_upload_dir_is_rejected(self):
        # A tampered DB row pointing outside the uploads dir must not be served.
        secret_path = Path(self.temp_dir.name) / "secret.txt"
        secret_path.write_text("top secret", encoding="utf-8")
        with self.SessionLocal() as db:
            question = Question(
                user_id=self.owner_user_id,
                origin_image="../secret.txt",
                content="traversal question",
            )
            db.add(question)
            db.commit()
            db.refresh(question)
            question_id = question.id

        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{question_id}/image",
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_legacy_static_prefix_values_resolve_against_relocated_uploads(self):
        with self.SessionLocal() as db:
            question = Question(
                user_id=self.owner_user_id,
                origin_image=f"/static/uploads/{IMAGE_FILENAME}",
                content="legacy url-shaped origin_image",
            )
            db.add(question)
            db.commit()
            db.refresh(question)
            question_id = question.id

        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{question_id}/image",
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PNG_BYTES)

    def test_api_responses_point_to_authenticated_image_endpoint(self):
        list_response = self.client.get(
            "/api/v1/questions?limit=50",
            headers=self.owner_headers,
        )
        self.assertEqual(list_response.status_code, 200)
        listed = {item["id"]: item for item in list_response.json()}
        self.assertEqual(
            listed[self.owner_question_id]["image_url"],
            f"{self.IMAGE_URL_PREFIX}/{self.owner_question_id}/image",
        )

        detail_response = self.client.get(
            f"/api/v1/questions/{self.owner_question_id}",
            headers=self.owner_headers,
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(
            detail_response.json()["image_url"],
            f"{self.IMAGE_URL_PREFIX}/{self.owner_question_id}/image",
        )

        history_response = self.client.get("/api/v1/history?limit=50", headers=self.owner_headers)
        self.assertEqual(history_response.status_code, 200)
        history_by_id = {item["id"]: item for item in history_response.json()}
        self.assertEqual(
            history_by_id[self.owner_question_id]["image_url"],
            f"{self.IMAGE_URL_PREFIX}/{self.owner_question_id}/image",
        )

    def test_public_static_mount_no_longer_serves_uploads(self):
        response = self.client.get(f"/static/uploads/{IMAGE_FILENAME}")
        self.assertEqual(response.status_code, 404)

    def test_upload_dir_inside_static_dir_is_rejected(self):
        settings.UPLOAD_DIR = str(self.static_dir / "uploads")
        try:
            with self.assertRaises(RuntimeError):
                settings.validate_upload_dir_isolation()
        finally:
            settings.UPLOAD_DIR = str(self.upload_dir)


if __name__ == "__main__":
    unittest.main()
