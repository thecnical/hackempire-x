from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hackempire.core.models import ChainResult, ToolAttempt
from hackempire.tools.base_tool import BaseTool, ToolExecutionError, ToolNotInstalledError, ToolTimeoutError

if TYPE_CHECKING:
    from hackempire.web.realtime_emitter import RealTimeEmitter
    from hackempire.tools.external.aegis_bridge import AegisBridge


class FallbackChain:
    """
    Tries tools in priority order, stopping on the first success.
    Returns a ChainResult in all cases and never raises.
    """

    def __init__(
        self,
        tools: list[BaseTool],
        emitter: Any,
        phase: str,
        aegis_bridge: "AegisBridge | None" = None,
    ) -> None:
        self._tools = tools
        self._emitter = emitter
        self._phase = phase
        self._aegis_bridge = aegis_bridge

    def execute(self, target: str) -> ChainResult:
        attempts: list[ToolAttempt] = []

        for tool in self._tools:
            # Notify emitter that this tool is starting
            try:
                self._emitter.emit_tool_start(self._phase, tool.name, target)
            except Exception:
                pass

            try:
                result: dict[str, Any] = tool.run(target)
            except (ToolNotInstalledError, ToolTimeoutError, ToolExecutionError) as e:
                attempts.append(ToolAttempt(tool_name=tool.name, status="failed", error=str(e)))
                try:
                    self._emitter.emit_tool_error(self._phase, tool.name, str(e))
                except Exception:
                    pass
                continue
            except Exception as e:
                # Catch-all: unexpected errors should not propagate
                attempts.append(ToolAttempt(tool_name=tool.name, status="failed", error=str(e)))
                try:
                    self._emitter.emit_tool_error(self._phase, tool.name, str(e))
                except Exception:
                    pass
                continue

            # Success
            attempts.append(ToolAttempt(tool_name=tool.name, status="success"))
            try:
                self._emitter.emit_tool_result(self._phase, tool.name, result)
            except Exception:
                pass

            return ChainResult(
                phase=self._phase,
                succeeded_tool=tool.name,
                results=result,
                tool_attempts=attempts,
                degraded=False,
            )

        # All primary tools failed — try AegisBridge if available
        if self._aegis_bridge is not None and self._aegis_bridge.is_available():
            aegis_result = self._aegis_bridge.run(target, self._phase)
            if not aegis_result.degraded:
                aegis_result.tool_attempts = attempts + aegis_result.tool_attempts
                return aegis_result
            attempts.extend(aegis_result.tool_attempts)

        return ChainResult(
            phase=self._phase,
            succeeded_tool=None,
            results={},
            tool_attempts=attempts,
            degraded=True,
        )
