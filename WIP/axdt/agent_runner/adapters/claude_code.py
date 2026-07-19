from __future__ import annotations

from pathlib import Path

from axdt.agent_runner.adapters.base import PlatformAdapter


class ClaudeCodeAdapter(PlatformAdapter):
    name = "claude-code"
    config_dir_name = ".claude"

    def build_launch_command(self, workdir: Path) -> list[str]:
        return ["claude"]
