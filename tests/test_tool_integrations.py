"""
Property-based and unit tests for new v4.4 tool integrations.

Property 10: All new tools implement BaseTool interface
  - For any tool class registered in ToolManager.TOOL_REGISTRY for the new v4 phases,
    the class SHALL be a subclass of BaseTool and SHALL implement check_installed(),
    build_command(target), and parse_output(raw_output) methods.
  **Validates: Requirements 4.6**

Property 11: Tool installation failure does not halt the scan
  - For any phase where one or more tools fail to install, the FallbackChain for that
    phase SHALL skip the failed tools and attempt the remaining tools, and the scan
    SHALL continue to the next phase.
  **Validates: Requirements 4.8**

Unit tests:
  - Test each new tool's parse_output() with representative raw output
  - Test that failed install marks tool as "not_installed" in ToolHealthTracker
  **Validates: Requirements 4.6, 4.8**
"""
from __future__ import annotations

import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)
_parent = os.path.dirname(_pkg_root)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import inspect
from typing import Any
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hackempire.tools.tool_manager import ToolManager
from hackempire.tools.health_tracker import ToolHealthTracker

# Import BaseTool via the same path the tools use (tools.base_tool, not hackempire.tools.base_tool)
# to avoid module identity mismatch when checking issubclass().
import importlib as _importlib
_base_tool_mod = _importlib.import_module("tools.base_tool")
BaseTool = _base_tool_mod.BaseTool
ToolNotInstalledError = _base_tool_mod.ToolNotInstalledError

# ---------------------------------------------------------------------------
# Collect all new v4.4 tool classes
# ---------------------------------------------------------------------------

from hackempire.tools.recon.theharvester_tool import TheHarvesterTool
from hackempire.tools.recon.reconng_tool import ReconNgTool
from hackempire.tools.recon.dnsenum_tool import DnsEnumTool
from hackempire.tools.recon.fierce_tool import FierceTool

from hackempire.tools.enum.wpprobe_tool import WPProbeTool
from hackempire.tools.enum.wpscan_tool import WPScanTool
from hackempire.tools.enum.joomscan_tool import JoomscanTool

from hackempire.tools.vuln.sstimap_tool import SSTImapTool
from hackempire.tools.vuln.zapproxy_tool import ZAPProxyTool
from hackempire.tools.vuln.semgrep_tool import SemgrepTool

from hackempire.tools.external.metasploit_mcp_tool import MetasploitMCPTool
from hackempire.tools.external.ysoserial_tool import YsoserialTool
from hackempire.tools.external.certipy_tool import CertipyTool

from hackempire.tools.post_exploit.adaptixc2_tool import AdaptixC2Tool
from hackempire.tools.post_exploit.atomic_operator_tool import AtomicOperatorTool
from hackempire.tools.post_exploit.pypykatz_tool import PypykatzTool
from hackempire.tools.post_exploit.pspy_tool import PspyTool
from hackempire.tools.post_exploit.evilwinrm_tool import EvilWinRMTool

ALL_NEW_TOOL_CLASSES = [
    TheHarvesterTool, ReconNgTool, DnsEnumTool, FierceTool,
    WPProbeTool, WPScanTool, JoomscanTool,
    SSTImapTool, ZAPProxyTool, SemgrepTool,
    MetasploitMCPTool, YsoserialTool, CertipyTool,
    AdaptixC2Tool, AtomicOperatorTool, PypykatzTool, PspyTool, EvilWinRMTool,
]

# ---------------------------------------------------------------------------
# Property 10: All new tools implement BaseTool interface
# ---------------------------------------------------------------------------

