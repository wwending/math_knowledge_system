import unittest
from unittest.mock import Mock, patch

import requests

from app.services.pdf_generation_service import (
    GotenbergPdfGenerationService,
    PdfGenerationError,
    PdfGenerationOptions,
)


class PdfGenerationServiceTests(unittest.TestCase):
    @patch("app.services.pdf_generation_service.requests.post")
    def test_posts_controlled_html_with_explicit_layout_contract(self, post: Mock):
        response = Mock()
        response.iter_content.return_value = [b"%PDF-1.7 generated"]
        response.raise_for_status.return_value = None
        post.return_value = response
        service = GotenbergPdfGenerationService(
            base_url="http://gotenberg:3000/",
            connect_timeout_seconds=4,
            read_timeout_seconds=45,
        )

        result = service.generate_pdf(
            "<!doctype html><html><body>中文</body></html>",
            PdfGenerationOptions.a4_portrait(),
        )

        self.assertEqual(result, b"%PDF-1.7 generated")
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://gotenberg:3000/forms/chromium/convert/html")
        self.assertEqual(kwargs["timeout"], (4, 45))
        self.assertIs(kwargs["stream"], True)
        self.assertEqual(kwargs["files"]["files"][0], "index.html")
        self.assertEqual(kwargs["files"]["files"][2], "text/html; charset=utf-8")
        self.assertIn("中文".encode("utf-8"), kwargs["files"]["files"][1])
        self.assertEqual(
            kwargs["data"],
            {
                "paperWidth": "8.268",
                "paperHeight": "11.693",
                "marginTop": "0.709",
                "marginBottom": "0.709",
                "marginLeft": "0.630",
                "marginRight": "0.630",
                "landscape": "false",
                "printBackground": "true",
                "preferCssPageSize": "false",
            },
        )

    @patch("app.services.pdf_generation_service.requests.post")
    def test_maps_timeout_and_upstream_errors_without_retry(self, post: Mock):
        service = GotenbergPdfGenerationService(base_url="http://gotenberg:3000")
        post.side_effect = requests.Timeout("upstream address must not leak")

        with self.assertRaises(PdfGenerationError):
            service.generate_pdf("<html></html>", PdfGenerationOptions.a4_portrait())

        post.assert_called_once()

    @patch("app.services.pdf_generation_service.requests.post")
    def test_landscape_keeps_base_dimensions_and_sets_orientation_flag(self, post: Mock):
        response = Mock()
        response.iter_content.return_value = [b"%PDF-1.7 landscape"]
        response.raise_for_status.return_value = None
        post.return_value = response
        options = PdfGenerationOptions(
            paper_size="A4",
            orientation="landscape",
            margin_top_mm=18,
            margin_bottom_mm=18,
            margin_left_mm=16,
            margin_right_mm=16,
        )

        GotenbergPdfGenerationService("http://gotenberg:3000").generate_pdf(
            "<html></html>",
            options,
        )

        data = post.call_args.kwargs["data"]
        self.assertEqual(data["paperWidth"], "8.268")
        self.assertEqual(data["paperHeight"], "11.693")
        self.assertEqual(data["landscape"], "true")
        self.assertEqual(options.page_width_mm, 297)
        self.assertEqual(options.page_height_mm, 210)

    @patch("app.services.pdf_generation_service.requests.post")
    def test_rejects_non_pdf_upstream_response(self, post: Mock):
        response = Mock()
        response.iter_content.return_value = [b"not a pdf"]
        response.raise_for_status.return_value = None
        post.return_value = response

        with self.assertRaises(PdfGenerationError):
            GotenbergPdfGenerationService("http://gotenberg:3000").generate_pdf(
                "<html></html>",
                PdfGenerationOptions.a4_portrait(),
            )

    @patch("app.services.pdf_generation_service.requests.post")
    def test_rejects_an_oversized_pdf_response(self, post: Mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.iter_content.return_value = [b"%PDF-123", b"456789"]
        post.return_value = response

        with self.assertRaises(PdfGenerationError):
            GotenbergPdfGenerationService(
                "http://gotenberg:3000",
                max_pdf_bytes=10,
            ).generate_pdf("<html></html>", PdfGenerationOptions.a4_portrait())

        response.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
