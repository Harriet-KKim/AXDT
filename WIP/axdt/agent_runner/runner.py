from __future__ import annotations

import re
import time
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

    INPUT_ACCEPTING = frozenset({AgentState.IDLE, AgentState.WAITING_INPUT})
    TAIL_WINDOW = 2000

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
        if not self._started:
            return AgentState.STARTING
        self._drain()
        if self._stop_requested:
            self._last_state = AgentState.STOPPED
            return self._last_state
        if not self._backend.is_alive():
            if (self._backend.last_error() is not None
                    or self._backend.exit_code() not in (None, 0)):
                self._last_state = AgentState.ERROR
            else:
                self._last_state = AgentState.STOPPED
            return self._last_state
        window = _strip_ansi(self._transcript)[-self.TAIL_WINDOW:]
        detected = self._adapter.detect_state(window)
        if detected is not None:
            self._last_state = detected
        return self._last_state

    def send_prompt(self, text: str) -> None:
        if not self._started:
            raise RuntimeError("session not started")
        state = self.poll_state()
        if state not in self.INPUT_ACCEPTING:
            raise RuntimeError(
                f"cannot send prompt in state {state.name}; "
                f"expected IDLE or WAITING_INPUT"
            )
        self._backend.send_text(self._adapter.format_prompt(text))

    def wait_until_idle(self, timeout: float, poll_interval: float = 0.5) -> AgentState:
        deadline = time.monotonic() + timeout
        state = self.poll_state()
        terminal = (AgentState.IDLE, AgentState.WAITING_INPUT,
                    AgentState.ERROR, AgentState.STOPPED)
        while state not in terminal:
            if time.monotonic() >= deadline:
                break
            time.sleep(poll_interval)
            state = self.poll_state()
        return state

    def stop(self) -> None:
        self._stop_requested = True
        self._backend.stop()
        self._last_state = AgentState.STOPPED

    @property
    def transcript(self) -> str:
        return self._transcript
