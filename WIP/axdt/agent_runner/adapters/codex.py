from __future__ import annotations

from pathlib import Path

from axdt.agent_runner.adapters.base import PlatformAdapter


class CodexAdapter(PlatformAdapter):
    name = "codex"
    config_dir_name = ".codex"

    # Provisional output markers — verified live in Phase 3 (PLATFORM_MATRIX.md).
    _ERROR_MARKERS = ("stream error:",)  # bare "error:" is too broad — false-positives on prose
    _WAITING_MARKERS = ("Allow command? [y/N]",)
    _BUSY_MARKERS = ("ctrl-c to interrupt",)
    _IDLE_MARKERS = ("\n› ",)  # "\n> " with the codex chevron

    def build_launch_command(self, workdir: Path) -> list[str]:
        return ["codex"]
