"""
TodoPlanner — generates and tracks a TodoList for a pentest session.

Responsibilities:
- Generate a 7-phase x 6-task TodoList via AIEngine
- Track task completion per phase
- Compute per-phase progress (0.0..1.0)
- Emit real-time updates via RealTimeEmitter on status changes
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from hackempire.core.models import TodoList

if TYPE_CHECKING:
    from hackempire.ai.ai_engine import AIEngine
    from hackempire.web.realtime_emitter import RealTimeEmitter

logger = logging.getLogger(__name__)


class TodoPlanner:
    """Manages todo list generation and progress tracking for a pentest session.

    Parameters
    ----------
    emitter:
        Optional ``RealTimeEmitter`` instance. When ``None``, status updates
        are not broadcast (useful for CLI / offline mode).
    """

    def __init__(self, emitter: RealTimeEmitter | None = None) -> None:
        self._emitter = emitter
        self._todo: TodoList | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, target: str, ai_engine: AIEngine) -> TodoList:
        """Generate a TodoList for *target* using *ai_engine*.

        Calls ``ai_engine.generate_todo_list(target)`` and stores the result
        in ``self._todo``.

        Returns
        -------
        TodoList
            The generated (or KB-fallback) todo list.
        """
        self._todo = ai_engine.generate_todo_list(target)
        return self._todo

    def mark_task_done(self, phase: str, task_index: int) -> None:
        """Mark the task at *task_index* in *phase* as ``"done"``.

        Silently ignores invalid phase names or out-of-range indices.
        Emits a ``todo_update`` event if an emitter is configured.
        """
        if self._todo is None:
            return

        tasks = self._todo.phases.get(phase)
        if tasks is None:
            return

        if task_index < 0 or task_index >= len(tasks):
            return

        tasks[task_index].status = "done"

        if self._emitter is not None:
            try:
                self._emitter.emit_todo_update(self._todo)
            except Exception as exc:  # noqa: BLE001
                logger.error("TodoPlanner: failed to emit todo update: %s", exc)

    def mark_phase_done(self, phase: str, chain_result: Any = None) -> None:  # noqa: ARG002
        """Mark all tasks in *phase* as ``"done"``.

        Provided for compatibility with the orchestrator which calls this
        after a phase completes. *chain_result* is accepted but not used.
        Emits a single ``todo_update`` after all tasks are updated.
        """
        if self._todo is None:
            return

        tasks = self._todo.phases.get(phase)
        if tasks is None:
            return

        for task in tasks:
            task.status = "done"

        if self._emitter is not None:
            try:
                self._emitter.emit_todo_update(self._todo)
            except Exception as exc:  # noqa: BLE001
                logger.error("TodoPlanner: failed to emit todo update: %s", exc)

    def get_progress(self) -> dict[str, float]:
        """Return per-phase completion progress.

        Returns
        -------
        dict[str, float]
            Mapping of phase name → fraction of done tasks (0.0..1.0).
            Phases with zero tasks map to 0.0.
        """
        if self._todo is None:
            return {}

        progress: dict[str, float] = {}
        for phase, tasks in self._todo.phases.items():
            total = len(tasks)
            if total == 0:
                progress[phase] = 0.0
            else:
                done = sum(1 for t in tasks if t.status == "done")
                ratio = done / total
                # Clamp to [0.0, 1.0] for safety
                progress[phase] = max(0.0, min(1.0, ratio))
        return progress
