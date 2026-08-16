from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import urlsplit

import requests
from loguru import logger


PaperSize = Literal["A4"]
Orientation = Literal["portrait", "landscape"]


class PdfGenerationError(RuntimeError):
    """Stable internal error raised when the PDF upstream cannot produce a PDF."""


@dataclass(frozen=True)
class PdfGenerationOptions:
    paper_size: PaperSize
    orientation: Orientation
    margin_top_mm: float
    margin_bottom_mm: float
    margin_left_mm: float
    margin_right_mm: float

    def __post_init__(self) -> None:
        if self.paper_size != "A4":
            raise ValueError("Unsupported paper size")
        if self.orientation not in {"portrait", "landscape"}:
            raise ValueError("Unsupported orientation")
        margins = (
            self.margin_top_mm,
            self.margin_bottom_mm,
            self.margin_left_mm,
            self.margin_right_mm,
        )
        if any(value < 0 or value > 50 for value in margins):
            raise ValueError("Margins must be between 0mm and 50mm")

    @classmethod
    def a4_portrait(cls) -> "PdfGenerationOptions":
        return cls(
            paper_size="A4",
            orientation="portrait",
            margin_top_mm=18,
            margin_bottom_mm=18,
            margin_left_mm=16,
            margin_right_mm=16,
        )

    @property
    def page_width_mm(self) -> float:
        return self.paper_height_mm if self.orientation == "landscape" else self.paper_width_mm

    @property
    def page_height_mm(self) -> float:
        return self.paper_width_mm if self.orientation == "landscape" else self.paper_height_mm

    @property
    def paper_width_mm(self) -> float:
        return 210

    @property
    def paper_height_mm(self) -> float:
        return 297


class PdfGenerationService(Protocol):
    def generate_pdf(self, html: str, options: PdfGenerationOptions) -> bytes: ...


def _inches(mm: float) -> str:
    return f"{mm / 25.4:.3f}"


class GotenbergPdfGenerationService:
    def __init__(
        self,
        base_url: str,
        connect_timeout_seconds: float = 5,
        read_timeout_seconds: float = 60,
        max_pdf_bytes: int = 50 * 1024 * 1024,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")
        parsed = urlsplit(normalized_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path:
            raise ValueError("PDF service URL must be an HTTP(S) origin without a path")
        self._conversion_url = f"{normalized_url}/forms/chromium/convert/html"
        self._timeout = (connect_timeout_seconds, read_timeout_seconds)
        self._max_pdf_bytes = max_pdf_bytes

    def generate_pdf(self, html: str, options: PdfGenerationOptions) -> bytes:
        form_data = {
            "paperWidth": _inches(options.paper_width_mm),
            "paperHeight": _inches(options.paper_height_mm),
            "marginTop": _inches(options.margin_top_mm),
            "marginBottom": _inches(options.margin_bottom_mm),
            "marginLeft": _inches(options.margin_left_mm),
            "marginRight": _inches(options.margin_right_mm),
            "landscape": "true" if options.orientation == "landscape" else "false",
            "printBackground": "true",
            "preferCssPageSize": "false",
        }
        try:
            response = requests.post(
                self._conversion_url,
                files={"files": ("index.html", html.encode("utf-8"), "text/html; charset=utf-8")},
                data=form_data,
                timeout=self._timeout,
                stream=True,
            )
            response.raise_for_status()
            chunks: list[bytes] = []
            total_bytes = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total_bytes += len(chunk)
                if total_bytes > self._max_pdf_bytes:
                    logger.warning("PDF generation upstream response exceeded byte limit")
                    raise PdfGenerationError("Generated PDF is too large")
                chunks.append(chunk)
            pdf_bytes = b"".join(chunks)
        except requests.Timeout as exc:
            logger.warning("PDF generation upstream timed out")
            raise PdfGenerationError("PDF generation timed out") from exc
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning("PDF generation upstream request failed status={}", status_code)
            raise PdfGenerationError("PDF generation upstream failed") from exc
        finally:
            if "response" in locals():
                response.close()

        if not pdf_bytes.startswith(b"%PDF-"):
            logger.warning("PDF generation upstream returned invalid content bytes={}", len(pdf_bytes))
            raise PdfGenerationError("PDF generation returned invalid content")
        return pdf_bytes
