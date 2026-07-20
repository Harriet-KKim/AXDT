from __future__ import annotations

import json
import re
import time
from pathlib import Path
from collections.abc import Mapping, Sequence

from axdt.agent_runner.state import AgentState
from axdt.agent_runner.adapters.base import PlatformAdapter
from axdt.agent_runner.backend import SessionBackend
from axdt.roles.spec import RoleSpec

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _parse_state(raw: str | None) -> tuple[str, float] | None:
    """Parse one line of hook-written state JSON: {"state": str, "ts": number}.
    Returns (state_value, ts), or None if raw is absent, malformed JSON, or
    missing/mistyped keys."""
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return None
    state_value = payload.get("state") if isinstance(payload, dict) else None
    ts = payload.get("ts") if isinstance(payload, dict) else None
    if not isinstance(state_value, str) or not isinstance(ts, (int, float)):
        return None
    return state_value, float(ts)


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
        self._last_state_ts: float | None = None
        self._stop_requested = False
        self._started = False

    def start_session(self, role: RoleSpec, workdir: Path,
                      env: Mapping[str, str] | None = None,
                      subagent_args: Sequence[str] = ()) -> None:
        if self._started:
            raise RuntimeError("session already started")
        if self._stop_requested:
            raise RuntimeError("cannot start a stopped runner")
        command = self._adapter.build_session_command(role, workdir, subagent_args)
        self._backend.start(command, workdir, env)
        self._started = True
        self._last_state = AgentState.STARTING

    @classmethod
    def attach(cls, adapter: PlatformAdapter, backend: SessionBackend) -> "AgentRunner":
        """Construct a runner on an already-attached backend (§2.5). Seeds
        the transcript by draining once — the "last TAIL_WINDOW bytes of
        the capture log" seeding is the concrete backend's concern; here we
        just drain once and set the read cursor to the end."""
        runner = cls(adapter, backend)
        runner._started = True
        runner._last_state = AgentState.STARTING
        runner._drain()
        runner._read_cursor = len(runner._transcript)
        return runner

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
        parsed = _parse_state(self._backend.read_state())
        # Staleness policy (gating on ts age) is deferred to slice B — idle
        # state files legitimately age with no activity, and a naive
        # threshold would strand the runner in STARTING. For now we only
        # parse and store ts.
        if parsed is not None:
            state_value, ts = parsed
            self._last_state_ts = ts
            detected = self._adapter.detect_state(state_value)
        else:
            detected = None
        if detected is not None:
            self._last_state = detected
        return self._last_state

    def send_prompt(self, text: str) -> None:
        if not self._started:
            raise RuntimeError("session not started")
        state = self.poll_state()
        if state is not AgentState.IDLE:
            raise RuntimeError(
                f"cannot send prompt in state {state.name}; expected IDLE"
            )
        self._backend.send_text(self._adapter.format_prompt(text))
        self.submit()

    def submit(self) -> None:
        if not self._started:
            raise RuntimeError("session not started")
        self._backend.send_key(self._adapter.submit_key())

    def clear_input(self) -> None:
        if not self._started:
            raise RuntimeError("session not started")
        self._backend.send_key(self._adapter.clear_key())

    def send_when_idle(self, text: str) -> bool:
        """Re-poll immediately before sending; if IDLE, clear_input ->
        send_text -> submit (§4.1), returning True. If not IDLE, return
        False instead of raising — this is the safe injection path (CLI
        `maintainer send` / `leader send`) with the pre-send re-poll and
        input-clear that send_prompt does not do."""
        state = self.poll_state()
        if state is not AgentState.IDLE:
            return False
        self.clear_input()
        self._backend.send_text(self._adapter.format_prompt(text))
        self.submit()
        return True

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
