from __future__ import annotations

from pathlib import Path

from axdt.agent_runner.adapters.base import PlatformAdapter


class ClaudeCodeAdapter(PlatformAdapter):
    name = "claude-code"
    config_dir_name = ".claude"

    # Provisional output markers — verified live in Phase 3 (PLATFORM_MATRIX.md).
    _ERROR_MARKERS = ("fatal:", "Error:")
    _WAITING_MARKERS = ("Do you want to proceed?",)
    _BUSY_MARKERS = ("Esc to interrupt",)
    _IDLE_MARKERS = ("\n> ",)

    def build_launch_command(self, workdir: Path) -> list[str]:
        return ["claude"]
