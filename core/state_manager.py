from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from typing import Any, Optional, Union

from core.phases import Phase


class StateManager:
    """
    Holds phase memory for HackEmpire X.

    Keeps a JSON-ready structure for each phase under:
      {"recon": {}, "enum": {}, "vuln": {}}

    Also maintains a global tool_health map updated after each phase:
      {"nmap": "ok", "ffuf": "timeout", ...}
    """

    def __init__(self) -> None:
        self.current_phase: Optional[str] = None
        self._results: dict[str, dict[str, Any]] = {
            Phase.RECON.value: {},
            Phase.ENUM.value: {},
            Phase.VULN.value: {},
        }
        # Global tool health across all phases.
        self._tool_health: dict[str, str] = {}

    def _phase_key(self, phase: Union[Phase, str]) -> Optional[str]:
        if isinstance(phase, Phase):
            return phase.value
        if isinstance(phase, str) and phase in self._results:
            return phase
        return None

    def set_phase(self, phase: Union[Phase, str]) -> None:
        key = self._phase_key(phase)
        if key is None:
            return
        self.current_phase = key

    def update(self, phase: Union[Phase, str], data: Mapping[str, Any]) -> None:
        key = self._phase_key(phase)
        if key is None:
            return

        # Safe merge: update only keys provided by `data`.
        # This prevents crashes if a phase already contains previous results.
        self._results[key].update(dict(data))

    def get_phase_data(self, phase: Union[Phase, str]) -> dict[str, Any]:
        key = self._phase_key(phase)
        if key is None:
            return {}
        return deepcopy(self._results[key])

    def get_all(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self._results)

    # ------------------------------------------------------------------
    # Tool health (global, cross-phase)
    # ------------------------------------------------------------------

    def update_tool_health(self, tool_status: Mapping[str, str]) -> None:
        """Merge a phase's tool_status dict into the global health map."""
        self._tool_health.update(dict(tool_status))

    def get_tool_health(self) -> dict[str, str]:
        """Return a copy of the global tool health map."""
        return dict(self._tool_health)

