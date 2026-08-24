import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash
from app.db.base import Base
from app.main import app
from app.models.question import Question
from app.models.question_revision import QuestionRevision
from app.models.source_asset import SourceAsset
from app.models.user import User, UserStatus


class PaperItemFigureTests(unittest.TestCase):
    """PaperItem figure snapshots and the in-paper figure channel (#59)."""

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
            self.user_id = self._create_user_in_db(db, "13700002001", "figure-user@example.com")
            self.other_user_id = self._create_user_in_db(db, "13700002002", "other-figure-user@example.com")

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.auth_headers = self._login("13700002001")
        self.other_auth_headers = self._login("13700002002")

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

    def _seed_question(
        self,
        *,
        user_id: int | None = None,
        content: str = "figured question",
        question_type: str | None = "solution",
        figure_file: tuple[str, bytes] | None = None,
        revision_asset: tuple[str, bytes] | None = None,
    ) -> int:
        """Seed a question. ``revision_asset`` attaches a #58-style figure asset
        to the latest revision; ``figure_file`` only sets the question-level
        reference (fallback path of the snapshot rule)."""
        with self.SessionLocal() as db:
            question = Question(
                user_id=user_id or self.user_id,
                content=content,
                origin_image="origin.png",
                question_type=question_type,
                difficulty_level=3,
                difficulty_label="中等",
                metadata_status="ready",
            )
            if figure_file is not None:
                name, data = figure_file
                (self.upload_dir / name).write_bytes(data)
                question.figure_image = name
            db.add(question)
            db.flush()

            if revision_asset is not None:
                name, data = revision_asset
                (self.upload_dir / name).write_bytes(data)
                asset = SourceAsset(
                    user_id=user_id or self.user_id,
                    kind="figure",
                    original_path=name,
                    normalized_path=None,
                    mime="image/jpeg",
                    size_bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                )
                db.add(asset)
                db.flush()
                db.add(
                    QuestionRevision(
                        question_id=question.id,
                        rev_no=1,
                        content={"text": content},
                        change_reason="test_seed",
                        figure_asset_id=asset.id,
                    )
                )
            db.commit()
            db.refresh(question)
            return question.id

    def _create_paper(self, question_ids: list[int], headers=None, title: str = "Figure Paper") -> int:
        response = self.client.post(
            "/api/v1/papers",
            headers=headers or self.auth_headers,
            json={
                "title": title,
                "description": "paper figures",
                "items": [
                    {"question_id": question_id, "score": index + 1}
                    for index, question_id in enumerate(question_ids)
                ],
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    def _items_by_question(self, paper_id: int) -> dict[int, dict]:
        response = self.client.get(f"/api/v1/papers/{paper_id}", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        return {item["question_id"]: item for item in response.json()["items"]}

    def _set_snapshot_directly(self, paper_id: int, paper_item_id: int, value: str | None) -> None:
        from app.models.paper import PaperItem

        with self.SessionLocal() as db:
            item = db.query(PaperItem).filter(
                PaperItem.id == paper_item_id, PaperItem.paper_id == paper_id
            ).first()
            self.assertIsNotNone(item)
            item.figure_image_snapshot = value
            db.commit()

    def _image(self, paper_id: int, paper_item_id: int, headers=None):
        return self.client.get(
            f"/api/v1/papers/{paper_id}/items/{paper_item_id}/image",
            headers=headers if headers is not None else self.auth_headers,
        )

    def _render(self, paper_id: int):
        return self.client.post(f"/api/v1/papers/{paper_id}/render-model", headers=self.auth_headers, json={})

    def _pdf(self, paper_id: int):
        return self.client.post(f"/api/v1/papers/{paper_id}/pdf", headers=self.auth_headers, json={})

    # --- snapshot creation semantics -------------------------------------

    def test_create_paper_freezes_figure_snapshot_from_revision_and_fallback(self):
        revision_question = self._seed_question(
            content="with revision asset",
            revision_asset=("rev_fig.jpg", b"revision-figure-bytes"),
        )
        fallback_question = self._seed_question(
            content="question level only",
            figure_file=("qlevel_fig.jpg", b"question-level-figure-bytes"),
        )

        paper_id = self._create_paper([revision_question, fallback_question])
        items = self._items_by_question(paper_id)

        self.assertEqual(items[revision_question]["figure_image_snapshot"], "rev_fig.jpg")
        self.assertEqual(items[fallback_question]["figure_image_snapshot"], "qlevel_fig.jpg")

    def test_plain_question_yields_empty_figure_snapshot(self):
        plain_question = self._seed_question(content="no figure at all")

        paper_id = self._create_paper([plain_question])
        items = self._items_by_question(paper_id)

        self.assertIsNone(items[plain_question]["figure_image_snapshot"])

    def test_later_source_question_change_does_not_alter_historical_paper(self):
        question_id = self._seed_question(revision_asset=("original.jpg", b"original-figure"))
        paper_id = self._create_paper([question_id])
        paper_item_id = self._items_by_question(paper_id)[question_id]["id"]

        # The user re-crops the figure on the source question afterwards.
        with self.SessionLocal() as db:
            asset = SourceAsset(
                user_id=self.user_id,
                kind="figure",
                original_path="replaced.jpg",
                mime="image/jpeg",
                size_bytes=len(b"replaced-figure"),
                sha256=hashlib.sha256(b"replaced-figure").hexdigest(),
            )
            db.add(asset)
            db.flush()
            db.add(
                QuestionRevision(
                    question_id=question_id,
                    rev_no=2,
                    content={"text": "x"},
                    change_reason="test_recrop",
                    figure_asset_id=asset.id,
                )
            )
            question = db.query(Question).filter(Question.id == question_id).first()
            question.figure_image = "replaced.jpg"
            db.commit()

        rendered = self._render(paper_id)
        served = self._image(paper_id, paper_item_id)

        self.assertEqual(rendered.status_code, 200)
        item = rendered.json()["sections"][0]["items"][0]
        self.assertEqual(item["figure_image_url"], f"/api/v1/papers/{paper_id}/items/{paper_item_id}/image")
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served.content, b"original-figure")

    # --- render model JSON hygiene ---------------------------------------

    def test_render_model_exposes_figure_url_without_paths_or_base64(self):
        figured = self._seed_question(content="figured", revision_asset=("figured.jpg", b"fig"))
        plain = self._seed_question(content="plain")
        paper_id = self._create_paper([figured, plain])
        items = self._items_by_question(paper_id)

        response = self._render(paper_id)

        self.assertEqual(response.status_code, 200)
        flat_items = [item for section in response.json()["sections"] for item in section["items"]]
        urls = {item["question_id"]: item["figure_image_url"] for item in flat_items}
        self.assertEqual(urls[figured], f"/api/v1/papers/{paper_id}/items/{items[figured]['id']}/image")
        self.assertIsNone(urls[plain])
        self.assertNotIn("data:image", response.text)
        self.assertNotIn(str(self.upload_dir), response.text)

    # --- in-paper image endpoint authz matrix -----------------------------

    def test_owner_receives_frozen_figure_bytes(self):
        question_id = self._seed_question(figure_file=("owner.jpg", b"owner-figure-bytes"))
        paper_id = self._create_paper([question_id])
        paper_item_id = self._items_by_question(paper_id)[question_id]["id"]

        response = self._image(paper_id, paper_item_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"owner-figure-bytes")
        self.assertTrue(response.headers["content-type"].startswith("image/jpeg"))

    def test_legacy_static_uploads_prefix_snapshot_still_resolves(self):
        question_id = self._seed_question(figure_file=("legacy.jpg", b"legacy-bytes"))
        paper_id = self._create_paper([question_id])
        paper_item_id = self._items_by_question(paper_id)[question_id]["id"]
        self._set_snapshot_directly(paper_id, paper_item_id, "/static/uploads/legacy.jpg")

        response = self._image(paper_id, paper_item_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"legacy-bytes")

    def test_endpoint_authz_matrix_follows_papers_404_convention(self):
        figured = self._seed_question(content="figured", revision_asset=("authz.jpg", b"authz-bytes"))
        other_owned = self._seed_question(user_id=self.other_user_id, content="foreign")
        plain = self._seed_question(content="second")
        own_paper = self._create_paper([figured], title="Own Paper")
        second_own_paper = self._create_paper([plain], title="Second Own Paper")
        foreign_paper = self._create_paper([other_owned], headers=self.other_auth_headers, title="Foreign Paper")

        own_item = self._items_by_question(own_paper)[figured]["id"]
        second_own_item = self._items_by_question(second_own_paper)[plain]["id"]

        # Unauthenticated callers are rejected by auth itself, before any
        # resource lookup; everything else follows the papers 404 convention.
        self.assertEqual(self._image(own_paper, own_item, headers={}).status_code, 401)

        hidden_cases = {
            "missing paper": self._image(999999, own_item).status_code,
            "cross-user paper": self._image(foreign_paper, own_item).status_code,
            "foreign paper with its own viewer": self.client.get(
                f"/api/v1/papers/{foreign_paper}/items/{own_item}/image",
                headers=self.other_auth_headers,
            ).status_code,
            "item belongs to another own paper": self._image(own_paper, second_own_item).status_code,
            "missing item": self._image(own_paper, 999999).status_code,
        }

        for label, status_code in hidden_cases.items():
            with self.subTest(case=label):
                self.assertEqual(status_code, 404)

    def test_empty_or_missing_or_traversal_snapshots_return_404(self):
        plain = self._seed_question(content="plain")
        ghost = self._seed_question(content="ghost", figure_file=("ghost.jpg", b"will-be-deleted"))
        traversal = self._seed_question(content="traversal")
        paper_id = self._create_paper([plain, ghost, traversal])
        items = self._items_by_question(paper_id)

        (self.upload_dir / "ghost.jpg").unlink()
        self._set_snapshot_directly(paper_id, items[traversal]["id"], "../../secret.jpg")

        self.assertEqual(self._image(paper_id, items[plain]["id"]).status_code, 404)
        self.assertEqual(self._image(paper_id, items[ghost]["id"]).status_code, 404)
        self.assertEqual(self._image(paper_id, items[traversal]["id"]).status_code, 404)

    # --- HTML/PDF embedding ------------------------------------------------

    @patch("app.api.v1.endpoints.pdf_generation_service.generate_pdf", return_value=b"%PDF-1.7 fig")
    def test_pdf_embeds_data_uri_and_relaxes_csp_only_for_figured_papers(self, generate_pdf):
        figured = self._seed_question(content="figured", revision_asset=("embed.jpg", b"embed-me"))
        plain = self._seed_question(content="plain")
        figured_paper = self._create_paper([figured])
        plain_paper = self._create_paper([plain])

        figured_response = self._pdf(figured_paper)
        plain_response = self._pdf(plain_paper)

        self.assertEqual(figured_response.status_code, 200)
        self.assertEqual(plain_response.status_code, 200)
        figured_html = generate_pdf.call_args_list[0].args[0]
        plain_html = generate_pdf.call_args_list[1].args[0]

        self.assertIn("data:image/jpeg;base64,", figured_html)
        self.assertIn('class="question-figure"', figured_html)
        self.assertIn("img-src data:", figured_html)
        self.assertIn(".question-figure { max-width: 100%", figured_html)

        self.assertNotIn("<img", plain_html.lower())
        self.assertNotIn(".question-figure", plain_html)
        self.assertIn("img-src &#x27;none&#x27;", plain_html)

    @patch("app.api.v1.endpoints.pdf_generation_service.generate_pdf", return_value=b"%PDF-1.7 fig")
    def test_pdf_names_the_oversized_question_and_refuses_to_generate(self, generate_pdf):
        oversized = self._seed_question(
            content="too big",
            revision_asset=("huge.jpg", b"\xff" * (5 * 1024 * 1024)),
        )
        paper_id = self._create_paper([oversized])

        response = self._pdf(paper_id)

        self.assertEqual(response.status_code, 413)
        self.assertIn("第 1 题", response.json()["detail"])
        generate_pdf.assert_not_called()


if __name__ == "__main__":
    unittest.main()
