"""
Tests for export routes — Task 21.1 (unit tests) and Task 21.2 (property test).

Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure hackempire root is importable
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from web.app import create_app
from web.routes import EXPORT_MIME_TYPES

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Task 21.1 — Unit tests for export routes
# ---------------------------------------------------------------------------

class TestExportRoutesMimeTypes:
    """Each valid format returns the correct MIME type with HTTP 200."""

    def test_json_mime_type(self, client):
        response = client.get("/api/export/json")
        assert response.status_code == 200
        assert "application/json" in response.content_type

    def test_html_mime_type(self, client):
        response = client.get("/api/export/html")
        assert response.status_code == 200
        assert "text/html" in response.content_type

    def test_markdown_mime_type(self, client):
        response = client.get("/api/export/markdown")
        assert response.status_code == 200
        assert "text/markdown" in response.content_type

    def test_csv_mime_type(self, client):
        response = client.get("/api/export/csv")
        assert response.status_code == 200
        assert "text/csv" in response.content_type

    def test_pdf_returns_content(self, client):
        # PDF may fall back to HTML if WeasyPrint is not installed; either is acceptable
        response = client.get("/api/export/pdf")
        assert response.status_code == 200
        assert response.content_type in (
            "application/pdf",
            "text/html",
            "text/html; charset=utf-8",
        )


class TestExportRoutesUnknownFormat:
    """Unknown format returns HTTP 400 with JSON error body containing the format name."""

    def test_unknown_format_status(self, client):
        response = client.get("/api/export/xml")
        assert response.status_code == 400

    def test_unknown_format_json_body(self, client):
        response = client.get("/api/export/xml")
        data = response.get_json()
        assert data is not None
        assert "error" in data
        assert "xml" in data["error"]

    def test_unknown_format_contains_format_name(self, client):
        response = client.get("/api/export/docx")
        data = response.get_json()
        assert "docx" in data["error"]

    def test_unknown_format_empty_string_like(self, client):
        response = client.get("/api/export/unknown")
        assert response.status_code == 400
        data = response.get_json()
        assert "unknown" in data["error"]


# ---------------------------------------------------------------------------
# Task 21.2 — Property test: Export MIME Type Correctness
#
# **Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5**
#
# Property 18: Export MIME Type Correctness
#   For every valid format string, the /api/export/<format> endpoint returns
#   HTTP 200 and a Content-Type header that matches the expected MIME type.
# ---------------------------------------------------------------------------

VALID_FORMATS = list(EXPORT_MIME_TYPES.keys())
# Exclude pdf from strict MIME check because WeasyPrint may not be installed
# and the route legitimately falls back to text/html.
STRICT_FORMATS = [f for f in VALID_FORMATS if f != "pdf"]


@given(fmt=st.sampled_from(STRICT_FORMATS))
@settings(max_examples=len(STRICT_FORMATS) * 3)
def test_property_export_mime_type_correctness(fmt: str) -> None:
    """**Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5**

    Property 18: For every valid format, the export endpoint returns the
    correct MIME type declared in EXPORT_MIME_TYPES.
    """
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get(f"/api/export/{fmt}")
        assert response.status_code == 200, (
            f"Expected 200 for format '{fmt}', got {response.status_code}"
        )
        expected_mime = EXPORT_MIME_TYPES[fmt]
        assert expected_mime in response.content_type, (
            f"Expected MIME '{expected_mime}' for format '{fmt}', "
            f"got '{response.content_type}'"
        )
