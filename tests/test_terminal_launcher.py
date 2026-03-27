"""
Unit and property-based tests for TerminalLauncher.

Unit tests:
  - PTY spawn failure returns None and scan continues
  - session_id uniqueness across concurrent sessions

Property 19: TerminalSession Unique IDs — all concurrent sessions have
distinct session_ids.
  **Validates: Requirements 5.6**
"""
from __future__ import annotations

import sys
import os
import types

_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)      # hackempire/
_parent = os.path.dirname(_pkg_root)    # repo root (contains hackempire/)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import subprocess
import threading
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Ensure pty is importable (mock it on Windows where it doesn't exist)
# ---------------------------------------------------------------------------

def _ensure_pty_mock():
    """Insert a minimal fake pty module into sys.modules if not present."""
    if "pty" not in sys.modules:
        fake_pty = types.ModuleType("pty")
        fake_pty.openpty = lambda: (10, 11)  # default stub
        sys.modules["pty"] = fake_pty


_ensure_pty_mock()

from hackempire.web.terminal_launcher import TerminalLauncher, TerminalSession  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_popen(pid: int = 12345) -> MagicMock:
    """Return a minimal Popen mock."""
    mock = MagicMock(spec=subprocess.Popen)
    mock.pid = pid
    return mock


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestTerminalLauncherUnit:
    """Unit tests for TerminalLauncher."""

    def test_launch_returns_none_when_pty_openpty_raises_oserror(self):
        """PTY spawn failure (OSError) returns None — scan continues normally."""
        launcher = TerminalLauncher(socketio=None)

        with patch.dict(sys.modules, {"pty": types.ModuleType("pty")}):
            sys.modules["pty"].openpty = MagicMock(side_effect=OSError("no pty"))
            result = launcher.launch([])

        assert result is None

    def test_launch_returns_none_when_pty_not_importable(self):
        """When pty module is not importable, launch() returns None."""
        launcher = TerminalLauncher(socketio=None)

        # Temporarily remove pty from sys.modules and make import fail
        original = sys.modules.pop("pty", None)
        try:
            import builtins
            real_import = builtins.__import__

            def _mock_import(name, *args, **kwargs):
                if name == "pty":
                    raise ImportError("no module named pty")
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=_mock_import):
                result = launcher.launch([])
        finally:
            if original is not None:
                sys.modules["pty"] = original
            elif "pty" in sys.modules:
                del sys.modules["pty"]
            _ensure_pty_mock()

        assert result is None

    def test_launch_returns_terminal_session_on_success(self):
        """Successful launch returns a TerminalSession with expected fields."""
        launcher = TerminalLauncher(socketio=None)
        mock_proc = _make_mock_popen(pid=9999)

        fake_pty = types.ModuleType("pty")
        fake_pty.openpty = MagicMock(return_value=(10, 11))

        with patch.dict(sys.modules, {"pty": fake_pty}), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch("os.close"), \
             patch("os.read", side_effect=OSError("eof")):
            session = launcher.launch([])

        assert session is not None
        assert isinstance(session, TerminalSession)
        assert session.pid == 9999
        assert session.fd == 10
        assert len(session.session_id) == 36  # UUID4 format

    def test_session_id_uniqueness_across_two_sessions(self):
        """Two concurrent sessions have distinct session_ids."""
        launcher = TerminalLauncher(socketio=None)
        mock_proc1 = _make_mock_popen(pid=1001)
        mock_proc2 = _make_mock_popen(pid=1002)

        popen_calls = iter([mock_proc1, mock_proc2])
        fd_pairs = iter([(10, 11), (12, 13)])

        fake_pty = types.ModuleType("pty")
        fake_pty.openpty = MagicMock(side_effect=fd_pairs)

        with patch.dict(sys.modules, {"pty": fake_pty}), \
             patch("subprocess.Popen", side_effect=popen_calls), \
             patch("os.close"), \
             patch("os.read", side_effect=OSError("eof")):
            s1 = launcher.launch([])
            s2 = launcher.launch([])

        assert s1 is not None
        assert s2 is not None
        assert s1.session_id != s2.session_id

    def test_launch_returns_none_when_popen_raises(self):
        """If Popen raises, launch() returns None."""
        launcher = TerminalLauncher(socketio=None)

        fake_pty = types.ModuleType("pty")
        fake_pty.openpty = MagicMock(return_value=(10, 11))

        with patch.dict(sys.modules, {"pty": fake_pty}), \
             patch("subprocess.Popen", side_effect=OSError("exec failed")), \
             patch("os.close"):
            result = launcher.launch([])

        assert result is None

    def test_write_silently_ignores_unknown_session(self):
        """write() with unknown session_id does not raise."""
        launcher = TerminalLauncher(socketio=None)
        launcher.write("nonexistent-id", "hello")  # must not raise

    def test_resize_silently_ignores_unknown_session(self):
        """resize() with unknown session_id does not raise."""
        launcher = TerminalLauncher(socketio=None)
        launcher.resize("nonexistent-id", 24, 80)  # must not raise

    def test_kill_silently_ignores_unknown_session(self):
        """kill() with unknown session_id does not raise."""
        launcher = TerminalLauncher(socketio=None)
        launcher.kill("nonexistent-id")  # must not raise

    def test_kill_removes_session_from_registry(self):
        """kill() removes the session from the internal registry."""
        launcher = TerminalLauncher(socketio=None)
        mock_proc = _make_mock_popen(pid=5555)

        fake_pty = types.ModuleType("pty")
        fake_pty.openpty = MagicMock(return_value=(20, 21))

        with patch.dict(sys.modules, {"pty": fake_pty}), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch("os.close"), \
             patch("os.read", side_effect=OSError("eof")):
            session = launcher.launch([])

        assert session is not None
        sid = session.session_id
        assert sid in launcher._sessions

        with patch("os.close"):
            launcher.kill(sid)

        assert sid not in launcher._sessions

    def test_socketio_emit_called_on_output(self):
        """Reader thread emits terminal_output via socketio when data arrives."""
        mock_socketio = MagicMock()
        launcher = TerminalLauncher(socketio=mock_socketio)
        mock_proc = _make_mock_popen(pid=7777)

        # Simulate one read returning data, then OSError to stop the loop
        read_results = iter([b"hello", OSError("eof")])

        def _fake_read(fd, size):
            val = next(read_results)
            if isinstance(val, Exception):
                raise val
            return val

        event = threading.Event()
        original_emit = mock_socketio.emit.side_effect

        def _emit_and_signal(*args, **kwargs):
            event.set()

        mock_socketio.emit.side_effect = _emit_and_signal

        fake_pty = types.ModuleType("pty")
        fake_pty.openpty = MagicMock(return_value=(30, 31))

        with patch.dict(sys.modules, {"pty": fake_pty}), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch("os.close"), \
             patch("os.read", side_effect=_fake_read):
            launcher.launch([])

        event.wait(timeout=2.0)
        mock_socketio.emit.assert_called_once()
        call_args = mock_socketio.emit.call_args
        assert call_args[0][0] == "terminal_output"
        assert call_args[0][1]["data"] == "hello"


