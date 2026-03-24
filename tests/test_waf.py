"""
Property-based tests for WafDetector and WafBypassStrategy.

Property 10: WafDetector Never Raises
  - detect() always returns WafResult, never raises
  **Validates: Requirements 7.2**

Property 11: WafBypassStrategy Returns Tampers for Known Vendors
  - all 7 known vendors return non-empty list
  **Validates: Requirements 7.6**
"""

import sys
import os
import json
from unittest.mock import MagicMock, patch

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)          # hackempire/
_parent = os.path.dirname(_pkg_root)        # repo root (contains hackempire/)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.core.models import WafResult
from hackempire.tools.waf.waf_detector import WafDetector
from hackempire.tools.waf.waf_bypass_strategy import WafBypassStrategy, WAF_TAMPER_MAP


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_target_st = st.text(min_size=1, max_size=200)

# Strategy: subprocess.run return values
@st.composite
def _subprocess_result_st(draw):
    """Generate various subprocess.run return values."""
    kind = draw(st.integers(min_value=0, max_value=4))
    mock = MagicMock()
    if kind == 0:
        # Success with detected=True
        data = [{"url": "http://example.com", "detected": True, "firewall": "Cloudflare", "manufacturer": "Cloudflare Inc."}]
        mock.returncode = 0
        mock.stdout = json.dumps(data).encode("utf-8")
    elif kind == 1:
        # Success with detected=False
        data = [{"url": "http://example.com", "detected": False, "firewall": None, "manufacturer": None}]
        mock.returncode = 0
        mock.stdout = json.dumps(data).encode("utf-8")
    elif kind == 2:
        # Non-zero return code
        mock.returncode = 1
        mock.stdout = b""
    elif kind == 3:
        # Invalid JSON output
        mock.returncode = 0
        mock.stdout = b"not valid json {{{"
    else:
        # Empty stdout
        mock.returncode = 0
        mock.stdout = b""
    return mock


# ---------------------------------------------------------------------------
# Property 10: WafDetector Never Raises
# ---------------------------------------------------------------------------

@given(target=_target_st, subprocess_result=_subprocess_result_st())
@settings(max_examples=200)
def test_property_10_waf_detector_never_raises_installed(target, subprocess_result):
    """Property 10: WafDetector Never Raises — detect() always returns WafResult,
    never raises when wafw00f is installed.

    **Validates: Requirements 7.2**
    """
    detector = WafDetector()
    with patch("hackempire.tools.waf.waf_detector.shutil.which", return_value="/usr/bin/wafw00f"), \
         patch("hackempire.tools.waf.waf_detector.subprocess.run", return_value=subprocess_result):
        try:
            result = detector.detect(target)
        except Exception as exc:
            raise AssertionError(
                f"WafDetector.detect() raised {type(exc).__name__}: {exc}"
            ) from exc

        assert isinstance(result, WafResult), (
            f"Expected WafResult, got {type(result)}"
        )


@given(target=_target_st)
@settings(max_examples=100)
def test_property_10_waf_detector_never_raises_not_installed(target):
    """Property 10: WafDetector Never Raises — detect() always returns WafResult
    when wafw00f is not installed.

    **Validates: Requirements 7.2**
    """
    detector = WafDetector()
    with patch("hackempire.tools.waf.waf_detector.shutil.which", return_value=None):
        try:
            result = detector.detect(target)
        except Exception as exc:
            raise AssertionError(
                f"WafDetector.detect() raised {type(exc).__name__}: {exc}"
            ) from exc

        assert isinstance(result, WafResult), (
            f"Expected WafResult, got {type(result)}"
        )
        assert result.detected is False
        assert result.vendor is None
        assert result.confidence == 0.0


@given(target=_target_st)
@settings(max_examples=100)
def test_property_10_waf_detector_never_raises_subprocess_exception(target):
    """Property 10: WafDetector Never Raises — detect() always returns WafResult
    even when subprocess.run raises an exception.

    **Validates: Requirements 7.2**
    """
    detector = WafDetector()
    with patch("hackempire.tools.waf.waf_detector.shutil.which", return_value="/usr/bin/wafw00f"), \
         patch("hackempire.tools.waf.waf_detector.subprocess.run", side_effect=OSError("process failed")):
        try:
            result = detector.detect(target)
        except Exception as exc:
            raise AssertionError(
                f"WafDetector.detect() raised {type(exc).__name__}: {exc}"
            ) from exc

        assert isinstance(result, WafResult), (
            f"Expected WafResult, got {type(result)}"
        )
        assert result.detected is False


# ---------------------------------------------------------------------------
# Explicit example-based tests for WafDetector
# ---------------------------------------------------------------------------

def test_waf_detector_not_installed_returns_no_detection():
    """When wafw00f is not installed, detect() returns WafResult(detected=False)."""
    detector = WafDetector()
    with patch("hackempire.tools.waf.waf_detector.shutil.which", return_value=None):
        result = detector.detect("http://example.com")
    assert isinstance(result, WafResult)
    assert result.detected is False
    assert result.vendor is None
    assert result.confidence == 0.0


