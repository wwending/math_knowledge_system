import unittest

from tests.test_paper_mvp import PaperMvpTests as _PaperMvpTests


class PaperResponseLineTests(_PaperMvpTests):

    def _patch_lines(self, paper, count, **overrides):
        payload = {
            "title": paper["title"],
            "description": paper["description"],
            "show_answer": overrides.get("show_answer", paper["show_answer"]),
            "show_analysis": overrides.get("show_analysis", paper["show_analysis"]),
            "items": [
                {
                    "kind": "existing",
                    "id": item["id"],
                    "question_id": item["question_id"],
                    "score": item["score"] or 0,
                    "response_line_count": count,
                }
                for item in paper["items"]
            ],
        }
        return self.client.patch(f"/api/v1/papers/{paper['id']}", headers=self.auth_headers, json=payload)

    def test_default_patch_bounds_and_render_height(self):
        question_id = self._create_question(content="response lines")
        paper = self._create_paper([question_id]).json()
        detail = self.client.get(f"/api/v1/papers/{paper['id']}", headers=self.auth_headers).json()
        self.assertEqual(detail["items"][0]["response_line_count"], 6)

        for count, expected_area in (
            (0, None),
            (1, {"mode": "after_each_question", "response_line_count": 1, "height_mm": 8}),
            (24, {"mode": "after_each_question", "response_line_count": 24, "height_mm": 192}),
        ):
            updated = self._patch_lines(detail, count)
            self.assertEqual(updated.status_code, 200)
            detail = updated.json()
            rendered = self.client.post(
                f"/api/v1/papers/{paper['id']}/render-model",
                headers=self.auth_headers,
                json={"answer_area_mode": "after_each_question"},
            ).json()
            self.assertEqual(rendered["sections"][0]["items"][0]["answer_area"], expected_area)

        for invalid in (-1, 25, 1.5, "6"):
            response = self._patch_lines(detail, invalid)
            self.assertEqual(response.status_code, 422)
        unchanged = self.client.get(f"/api/v1/papers/{paper['id']}", headers=self.auth_headers).json()
        self.assertEqual(unchanged["items"][0]["response_line_count"], 24)

    def test_answers_and_legacy_none_only_hide_saved_lines(self):
        question_id = self._create_question(
            content="stem",
            revision_content={"text": "stem", "answer": "answer", "analysis": "analysis"},
        )
        paper = self._create_paper([question_id]).json()
        detail = self.client.get(f"/api/v1/papers/{paper['id']}", headers=self.auth_headers).json()
        detail = self._patch_lines(detail, 9, show_answer=True).json()

        for mode in ("none", "after_each_question"):
            rendered = self.client.post(
                f"/api/v1/papers/{paper['id']}/render-model",
                headers=self.auth_headers,
                json={"answer_area_mode": mode},
            ).json()
            self.assertIsNone(rendered["sections"][0]["items"][0]["answer_area"])
        self.assertEqual(detail["items"][0]["response_line_count"], 9)

        detail = self._patch_lines(detail, 9, show_answer=False).json()
        rendered = self.client.post(
            f"/api/v1/papers/{paper['id']}/render-model",
            headers=self.auth_headers,
            json={"answer_area_mode": "after_each_question"},
        ).json()
        self.assertEqual(rendered["sections"][0]["items"][0]["answer_area"]["height_mm"], 72)


if __name__ == "__main__":
    unittest.main()
