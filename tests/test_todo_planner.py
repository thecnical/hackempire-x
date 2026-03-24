"""
Property-based tests for TodoPlanner.

Property 9: TodoPlanner Progress Bounds
  - get_progress() always returns floats between 0.0 and 1.0
  **Validates: Requirements 3.6**
"""

import sys
import os

# Ensure hackempire package is importable regardless of working directory
_here = os.path.dirname(os.path.abspath(__file__))
_pkg_root = os.path.dirname(_here)      # hackempire/
_parent = os.path.dirname(_pkg_root)    # repo root (contains hackempire/)
for _p in (_pkg_root, _parent):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unittest.mock import MagicMock

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from hackempire.core.models import TodoList, TodoTask
from hackempire.core.todo_planner import TodoPlanner

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_PHASE_NAMES = [
    "recon",
    "url_discovery",
    "enumeration",
    "vuln_scan",
    "exploitation",
    "post_exploit",
    "reporting",
]

_status_st = st.sampled_from(["pending", "running", "done", "failed", "skipped"])


def _make_task(index: int, status: str) -> TodoTask:
    return TodoTask(
        index=index,
        description=f"Task {index}",
        tool=f"tool_{index}",
        status=status,
    )


# Strategy: generate a list of tasks with hypothesis-controlled statuses
_tasks_st = st.lists(
    _status_st,
    min_size=0,
    max_size=10,
).map(lambda statuses: [_make_task(i, s) for i, s in enumerate(statuses)])

# Strategy: generate a phases dict with 1–7 phases, each with 0–10 tasks
_phases_st = st.dictionaries(
    keys=st.sampled_from(_PHASE_NAMES),
    values=_tasks_st,
    min_size=1,
    max_size=7,
)

# Strategy: generate a complete TodoList
_todo_list_st = _phases_st.map(
    lambda phases: TodoList(target="example.com", phases=phases)
)


def _make_planner_with_todo(todo: TodoList) -> TodoPlanner:
    """Return a TodoPlanner whose generate() returns the given TodoList."""
    mock_engine = MagicMock()
    mock_engine.generate_todo_list.return_value = todo
    planner = TodoPlanner(emitter=None)
    planner.generate("example.com", mock_engine)
    return planner


# ---------------------------------------------------------------------------
# Property 9: TodoPlanner Progress Bounds
# ---------------------------------------------------------------------------

@given(todo=_todo_list_st)
@settings(max_examples=300)
def test_property_9_progress_bounds(todo):
    """Property 9: TodoPlanner Progress Bounds — get_progress() always returns
    floats between 0.0 and 1.0 inclusive for any TodoList state.

    **Validates: Requirements 3.6**
    """
    planner = _make_planner_with_todo(todo)
    progress = planner.get_progress()

    assert isinstance(progress, dict), f"Expected dict, got {type(progress)}"
    for phase, value in progress.items():
        assert isinstance(value, float), (
            f"Phase '{phase}' progress is {type(value)}, expected float"
        )
        assert 0.0 <= value <= 1.0, (
            f"Phase '{phase}' progress {value} is out of [0.0, 1.0]"
        )


@given(todo=_todo_list_st)
@settings(max_examples=200)
def test_property_9_progress_keys_match_phases(todo):
    """Property 9 (keys): get_progress() returns exactly the same phase keys
    as the TodoList.phases dict.

    **Validates: Requirements 3.6**
    """
    planner = _make_planner_with_todo(todo)
    progress = planner.get_progress()
    assert set(progress.keys()) == set(todo.phases.keys())


@given(
    phase=st.sampled_from(_PHASE_NAMES),
    n_tasks=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=200)
def test_property_9_marking_done_increases_progress(phase, n_tasks):
    """Property 9 (monotonicity): marking tasks done never decreases progress.

    **Validates: Requirements 3.6**
    """
    tasks = [_make_task(i, "pending") for i in range(n_tasks)]
    todo = TodoList(target="example.com", phases={phase: tasks})
    planner = _make_planner_with_todo(todo)

    prev = planner.get_progress().get(phase, 0.0)
    for i in range(n_tasks):
        planner.mark_task_done(phase, i)
        current = planner.get_progress().get(phase, 0.0)
        assert current >= prev, (
            f"Progress decreased after marking task {i} done: {prev} -> {current}"
        )
        prev = current


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_progress_empty_todo():
    """Edge case: no todo generated — get_progress() returns empty dict."""
    planner = TodoPlanner(emitter=None)
    assert planner.get_progress() == {}


def test_progress_empty_phase():
    """Edge case: a phase with zero tasks maps to 0.0."""
    todo = TodoList(target="example.com", phases={"recon": []})
    planner = _make_planner_with_todo(todo)
    progress = planner.get_progress()
    assert progress["recon"] == 0.0


def test_progress_all_done():
    """Edge case: all tasks done → progress == 1.0 for that phase."""
    tasks = [_make_task(i, "done") for i in range(6)]
    todo = TodoList(target="example.com", phases={"recon": tasks})
    planner = _make_planner_with_todo(todo)
    assert planner.get_progress()["recon"] == 1.0


def test_progress_none_done():
    """Edge case: no tasks done → progress == 0.0 for that phase."""
    tasks = [_make_task(i, "pending") for i in range(6)]
    todo = TodoList(target="example.com", phases={"recon": tasks})
    planner = _make_planner_with_todo(todo)
    assert planner.get_progress()["recon"] == 0.0


def test_progress_partial():
    """Edge case: 3 of 6 tasks done → progress == 0.5."""
    tasks = [_make_task(i, "done" if i < 3 else "pending") for i in range(6)]
    todo = TodoList(target="example.com", phases={"recon": tasks})
    planner = _make_planner_with_todo(todo)
    assert planner.get_progress()["recon"] == 0.5