# Feature: hackempire-x-v4, Property 10: All new tools implement BaseTool interface
@given(st.sampled_from(ALL_NEW_TOOL_CLASSES))
@settings(max_examples=10)
def test_property_10_all_new_tools_implement_basetool_interface(tool_class: type) -> None:
    """Property 10: All new tools implement BaseTool interface.

    For any tool class registered in ToolManager.TOOL_REGISTRY for the new v4 phases,
    the class SHALL be a subclass of BaseTool and SHALL implement check_installed(),
    build_command(target), and parse_output(raw_output) methods.

    **Validates: Requirements 4.6**
    """
    # Must be a subclass of BaseTool
    assert issubclass(tool_class, BaseTool), (
        f"{tool_class.__name__} must be a subclass of BaseTool"
    )

    # Must have a non-empty name class attribute
    assert hasattr(tool_class, "name") and isinstance(tool_class.name, str) and tool_class.name.strip(), (
        f"{tool_class.__name__} must have a non-empty 'name' class attribute"
    )

    # Must implement check_installed()
    assert hasattr(tool_class, "check_installed"), (
        f"{tool_class.__name__} must implement check_installed()"
    )
    check_installed_method = getattr(tool_class, "check_installed")
    assert callable(check_installed_method), (
        f"{tool_class.__name__}.check_installed must be callable"
    )

    # Must implement build_command(target)
    assert hasattr(tool_class, "build_command"), (
        f"{tool_class.__name__} must implement build_command(target)"
    )
    build_command_method = getattr(tool_class, "build_command")
    assert callable(build_command_method), (
        f"{tool_class.__name__}.build_command must be callable"
    )
    sig = inspect.signature(build_command_method)
    params = list(sig.parameters.keys())
    # Should have 'self' and 'target' parameters
    assert "target" in params, (
        f"{tool_class.__name__}.build_command must accept a 'target' parameter"
    )

    # Must implement parse_output(raw_output)
    assert hasattr(tool_class, "parse_output"), (
        f"{tool_class.__name__} must implement parse_output(raw_output)"
    )
    parse_output_method = getattr(tool_class, "parse_output")
    assert callable(parse_output_method), (
        f"{tool_class.__name__}.parse_output must be callable"
    )
    sig2 = inspect.signature(parse_output_method)
    params2 = list(sig2.parameters.keys())
    assert "raw_output" in params2, (
        f"{tool_class.__name__}.parse_output must accept a 'raw_output' parameter"
    )

    # parse_output must return a dict with at least 'findings' and 'raw' keys
    instance = tool_class(timeout_s=30.0, web_scheme="https")
    result = instance.parse_output("sample output")
    assert isinstance(result, dict), (
        f"{tool_class.__name__}.parse_output must return a dict"
    )
    assert "findings" in result, (
        f"{tool_class.__name__}.parse_output must return a dict with 'findings' key"
    )
    assert "raw" in result, (
        f"{tool_class.__name__}.parse_output must return a dict with 'raw' key"
    )


# ---------------------------------------------------------------------------
# Property 11: Tool installation failure does not halt the scan
# ---------------------------------------------------------------------------

# Feature: hackempire-x-v4, Property 11: Tool installation failure does not halt the scan
@given(st.sampled_from(ALL_NEW_TOOL_CLASSES))
@settings(max_examples=10)
def test_property_11_tool_install_failure_does_not_halt_scan(tool_class: type) -> None:
    """Property 11: Tool installation failure does not halt the scan.

    For any phase where one or more tools fail to install, the FallbackChain for that
    phase SHALL skip the failed tools and attempt the remaining tools, and the scan
    SHALL continue to the next phase.

    **Validates: Requirements 4.8**
    """
    from hackempire.core.fallback_chain import FallbackChain

    # Create a mock emitter
    class _NoOpEmitter:
        def emit_tool_start(self, *a, **kw): pass
        def emit_tool_result(self, *a, **kw): pass
        def emit_tool_error(self, *a, **kw): pass

    # Create an instance of the tool with check_installed() patched to return False
    instance = tool_class(timeout_s=5.0, web_scheme="https")

    # A tool that always succeeds (fallback)
    class _SuccessTool:
        name = "success_fallback"
        def run(self, target: str) -> dict:
            return {"findings": ["fallback_result"], "raw": "ok"}

    # Build a FallbackChain: [failing_tool, success_tool]
    # The failing tool raises ToolNotInstalledError (simulating install failure)
    class _FailingTool:
        name = tool_class.name
        def run(self, target: str) -> dict:
            raise ToolNotInstalledError(f"{tool_class.name} not installed")

    chain = FallbackChain(
        tools=[_FailingTool(), _SuccessTool()],
        emitter=_NoOpEmitter(),
        phase="test_phase",
    )

    # The chain must NOT raise and must succeed via the fallback tool
    result = chain.execute("example.com")

    assert not result.degraded, (
        f"FallbackChain should not be degraded when a fallback tool succeeds "
        f"(tool_class={tool_class.__name__})"
    )
    assert result.succeeded_tool == "success_fallback", (
        f"Expected succeeded_tool='success_fallback', got {result.succeeded_tool!r}"
    )


# ---------------------------------------------------------------------------
# Unit tests: parse_output() with representative raw output
# ---------------------------------------------------------------------------

def _make_tool(cls: type, **kwargs: Any):
    return cls(timeout_s=30.0, web_scheme="https", **kwargs)


def test_theharvester_parse_output_emails_and_subdomains():
    tool = _make_tool(TheHarvesterTool)
    raw = "user@example.com\napi.example.com\nmail.example.com\n"
    result = tool.parse_output(raw)
    assert "emails" in result
    assert "subdomains" in result
    assert "user@example.com" in result["emails"]
    assert "api.example.com" in result["subdomains"]
    assert result["raw"] == raw