# ---------------------------------------------------------------------------
# Property 19: TerminalSession Unique IDs
# ---------------------------------------------------------------------------

@st.composite
def _tool_lists(draw):
    """Generate lists of tool name strings."""
    return draw(st.lists(
        st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("Ll", "Lu", "Nd"),
                whitelist_characters="-_",
            ),
        ),
        min_size=0,
        max_size=5,
    ))


@given(tool_lists=st.lists(_tool_lists(), min_size=1, max_size=10))
@settings(max_examples=10, deadline=None)
def test_property_19_terminal_session_unique_ids(tool_lists):
    """Property 19: TerminalSession Unique IDs — all concurrent sessions have
    distinct session_ids.

    **Validates: Requirements 5.6**
    """
    launcher = TerminalLauncher(socketio=None)
    session_ids = []
    fd_counter = [100]

    def _fake_openpty():
        master = fd_counter[0]
        slave = fd_counter[0] + 1
        fd_counter[0] += 2
        return master, slave

    def _fake_popen(*args, **kwargs):
        mock = MagicMock(spec=subprocess.Popen)
        mock.pid = fd_counter[0] + 1000
        return mock

    fake_pty = types.ModuleType("pty")
    fake_pty.openpty = _fake_openpty

    with patch.dict(sys.modules, {"pty": fake_pty}), \
         patch("subprocess.Popen", side_effect=_fake_popen), \
         patch("os.close"), \
         patch("os.read", side_effect=OSError("eof")):
        for tools in tool_lists:
            session = launcher.launch(tools)
            if session is not None:
                session_ids.append(session.session_id)

    # All session_ids must be unique
    assert len(session_ids) == len(set(session_ids)), (
        f"Duplicate session_ids found: {session_ids}"
    )
