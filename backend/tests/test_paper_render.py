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
from app.models.user import User, UserStatus
from app.services.pdf_generation_service import PdfGenerationError


class PaperRenderModelTests(unittest.TestCase):
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
            self.user_id = self._create_user_in_db(db, "13700001001", "render-user@example.com")
            self.other_user_id = self._create_user_in_db(db, "13700001002", "other-render-user@example.com")

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.auth_headers = self._login("13700001001")
        self.other_auth_headers = self._login("13700001002")

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
        tags=None,
        revision_content: dict | None = None,
        question_type: str | None = "single_choice",
        metadata_status: str | None = "ready",
    ) -> int:
        with self.SessionLocal() as db:
            question = Question(
                user_id=user_id or self.user_id,
                content=content,
                knowledge_tags=tags,
                origin_image="question.png",
                question_type=question_type,
                difficulty_level=3,
                difficulty_label="中等",
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

    def _create_paper(
        self,
        question_ids: list[int],
        headers: dict[str, str] | None = None,
        title: str = "Render Paper",
    ) -> int:
        response = self.client.post(
            "/api/v1/papers",
            headers=headers or self.auth_headers,
            json={
                "title": title,
                "description": "render model",
                "items": [
                    {"question_id": question_id, "score": index + 1}
                    for index, question_id in enumerate(question_ids)
                ],
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    def _render(self, paper_id: int, payload: dict | None = None, headers: dict[str, str] | None = None):
        return self.client.post(
            f"/api/v1/papers/{paper_id}/render-model",
            headers=headers or self.auth_headers,
            json=payload or {},
        )

    def _pdf(self, paper_id: int, payload: dict | None = None, headers: dict[str, str] | None = None):
        return self.client.post(
            f"/api/v1/papers/{paper_id}/pdf",
            headers=headers or self.auth_headers,
            json=payload or {},
        )

    def test_default_homework_student_none_render_model(self):
        question_id = self._create_question(
            content="base content",
            tags=["函数", {"label": "集合", "score": 0.8}, None],
            revision_content={
                "text": "revision content",
                "answer": "hidden answer",
                "analysis": "hidden analysis",
                "knowledge_tags": ["函数", {"label": "集合", "score": 0.8}, None],
            },
        )
        paper_id = self._create_paper([question_id])

        response = self._render(paper_id)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["template_type"], "homework")
        self.assertEqual(payload["version"], "student")
        self.assertEqual(payload["paper_size"], "A4")
        self.assertEqual(payload["group_by"], "question_type")
        self.assertEqual(payload["sort_by"], "position")
        self.assertEqual(payload["answer_area_mode"], "none")
        self.assertEqual(payload["paper"]["title"], "Render Paper")
        item = payload["sections"][0]["items"][0]
        self.assertEqual(item["content"], "revision content")
        self.assertEqual(item["knowledge_tags"], [{"label": "函数", "score": None}, {"label": "集合", "score": 0.8}])
        self.assertIsNone(item["answer_area"])

    def test_after_each_question_returns_answer_area(self):
        question_id = self._create_question()
        paper_id = self._create_paper([question_id])

        response = self._render(paper_id, {"answer_area_mode": "after_each_question"})

        self.assertEqual(response.status_code, 200)
        item = response.json()["sections"][0]["items"][0]
        self.assertEqual(item["answer_area"], {"mode": "after_each_question", "height_mm": 50})

    def test_groups_by_question_type_and_sorts_by_position_with_global_display_number(self):
        first_solution = self._create_question(content="first solution", question_type="solution")
        second_choice = self._create_question(content="second choice", question_type="single_choice")
        third_solution = self._create_question(content="third solution", question_type="solution")

        paper_id = self._create_paper([first_solution, second_choice, third_solution])
        response = self._render(paper_id, {"answer_area_mode": "after_each_question"})

        self.assertEqual(response.status_code, 200)
        sections = response.json()["sections"]
        self.assertEqual([section["key"] for section in sections], ["solution", "single_choice"])
        self.assertEqual(
            [(item["question_id"], item["position"], item["display_number"]) for item in sections[0]["items"]],
            [(first_solution, 1, 1), (third_solution, 3, 3)],
        )
        self.assertEqual(sections[1]["items"][0]["display_number"], 2)
        self.assertEqual(
            [item["answer_area"] for section in sections for item in section["items"]],
            [{"mode": "after_each_question", "height_mm": 50}] * 3,
        )

    def test_empty_question_type_goes_to_unknown_section(self):
        question_id = self._create_question(question_type=None, metadata_status="pending")
        paper_id = self._create_paper([question_id])

        response = self._render(paper_id)

        self.assertEqual(response.status_code, 200)
        section = response.json()["sections"][0]
        self.assertEqual(section["key"], "unknown")
        self.assertEqual(section["title"], "未分类")
        self.assertEqual(section["items"][0]["question_type"], "unknown")

    def test_student_response_does_not_include_answer_or_analysis_snapshots(self):
        question_id = self._create_question(
            revision_content={
                "text": "student visible",
                "answer": "must not return",
                "analysis": "must not return",
            },
        )
        paper_id = self._create_paper([question_id])

        response = self._render(paper_id)

        self.assertEqual(response.status_code, 200)
        item = response.json()["sections"][0]["items"][0]
        self.assertNotIn("answer_snapshot", item)
        self.assertNotIn("analysis_snapshot", item)
        self.assertIsNone(item["answer"])
        self.assertIsNone(item["analysis"])
        self.assertEqual(item["section_snapshot"]["sections"]["answer"]["blocks"], [])
        self.assertEqual(item["section_snapshot"]["sections"]["analysis"]["blocks"], [])

    def test_missing_or_cross_user_paper_returns_404(self):
        own_question_id = self._create_question(content="own")
        other_question_id = self._create_question(user_id=self.other_user_id, content="other")
        own_paper_id = self._create_paper([own_question_id])
        other_paper_id = self._create_paper([other_question_id], headers=self.other_auth_headers)

        missing_response = self._render(999999)
        cross_user_response = self._render(other_paper_id)
        other_user_response = self._render(own_paper_id, headers=self.other_auth_headers)

        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(cross_user_response.status_code, 404)
        self.assertEqual(other_user_response.status_code, 404)

    @patch("app.api.v1.endpoints.pdf_generation_service.generate_pdf", return_value=b"%PDF-1.7 test")
    def test_owner_pdf_export_uses_render_model_and_returns_attachment(self, generate_pdf):
        question_id = self._create_question(
            revision_content={"text": "PDF model source: $x^2$"},
            question_type="solution",
        )
        paper_id = self._create_paper([question_id])

        response = self._pdf(paper_id, {"answer_area_mode": "after_each_question"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(response.content, b"%PDF-1.7 test")
        disposition = response.headers["content-disposition"]
        self.assertIn("attachment", disposition)
        self.assertIn(".pdf", disposition)
        html, options = generate_pdf.call_args.args
        self.assertIn("PDF model source", html)
        self.assertIn("解答题", html)
        self.assertEqual(html.count('class="answer-area"'), 1)
        self.assertIn('class="answer-area" style="height: 50mm"', html)
        self.assertNotIn('class="answer-line"', html)
        self.assertEqual(options.paper_size, "A4")

    @patch("app.api.v1.endpoints.pdf_generation_service.generate_pdf", return_value=b"%PDF-1.7 test")
    def test_pdf_export_missing_and_cross_user_papers_are_hidden(self, generate_pdf):
        own_question_id = self._create_question(content="own PDF")
        other_question_id = self._create_question(user_id=self.other_user_id, content="other PDF")
        own_paper_id = self._create_paper([own_question_id])
        other_paper_id = self._create_paper([other_question_id], headers=self.other_auth_headers)

        self.assertEqual(self._pdf(999999).status_code, 404)
        self.assertEqual(self._pdf(other_paper_id).status_code, 404)
        self.assertEqual(self._pdf(own_paper_id, headers=self.other_auth_headers).status_code, 404)
        generate_pdf.assert_not_called()

    @patch(
        "app.api.v1.endpoints.pdf_generation_service.generate_pdf",
        side_effect=PdfGenerationError("internal upstream details"),
    )
    def test_pdf_service_failure_returns_controlled_503(self, generate_pdf):
        question_id = self._create_question(content="service failure")
        paper_id = self._create_paper([question_id])

        response = self._pdf(paper_id)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "PDF 生成服务暂时不可用，请稍后重试"})
        self.assertNotIn("internal", response.text)
        generate_pdf.assert_called_once()

    @patch("app.api.v1.endpoints.pdf_generation_service.generate_pdf", return_value=b"%PDF-1.7 test")
    def test_pdf_export_requires_auth_and_sanitizes_download_filename(self, generate_pdf):
        question_id = self._create_question(content="safe filename")
        paper_id = self._create_paper(
            [question_id],
            title="../evil\r\nX-Injected: yes 中文",
        )

        unauthenticated = self.client.post(f"/api/v1/papers/{paper_id}/pdf", json={})
        response = self._pdf(paper_id)

        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(response.status_code, 200)
        disposition = response.headers["content-disposition"]
        self.assertNotIn("\r", disposition)
        self.assertNotIn("\n", disposition)
        self.assertNotIn("../", disposition)
        self.assertIn(f'filename="paper-{paper_id}.pdf"', disposition)
