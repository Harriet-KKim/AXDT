from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from collections.abc import Mapping


class SessionBackend(ABC):
    """Execution substrate. Phase 3 = TmuxDockerBackend; now = FakeBackend."""

    @abstractmethod
    def start(self, command: list[str], cwd: Path,
              env: Mapping[str, str] | None = None) -> None:
        """Start the session. Runtime launch failure (e.g. command-not-found)
        is surfaced via is_alive()=False + last_error(), NOT raised."""

    @abstractmethod
    def send_text(self, text: str) -> None:
        """Inject literal text (format_prompt output verbatim)."""

    @abstractmethod
    def read_new_output(self) -> str:
        """Output appended since the last read. Called only by AgentRunner._drain."""

    @abstractmethod
    def is_alive(self) -> bool:
        ...

    @abstractmethod
    def exit_code(self) -> int | None:
        """None while running, 0 on clean exit, non-zero on failure."""

    @abstractmethod
    def last_error(self) -> str | None:
        """start/IO error message, else None."""

    @abstractmethod
    def stop(self) -> None:
        """Idempotent."""

    @abstractmethod
    def read_state(self) -> str | None:
        """Raw contents of the hook-written state file (one-line JSON), or
        None if the file is absent/unreadable. Reading logic (host path or
        container exec) is the concrete backend's concern."""

    @abstractmethod
    def send_key(self, key: str) -> None:
        """Send a NAMED key event ('Enter', 'C-u'), not literal text.
        tmux backend maps to `send-keys -t <win> <key>` — NOT `-l`.
        send_text uses `-l` for literal strings; key names sent with `-l`
        would be typed as characters."""

    @classmethod
    def attach(cls, *args, **kwargs) -> "SessionBackend":
        """Reattach to an already-running session (§2.5). Raises NotStarted
        if nothing to attach to. Default: NotImplementedError — some
        backends have no reattach concept."""
        raise NotImplementedError

    @classmethod
    def post_mortem(cls, *args, **kwargs) -> tuple[int | None, str | None]:
        """Exit code + last error of a dead session; called after attach
        fails, so no instance — classmethod. If the container is still
        alive (half-state: window gone), return
        (None, 'half-state: container alive') so a live session is not
        misjudged dead (§2.5). Default: NotImplementedError."""
        raise NotImplementedError


class FakeBackend(SessionBackend):
    """Deterministic in-memory backend for tests."""

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.start_calls: list[tuple[list[str], Path, dict | None]] = []
        self.sent: list[str] = []
        self.keys: list[str] = []
        self._out_queue: list[str] = []
        self._alive = False
        self._exit_code: int | None = None
        self._last_error: str | None = None
        self._fail_on_start = False
        self._state_raw: str | None = None

    # --- test scripting helpers ---
    def script_output(self, *chunks: str) -> None:
        self._out_queue.extend(chunks)

    def script_state(self, state: str | None, ts: float | None = None) -> None:
        if state is None:
            self._state_raw = None  # file absent
        else:
            self._state_raw = json.dumps(
                {"state": state, "ts": (ts if ts is not None else time.time())}
            )

    def script_state_raw(self, raw: str | None) -> None:
        """상태 파일 원문을 그대로 세팅(정형 JSON 우회) — 견고성 테스트가 악성/부분 원문을 주입할 때 쓴다."""
        self._state_raw = raw

    def script_start_failure(self, message: str = "command not found") -> None:
        self._fail_on_start = True
        self._last_error = message

    def script_exit(self, code: int) -> None:
        self._alive = False
        self._exit_code = code

    # --- SessionBackend impl ---
    def start(self, command, cwd, env=None) -> None:
        self.start_calls.append((list(command), cwd, dict(env) if env is not None else None))
        self.started = True
        self._alive = not self._fail_on_start

    def send_text(self, text: str) -> None:
        self.sent.append(text)

    def send_key(self, key: str) -> None:
        self.keys.append(key)

    def read_new_output(self) -> str:
        if not self._out_queue:
            return ""
        chunk = "".join(self._out_queue)
        self._out_queue.clear()
        return chunk

    def is_alive(self) -> bool:
        return self._alive

    def exit_code(self) -> int | None:
        return self._exit_code

    def last_error(self) -> str | None:
        return self._last_error

    def stop(self) -> None:
        self.stopped = True
        self._alive = False
        if self._exit_code is None:
            self._exit_code = 0

    def read_state(self) -> str | None:
        return self._state_raw
