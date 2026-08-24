"""Unit tests for the #58 layout analysis service (fakes only, no network)."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.core.config import settings
from app.services import layout_service as layout_service_module
from app.services.layout_service import (
    LayoutModelUnavailable,
    LayoutService,
)


def _write_real_png(path: Path, width: int = 200, height: int = 100) -> None:
    Image.new("RGB", (width, height), color=(240, 240, 240)).save(path, format="PNG")


class LayoutServiceDetectTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root_dir = Path(self.temp_dir.name)
        self.image_path = root_dir / "question.png"
        _write_real_png(self.image_path)

        self._old_enabled = settings.LAYOUT_ENABLED
        self._old_model_dir = settings.LAYOUT_MODEL_DIR
        self._old_min_area = settings.LAYOUT_MIN_AREA_RATIO
        self._old_labels = settings.LAYOUT_FIGURE_LABELS
        settings.LAYOUT_ENABLED = True
        settings.LAYOUT_MODEL_DIR = str(root_dir / "weights")
        settings.LAYOUT_FIGURE_LABELS = "figure"

    def tearDown(self):
        settings.LAYOUT_ENABLED = self._old_enabled
        settings.LAYOUT_MODEL_DIR = self._old_model_dir
        settings.LAYOUT_MIN_AREA_RATIO = self._old_min_area
        settings.LAYOUT_FIGURE_LABELS = self._old_labels
        self.temp_dir.cleanup()

    def _service_with_engine(self, engine):
        return LayoutService(engine_factory=lambda: engine)

    @staticmethod
    def _engine_result(boxes, class_names, scores):
        return SimpleNamespace(boxes=boxes, class_names=class_names, scores=scores)

    def test_detect_normalizes_clamps_and_sorts_figure_boxes(self):
        engine_boxes = [
            [10.0, 50.0, 90.0, 130.0],   # figure lower half (y2 clamps to 100), kept
            [0.0, -20.0, 100.0, 20.0],   # clamped to top edge, kept
            [5.0, 5.0, 60.0, 40.0],      # "table" label -> filtered out
            [150.0, 10.0, 199.0, 13.0],  # tiny area -> filtered out by default ratio
        ]
        labels = ["figure", "figure", "table", "figure"]
        scores = [0.91, 0.72, 0.99, 0.66]
        service = self._service_with_engine(lambda img: self._engine_result(engine_boxes, labels, scores))

        result = service.detect(self.image_path)

        self.assertTrue(result.success)
        self.assertEqual([box.label for box in result.boxes], ["figure", "figure"])
        top_box, lower_box = result.boxes
        # Sorted by y: clamped top edge box first; normalized xywh on a 200x100 image.
        self.assertEqual([round(v, 4) for v in top_box.bbox], [0.0, 0.0, 0.5, 0.2])
        self.assertEqual([round(v, 4) for v in lower_box.bbox], [0.05, 0.5, 0.4, 0.5])
        self.assertEqual(lower_box.score, 0.91)
        self.assertGreaterEqual(result.latency_ms, 0)

    def test_disabled_configuration_degrades_without_calling_the_engine(self):
        settings.LAYOUT_ENABLED = False
        called = []
        service = self._service_with_engine(lambda img: called.append(img))

        result = service.detect(self.image_path)

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "disabled")
        self.assertEqual(called, [])

    def test_engine_exception_degrades_to_engine_error(self):
        def boom(img):
            raise RuntimeError("onnx exploded")

        result = self._service_with_engine(boom).detect(self.image_path)

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "engine_error")

    def test_timeout_degrades(self):
        import time

        def slow(img):
            time.sleep(0.3)

        old_timeout = settings.LAYOUT_TIMEOUT_SECONDS
        settings.LAYOUT_TIMEOUT_SECONDS = 0.05
        try:
            result = self._service_with_engine(slow).detect(self.image_path)
        finally:
            settings.LAYOUT_TIMEOUT_SECONDS = old_timeout

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "timeout")

    def test_unreadable_image_degrades_instead_of_raising(self):
        engine = lambda img: self._engine_result([[1, 1, 2, 2]], ["figure"], [0.9])
        result = self._service_with_engine(engine).detect(self.image_path.parent / "missing.png")

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "engine_error")


class LayoutModelProvisionTests(unittest.TestCase):
    """ensure_model(): download once, verify SHA256, never re-download."""

    MODEL_BYTES = b"fake-onnx-model-bytes"
    MODEL_SHA256 = hashlib.sha256(MODEL_BYTES).hexdigest()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_dir = Path(self.temp_dir.name) / "weights"
        self._old_dir = settings.LAYOUT_MODEL_DIR
        self._old_path = settings.LAYOUT_MODEL_PATH
        self._old_type = settings.LAYOUT_MODEL_TYPE
        settings.LAYOUT_MODEL_DIR = str(self.model_dir)
        settings.LAYOUT_MODEL_PATH = ""
        settings.LAYOUT_MODEL_TYPE = "doclayout_docstructbench"

    def tearDown(self):
        settings.LAYOUT_MODEL_DIR = self._old_dir
        settings.LAYOUT_MODEL_PATH = self._old_path
        settings.LAYOUT_MODEL_TYPE = self._old_type
        self.temp_dir.cleanup()

    def _fake_response(self):
        model_bytes = self.MODEL_BYTES

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def raise_for_status(self):
                return None

            def iter_content(self, chunk_size):
                yield model_bytes

        return FakeResponse()

    def test_downloads_once_verifies_and_reuses_cached_file(self):
        service = LayoutService()
        download_calls = []

        def fake_get(url, stream=True, timeout=None):
            download_calls.append(url)
            return self._fake_response()

        with patch.object(layout_service_module, "MODEL_SPECS", {
            "doclayout_docstructbench": ("https://models.example/model.onnx", self.MODEL_SHA256)
        }), patch.object(layout_service_module.requests, "get", side_effect=fake_get):
            first = service.ensure_model()
            second = service.ensure_model()

        self.assertTrue(first.is_file())
        self.assertEqual(first.read_bytes(), self.MODEL_BYTES)
        self.assertEqual(first, second)
        self.assertEqual(len(download_calls), 1)

    def test_checksum_mismatch_raises_download_failed_and_leaves_no_file(self):
        service = LayoutService()
        bad_spec = {"doclayout_docstructbench": ("https://models.example/model.onnx", "0" * 64)}

        with patch.object(layout_service_module, "MODEL_SPECS", bad_spec), \
                patch.object(layout_service_module.requests, "get", side_effect=lambda *a, **k: self._fake_response()):
            with self.assertRaises(LayoutModelUnavailable) as ctx:
                service.ensure_model()

        self.assertEqual(ctx.exception.error_type, "download_failed")
        self.assertEqual(list(self.model_dir.glob("*")), [])

    def test_unknown_model_type_requires_explicit_path(self):
        settings.LAYOUT_MODEL_TYPE = "some_custom_model"
        service = LayoutService()

        with self.assertRaises(LayoutModelUnavailable) as ctx:
            service.ensure_model()

        self.assertEqual(ctx.exception.error_type, "model_missing")

    def test_explicit_model_path_is_trusted_as_is(self):
        custom = Path(self.temp_dir.name) / "custom.onnx"
        custom.write_bytes(b"custom-bytes")
        settings.LAYOUT_MODEL_PATH = str(custom)
        service = LayoutService()

        resolved = service.ensure_model()

        self.assertEqual(resolved, custom)


class MaskedImageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root_dir = Path(self.temp_dir.name)
        self.image_path = root_dir / "question.png"
        _write_real_png(self.image_path)

        self._old_upload_dir = settings.UPLOAD_DIR
        settings.UPLOAD_DIR = str(root_dir / "uploads")
        Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        settings.UPLOAD_DIR = self._old_upload_dir
        self.temp_dir.cleanup()

    def test_write_masked_image_whites_out_regions_and_returns_temp_path(self):
        boxes = [
            layout_service_module.FigureBox(bbox=[0.0, 0.0, 0.5, 1.0], label="figure", score=0.9),
            layout_service_module.FigureBox(bbox=[0.75, 0.25, 0.25, 0.25], label="figure", score=0.8),
        ]

        masked = layout_service_module.write_masked_image(self.image_path, boxes)

        self.assertIsNotNone(masked)
        self.assertTrue(masked.is_file())
        with Image.open(masked) as img:
            self.assertEqual(img.size, (200, 100))
            pixel_left_half = img.getpixel((50, 50))
            pixel_kept_text = img.getpixel((125, 12))
        self.assertEqual(pixel_left_half, (255, 255, 255))
        self.assertNotEqual(pixel_kept_text, (255, 255, 255))

    def test_write_masked_image_returns_none_for_empty_or_broken_input(self):
        self.assertIsNone(layout_service_module.write_masked_image(self.image_path, []))
        self.assertIsNone(
            layout_service_module.write_masked_image(self.image_path.parent / "gone.png",
                                                     [layout_service_module.FigureBox([0, 0, 1, 1], "figure", 0.9)])
        )

    def test_remove_quiet_handles_none_and_missing_files(self):
        layout_service_module.remove_quiet(None)
        layout_service_module.remove_quiet(Path(self.temp_dir.name) / "nope.jpg")  # must not raise


if __name__ == "__main__":
    unittest.main()
