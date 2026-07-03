from __future__ import annotations

import re
from pathlib import Path
from collections.abc import Mapping

from axdt.agent_runner.state import AgentState
from axdt.agent_runner.adapters.base import PlatformAdapter
from axdt.agent_runner.backend import SessionBackend

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


class AgentRunner:
    """Common agent runner = PlatformAdapter + SessionBackend (composition)."""

    def __init__(self, adapter: PlatformAdapter, backend: SessionBackend) -> None:
        self._adapter = adapter
        self._backend = backend
        self._transcript = ""
        self._read_cursor = 0
        self._last_state = AgentState.STARTING
        self._stop_requested = False
        self._started = False

    def start_session(self, workdir: Path,
                      env: Mapping[str, str] | None = None) -> None:
        if self._started:
            raise RuntimeError("session already started")
        if self._stop_requested:
            raise RuntimeError("cannot start a stopped runner")
        command = self._adapter.build_launch_command(workdir)
        self._backend.start(command, workdir, env)
        self._started = True
        self._last_state = AgentState.STARTING

    def _drain(self) -> None:
        if not self._started:
            return
        chunk = self._backend.read_new_output()
        if chunk:
            self._transcript += chunk

    def read_output(self) -> str:
        if not self._started:
            return ""
        self._drain()
        new = self._transcript[self._read_cursor:]
        self._read_cursor = len(self._transcript)
        return new

    def poll_state(self) -> AgentState:
        # Lifecycle stub — full state classification is added in Task 6.
        self._drain()
        return self._last_state

    def stop(self) -> None:
        self._stop_requested = True
        self._backend.stop()
        self._last_state = AgentState.STOPPED

    @property
    def transcript(self) -> str:
        return self._transcript