def test_reconng_parse_output_hosts():
    tool = _make_tool(ReconNgTool)
    raw = "[*] api.target.com\n[*] mail.target.com\n"
    result = tool.parse_output(raw)
    assert "subdomains" in result
    assert isinstance(result["findings"], list)
    assert result["raw"] == raw


def test_dnsenum_parse_output_subdomains():
    tool = _make_tool(DnsEnumTool)
    raw = "sub.example.com.  300  IN  A  1.2.3.4\nmail.example.com.  300  IN  A  5.6.7.8\n"
    result = tool.parse_output(raw)
    assert "subdomains" in result
    assert "sub.example.com" in result["subdomains"]
    assert result["raw"] == raw


def test_dnsenum_parse_output_zone_transfer():
    tool = _make_tool(DnsEnumTool)
    raw = "Zone transfer success for example.com\nsub.example.com.  300  IN  A  1.2.3.4\n"
    result = tool.parse_output(raw)
    assert result["zone_transfer"] is True
    assert "zone_transfer_success" in result["findings"]


def test_fierce_parse_output_subdomains():
    tool = _make_tool(FierceTool)
    raw = "Found: api.example.com. (1.2.3.4)\nFound: mail.example.com. (5.6.7.8)\n"
    result = tool.parse_output(raw)
    assert "subdomains" in result
    assert "api.example.com" in result["subdomains"]
    assert result["raw"] == raw


def test_wpprobe_parse_output_plugins():
    tool = _make_tool(WPProbeTool)
    raw = "wp-content/plugins/contact-form-7/readme.txt\nwp-content/plugins/yoast-seo/readme.txt\n"
    result = tool.parse_output(raw)
    assert "plugins" in result
    assert "contact-form-7" in result["plugins"]
    assert result["raw"] == raw


def test_wpscan_parse_output_vulnerabilities():
    tool = _make_tool(WPScanTool)
    raw = "[!] Title: WordPress 5.0 - Remote Code Execution\n[!] CVE-2019-8942\n"
    result = tool.parse_output(raw)
    assert "vulnerabilities" in result
    assert len(result["vulnerabilities"]) > 0
    assert result["raw"] == raw


def test_joomscan_parse_output_version_and_vulns():
    tool = _make_tool(JoomscanTool)
    raw = "Joomla 3.9.12 detected\n[!] Vulnerability: SQL Injection in component\n"
    result = tool.parse_output(raw)
    assert result["version"] == "3.9.12"
    assert len(result["vulnerabilities"]) > 0
    assert result["raw"] == raw


def test_sstimap_parse_output_ssti():
    tool = _make_tool(SSTImapTool)
    raw = "[+] SSTI vulnerability confirmed in parameter 'name'\nEngine: Jinja2\n"
    result = tool.parse_output(raw)
    assert len(result["vulnerabilities"]) > 0
    assert result["engine"] == "Jinja2"
    assert result["raw"] == raw


def test_zapproxy_parse_output_alerts():
    tool = _make_tool(ZAPProxyTool)
    raw = "High: Cross Site Scripting (Reflected)\nMedium: X-Frame-Options Header Not Set\n"
    result = tool.parse_output(raw)
    assert "vulnerabilities" in result
    assert len(result["vulnerabilities"]) >= 2
    assert result["raw"] == raw


def test_semgrep_parse_output_json():
    tool = _make_tool(SemgrepTool)
    import json
    raw = json.dumps({
        "results": [
            {"check_id": "python.sql-injection", "path": "app.py", "start": {"line": 10},
             "extra": {"severity": "ERROR"}}
        ]
    })
    result = tool.parse_output(raw)
    assert "vulnerabilities" in result
    assert len(result["vulnerabilities"]) == 1
    assert result["vulnerabilities"][0]["title"] == "python.sql-injection"


def test_semgrep_parse_output_fallback_text():
    tool = _make_tool(SemgrepTool)
    raw = "error: hardcoded password found in config.py\nwarning: SQL injection risk\n"
    result = tool.parse_output(raw)
    assert isinstance(result["findings"], list)
    assert result["raw"] == raw


def test_metasploit_mcp_parse_output_sessions():
    tool = _make_tool(MetasploitMCPTool)
    raw = "[*] Meterpreter session 1 opened (10.0.0.1:4444 -> 10.0.0.2:1234)\n"
    result = tool.parse_output(raw)
    assert "sessions" in result
    assert len(result["sessions"]) > 0
    assert result["raw"] == raw


def test_ysoserial_parse_output_gadgets():
    tool = _make_tool(YsoserialTool)
    raw = "CommonsCollections1  @frohoff\nCommonsCollections2  @frohoff\nSpring1  @frohoff\n"
    result = tool.parse_output(raw)
    assert "gadget_chains" in result
    assert len(result["gadget_chains"]) > 0
    assert result["raw"] == raw


