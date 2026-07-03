from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from axdt.agent_runner.state import AgentState


class PlatformAdapter(ABC):
    """Platform-specific knowledge (Claude Code / Codex).

    Shared lifecycle helpers (format_prompt, detect_state) live here as
    concrete methods driven by subclass data (the marker tuples). Subclasses
    normally declare only data + build_launch_command, and may override the
    concrete methods when a platform genuinely diverges (Phase 3).
    """

    name: str
    config_dir_name: str

    # Output markers (subclasses fill these). Precedence: ERROR > WAITING_INPUT
    # > BUSY > IDLE. Provisional — verified live in Phase 3 (PLATFORM_MATRIX.md).
    _ERROR_MARKERS: tuple[str, ...] = ()
    _WAITING_MARKERS: tuple[str, ...] = ()
    _BUSY_MARKERS: tuple[str, ...] = ()
    _IDLE_MARKERS: tuple[str, ...] = ()

    def config_dir(self, workdir: Path) -> Path:
        """Resolved config dir = workdir / config_dir_name."""
        return workdir / self.config_dir_name

    @abstractmethod
    def build_launch_command(self, workdir: Path) -> list[str]:
        """argv that starts the agent CLI session.

        Config is resolved via cwd=workdir (the backend runs this argv with
        cwd=workdir, and config_dir = workdir/config_dir_name lives inside it).
        Explicit config flags are provisional and verified live in Phase 3
        (PLATFORM_MATRIX.md).
        """

    def format_prompt(self, text: str) -> str:
        """Render a prompt for injection. Returns literal text passed verbatim
        to SessionBackend.send_text (including the submit newline). Override if
        a platform needs a different submit convention (Phase 3)."""
        return text + "\n"

    def detect_state(self, recent_output: str) -> AgentState | None:
        """Infer state from an (already ANSI-normalised, windowed) output tail
        using the subclass marker tuples. The marker appearing **latest** in the
        window wins (most-recent signal), so a fresh prompt after a BUSY spinner
        recovers to IDLE instead of sticking. The ERROR > WAITING_INPUT > BUSY >
        IDLE order only breaks ties when two markers start at the same position.
        Return None when no marker is present (runner keeps the previous state).
        Override for non-marker detection logic."""
        best_state: AgentState | None = None
        best_pos = -1
        for markers, state in (
            (self._ERROR_MARKERS, AgentState.ERROR),
            (self._WAITING_MARKERS, AgentState.WAITING_INPUT),
            (self._BUSY_MARKERS, AgentState.BUSY),
            (self._IDLE_MARKERS, AgentState.IDLE),
        ):
            for marker in markers:
                pos = recent_output.rfind(marker)
                if pos > best_pos:
                    best_pos, best_state = pos, state
        return best_state
