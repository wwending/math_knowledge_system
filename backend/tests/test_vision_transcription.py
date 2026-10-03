import base64
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

import httpx
import pytest
from openai import APITimeoutError
from PIL import Image

from app.api.v1 import endpoints
from app.core.config import settings
from app.models.draft import Draft
from app.models.llm_run import LLMRun
from app.models.ocr_run import OCRRun
from app.models.question import Question
from app.models.question_revision import QuestionRevision
from app.services.layout_service import FigureBox, LayoutResult
from app.services.ocr_providers.vision import VisionOcrProvider, parse_transcription
from tests import test_draft_pipeline as legacy_pipeline

CASES = json.loads((Path(__file__).parent / "fixtures/vision_draft40.json").read_text(encoding="utf-8"))["cases"]


def response(raw, finish="stop", choices=True):
    return NS(id="completion-vision", _request_id="request-vision", model="deepseek-flash", usage=NS(prompt_tokens=15, completion_tokens=20, total_tokens=35),
              choices=[NS(finish_reason=finish, message=NS(content=raw))] if choices else [])


@pytest.fixture
def sdk(monkeypatch):
    monkeypatch.setattr(settings, "VISION_API_KEY", "mock-vision-key")
    with patch("app.services.ocr_providers.vision.OpenAI") as factory:
        client = factory.return_value.__enter__.return_value
        client.chat.completions.create.return_value = response(json.dumps(CASES[0]))
        yield factory, client.chat.completions.create


@pytest.fixture
def image_path(tmp_path):
    path = tmp_path / "crop.png"
    Image.new("RGB", (100, 80), "black").save(path)
    return str(path)


@pytest.mark.parametrize("case", CASES)
def test_draft40_faithful_separation(case):
    parsed = parse_transcription(json.dumps(case))
    assert parsed["statement"] == case["statement"]
    assert parsed["handwriting_annotations"] == case["handwriting_annotations"]
    assert "Delta" not in parsed["statement"]


@pytest.mark.parametrize("command", ["frac{1}{2}", "beta", "theta", "neq0", "rightarrow"])
def test_single_backslash_formula_escape_rejected_without_repair(sdk, image_path, command):
    raw = json.dumps({**CASES[0], "statement": "$\\" + command + "$"})
    raw = raw.replace("\\\\" + command, "\\" + command)
    # These malformed commands are valid JSON, so json.loads alone is insufficient.
    assert json.loads(raw)["statement"] != "$\\" + command + "$"
    sdk[1].return_value = response(raw)
    assert VisionOcrProvider().recognize(image_path).error_type == "invalid_response"
    assert sdk[1].call_count == 1


def test_legitimate_line_breaks_and_escaped_latex_preserved():
    statement = "first\nnext line\r\nreal line\ttab\n$\\frac{1}{2}+\\theta\\neq0\\rightarrow\\beta$"
    obj = {**CASES[0], "statement": statement, "handwriting_annotations": ["first\nnext"]}
    assert parse_transcription(json.dumps(obj))["statement"] == statement


def test_evaluated_request_contract_and_honest_identifiers(sdk, image_path):
    result = VisionOcrProvider().recognize(image_path)
    assert result.success
    args = sdk[1].call_args.kwargs
    assert args["extra_body"] == {"thinking": {"type": "disabled"}}
    assert args["messages"][1]["content"][0]["image_url"]["detail"] == "original"
    assert result.raw_response_summary["request_id"] == "request-vision"
    assert result.raw_response_summary["response_id"] == "completion-vision"


def test_missing_http_request_id_is_null(sdk, image_path):
    reply = response(json.dumps(CASES[0]))
    del reply._request_id
    sdk[1].return_value = reply
    result = VisionOcrProvider().recognize(image_path)
    assert result.success
    assert result.raw_response_summary["request_id"] is None
    assert result.raw_response_summary["response_id"] == "completion-vision"


@pytest.mark.parametrize("raw,finish,choices,code", [
    ("", "stop", True, "empty_response"),
    ("{}", "stop", False, "empty_response"),
    (json.dumps(CASES[0]), "length", True, "truncated_response"),
    ("# 题目\n正文\n# 批注\nDelta", "stop", True, "invalid_response"),
    ('{"statement":"$\\frac{1}{2}$","handwriting_annotations":[],"uncertainties":[]}', "stop", True, "invalid_response"),
    ('{"statement":"$\\neq0$","handwriting_annotations":[],"uncertainties":[]}', "stop", True, "invalid_response"),
    ('{"statement":"正文"}', "stop", True, "invalid_response"),
    ('{"statement":"正文","statement":"批注"}', "stop", True, "invalid_response"),
])
def test_failures_never_repair_or_retry(sdk, image_path, raw, finish, choices, code):
    factory, generate = sdk
    generate.return_value = response(raw, finish, choices)
    result = VisionOcrProvider().recognize(image_path)
    assert result.error_type == code
    assert not result.text
    assert generate.call_count == 1
    assert factory.call_args.kwargs["max_retries"] == 0


def test_timeout_no_retry_or_exception_leak(sdk, image_path):
    _, generate = sdk
    generate.side_effect = APITimeoutError(request=httpx.Request("POST", "https://example.invalid"))
    result = VisionOcrProvider().recognize(image_path)
    assert result.error_type == "timeout"
    assert generate.call_count == 1


