import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import endpoints
from app.core.config import settings
from app.core.constants import PDF_TEMP_TTL_SECONDS
from app.core.database import get_db
from app.core.security import get_password_hash
from app.db.base import Base
from app.main import app
from app.models.user import User, UserStatus


class LegacyUploadLimitTests(unittest.TestCase):
    """Bounded uploads for the legacy /recognize and /upload_pdf endpoints (#103).

    Both endpoints previously streamed request bodies to disk without a size cap;
    upload_pdf also rendered an unbounded number of pages and left every artifact
    in pdf_temp forever.
    """

    TEST_PHONE = "13800000099"
    TEST_PASSWORD = "Secret123!"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root_dir = Path(self.temp_dir.name)
        self.static_dir = root_dir / "static"
        # New layout (#103): pdf_temp lives outside the publicly mounted static dir.
        self.upload_dir = root_dir / "uploads"
        self.pdf_temp_dir = root_dir / "pdf_temp"
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
                email="limits@example.com",
                phone=self.TEST_PHONE,
                display_name="Tester",
                hashed_password=get_password_hash(self.TEST_PASSWORD),
                role="user",
                status=UserStatus.ACTIVE.value,
            )
            db.add(user)
            db.commit()

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

    @staticmethod
    def _write_pdf(path: Path, page_count: int) -> bytes:
        document = fitz.open()
        try:
            for _ in range(page_count):
                document.new_page()
            document.save(str(path))
        finally:
            document.close()
        return path.read_bytes()

    def test_recognize_rejects_oversized_upload(self):
        with patch.object(endpoints, "MAX_ASSET_SIZE_BYTES", 100):
            response = self.client.post(
                "/api/v1/recognize",
                headers=self.auth_headers,
                files={"file": ("question.png", b"x" * 200, "image/png")},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"], "File too large")
        self.assertEqual(os.listdir(self.upload_dir), [])

    def test_upload_pdf_rejects_oversized_file(self):
        with patch.object(endpoints, "MAX_ASSET_SIZE_BYTES", 100):
            response = self.client.post(
                "/api/v1/upload_pdf",
                headers=self.auth_headers,
                files={"file": ("paper.pdf", b"%PDF-1.4 " + b"x" * 200, "application/pdf")},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"], "File too large")
        self.assertEqual(os.listdir(self.pdf_temp_dir), [])

    def test_upload_pdf_rejects_too_many_pages(self):
        pdf_path = Path(self.temp_dir.name) / "many_pages.pdf"
        payload = self._write_pdf(pdf_path, 3)
        with patch.object(endpoints, "MAX_PDF_PAGES", 2):
            response = self.client.post(
                "/api/v1/upload_pdf",
                headers=self.auth_headers,
                files={"file": ("paper.pdf", payload, "application/pdf")},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"], endpoints.PDF_TOO_MANY_PAGES_MESSAGE)
        self.assertEqual(os.listdir(self.pdf_temp_dir), [])

    def test_upload_pdf_accepts_small_pdf(self):
        pdf_path = Path(self.temp_dir.name) / "one_page.pdf"
        payload = self._write_pdf(pdf_path, 1)
        response = self.client.post(
            "/api/v1/upload_pdf",
            headers=self.auth_headers,
            files={"file": ("paper.pdf", payload, "application/pdf")},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["total_pages"], 1)
        self.assertEqual(len(body["images"]), 1)

    def test_upload_pdf_sweeps_stale_pdf_temp_files(self):
        stale_path = self.pdf_temp_dir / "stale.jpg"
        stale_path.write_bytes(b"stale")
        fresh_path = self.pdf_temp_dir / "fresh.txt"
        fresh_path.write_bytes(b"fresh")
        stale_time = time.time() - PDF_TEMP_TTL_SECONDS - 60
        os.utime(stale_path, (stale_time, stale_time))

        pdf_path = Path(self.temp_dir.name) / "one_page.pdf"
        payload = self._write_pdf(pdf_path, 1)
        response = self.client.post(
            "/api/v1/upload_pdf",
            headers=self.auth_headers,
            files={"file": ("paper.pdf", payload, "application/pdf")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(stale_path.exists())
        self.assertTrue(fresh_path.exists())


if __name__ == "__main__":
    unittest.main()
