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
from app.models.paper import Paper, PaperItem
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

    def _update_paper(
        self,
        paper_id: int,
        payload: dict,
        headers: dict[str, str] | None = None,
    ):
        return self.client.patch(
            f"/api/v1/papers/{paper_id}",
            headers=headers or self.auth_headers,
            json=payload,
        )

    @staticmethod
    def _existing_item(item: dict, **changes) -> dict:
        payload = {
            "kind": "existing",
            "id": item["id"],
            "question_id": item["question_id"],
            "score": item["score"] or 0,
            "content_snapshot": item["content_snapshot"],
            "answer_snapshot": item["answer_snapshot"],
            "analysis_snapshot": item["analysis_snapshot"],
        }
        payload.update(changes)
        return payload

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

    def test_owner_updates_metadata_score_and_snapshots_without_changing_question_bank(self):
        question_id = self._create_question(
            content="question table original",
            revision_content={
                "text": "revision original",
                "answer": "answer original",
                "analysis": "analysis original",
            },
        )
        created = self._create_paper([question_id]).json()
        original_updated_at = created["updated_at"]

        response = self._update_paper(
            created["id"],
            {
                "title": "  Edited Paper  ",
                "description": "  edited description  ",
                "items": [
                    self._existing_item(
                        created["items"][0],
                        score=12.5,
                        content_snapshot="试卷专用修改后的题干",
                        answer_snapshot="paper-only answer",
                        analysis_snapshot="paper-only analysis",
                    )
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["title"], "Edited Paper")
        self.assertEqual(payload["description"], "edited description")
        self.assertEqual(payload["total_score"], 12.5)
        self.assertNotEqual(payload["updated_at"], original_updated_at)
        self.assertEqual(payload["items"][0]["content_snapshot"], "试卷专用修改后的题干")
        self.assertEqual(payload["items"][0]["answer_snapshot"], "paper-only answer")
        self.assertEqual(payload["items"][0]["analysis_snapshot"], "paper-only analysis")

        detail = self.client.get(f"/api/v1/papers/{created['id']}", headers=self.auth_headers).json()
        listing = self.client.get("/api/v1/papers", headers=self.auth_headers).json()
        listed = next(item for item in listing if item["id"] == created["id"])
        self.assertEqual(detail, payload)
        self.assertEqual((listed["title"], listed["item_count"], listed["total_score"]), ("Edited Paper", 1, 12.5))

        with self.SessionLocal() as db:
            question = db.query(Question).filter(Question.id == question_id).one()
            revision = (
                db.query(QuestionRevision)
                .filter(QuestionRevision.question_id == question_id)
                .order_by(QuestionRevision.rev_no.desc())
                .first()
            )
            self.assertEqual(question.content, "question table original")
            self.assertEqual(revision.content["text"], "revision original")
            self.assertEqual(revision.content["answer"], "answer original")
            self.assertEqual(revision.content["analysis"], "analysis original")

    def test_two_items_can_swap_positions_and_positions_remain_contiguous(self):
        first_id = self._create_question(content="first")
        second_id = self._create_question(content="second")
        created = self._create_paper([first_id, second_id]).json()

        response = self._update_paper(
            created["id"],
            {
                "title": created["title"],
                "description": created["description"],
                "items": [
                    self._existing_item(created["items"][1]),
                    self._existing_item(created["items"][0]),
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(item["question_id"], item["position"]) for item in response.json()["items"]],
            [(second_id, 1), (first_id, 2)],
        )

    def test_new_items_can_precede_retained_items_without_position_collision(self):
        retained_ids = [self._create_question(content=f"retained {index}") for index in range(2)]
        added_ids = [self._create_question(content=f"added {index}") for index in range(3)]
        created = self._create_paper(retained_ids).json()
        expected_ids = added_ids + retained_ids

        response = self._update_paper(
            created["id"],
            {
                "title": created["title"],
                "description": created["description"],
                "items": [
                    *[
                        {"kind": "question", "question_id": question_id, "score": 1}
                        for question_id in added_ids
                    ],
                    *[self._existing_item(item) for item in created["items"]],
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(item["question_id"], item["position"]) for item in response.json()["items"]],
            [(question_id, position) for position, question_id in enumerate(expected_ids, start=1)],
        )

    def test_update_deletes_item_and_adds_latest_owned_question_snapshot(self):
        removed_id = self._create_question(content="remove me")
        retained_id = self._create_question(content="retain me")
        added_id = self._create_question(
            content="question table text",
            revision_content={"text": "revision v1", "answer": "answer v1"},
            question_type="solution",
            difficulty_level=4,
            difficulty_label="较难",
            metadata_status="ready",
        )
        with self.SessionLocal() as db:
            latest_revision = QuestionRevision(
                question_id=added_id,
                rev_no=2,
                content={
                    "text": "latest revision text",
                    "answer": "latest answer",
                    "analysis": "latest analysis",
                    "knowledge_tags": [{"label": "latest-tag", "score": 1.0}],
                },
                change_reason="test_latest",
            )
            db.add(latest_revision)
            db.commit()
            db.refresh(latest_revision)
            latest_revision_id = latest_revision.id

        created = self._create_paper([removed_id, retained_id]).json()
        response = self._update_paper(
            created["id"],
            {
                "title": created["title"],
                "description": None,
                "items": [
                    self._existing_item(created["items"][1], score=3),
                    {"kind": "question", "question_id": added_id, "score": 7},
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["item_count"], 2)
        self.assertEqual(payload["total_score"], 10)
        self.assertEqual([item["question_id"] for item in payload["items"]], [retained_id, added_id])
        added = payload["items"][1]
        self.assertEqual(added["content_snapshot"], "latest revision text")
        self.assertEqual(added["answer_snapshot"], "latest answer")
        self.assertEqual(added["analysis_snapshot"], "latest analysis")
        self.assertEqual(added["knowledge_tags_snapshot"], [{"label": "latest-tag", "score": 1.0}])
        self.assertEqual(added["question_type_snapshot"], "solution")
        self.assertEqual(added["difficulty_level_snapshot"], 4)
        with self.SessionLocal() as db:
            item = db.query(PaperItem).filter(PaperItem.id == added["id"]).one()
            self.assertEqual(item.question_revision_id, latest_revision_id)
            self.assertIsNone(db.query(PaperItem).filter(PaperItem.question_id == removed_id).first())

    def test_new_question_allows_explicit_text_overrides_but_keeps_server_metadata_snapshot(self):
        existing_id = self._create_question(content="existing")
        added_id = self._create_question(
            content="bank content",
            revision_content={"text": "latest bank content", "answer": "bank answer"},
            question_type="single_choice",
            difficulty_level=2,
            difficulty_label="较易",
            metadata_status="ready",
        )
        created = self._create_paper([existing_id]).json()

        response = self._update_paper(
            created["id"],
            {
                "title": created["title"],
                "description": created["description"],
                "items": [
                    self._existing_item(created["items"][0]),
                    {
                        "kind": "question",
                        "question_id": added_id,
                        "score": 5,
                        "content_snapshot": "new item paper-only content",
                        "answer_snapshot": None,
                        "analysis_snapshot": "new item paper-only analysis",
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        added = response.json()["items"][1]
        self.assertEqual(added["content_snapshot"], "new item paper-only content")
        self.assertIsNone(added["answer_snapshot"])
        self.assertEqual(added["analysis_snapshot"], "new item paper-only analysis")
        self.assertEqual(added["question_type_snapshot"], "single_choice")
        self.assertEqual(added["difficulty_level_snapshot"], 2)

    def test_update_rejects_empty_items_duplicate_questions_and_invalid_text(self):
        question_id = self._create_question(content="valid")
        created = self._create_paper([question_id]).json()
        base = {"title": created["title"], "description": created["description"]}

        empty = self._update_paper(created["id"], {**base, "items": []})
        duplicate = self._update_paper(
            created["id"],
            {
                **base,
                "items": [
                    self._existing_item(created["items"][0]),
                    {"kind": "question", "question_id": question_id, "score": 1},
                ],
            },
        )
        empty_title = self._update_paper(
            created["id"],
            {**base, "title": "   ", "items": [self._existing_item(created["items"][0])]},
        )
        empty_content = self._update_paper(
            created["id"],
            {
                **base,
                "items": [self._existing_item(created["items"][0], content_snapshot="  ")],
            },
        )

        self.assertEqual(empty.status_code, 422)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(empty_title.status_code, 422)
        self.assertEqual(empty_content.status_code, 422)

    def test_update_hides_missing_cross_user_paper_and_cross_user_question(self):
        own_question_id = self._create_question(content="own")
        other_question_id = self._create_question(user_id=self.other_user_id, content="other")
        created = self._create_paper([own_question_id]).json()
        payload = {
            "title": created["title"],
            "description": created["description"],
            "items": [self._existing_item(created["items"][0])],
        }

        self.assertEqual(self._update_paper(999999, payload).status_code, 404)
        self.assertEqual(self._update_paper(created["id"], payload, self.other_auth_headers).status_code, 404)
        cross_question = self._update_paper(
            created["id"],
            {
                **payload,
                "title": "must not persist",
                "items": [
                    self._existing_item(created["items"][0]),
                    {"kind": "question", "question_id": other_question_id, "score": 1},
                ],
            },
        )
        self.assertEqual(cross_question.status_code, 404)
        unchanged = self.client.get(f"/api/v1/papers/{created['id']}", headers=self.auth_headers).json()
        self.assertEqual(unchanged["title"], created["title"])
        self.assertEqual(unchanged["item_count"], 1)

    def test_update_rejects_non_draft_paper(self):
        question_id = self._create_question()
        created = self._create_paper([question_id]).json()
        with self.SessionLocal() as db:
            paper = db.query(Paper).filter(Paper.id == created["id"]).one()
            paper.status = "published"
            db.commit()

        response = self._update_paper(
            created["id"],
            {
                "title": "not allowed",
                "description": None,
                "items": [self._existing_item(created["items"][0])],
            },
        )

        self.assertEqual(response.status_code, 409)

    def test_invalid_item_id_does_not_partially_update_paper(self):
        question_id = self._create_question()
        created = self._create_paper([question_id]).json()
        invalid_item = self._existing_item(created["items"][0])
        invalid_item["id"] = 999999

        response = self._update_paper(
            created["id"],
            {"title": "must rollback", "description": None, "items": [invalid_item]},
        )

        self.assertEqual(response.status_code, 404)
        unchanged = self.client.get(f"/api/v1/papers/{created['id']}", headers=self.auth_headers).json()
        self.assertEqual(unchanged["title"], created["title"])
        self.assertEqual(unchanged["items"], created["items"])

    def test_render_model_uses_saved_snapshot_score_order_add_and_delete(self):
        deleted_id = self._create_question(content="deleted")
        moved_id = self._create_question(content="moved")
        added_id = self._create_question(content="added latest")
        created = self._create_paper([deleted_id, moved_id]).json()
        updated = self._update_paper(
            created["id"],
            {
                "title": "render edited",
                "description": "render description",
                "items": [
                    self._existing_item(
                        created["items"][1],
                        score=8,
                        content_snapshot="moved paper snapshot",
                    ),
                    {"kind": "question", "question_id": added_id, "score": 2},
                ],
            },
        )
        self.assertEqual(updated.status_code, 200)

        rendered = self.client.post(
            f"/api/v1/papers/{created['id']}/render-model",
            headers=self.auth_headers,
            json={"answer_area_mode": "after_each_question"},
        )

        self.assertEqual(rendered.status_code, 200)
        model = rendered.json()
        rendered_items = [item for section in model["sections"] for item in section["items"]]
        self.assertEqual(model["paper"]["title"], "render edited")
        self.assertEqual(model["paper"]["item_count"], 2)
        self.assertEqual(model["paper"]["total_score"], 10)
        self.assertEqual(
            [(item["question_id"], item["position"], item["score"], item["content"]) for item in rendered_items],
            [
                (moved_id, 1, 8, "moved paper snapshot"),
                (added_id, 2, 2, "added latest"),
            ],
        )

    def test_update_rejects_question_moved_to_trash(self):
        existing_id = self._create_question(content="existing")
        added_id = self._create_question(content="added")
        created = self._create_paper([existing_id]).json()
        trashed = self.client.post(f"/api/v1/questions/{added_id}/trash", headers=self.auth_headers)
        self.assertEqual(trashed.status_code, 200)
        response = self._update_paper(
            created["id"],
            {"title": created["title"], "description": None, "items": [
                self._existing_item(created["items"][0]),
                {"kind": "question", "question_id": added_id, "score": 1},
            ]},
        )
        self.assertEqual(response.status_code, 404)

    def test_update_rejects_permanently_deleted_question(self):
        existing_id = self._create_question(content="existing")
        added_id = self._create_question(content="added")
        created = self._create_paper([existing_id]).json()
        self.assertEqual(self.client.post(f"/api/v1/questions/{added_id}/trash", headers=self.auth_headers).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/v1/questions/{added_id}/permanent", headers=self.auth_headers).status_code, 200)
        response = self._update_paper(
            created["id"],
            {"title": created["title"], "description": None, "items": [
                self._existing_item(created["items"][0]),
                {"kind": "question", "question_id": added_id, "score": 1},
            ]},
        )
        self.assertEqual(response.status_code, 404)

    def test_existing_paper_snapshot_survives_question_edit_and_permanent_delete(self):
        question_id = self._create_question(content="frozen")
        created = self._create_paper([question_id]).json()
        self.assertEqual(self.client.put(f"/api/v1/questions/{question_id}", headers=self.auth_headers, json={"content": "changed"}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/questions/{question_id}/trash", headers=self.auth_headers).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/v1/questions/{question_id}/permanent", headers=self.auth_headers).status_code, 200)
        detail = self.client.get(f"/api/v1/papers/{created['id']}", headers=self.auth_headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["items"][0]["content_snapshot"], "frozen")
