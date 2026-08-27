import unittest
from datetime import timedelta
from unittest.mock import Mock, patch

from sqlalchemy.exc import IntegrityError

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.question import Question
from app.models.question_revision import QuestionRevision
from app.models.user import User
from app.schemas.question import QuestionUpdate
from app.services.question_service import update, trash, restore, permanent, owned, latest, utcnow


class QuestionEditTrashTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = User(username="u", email="u@example.com", phone="100", display_name="U", hashed_password="x", role="user", status="active")
        self.other = User(username="v", email="v@example.com", phone="101", display_name="V", hashed_password="x", role="user", status="active")
        self.db.add_all([self.user, self.other]); self.db.commit()
        self.q = Question(user_id=self.user.id, content="old", answer="a", knowledge_tags=[])
        self.db.add(self.q); self.db.commit()

    def tearDown(self): self.db.close(); self.engine.dispose()

    def test_revision_edit_noop_and_compatibility(self):
        q, created, rev = update(self.db, self.user, self.q.id, QuestionUpdate(content="new"))
        self.assertTrue(created); self.assertEqual(rev.rev_no, 1); self.assertEqual(q.content, "new")
        _, created, same = update(self.db, self.user, self.q.id, QuestionUpdate(content="new"))
        self.assertFalse(created); self.assertEqual(same.rev_no, 1)
        self.assertEqual(self.db.query(QuestionRevision).count(), 1)

    def test_revision_conflict_and_owner_404(self):
        update(self.db, self.user, self.q.id, QuestionUpdate(content="new"))
        with self.assertRaisesRegex(HTTPException, "版本冲突"):
            update(self.db, self.user, self.q.id, QuestionUpdate(content="x", expected_revision_no=99))
        with self.assertRaisesRegex(HTTPException, "资源不存在"):
            owned(self.db, self.other, self.q.id)

    def test_question_type_uses_canonical_values(self):
        for question_type in ("single_choice", "multiple_choice", "fill_blank", "solution", "judge", "unknown"):
            update(self.db, self.user, self.q.id, QuestionUpdate(question_type=question_type))
        with self.assertRaisesRegex(HTTPException, "非法题型"):
            update(self.db, self.user, self.q.id, QuestionUpdate(question_type="choice"))

    def test_revision_integrity_race_rolls_back_and_session_remains_usable(self):
        original_commit = self.db.commit
        state = {"first": True}

        def commit_with_race():
            if state["first"]:
                state["first"] = False
                self.db.rollback()
                raise IntegrityError("uq_question_revisions_question_id_rev_no", {}, Exception("race"))
            return original_commit()

        with patch.object(self.db, "commit", side_effect=commit_with_race):
            with self.assertRaisesRegex(HTTPException, "版本冲突"):
                update(self.db, self.user, self.q.id, QuestionUpdate(content="raced"))
        self.assertEqual(self.db.query(Question).count(), 1)
        update(self.db, self.user, self.q.id, QuestionUpdate(content="usable"))
        self.assertEqual(self.db.query(Question).one().content, "usable")

    def test_all_editable_fields_are_projected_into_revision(self):
        _, _, rev = update(self.db, self.user, self.q.id, QuestionUpdate(
            content="题干", answer="答案", analysis="解析", knowledge_tags=[{"label": "圆"}],
            question_type="solution", difficulty_level=4,
        ))
        self.assertEqual(rev.content["text"], "题干")
        self.assertEqual(rev.content["answer"], "答案")
        self.assertEqual(rev.content["knowledge_tags"][0]["label"], "圆")
        self.assertEqual(rev.content["difficulty_level"], 4)

    def test_trash_restore_restarts_retention_and_permanent_is_logical(self):
        q = trash(self.db, self.user, self.q.id)
        self.assertIsNotNone(q.deleted_at); self.assertIsNotNone(q.purge_at)
        with self.assertRaises(HTTPException): owned(self.db, self.user, q.id)
        old_purge = q.purge_at
        restore(self.db, self.user, q.id)
        q = trash(self.db, self.user, q.id)
        self.assertGreater(q.purge_at, old_purge)
        permanent(self.db, self.user, q.id)
        self.assertIsNotNone(q.purged_at)
        self.assertIsNotNone(self.db.get(QuestionRevision, 1)) if self.db.query(QuestionRevision).count() else None

    def test_expired_question_is_invisible(self):
        q = trash(self.db, self.user, self.q.id)
        q.purge_at = utcnow() - timedelta(seconds=1); self.db.commit()
        with self.assertRaisesRegex(HTTPException, "资源不存在"): owned(self.db, self.user, q.id, include_trash=True)


if __name__ == "__main__": unittest.main()
