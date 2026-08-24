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
from app.models.draft import Draft
from app.models.source_asset import SourceAsset
from app.models.user import User, UserStatus

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-image-bytes"
IMAGE_FILENAME = "sample-crop.png"


class DraftImageAccessTests(unittest.TestCase):
    """Regression coverage for the authenticated draft image channel (#22).

    Ownership is asserted on the Draft row on purpose (same rationale as the
    question image endpoint in #44): SourceAsset rows are globally deduplicated
    by sha256, so the asset row itself carries no owner semantics.
    """

    TEST_PASSWORD = "Secret123!"
    IMAGE_URL_PREFIX = "/api/v1/drafts"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root_dir = Path(self.temp_dir.name)
        self.static_dir = root_dir / "static"
        # #44 layout: uploads live outside the publicly mounted static dir.
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
            self.owner_user_id = self._create_user_in_db(db, "13700000021", "draft-owner@example.com")
            self.other_user_id = self._create_user_in_db(db, "13700000022", "draft-other@example.com")
            self.owner_asset_id = self._create_asset_in_db(
                db,
                user_id=self.owner_user_id,
                original_path=IMAGE_FILENAME,
            )
            self.owner_draft_id = self._create_draft_in_db(
                db,
                user_id=self.owner_user_id,
                source_asset_id=self.owner_asset_id,
            )
            # Models what the sha256 dedup path produces: the second user's own
            # draft references stored bytes that originated from another user.
            self.shared_draft_id = self._create_draft_in_db(
                db,
                user_id=self.other_user_id,
                source_asset_id=self.owner_asset_id,
            )
            self.missing_file_draft_id = self._create_draft_in_db(
                db,
                user_id=self.owner_user_id,
                source_asset_id=self._create_asset_in_db(
                    db,
                    user_id=self.owner_user_id,
                    original_path="deleted-from-disk.png",
                ),
            )
            self.empty_path_draft_id = self._create_draft_in_db(
                db,
                user_id=self.owner_user_id,
                source_asset_id=self._create_asset_in_db(
                    db,
                    user_id=self.owner_user_id,
                    original_path="",
                ),
            )

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.owner_headers = self._login("13700000021")
        self.other_headers = self._login("13700000022")

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

    def _create_asset_in_db(self, db, *, user_id: int, original_path: str) -> int:
        asset = SourceAsset(
            user_id=user_id,
            kind="image",
            original_path=original_path,
            normalized_path=None,
            mime="image/png",
            size_bytes=len(PNG_BYTES),
            sha256=f"sha256-test-{db.query(SourceAsset).count() + 1}",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset.id

    def _create_draft_in_db(self, db, *, user_id: int, source_asset_id: int) -> int:
        draft = Draft(
            user_id=user_id,
            source_asset_id=source_asset_id,
            crop_bbox={},
            status="draft_ready",
            current_content={"text": "recognized content", "knowledge_tags": []},
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return draft.id

    def _login(self, phone: str) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/token",
            data={"username": phone, "password": self.TEST_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def test_unauthenticated_request_cannot_fetch_draft_image(self):
        response = self.client.get(f"{self.IMAGE_URL_PREFIX}/{self.owner_draft_id}/image")
        self.assertEqual(response.status_code, 401)

    def test_non_owner_receives_403_for_foreign_draft_image(self):
        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{self.owner_draft_id}/image",
            headers=self.other_headers,
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_receives_draft_image_bytes(self):
        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{self.owner_draft_id}/image",
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PNG_BYTES)
        self.assertTrue(response.headers["content-type"].startswith("image/"))

    def test_shared_asset_bytes_readable_via_own_draft(self):
        # The second user owns the referencing draft even though the underlying
        # asset/file originated from the first user (sha256 dedup).
        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{self.shared_draft_id}/image",
            headers=self.other_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PNG_BYTES)

    def test_missing_asset_file_returns_404(self):
        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{self.missing_file_draft_id}/image",
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_asset_without_resolvable_path_returns_404(self):
        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{self.empty_path_draft_id}/image",
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_path_traversal_outside_upload_dir_is_rejected(self):
        # A tampered DB row pointing outside the uploads dir must not be served.
        secret_path = Path(self.temp_dir.name) / "secret.txt"
        secret_path.write_text("top secret", encoding="utf-8")
        with self.SessionLocal() as db:
            traversal_draft_id = self._create_draft_in_db(
                db,
                user_id=self.owner_user_id,
                source_asset_id=self._create_asset_in_db(
                    db,
                    user_id=self.owner_user_id,
                    original_path="../secret.txt",
                ),
            )

        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{traversal_draft_id}/image",
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_legacy_static_prefix_asset_path_resolves(self):
        with self.SessionLocal() as db:
            legacy_draft_id = self._create_draft_in_db(
                db,
                user_id=self.owner_user_id,
                source_asset_id=self._create_asset_in_db(
                    db,
                    user_id=self.owner_user_id,
                    original_path=f"/static/uploads/{IMAGE_FILENAME}",
                ),
            )

        response = self.client.get(
            f"{self.IMAGE_URL_PREFIX}/{legacy_draft_id}/image",
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PNG_BYTES)


if __name__ == "__main__":
    unittest.main()
