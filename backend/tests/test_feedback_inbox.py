import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash
from app.db.base import Base
from app.main import app
from app.models.user import User, UserStatus
from app.services import feedback_service


def _png_bytes() -> bytes:
    """A real 1x1 PNG — the endpoint PIL-verifies uploads, so fabricated bytes
    that merely claim image/png must not be used for happy paths."""
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1)).save(buffer, format="PNG")
    return buffer.getvalue()


class FeedbackInboxTests(unittest.TestCase):
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
            self.user_id = self._create_user_in_db(db, "13700000001", "feedback-user@example.com")
            self.other_user_id = self._create_user_in_db(db, "13700000002", "other-feedback-user@example.com")
            self.admin_user_id = self._create_user_in_db(
                db, "13700000003", "admin-user@example.com", role="admin"
            )

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
        self.admin_auth_headers = self._login("13700000003")

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        settings.STATIC_DIR = self._old_static_dir
        settings.UPLOAD_DIR = self._old_upload_dir
        settings.PDF_TEMP_DIR = self._old_pdf_temp_dir
        self.temp_dir.cleanup()

    def _create_user_in_db(self, db, phone: str, email: str, role: str = "user") -> int:
        user = User(
            username=phone,
            email=email,
            phone=phone,
            display_name=f"User {phone}",
            hashed_password=get_password_hash(self.TEST_PASSWORD),
            role=role,
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

    # --- helpers -----------------------------------------------------------

    def _create_feedback(
        self,
        headers: dict[str, str],
        *,
        content: str = "组卷导出 PDF 报错",
        category: str = "bug",
        png_count: int = 0,
        raw_files: list[tuple[bytes, str, str]] | None = None,
    ) -> dict:
        # Field name must match the endpoint parameter: "screenshots".
        files: list[tuple[str, tuple[str, bytes, str]]] = [
            ("screenshots", (f"shot{i}.png", _png_bytes(), "image/png"))
            for i in range(png_count)
        ]
        for blob, name, mime in raw_files or []:
            files.append(("screenshots", (name, blob, mime)))
        response = self.client.post(
            "/api/v1/feedback",
            data={"content": content, "category": category},
            files=files,
            headers=headers,
        )
        return response

    def _upload_dir_files(self) -> set[str]:
        return {path.name for path in self.upload_dir.iterdir() if path.is_file()}

    def _set_status(self, feedback_id: int, status: str, review_note: str | None = None):
        return self.client.patch(
            f"/api/v1/admin/feedback/{feedback_id}/status",
            json={"status": status, "review_note": review_note},
            headers=self.admin_auth_headers,
        )

    # --- create ------------------------------------------------------------

    def test_create_without_screenshot_returns_pending(self):
        response = self._create_feedback(self.auth_headers)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["category"], "bug")
        self.assertEqual(body["screenshots"], [])
        self.assertIsNone(body["review_note"])

    def test_create_with_two_screenshots_stores_files(self):
        response = self._create_feedback(self.auth_headers, png_count=2)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["screenshots"]), 2)
        for shot in body["screenshots"]:
            self.assertTrue(shot["url"].startswith("/api/v1/feedback/"))
        self.assertEqual(len(self._upload_dir_files()), 2)

    def test_create_five_screenshots_boundary_ok(self):
        response = self._create_feedback(self.auth_headers, png_count=5)
        self.assertEqual(response.status_code, 200)

    def test_create_over_limit_rejected_without_leftovers(self):
        response = self._create_feedback(self.auth_headers, png_count=6)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(feedback_service.FEEDBACK_SCREENSHOT_LIMIT_MESSAGE, response.json()["detail"])
        self.assertEqual(self._upload_dir_files(), set())

    def test_create_content_too_long_422(self):
        response = self._create_feedback(self.auth_headers, content="字" * 501)
        self.assertEqual(response.status_code, 422)

    def test_create_whitespace_only_content_400(self):
        response = self._create_feedback(self.auth_headers, content="   \n  ")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], feedback_service.FEEDBACK_CONTENT_EMPTY_MESSAGE)

    def test_create_invalid_category_422(self):
        response = self._create_feedback(self.auth_headers, category="other")
        self.assertEqual(response.status_code, 422)

    def test_create_pdf_mime_rejected_even_though_shared_assets_allow_it(self):
        response = self._create_feedback(
            self.auth_headers,
            raw_files=[(b"%PDF-1.4 fake", "doc.pdf", "application/pdf")],
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], feedback_service.UNSUPPORTED_IMAGE_TYPE_MESSAGE)
        self.assertEqual(self._upload_dir_files(), set())

    def test_create_corrupt_image_400_without_leftover(self):
        response = self._create_feedback(
            self.auth_headers,
            raw_files=[(b"\x89PNG\r\n\x1a\n this is not really a png", "fake.png", "image/png")],
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], feedback_service.INVALID_IMAGE_FILE_MESSAGE)
        self.assertEqual(self._upload_dir_files(), set())

    def test_create_mixed_valid_then_corrupt_cleans_valid_one(self):
        response = self._create_feedback(
            self.auth_headers,
            raw_files=[(_png_bytes(), "good.png", "image/png"), (b"broken", "bad.png", "image/png")],
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._upload_dir_files(), set())

    def test_create_oversize_413_without_leftover(self):
        with mock.patch.object(feedback_service, "MAX_ASSET_SIZE_BYTES", 64):
            response = self._create_feedback(
                self.auth_headers,
                raw_files=[(b"x" * 4096, "big.png", "image/png")],
            )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self._upload_dir_files(), set())

    def test_create_unauthenticated_401(self):
        response = self.client.post(
            "/api/v1/feedback",
            data={"content": "hi", "category": "bug"},
        )
        self.assertIn(response.status_code, (401, 403))

    # --- visibility / list -------------------------------------------------

    def test_list_shows_only_own_rows(self):
        self._create_feedback(self.auth_headers)
        self._create_feedback(self.auth_headers, content="第二条")
        self._create_feedback(self.other_auth_headers, content="别人的反馈")

        mine = self.client.get("/api/v1/feedback", headers=self.auth_headers).json()
        theirs = self.client.get("/api/v1/feedback", headers=self.other_auth_headers).json()
        self.assertEqual(mine["total"], 2)
        self.assertEqual(theirs["total"], 1)
        self.assertTrue(all(item["content"] != "别人的反馈" for item in mine["items"]))

    def test_list_filters_by_category_and_status(self):
        self._create_feedback(self.auth_headers, category="bug")
        feature = self._create_feedback(self.auth_headers, content="希望支持深色模式", category="feature").json()

        bugs = self.client.get(
            "/api/v1/feedback", params={"category": "bug"}, headers=self.auth_headers
        ).json()
        self.assertEqual(bugs["total"], 1)

        self._set_status(feature["id"], "adopted")
        adopted = self.client.get(
            "/api/v1/feedback", params={"status": "adopted"}, headers=self.auth_headers
        ).json()
        self.assertEqual([item["id"] for item in adopted["items"]], [feature["id"]])

    # --- edit ---------------------------------------------------------------

    def test_edit_pending_content_and_category(self):
        feedback = self._create_feedback(self.auth_headers).json()
        response = self.client.patch(
            f"/api/v1/feedback/{feedback['id']}",
            data={"content": "更新后的描述", "category": "suggestion"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "更新后的描述")
        self.assertEqual(response.json()["category"], "suggestion")

    def test_edit_replace_screenshots_updates_disk(self):
        created = self._create_feedback(self.auth_headers, png_count=2).json()
        old_ids = [shot["id"] for shot in created["screenshots"]]
        old_files = set(self._upload_dir_files())

        response = self.client.patch(
            f"/api/v1/feedback/{created['id']}",
            data={"remove_screenshot_ids": str(old_ids[0])},
            files=[("new_screenshots", ("new.png", _png_bytes(), "image/png"))],
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["screenshots"]), 2)
        remaining_ids = {shot["id"] for shot in body["screenshots"]}
        self.assertNotIn(old_ids[0], remaining_ids)

        current_files = self._upload_dir_files()
        self.assertEqual(len(current_files), 2)
        self.assertTrue(old_files - current_files, "被移除的截图文件应从磁盘删除")

    def test_edit_remove_all_screenshots(self):
        created = self._create_feedback(self.auth_headers, png_count=2).json()
        ids = ",".join(str(shot["id"]) for shot in created["screenshots"])
        response = self.client.patch(
            f"/api/v1/feedback/{created['id']}",
            data={"remove_screenshot_ids": ids},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["screenshots"], [])
        self.assertEqual(self._upload_dir_files(), set())

    def test_edit_adding_beyond_limit_400(self):
        created = self._create_feedback(self.auth_headers, png_count=4).json()
        response = self.client.patch(
            f"/api/v1/feedback/{created['id']}",
            files=[
                ("new_screenshots", ("a.png", _png_bytes(), "image/png")),
                ("new_screenshots", ("b.png", _png_bytes(), "image/png")),
            ],
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._upload_dir_files().__len__(), 4)

    def test_edit_unknown_and_malformed_remove_ids_tolerated(self):
        created = self._create_feedback(self.auth_headers, png_count=1).json()
        response = self.client.patch(
            f"/api/v1/feedback/{created['id']}",
            data={"remove_screenshot_ids": "abc,999999"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["screenshots"]), 1)

    def test_edit_after_processed_409(self):
        created = self._create_feedback(self.auth_headers).json()
        self._set_status(created["id"], "rejected", "重复反馈")
        response = self.client.patch(
            f"/api/v1/feedback/{created['id']}",
            data={"content": "试图改已处理的"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 409)

    def test_edit_other_users_row_404(self):
        created = self._create_feedback(self.other_auth_headers).json()
        response = self.client.patch(
            f"/api/v1/feedback/{created['id']}",
            data={"content": "改别人的"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 404)

    def test_empty_patch_returns_row_unchanged(self):
        created = self._create_feedback(self.auth_headers, content="原始内容").json()
        response = self.client.patch(
            f"/api/v1/feedback/{created['id']}", data={}, headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "原始内容")

    # --- withdraw -----------------------------------------------------------

    def test_withdraw_own_pending_removes_rows_and_files(self):
        created = self._create_feedback(self.auth_headers, png_count=1).json()
        self.assertEqual(len(self._upload_dir_files()), 1)
        response = self.client.delete(
            f"/api/v1/feedback/{created['id']}", headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], feedback_service.FEEDBACK_WITHDRAWN_MESSAGE)
        listed = self.client.get("/api/v1/feedback", headers=self.auth_headers).json()
        self.assertEqual(listed["total"], 0)
        self.assertEqual(self._upload_dir_files(), set())

    def test_withdraw_after_processed_409(self):
        created = self._create_feedback(self.auth_headers).json()
        self._set_status(created["id"], "adopted")
        response = self.client.delete(
            f"/api/v1/feedback/{created['id']}", headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 409)

    def test_withdraw_foreign_404(self):
        created = self._create_feedback(self.other_auth_headers).json()
        response = self.client.delete(
            f"/api/v1/feedback/{created['id']}", headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 404)

    # --- screenshot serving --------------------------------------------------

    def test_screenshot_owner_and_admin_can_read(self):
        created = self._create_feedback(self.auth_headers, png_count=1).json()
        url = created["screenshots"][0]["url"]
        owner_response = self.client.get(url, headers=self.auth_headers)
        self.assertEqual(owner_response.status_code, 200)
        self.assertTrue(owner_response.headers["content-type"].startswith("image/"))
        admin_response = self.client.get(url, headers=self.admin_auth_headers)
        self.assertEqual(admin_response.status_code, 200)

    def test_screenshot_other_user_404(self):
        created = self._create_feedback(self.auth_headers, png_count=1).json()
        url = created["screenshots"][0]["url"]
        response = self.client.get(url, headers=self.other_auth_headers)
        self.assertEqual(response.status_code, 404)

    def test_screenshot_missing_target_404(self):
        created = self._create_feedback(self.auth_headers).json()
        response = self.client.get(
            f"/api/v1/feedback/{created['id']}/screenshots/999999", headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 404)

    # --- admin surface --------------------------------------------------------

    def test_admin_list_requires_admin(self):
        response = self.client.get("/api/v1/admin/feedback", headers=self.auth_headers)
        self.assertEqual(response.status_code, 403)

    def test_admin_list_sees_all_with_attribution(self):
        mine = self._create_feedback(self.auth_headers, png_count=1).json()
        other = self._create_feedback(self.other_auth_headers, content="他人反馈").json()

        response = self.client.get("/api/v1/admin/feedback", headers=self.admin_auth_headers)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 2)
        by_id = {item["id"]: item for item in body["items"]}
        self.assertEqual(by_id[mine["id"]]["submitter_phone"], "13700000001")
        self.assertEqual(by_id[other["id"]]["submitter_display_name"], "User 13700000002")
        self.assertEqual(by_id[mine["id"]]["user_id"], self.user_id)

    def test_admin_list_q_filters_content_and_submitter(self):
        target = self._create_feedback(self.auth_headers, content="深色模式需求").json()
        self._create_feedback(self.other_auth_headers, content="无关内容")

        by_content = self.client.get(
            "/api/v1/admin/feedback", params={"q": "深色"}, headers=self.admin_auth_headers
        ).json()
        self.assertEqual([item["id"] for item in by_content["items"]], [target["id"]])

        by_submitter = self.client.get(
            "/api/v1/admin/feedback", params={"q": "13700000002"}, headers=self.admin_auth_headers
        ).json()
        self.assertEqual(by_submitter["total"], 1)

    def test_admin_set_status_with_note_visible_to_submitter(self):
        created = self._create_feedback(self.auth_headers).json()
        response = self._set_status(created["id"], "adopted", "下个迭代排期")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "adopted")
        self.assertEqual(body["review_note"], "下个迭代排期")

        own = self.client.get("/api/v1/feedback", headers=self.auth_headers).json()
        self.assertEqual(own["items"][0]["status"], "adopted")
        self.assertEqual(own["items"][0]["review_note"], "下个迭代排期")

    def test_admin_free_transition_correction(self):
        created = self._create_feedback(self.auth_headers).json()
        self._set_status(created["id"], "rejected", "误判")
        back = self._set_status(created["id"], "pending", None)
        self.assertEqual(back.status_code, 200)
        self.assertEqual(back.json()["status"], "pending")
        self.assertIsNone(back.json()["review_note"])

    def test_admin_status_validation_errors(self):
        created = self._create_feedback(self.auth_headers).json()
        bad_enum = self._set_status(created["id"], "closed")
        self.assertEqual(bad_enum.status_code, 422)
        long_note = self.client.patch(
            f"/api/v1/admin/feedback/{created['id']}/status",
            json={"status": "adopted", "review_note": "x" * 501},
            headers=self.admin_auth_headers,
        )
        self.assertEqual(long_note.status_code, 422)

    def test_admin_set_status_missing_404(self):
        response = self._set_status(999999, "adopted")
        self.assertEqual(response.status_code, 404)

    # --- export ---------------------------------------------------------------

    def test_export_default_markdown_contains_pending_only(self):
        pending = self._create_feedback(self.auth_headers, png_count=1).json()
        adopted = self._create_feedback(self.other_auth_headers, content="已采纳项", category="feature").json()
        self._set_status(adopted["id"], "adopted")

        response = self.client.get("/api/v1/admin/feedback/export", headers=self.admin_auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/markdown"))
        text = response.text
        self.assertTrue(text.startswith("# 用户反馈导出"))
        self.assertIn(f"#{pending['id']}", text)
        self.assertIn("[问题]", text)
        self.assertIn("13700000001", text)
        self.assertIn(str(self.upload_dir), text)
        self.assertNotIn(f"#{adopted['id']} ", text.split("# 用户反馈导出")[1][:200])
        self.assertNotIn("已采纳项", text)

    def test_export_json_shape_with_absolute_paths(self):
        created = self._create_feedback(self.auth_headers, png_count=2).json()
        response = self.client.get(
            "/api/v1/admin/feedback/export",
            params={"format": "json"},
            headers=self.admin_auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["count"], 1)
        item = payload["items"][0]
        self.assertEqual(item["id"], created["id"])
        self.assertEqual(item["submitter"]["phone"], "13700000001")
        self.assertEqual(len(item["screenshot_files"]), 2)
        for path in item["screenshot_files"]:
            self.assertTrue(Path(path).is_absolute())
            self.assertIn(str(self.upload_dir), path)
            self.assertTrue(Path(path).is_file())
        self.assertIn("exported_at", payload)

    def test_export_status_filter_adopts(self):
        adopted = self._create_feedback(self.auth_headers).json()
        self._create_feedback(self.other_auth_headers, content="仍待处理")
        self._set_status(adopted["id"], "adopted")

        response = self.client.get(
            "/api/v1/admin/feedback/export",
            params={"format": "json", "status": "adopted"},
            headers=self.admin_auth_headers,
        )
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["id"], adopted["id"])

    def test_export_empty_result_is_valid(self):
        for fmt in ("markdown", "json"):
            response = self.client.get(
                "/api/v1/admin/feedback/export", params={"format": fmt}, headers=self.admin_auth_headers
            )
            self.assertEqual(response.status_code, 200)
            if fmt == "markdown":
                self.assertIn("共 0 条", response.text)
            else:
                self.assertEqual(response.json()["count"], 0)

    def test_export_requires_admin(self):
        response = self.client.get("/api/v1/admin/feedback/export", headers=self.auth_headers)
        self.assertEqual(response.status_code, 403)

    def test_export_bad_format_422(self):
        response = self.client.get(
            "/api/v1/admin/feedback/export",
            params={"format": "csv"},
            headers=self.admin_auth_headers,
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