def test_waf_detector_subprocess_fails_returns_no_detection():
    """When wafw00f exits with non-zero code, detect() returns WafResult(detected=False)."""
    detector = WafDetector()
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = b""
    with patch("hackempire.tools.waf.waf_detector.shutil.which", return_value="/usr/bin/wafw00f"), \
         patch("hackempire.tools.waf.waf_detector.subprocess.run", return_value=mock_result):
        result = detector.detect("http://example.com")
    assert isinstance(result, WafResult)
    assert result.detected is False


def test_waf_detector_invalid_json_returns_no_detection():
    """When wafw00f returns invalid JSON, detect() returns WafResult(detected=False)."""
    detector = WafDetector()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = b"not valid json {{{"
    with patch("hackempire.tools.waf.waf_detector.shutil.which", return_value="/usr/bin/wafw00f"), \
         patch("hackempire.tools.waf.waf_detector.subprocess.run", return_value=mock_result):
        result = detector.detect("http://example.com")
    assert isinstance(result, WafResult)
    assert result.detected is False


def test_waf_detector_detected_true():
    """When wafw00f returns detected=True, detect() returns WafResult with vendor."""
    detector = WafDetector()
    data = [{"url": "http://example.com", "detected": True, "firewall": "Cloudflare", "manufacturer": "Cloudflare Inc."}]
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(data).encode("utf-8")
    with patch("hackempire.tools.waf.waf_detector.shutil.which", return_value="/usr/bin/wafw00f"), \
         patch("hackempire.tools.waf.waf_detector.subprocess.run", return_value=mock_result):
        result = detector.detect("http://example.com")
    assert isinstance(result, WafResult)
    assert result.detected is True
    assert result.vendor == "Cloudflare"
    assert result.confidence == 0.8


def test_waf_detector_detected_false():
    """When wafw00f returns detected=False, detect() returns WafResult with no vendor."""
    detector = WafDetector()
    data = [{"url": "http://example.com", "detected": False, "firewall": None, "manufacturer": None}]
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(data).encode("utf-8")
    with patch("hackempire.tools.waf.waf_detector.shutil.which", return_value="/usr/bin/wafw00f"), \
         patch("hackempire.tools.waf.waf_detector.subprocess.run", return_value=mock_result):
        result = detector.detect("http://example.com")
    assert isinstance(result, WafResult)
    assert result.detected is False
    assert result.vendor is None
    assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# Property 11: WafBypassStrategy Returns Tampers for Known Vendors
# ---------------------------------------------------------------------------

KNOWN_VENDORS = list(WAF_TAMPER_MAP.keys())  # cloudflare, akamai, modsecurity, imperva, f5, barracuda, sucuri


@given(vendor=st.sampled_from(KNOWN_VENDORS))
@settings(max_examples=100)
def test_property_11_known_vendors_return_non_empty_tampers(vendor):
    """Property 11: WafBypassStrategy Returns Tampers for Known Vendors —
    all 7 known vendors return non-empty list.

    **Validates: Requirements 7.6**
    """
    strategy = WafBypassStrategy()
    tampers = strategy.get_sqlmap_tampers(vendor)
    assert isinstance(tampers, list), (
        f"Expected list for vendor={vendor!r}, got {type(tampers)}"
    )
    assert len(tampers) > 0, (
        f"Expected non-empty tamper list for vendor={vendor!r}, got empty list"
    )


# ---------------------------------------------------------------------------
# Explicit example-based tests for WafBypassStrategy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("vendor", KNOWN_VENDORS)
def test_waf_bypass_all_known_vendors_return_non_empty(vendor):
    """All 7 known vendors return a non-empty tamper list."""
    strategy = WafBypassStrategy()
    tampers = strategy.get_sqlmap_tampers(vendor)
    assert isinstance(tampers, list)
    assert len(tampers) > 0, f"Empty tamper list for vendor: {vendor}"


@pytest.mark.parametrize("vendor", ["Cloudflare", "CLOUDFLARE", "CloudFlare"])
def test_waf_bypass_case_insensitive_matching(vendor):
    """get_sqlmap_tampers() matches vendor names case-insensitively."""
    strategy = WafBypassStrategy()
    tampers = strategy.get_sqlmap_tampers(vendor)
    assert isinstance(tampers, list)
    assert len(tampers) > 0, f"Empty tamper list for case variant: {vendor}"
    # Should match the cloudflare entry
    assert tampers == list(WAF_TAMPER_MAP["cloudflare"])


def test_waf_bypass_none_vendor_returns_default():
    """None vendor returns the default tamper list."""
    strategy = WafBypassStrategy()
    tampers = strategy.get_sqlmap_tampers(None)
    assert tampers == ["space2comment", "randomcase"]


def test_waf_bypass_unknown_vendor_returns_default():
    """Unknown vendor returns the default tamper list."""
    strategy = WafBypassStrategy()
    tampers = strategy.get_sqlmap_tampers("unknown_waf_xyz")
    assert tampers == ["space2comment", "randomcase"]


def test_waf_bypass_returns_copy_not_reference():
    """get_sqlmap_tampers() returns a copy, not the original list."""
    strategy = WafBypassStrategy()
    tampers1 = strategy.get_sqlmap_tampers("cloudflare")
    tampers2 = strategy.get_sqlmap_tampers("cloudflare")
    tampers1.append("extra")
    assert "extra" not in tampers2, "Mutating returned list should not affect subsequent calls"
