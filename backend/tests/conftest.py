"""Shared pytest fixtures for the backend test suite.

The suite must stay hermetic (AGENTS.md: no real network / model downloads).
#58 layout detection is enabled by default in production configuration, so an
autouse fixture switches it off for every test; the layout-specific suites
(test_layout_service, test_draft_figures) re-enable it locally and inject
fakes instead of touching the real engine.
"""

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _layout_detection_off():
    original = settings.LAYOUT_ENABLED
    settings.LAYOUT_ENABLED = False
    yield
    settings.LAYOUT_ENABLED = original