def test_certipy_parse_output_esc_vulns():
    tool = _make_tool(CertipyTool)
    raw = "[!] ESC1 - Enrollee Supplies Subject\nTemplate Name : UserTemplate\n"
    result = tool.parse_output(raw)
    assert "vulnerabilities" in result
    assert len(result["vulnerabilities"]) > 0
    assert result["vulnerabilities"][0]["technique"] == "ESC1"
    assert "UserTemplate" in result["templates"]
    assert result["raw"] == raw


def test_adaptixc2_parse_output_agents():
    tool = _make_tool(AdaptixC2Tool)
    raw = "[+] Agent connected from 10.0.0.5\n[+] Agent check-in: beacon_001\n"
    result = tool.parse_output(raw)
    assert "agents" in result
    assert len(result["agents"]) > 0
    assert result["raw"] == raw


def test_atomic_operator_parse_output_tests():
    tool = _make_tool(AtomicOperatorTool)
    raw = "Executing T1059.001 - PowerShell\nTest executed successfully\nT1003.001 - LSASS Memory\n"
    result = tool.parse_output(raw)
    assert "tests_executed" in result
    assert len(result["tests_executed"]) > 0
    assert result["raw"] == raw


def test_pypykatz_parse_output_credentials():
    tool = _make_tool(PypykatzTool)
    raw = "Username : Administrator\nNT : aad3b435b51404eeaad3b435b51404ee\n"
    result = tool.parse_output(raw)
    assert "credentials" in result
    assert result["raw"] == raw


def test_pspy_parse_output_privileged_procs():
    tool = _make_tool(PspyTool)
    raw = "UID=0    PID=1234   | CMD=/usr/bin/cron -f\nUID=1000 PID=5678   | CMD=/bin/bash\n"
    result = tool.parse_output(raw)
    assert "privileged_processes" in result
    assert len(result["privileged_processes"]) == 1
    assert result["raw"] == raw


def test_evilwinrm_parse_output_shell():
    tool = _make_tool(EvilWinRMTool)
    raw = "Evil-WinRM shell v3.4\nPS C:\\Users\\Administrator> whoami\n"
    result = tool.parse_output(raw)
    assert "shell_obtained" in result
    assert result["raw"] == raw


# ---------------------------------------------------------------------------
# Unit tests: failed install marks tool as "not_installed" in ToolHealthTracker
# ---------------------------------------------------------------------------

def test_failed_install_marks_not_installed_in_health_tracker():
    """Test that a tool failing check_installed() is recorded as 'not_installed'."""
    tracker = ToolHealthTracker()

    for tool_class in ALL_NEW_TOOL_CLASSES:
        instance = tool_class(timeout_s=5.0, web_scheme="https")
        # Simulate install failure: check_installed returns False → run() raises ToolNotInstalledError
        with patch.object(instance, "check_installed", return_value=False):
            try:
                instance.run("example.com")
            except ToolNotInstalledError:
                tracker.record(instance.name, "not_installed")

        assert tracker.get(instance.name) == "not_installed", (
            f"Expected 'not_installed' for {tool_class.__name__}, "
            f"got {tracker.get(instance.name)!r}"
        )


def test_all_new_tools_registered_in_tool_registry():
    """All new v4.4 tool classes must be present in ToolManager.TOOL_REGISTRY."""
    all_registered_names: set[str] = set()
    for tool_classes in ToolManager.TOOL_REGISTRY.values():
        for cls in tool_classes:
            all_registered_names.add(cls.__name__)

    for tool_class in ALL_NEW_TOOL_CLASSES:
        assert tool_class.__name__ in all_registered_names, (
            f"{tool_class.__name__} is not registered in ToolManager.TOOL_REGISTRY"
        )


def test_new_tools_have_unique_names():
    """All new v4.4 tool classes must have unique name attributes."""
    names = [cls.name for cls in ALL_NEW_TOOL_CLASSES]
    assert len(names) == len(set(names)), (
        f"Duplicate tool names found: {[n for n in names if names.count(n) > 1]}"
    )


def test_parse_output_always_returns_dict_with_findings_and_raw():
    """parse_output() must always return a dict with 'findings' and 'raw' keys."""
    for tool_class in ALL_NEW_TOOL_CLASSES:
        instance = tool_class(timeout_s=30.0, web_scheme="https")
        for raw in ["", "some output", "error: something went wrong"]:
            result = instance.parse_output(raw)
            assert isinstance(result, dict), (
                f"{tool_class.__name__}.parse_output must return a dict"
            )
            assert "findings" in result, (
                f"{tool_class.__name__}.parse_output must include 'findings' key"
            )
            assert "raw" in result, (
                f"{tool_class.__name__}.parse_output must include 'raw' key"
            )
            assert result["raw"] == raw, (
                f"{tool_class.__name__}.parse_output must preserve raw output"
            )
