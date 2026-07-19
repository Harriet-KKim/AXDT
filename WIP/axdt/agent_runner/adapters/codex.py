from __future__ import annotations

from pathlib import Path

from axdt.agent_runner.adapters.base import PlatformAdapter


class CodexAdapter(PlatformAdapter):
    name = "codex"
    config_dir_name = ".codex"

    def build_launch_command(self, workdir: Path) -> list[str]:
        return ["codex"]
