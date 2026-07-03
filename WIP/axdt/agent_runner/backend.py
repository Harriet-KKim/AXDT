from __future__ import annotations

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


class FakeBackend(SessionBackend):
    """Deterministic in-memory backend for tests."""

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.start_calls: list[tuple[list[str], Path, dict | None]] = []
        self.sent: list[str] = []
        self._out_queue: list[str] = []
        self._alive = False
        self._exit_code: int | None = None
        self._last_error: str | None = None
        self._fail_on_start = False

    # --- test scripting helpers ---
    def script_output(self, *chunks: str) -> None:
        self._out_queue.extend(chunks)

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
