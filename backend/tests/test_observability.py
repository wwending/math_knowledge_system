import re
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from loguru import logger

from app.core.config import settings
from app.core.error_handlers import INTERNAL_ERROR_MESSAGE, register_error_handlers
from app.core.logging import DEFAULT_LOG_FORMAT, setup_logging
from app.core.request_context import RequestContextMiddleware, new_request_id, sanitize_request_id
from app.main import app


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_dir = Path(self.temp_dir.name) / "logs"
        self._old_log_dir = settings.LOG_DIR
        settings.LOG_DIR = str(self.log_dir)
        setup_logging(level="DEBUG")

    def tearDown(self):
        settings.LOG_DIR = self._old_log_dir
        logger.complete()
        setup_logging()
        self.temp_dir.cleanup()

    def test_sanitize_request_id_accepts_safe_values_only(self):
        self.assertEqual(sanitize_request_id("  abc-123_XYZ  "), "abc-123_XYZ")
        self.assertIsNone(sanitize_request_id(None))
        self.assertIsNone(sanitize_request_id(""))
        self.assertIsNone(sanitize_request_id("bad id!\n"))
        self.assertIsNone(sanitize_request_id("x" * 65))

    def test_new_request_id_is_short_hex(self):
        self.assertRegex(new_request_id(), r"^[0-9a-f]{12}$")

    def test_healthz_reports_database_and_version(self):
        client = TestClient(app)
        response = client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["database"], "ok")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["app_env"], settings.APP_ENV_NORMALIZED)
        self.assertIn("git_sha", payload)

    def test_request_id_echoed_and_honored(self):
        client = TestClient(app)

        with_header = client.get("/healthz", headers={"X-Request-ID": "test-req-123"})
        self.assertEqual(with_header.headers["x-request-id"], "test-req-123")

        without_header = client.get("/healthz")
        echoed = without_header.headers["x-request-id"]
        self.assertRegex(echoed, r"^[0-9a-f]{12}$")

    def test_invalid_incoming_request_id_replaced(self):
        client = TestClient(app)
        response = client.get("/healthz", headers={"X-Request-ID": "bad id!\n"})
        replaced = response.headers["x-request-id"]
        self.assertNotEqual(replaced, "bad id!\n")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{12}", replaced))

    def test_access_log_line_written_with_request_id(self):
        messages: list[str] = []
        sink_id = logger.add(messages.append, level="DEBUG", format=DEFAULT_LOG_FORMAT)
        try:
            client = TestClient(app)
            response = client.get("/healthz", headers={"X-Request-ID": "access-log-check"})
            request_id = response.headers["x-request-id"]
        finally:
            logger.remove(sink_id)

        combined = "".join(messages)
        self.assertIn("[Access]", combined)
        self.assertIn("/healthz", combined)
        self.assertIn(request_id, combined)
        self.assertIn("access-log-check", combined)

    def test_unhandled_exception_returns_json_with_request_id(self):
        probe = FastAPI()

        @probe.get("/boom")
        def boom():
            raise ValueError("boom")

        probe.add_middleware(RequestContextMiddleware)
        register_error_handlers(probe)

        client = TestClient(probe, raise_server_exceptions=False)
        response = client.get("/boom", headers={"X-Request-ID": "crash-case-1"})

        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body["detail"], INTERNAL_ERROR_MESSAGE)
        self.assertEqual(body["request_id"], "crash-case-1")
        self.assertEqual(response.headers["x-request-id"], "crash-case-1")

    def test_unhandled_exception_generates_request_id_when_missing(self):
        probe = FastAPI()

        @probe.get("/boom")
        def boom():
            raise ValueError("boom")

        probe.add_middleware(RequestContextMiddleware)
        register_error_handlers(probe)

        client = TestClient(probe, raise_server_exceptions=False)
        response = client.get("/boom")

        body = response.json()
        self.assertEqual(response.status_code, 500)
        self.assertRegex(body["request_id"], r"^[0-9a-f]{12}$")

    def test_file_sink_contains_contextualized_request_id(self):
        with logger.contextualize(request_id="abc123"):
            logger.info("contextualized log line")
        logger.complete()

        log_file = Path(settings.LOG_DIR_PATH) / "app.log"
        content = log_file.read_text(encoding="utf-8")
        self.assertIn("contextualized log line", content)
        self.assertIn("abc123", content)


if __name__ == "__main__":
    unittest.main()
