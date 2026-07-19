from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from axdt.agent_runner.state import AgentState


class PlatformAdapter(ABC):
    """Platform-specific knowledge (Claude Code / Codex).

    A CLI hook writes the session state to a file; the backend reads it
    (SessionBackend.read_state); the runner extracts the state value and
    passes it to detect_state, which maps it to an AgentState. Subclasses
    normally declare only config_dir_name + build_launch_command; the hook
    state names are shared across platforms, so detect_state only needs
    overriding when a platform's hook emits different names (Phase 3).
    """

    name: str
    config_dir_name: str

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

    _STATE_MAP: dict[str, AgentState] = {
        "idle": AgentState.IDLE,
        "start": AgentState.IDLE,
        "busy": AgentState.BUSY,
        "waiting": AgentState.WAITING_INPUT,
    }

    def detect_state(self, raw_state: str | None) -> AgentState | None:
        """Map a hook-emitted state value to an AgentState.

        raw_state is the already-extracted state value (e.g. "busy"), not
        screen output and not the raw JSON line. Unknown values (including
        None) return None — inconclusive, so the runner keeps its previous
        state. Override if a platform's hook emits different state names."""
        if raw_state is None:
            return None
        return self._STATE_MAP.get(raw_state)
