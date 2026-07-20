from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from collections.abc import Mapping, Sequence

from axdt.agent_runner.state import AgentState
from axdt.agent_runner.adapters.base import PlatformAdapter
from axdt.agent_runner.backend import SessionBackend
from axdt.roles.spec import RoleSpec

# 런타임 미사용 — Phase 3 live_probe 재작성이 재사용 예정이라 존치(제거 금지).
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _parse_state(raw: str | None) -> tuple[str, float] | None:
    """Parse one line of hook-written state JSON: {"state": str, "ts": number}.
    Returns (state_value, ts), or None if raw is absent, malformed JSON, or
    missing/mistyped keys. Never raises — any malformed/adversarial input
    (truncated JSON, wrong types, bool ts, NaN/Infinity, huge ints that
    overflow float()) yields None instead of propagating an exception."""
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError, RecursionError):
        # RecursionError: 깊게 중첩된 JSON에서 json.loads가 던진다(RuntimeError
        # 하위형이라 ValueError/TypeError에 안 잡힘). 컨테이너 내 에이전트가
        # 상태 파일에 그런 원문을 써도 poll_state 무예외 계약을 지킨다.
        return None
    state_value = payload.get("state") if isinstance(payload, dict) else None
    ts = payload.get("ts") if isinstance(payload, dict) else None
    if not isinstance(state_value, str):
        return None
    if isinstance(ts, bool):
        return None  # bool is an int subtype in Python; exclude explicitly
    if not isinstance(ts, (int, float)):
        return None
    # math.isfinite() itself raises OverflowError on an int too large to
    # convert to float (e.g. a 400-digit literal) — so it must share the
    # try/except with float(ts) below, not precede it unguarded.
    try:
        if not math.isfinite(ts):
            return None  # NaN / Infinity
        ts_f = float(ts)
    except (OverflowError, ValueError):
        return None  # e.g. huge int literals that overflow float()
    return state_value, ts_f


class AgentRunner:
    """Common agent runner = PlatformAdapter + SessionBackend (composition)."""

    # 런타임 미사용 — Phase 3 live_probe 재작성이 재사용 예정이라 존치(제거 금지).
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
        # Both staleness (gating on ts age) and ordering (ignoring a record
        # whose ts moved backward) are deferred to slice B. An age threshold
        # would strand the runner in STARTING because idle files legitimately
        # age; a backward-ts guard would wedge the session in BUSY on a clock
        # step, an edge only the age-based stuck-detection (also slice B) can
        # rescue. The two must land together with live hook-clock measurement.
        # For now we only parse and store ts. (handoff §3)
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
        input-clear that send_prompt does not do.

        Caller responsibility: right after submit() the UserPromptSubmit hook
        has not yet written `busy`, so the state file still reads `idle`.
        Re-calling send_when_idle inside that window returns True and injects
        again. The inject() path guards this with post-submit exit-from-IDLE
        observation (§4.1 step 6); a direct CLI caller must do the same or
        accept the double-injection risk."""
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