def test_image_budget_rejects_before_call(sdk, image_path, monkeypatch):
    monkeypatch.setattr(settings, "VISION_MAX_IMAGE_BYTES", 1)
    assert VisionOcrProvider().recognize(image_path).error_type == "image_too_large"
    sdk[1].assert_not_called()


def test_output_records_redact_echoed_inputs(sdk, image_path):
    obj = {**CASES[0], "handwriting_annotations": ["mock-vision-key data:image/png;base64," + "A" * 300]}
    sdk[1].return_value = response(json.dumps(obj))
    result = VisionOcrProvider().recognize(image_path)
    recorded = json.dumps(result.raw_response_summary)
    assert result.success
    assert "mock-vision-key" not in recorded
    assert "data:image" not in recorded
    assert "A" * 300 not in recorded
    assert result.raw_response_summary["usage"]["total_tokens"] == 35


@pytest.fixture
def pipeline():
    harness = legacy_pipeline.DraftPipelineTests(methodName="runTest")
    harness.setUp()
    try:
        with patch.object(settings, "OCR_PROVIDER", "vision"):
            yield harness
    finally:
        harness.tearDown()
        harness.doCleanups()


@pytest.mark.parametrize("missing_metadata", [False, True])
def test_recognize_save_one_generation_unmasked_and_metadata(pipeline, sdk, missing_metadata):
    case = CASES[1] if not missing_metadata else {**CASES[1], "knowledge_tags": None,
        "question_type": "invented", "difficulty": {"level": True}}
    sdk[1].return_value = response(json.dumps(case))
    draft_id = pipeline._create_draft(pipeline._create_source_asset())
    Image.new("RGB", (100, 80), "black").save(pipeline.upload_dir / "asset.png")
    with pipeline.SessionLocal() as db:
        stale = LLMRun(draft_id=draft_id, provider="deepseek", prompt_version="v1")
        db.add(stale)
        db.flush()
        draft = db.get(Draft, draft_id)
        draft.last_llm_run_id = stale.id
        draft.question_type = "judge"
        db.commit()
    layout = LayoutResult(success=True, boxes=[FigureBox(bbox=[0.1, 0.1, 0.3, 0.3], label="figure", score=0.9)], latency_ms=1)
    with patch.object(endpoints.layout_service, "detect", return_value=layout), \
         patch.object(endpoints, "write_masked_image") as mask, \
         patch.object(endpoints.nlp_service, "analyze") as cleanup, \
         patch.object(endpoints, "evaluate_question_metadata_task") as metadata:
        recognized = pipeline.client.post(f"/api/v1/drafts/{draft_id}/recognize", headers=pipeline.auth_headers).json()
        assert recognized["success"]
        assert recognized["last_llm_run_id"] is None
        assert recognized["content"] == case["statement"]
        assert recognized["recognition_debug"]["handwriting_annotations"] == case["handwriting_annotations"]
        assert recognized["recognition_debug"]["uncertainties"]
        assert bool(recognized["warning"]) == missing_metadata
        saved = pipeline.client.post(f"/api/v1/drafts/{draft_id}/save-to-bank", headers=pipeline.auth_headers)
        assert saved.status_code == 200, saved.text
        assert sdk[1].call_count == 1
        cleanup.assert_not_called()
        metadata.assert_not_called()
        mask.assert_not_called()
    url = sdk[1].call_args.kwargs["messages"][1]["content"][0]["image_url"]["url"]
    with Image.open(BytesIO(base64.b64decode(url.split(",", 1)[1]))) as image:
        assert image.size == (100, 80)
        assert image.getpixel((20, 20)) == (0, 0, 0)
    with pipeline.SessionLocal() as db:
        question = db.get(Question, saved.json()["question_id"])
        revision = db.get(QuestionRevision, saved.json()["question_revision_id"])
        assert question.content == case["statement"]
        assert "Delta" not in question.content
        assert revision.llm_run_id is None
        assert question.question_type == (None if missing_metadata else "solution")
        assert question.difficulty_level == (None if missing_metadata else 2)
        assert question.knowledge_tags == ([] if missing_metadata else [{"label": "一元二次方程", "score": 1.0}])
        assert question.metadata_status == ("failed" if missing_metadata else "ready")
        run = db.get(OCRRun, revision.ocr_run_id)
        assert run.response_raw_json["raw_response_summary"]["request_id"] == "request-vision"
        assert run.request_params_redacted["ocr_input"] == "original"


def test_failed_retry_clears_old_cleanup_and_cannot_save(pipeline, sdk):
    draft_id = pipeline._create_draft(pipeline._create_source_asset())
    with pipeline.SessionLocal() as db:
        stale = LLMRun(draft_id=draft_id, provider="deepseek", prompt_version="v1")
        db.add(stale)
        db.flush()
        draft = db.get(Draft, draft_id)
        draft.last_llm_run_id = stale.id
        draft.current_content = {"text": "old text"}
        db.commit()
    sdk[1].return_value = response("not json")
    result = pipeline.client.post(f"/api/v1/drafts/{draft_id}/recognize", headers=pipeline.auth_headers).json()
    assert result["status"] == "failed"
    assert result["last_llm_run_id"] is None
    assert result["content"] == ""
    assert pipeline.client.post(f"/api/v1/drafts/{draft_id}/save-to-bank", headers=pipeline.auth_headers).status_code == 409
    assert sdk[1].call_count == 1
