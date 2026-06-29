# Phase 5 Agent Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the AXDT common agent runner abstraction — `AgentRunner` composing a `PlatformAdapter` (Claude Code / Codex) and an injected `SessionBackend` — at interface + test-skeleton depth.

**Architecture:** Three-axis composition. `AgentRunner` owns the synchronous, polling lifecycle (start → send → read → poll → stop). `PlatformAdapter` holds platform-specific knowledge (launch argv, prompt formatting, output→state detection). `SessionBackend` is the execution substrate, injected; tests use the in-memory `FakeBackend`, Phase 3 will add `TmuxDockerBackend`. `read_output` is monitoring/liveness only — authoritative results flow through report files (ADR-0003).

**Tech Stack:** Python ≥3.10 (stdlib only: `enum`, `abc`, `re`, `time`, `pathlib`), pytest.

**Spec:** `WIP/specs/2026-06-26-phase5-agent-runner-design.md` (commit 84c1cf9, Codex-reviewed READY).

## Global Constraints

- Python `requires-python = ">=3.10"` (uses `X | None` / `list[str]` annotations).
- All code lives under `WIP/` (D12 — AXDT self-implementation, temporary location). Package root = `WIP/`, package = `axdt`.
- Synchronous + polling only — **no asyncio**.
- `AgentState` is a controlled vocabulary: `STARTING, IDLE, BUSY, WAITING_INPUT, STOPPED, ERROR`. Do not add members without updating the spec.
- `read_output`/`poll_state` are monitoring/liveness only; the runner MUST NOT parse stdout into authoritative results.
- Stdlib only — do not add third-party runtime dependencies.
- Run all commands from the `WIP/` directory (`cd WIP`).

---

### Task 1: Project scaffold + `AgentState`

**Files:**
- Create: `WIP/pyproject.toml`
- Create: `WIP/axdt/__init__.py`
- Create: `WIP/axdt/agent_runner/__init__.py`
- Create: `WIP/axdt/agent_runner/state.py`
- Create: `WIP/axdt/agent_runner/tests/__init__.py`
- Test: `WIP/axdt/agent_runner/tests/test_state.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `axdt.agent_runner.state.AgentState` — Enum with members `STARTING, IDLE, BUSY, WAITING_INPUT, STOPPED, ERROR`, each `.value` the lowercase name.

- [ ] **Step 1: Create the package scaffold**

`WIP/pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "axdt"
version = "0.0.0"
description = "AXDT self-implementation (temporary WIP location)"
requires-python = ">=3.10"

[tool.setuptools.packages.find]
where = ["."]
include = ["axdt*"]

[tool.pytest.ini_options]
testpaths = ["axdt"]
addopts = "-q"
```

`WIP/axdt/__init__.py`: (empty file)

`WIP/axdt/agent_runner/__init__.py`: (empty file)

`WIP/axdt/agent_runner/tests/__init__.py`: (empty file)

- [ ] **Step 2: Write the failing test**

`WIP/axdt/agent_runner/tests/test_state.py`:
```python
from axdt.agent_runner.state import AgentState


def test_vocabulary_is_exactly_the_controlled_set():
    assert {s.name for s in AgentState} == {
        "STARTING", "IDLE", "BUSY", "WAITING_INPUT", "STOPPED", "ERROR",
    }


def test_values_are_lowercase_names():
    for s in AgentState:
        assert s.value == s.name.lower()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'axdt.agent_runner.state'`

- [ ] **Step 4: Write minimal implementation**

`WIP/axdt/agent_runner/state.py`:
```python
from enum import Enum


class AgentState(Enum):
    """Controlled state vocabulary. adapter.detect_state maps output -> one of these."""

    STARTING = "starting"
    IDLE = "idle"                   # ready to receive a prompt
    BUSY = "busy"                   # processing
    WAITING_INPUT = "waiting_input"  # awaiting user/upstream input
    STOPPED = "stopped"
    ERROR = "error"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_state.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add WIP/pyproject.toml WIP/axdt/__init__.py WIP/axdt/agent_runner/__init__.py WIP/axdt/agent_runner/state.py WIP/axdt/agent_runner/tests/__init__.py WIP/axdt/agent_runner/tests/test_state.py
git commit -m "feat(phase5): scaffold axdt package + AgentState vocabulary"
```

---

### Task 2: `PlatformAdapter` ABC + `ClaudeCodeAdapter`

**Files:**
- Create: `WIP/axdt/agent_runner/adapters/__init__.py`
- Create: `WIP/axdt/agent_runner/adapters/base.py`
- Create: `WIP/axdt/agent_runner/adapters/claude_code.py`
- Test: `WIP/axdt/agent_runner/tests/test_adapters.py`

**Interfaces:**
- Consumes: `AgentState` (Task 1).
- Produces:
  - `PlatformAdapter(ABC)` with class attrs `name: str`, `config_dir_name: str`; concrete `config_dir(self, workdir: Path) -> Path` returning `workdir / config_dir_name`; abstract `build_launch_command(self, workdir: Path) -> list[str]`, `format_prompt(self, text: str) -> str`, `detect_state(self, recent_output: str) -> AgentState | None`.
  - `ClaudeCodeAdapter()` — `name="claude-code"`, `config_dir_name=".claude"`, `build_launch_command(workdir) == ["claude"]`, `format_prompt(t) == t + "\n"`, `detect_state` per markers below.

- [ ] **Step 1: Write the failing test**

`WIP/axdt/agent_runner/tests/test_adapters.py`:
```python
from pathlib import Path

from axdt.agent_runner.state import AgentState
from axdt.agent_runner.adapters.base import PlatformAdapter
from axdt.agent_runner.adapters.claude_code import ClaudeCodeAdapter


def test_platform_adapter_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        PlatformAdapter()  # cannot instantiate abstract base


def test_claude_identity_and_config_dir():
    a = ClaudeCodeAdapter()
    assert a.name == "claude-code"
    assert a.config_dir_name == ".claude"
    assert a.config_dir(Path("/work/wt")) == Path("/work/wt/.claude")


def test_claude_launch_and_prompt():
    a = ClaudeCodeAdapter()
    assert a.build_launch_command(Path("/work/wt")) == ["claude"]
    assert a.format_prompt("hi") == "hi\n"


def test_claude_detect_state_markers():
    a = ClaudeCodeAdapter()
    assert a.detect_state("fatal: boom") is AgentState.ERROR
    assert a.detect_state("Do you want to proceed?") is AgentState.WAITING_INPUT
    assert a.detect_state("... Esc to interrupt") is AgentState.BUSY
    assert a.detect_state("\n> ") is AgentState.IDLE
    assert a.detect_state("random noise") is None  # inconclusive
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_adapters.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'axdt.agent_runner.adapters'`

- [ ] **Step 3: Write minimal implementation**

`WIP/axdt/agent_runner/adapters/__init__.py`: (empty file)

`WIP/axdt/agent_runner/adapters/base.py`:
```python
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from axdt.agent_runner.state import AgentState


class PlatformAdapter(ABC):
    """Platform-specific knowledge (Claude Code / Codex)."""

    name: str
    config_dir_name: str

    def config_dir(self, workdir: Path) -> Path:
        """Resolved config dir = workdir / config_dir_name."""
        return workdir / self.config_dir_name

    @abstractmethod
    def build_launch_command(self, workdir: Path) -> list[str]:
        """argv that starts the agent CLI session.

        Provisional flags are verified live in Phase 3 (PLATFORM_MATRIX.md).
        The backend runs this argv with cwd=workdir, so config_dir is resolved
        relatively via the working directory.
        """

    @abstractmethod
    def format_prompt(self, text: str) -> str:
        """Render a prompt for injection. Returns literal text passed verbatim
        to SessionBackend.send_text (including the submit newline)."""

    @abstractmethod
    def detect_state(self, recent_output: str) -> AgentState | None:
        """Infer state from an (already ANSI-normalised, windowed) output tail.
        Return None when inconclusive (runner keeps the previous state)."""
```

`WIP/axdt/agent_runner/adapters/claude_code.py`:
```python
from __future__ import annotations

from pathlib import Path

from axdt.agent_runner.state import AgentState
from axdt.agent_runner.adapters.base import PlatformAdapter


class ClaudeCodeAdapter(PlatformAdapter):
    name = "claude-code"
    config_dir_name = ".claude"

    # Provisional output markers — verified live in Phase 3 (PLATFORM_MATRIX.md).
    # Precedence: ERROR > WAITING_INPUT > BUSY > IDLE.
    _ERROR_MARKERS = ("fatal:", "Error:")
    _WAITING_MARKERS = ("Do you want to proceed?",)
    _BUSY_MARKERS = ("Esc to interrupt",)
    _IDLE_MARKERS = ("\n> ",)

    def build_launch_command(self, workdir: Path) -> list[str]:
        return ["claude"]

    def format_prompt(self, text: str) -> str:
        return text + "\n"

    def detect_state(self, recent_output: str) -> AgentState | None:
        if any(m in recent_output for m in self._ERROR_MARKERS):
            return AgentState.ERROR
        if any(m in recent_output for m in self._WAITING_MARKERS):
            return AgentState.WAITING_INPUT
        if any(m in recent_output for m in self._BUSY_MARKERS):
            return AgentState.BUSY
        if any(m in recent_output for m in self._IDLE_MARKERS):
            return AgentState.IDLE
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_adapters.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add WIP/axdt/agent_runner/adapters/__init__.py WIP/axdt/agent_runner/adapters/base.py WIP/axdt/agent_runner/adapters/claude_code.py WIP/axdt/agent_runner/tests/test_adapters.py
git commit -m "feat(phase5): PlatformAdapter ABC + ClaudeCodeAdapter"
```

---

### Task 3: `CodexAdapter`

**Files:**
- Create: `WIP/axdt/agent_runner/adapters/codex.py`
- Modify: `WIP/axdt/agent_runner/tests/test_adapters.py` (append cases)

**Interfaces:**
- Consumes: `PlatformAdapter` (Task 2), `AgentState` (Task 1).
- Produces: `CodexAdapter()` — `name="codex"`, `config_dir_name=".codex"`, `build_launch_command(workdir) == ["codex"]`, `format_prompt(t) == t + "\n"`, `detect_state` per its own markers.

- [ ] **Step 1: Write the failing test (append to test_adapters.py)**

Append to `WIP/axdt/agent_runner/tests/test_adapters.py`:
```python
from axdt.agent_runner.adapters.codex import CodexAdapter


def test_codex_identity_and_config_dir():
    a = CodexAdapter()
    assert a.name == "codex"
    assert a.config_dir_name == ".codex"
    assert a.config_dir(Path("/work/wt")) == Path("/work/wt/.codex")


def test_codex_launch_and_prompt():
    a = CodexAdapter()
    assert a.build_launch_command(Path("/work/wt")) == ["codex"]
    assert a.format_prompt("hi") == "hi\n"


def test_codex_detect_state_markers():
    a = CodexAdapter()
    assert a.detect_state("stream error: boom") is AgentState.ERROR
    assert a.detect_state("Allow command? [y/N]") is AgentState.WAITING_INPUT
    assert a.detect_state("working (ctrl-c to interrupt)") is AgentState.BUSY
    assert a.detect_state("\n› ") is AgentState.IDLE
    assert a.detect_state("random noise") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_adapters.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'axdt.agent_runner.adapters.codex'`

- [ ] **Step 3: Write minimal implementation**

`WIP/axdt/agent_runner/adapters/codex.py`:
```python
from __future__ import annotations

from pathlib import Path

from axdt.agent_runner.state import AgentState
from axdt.agent_runner.adapters.base import PlatformAdapter


class CodexAdapter(PlatformAdapter):
    name = "codex"
    config_dir_name = ".codex"

    # Provisional output markers — verified live in Phase 3 (PLATFORM_MATRIX.md).
    # Precedence: ERROR > WAITING_INPUT > BUSY > IDLE.
    _ERROR_MARKERS = ("stream error:", "error:")
    _WAITING_MARKERS = ("Allow command? [y/N]",)
    _BUSY_MARKERS = ("ctrl-c to interrupt",)
    _IDLE_MARKERS = ("\n› ",)  # "\n› "

    def build_launch_command(self, workdir: Path) -> list[str]:
        return ["codex"]

    def format_prompt(self, text: str) -> str:
        return text + "\n"

    def detect_state(self, recent_output: str) -> AgentState | None:
        if any(m in recent_output for m in self._ERROR_MARKERS):
            return AgentState.ERROR
        if any(m in recent_output for m in self._WAITING_MARKERS):
            return AgentState.WAITING_INPUT
        if any(m in recent_output for m in self._BUSY_MARKERS):
            return AgentState.BUSY
        if any(m in recent_output for m in self._IDLE_MARKERS):
            return AgentState.IDLE
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_adapters.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add WIP/axdt/agent_runner/adapters/codex.py WIP/axdt/agent_runner/tests/test_adapters.py
git commit -m "feat(phase5): CodexAdapter"
```

---

### Task 4: `SessionBackend` ABC + `FakeBackend`

**Files:**
- Create: `WIP/axdt/agent_runner/backend.py`
- Test: `WIP/axdt/agent_runner/tests/test_backend.py`

**Interfaces:**
- Consumes: nothing (pure substrate contract).
- Produces:
  - `SessionBackend(ABC)`: `start(command, cwd, env=None) -> None` (non-raising on runtime launch failure), `send_text(text) -> None`, `read_new_output() -> str` (increment since last read), `is_alive() -> bool`, `exit_code() -> int | None`, `last_error() -> str | None`, `stop() -> None` (idempotent).
  - `FakeBackend()` with scripting helpers: `script_output(*chunks)`, `script_start_failure(message=...)`, `script_exit(code)`; recorders: `.start_calls` (list of `(command, cwd, env)`), `.sent` (list of texts), `.started`, `.stopped`.

- [ ] **Step 1: Write the failing test**

`WIP/axdt/agent_runner/tests/test_backend.py`:
```python
from pathlib import Path

import pytest

from axdt.agent_runner.backend import SessionBackend, FakeBackend


def test_session_backend_is_abstract():
    with pytest.raises(TypeError):
        SessionBackend()


def test_fake_records_start_and_send():
    b = FakeBackend()
    b.start(["claude"], Path("/wt"), {"K": "V"})
    assert b.started is True
    assert b.is_alive() is True
    assert b.start_calls == [(["claude"], Path("/wt"), {"K": "V"})]
    b.send_text("hello\n")
    assert b.sent == ["hello\n"]


def test_fake_read_new_output_is_incremental():
    b = FakeBackend()
    b.script_output("aa", "bb")
    b.start(["codex"], Path("/wt"))
    assert b.read_new_output() == "aabb"
    assert b.read_new_output() == ""  # drained


def test_fake_start_failure_is_non_raising():
    b = FakeBackend()
    b.script_start_failure("command not found")
    b.start(["claude"], Path("/wt"))  # must NOT raise
    assert b.is_alive() is False
    assert b.last_error() == "command not found"


def test_fake_exit_and_stop():
    b = FakeBackend()
    b.start(["claude"], Path("/wt"))
    b.script_exit(137)
    assert b.is_alive() is False
    assert b.exit_code() == 137
    b.stop()
    b.stop()  # idempotent, no raise
    assert b.stopped is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_backend.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'axdt.agent_runner.backend'`

- [ ] **Step 3: Write minimal implementation**

`WIP/axdt/agent_runner/backend.py`:
```python
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
        self.start_calls.append((list(command), cwd, dict(env) if env else None))
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_backend.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add WIP/axdt/agent_runner/backend.py WIP/axdt/agent_runner/tests/test_backend.py
git commit -m "feat(phase5): SessionBackend ABC + FakeBackend"
```

---

### Task 5: `AgentRunner`

**Files:**
- Create: `WIP/axdt/agent_runner/runner.py`
- Test: `WIP/axdt/agent_runner/tests/test_runner.py`

**Interfaces:**
- Consumes: `AgentState` (Task 1), `PlatformAdapter` + `ClaudeCodeAdapter` (Task 2), `SessionBackend` + `FakeBackend` (Task 4).
- Produces: `AgentRunner(adapter, backend)` with `INPUT_ACCEPTING = frozenset({IDLE, WAITING_INPUT})`, `TAIL_WINDOW = 2000`, methods `start_session(workdir, env=None)`, `send_prompt(text)`, `read_output() -> str`, `poll_state() -> AgentState`, `wait_until_idle(timeout, poll_interval=0.5) -> AgentState`, `stop()`, property `transcript -> str`. Module helper `_strip_ansi(text) -> str`.

- [ ] **Step 1: Write the failing lifecycle + drain/cursor test**

`WIP/axdt/agent_runner/tests/test_runner.py`:
```python
from pathlib import Path

import pytest

from axdt.agent_runner.state import AgentState
from axdt.agent_runner.backend import FakeBackend
from axdt.agent_runner.adapters.claude_code import ClaudeCodeAdapter
from axdt.agent_runner.runner import AgentRunner, _strip_ansi


def make(backend=None):
    backend = backend or FakeBackend()
    return AgentRunner(ClaudeCodeAdapter(), backend), backend


def test_start_session_invokes_backend_with_launch_command():
    runner, backend = make()
    runner.start_session(Path("/wt"), {"K": "V"})
    assert backend.start_calls == [(["claude"], Path("/wt"), {"K": "V"})]


def test_strip_ansi_removes_escape_sequences():
    assert _strip_ansi("\x1b[31mred\x1b[0m> ") == "red> "


def test_read_output_increments_and_accumulates_transcript():
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_output("aa")
    assert runner.read_output() == "aa"
    backend.script_output("bb")
    assert runner.read_output() == "bb"
    assert runner.transcript == "aabb"


def test_read_output_before_start_is_empty():
    runner, _ = make()
    assert runner.read_output() == ""


def test_cursor_independent_of_poll_state():
    # R1-#1: poll_state draining must not starve read_output.
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_output("hello")
    runner.poll_state()                  # drains "hello" into transcript
    assert runner.read_output() == "hello"  # still delivered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'axdt.agent_runner.runner'`

- [ ] **Step 3: Write the runner implementation**

`WIP/axdt/agent_runner/runner.py`:
```python
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
        terminal = (AgentState.IDLE, AgentState.WAITING_INPUT, AgentState.ERROR)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_runner.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Write the failing state-machine tests (append)**

Append to `WIP/axdt/agent_runner/tests/test_runner.py`:
```python
def test_poll_state_detects_idle_from_marker():
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_output("\n> ")
    assert runner.poll_state() is AgentState.IDLE


def test_poll_state_keeps_previous_when_detect_inconclusive():
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_output("\n> ")
    assert runner.poll_state() is AgentState.IDLE
    backend.script_output("noise with no marker")
    assert runner.poll_state() is AgentState.IDLE  # unchanged (detect -> None)


def test_poll_state_maps_failure_to_error():
    # R1-#2: dead with last_error / non-zero exit -> ERROR.
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_exit(2)
    assert runner.poll_state() is AgentState.ERROR


def test_poll_state_clean_exit_is_stopped():
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_exit(0)
    assert runner.poll_state() is AgentState.STOPPED


def test_stop_normalises_even_with_nonzero_exit():
    # R2-1: intentional stop() must not be reclassified ERROR.
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_exit(137)   # e.g. killed
    runner.stop()
    assert runner.poll_state() is AgentState.STOPPED


def test_send_prompt_rejected_in_non_accepting_states():
    # R2-2: only IDLE / WAITING_INPUT accept prompts.
    runner, backend = make()
    runner.start_session(Path("/wt"))   # state STARTING
    with pytest.raises(RuntimeError):
        runner.send_prompt("hi")
    backend.script_output("\n> ")       # -> IDLE
    runner.send_prompt("hi")
    assert backend.sent == ["hi\n"]


def test_send_prompt_before_start_raises():
    runner, _ = make()
    with pytest.raises(RuntimeError):
        runner.send_prompt("hi")


def test_send_prompt_after_stop_raises():
    runner, backend = make()
    runner.start_session(Path("/wt"))
    runner.stop()
    with pytest.raises(RuntimeError):
        runner.send_prompt("hi")


def test_start_twice_raises():
    runner, _ = make()
    runner.start_session(Path("/wt"))
    with pytest.raises(RuntimeError):
        runner.start_session(Path("/wt"))


def test_start_launch_failure_becomes_error():
    # R2-3: backend reports launch failure non-raising -> poll_state ERROR.
    backend = FakeBackend()
    backend.script_start_failure("command not found")
    runner, _ = make(backend)
    runner.start_session(Path("/wt"))   # must not raise
    assert runner.poll_state() is AgentState.ERROR


def test_wait_until_idle_returns_on_idle():
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_output("\n> ")
    assert runner.wait_until_idle(timeout=0.05, poll_interval=0.01) is AgentState.IDLE


def test_wait_until_idle_times_out():
    runner, backend = make()
    runner.start_session(Path("/wt"))   # stays STARTING, no idle marker
    assert runner.wait_until_idle(timeout=0.03, poll_interval=0.01) is AgentState.STARTING


def test_stop_is_idempotent():
    runner, backend = make()
    runner.start_session(Path("/wt"))
    runner.stop()
    runner.stop()  # no raise
    assert backend.stopped is True


def test_stdout_is_not_authoritative_result():
    # R1-#4: runner exposes no result-parsing API; read_output is raw text.
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_output("RESULT: 42")
    assert runner.read_output() == "RESULT: 42"   # verbatim, unparsed
    assert not hasattr(runner, "result")
    assert not hasattr(runner, "get_result")
```

- [ ] **Step 6: Run the full runner suite to verify it passes**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_runner.py -v`
Expected: PASS (18 passed)

- [ ] **Step 7: Run the whole suite**

Run: `cd WIP && python -m pytest -v`
Expected: PASS (all tests across state/adapters/backend/runner green)

- [ ] **Step 8: Commit**

```bash
git add WIP/axdt/agent_runner/runner.py WIP/axdt/agent_runner/tests/test_runner.py
git commit -m "feat(phase5): AgentRunner lifecycle + state machine (R1/R2 contracts)"
```

---

### Task 6: Deliverable docs — `PLATFORM_MATRIX.md` + package `README.md`

**Files:**
- Create: `WIP/axdt/agent_runner/PLATFORM_MATRIX.md`
- Create: `WIP/axdt/agent_runner/README.md`

**Interfaces:**
- Consumes: the final shapes of `ClaudeCodeAdapter` / `CodexAdapter` / `AgentRunner` (Tasks 2-5).
- Produces: documentation only (no importable symbols). These are the "플랫폼별 동작 차이 검증 매트릭스" (TODO Phase 5) and the D11 directory README.

- [ ] **Step 1: Write `PLATFORM_MATRIX.md`**

`WIP/axdt/agent_runner/PLATFORM_MATRIX.md`:
```markdown
# 플랫폼별 동작 차이 검증 매트릭스 (Phase 5)

> 범위: agent runner 어댑터의 플랫폼 차이. **확정** = 단위 테스트로 고정됨.
> **provisional** = Phase 3 `TmuxDockerBackend` 라이브 검증 시 확정.

| 항목 | ClaudeCodeAdapter | CodexAdapter | 상태 |
|---|---|---|---|
| `name` | `claude-code` | `codex` | 확정 (test_adapters) |
| `config_dir_name` | `.claude` | `.codex` | 확정 |
| `config_dir(workdir)` | `workdir/.claude` | `workdir/.codex` | 확정 |
| `build_launch_command` | `["claude"]` | `["codex"]` | provisional (실 플래그 Phase 3) |
| `format_prompt(t)` | `t + "\n"` (literal) | `t + "\n"` (literal) | 확정 (계약) / 제출 키 provisional |
| ERROR 마커 | `fatal:`, `Error:` | `stream error:`, `error:` | provisional |
| WAITING_INPUT 마커 | `Do you want to proceed?` | `Allow command? [y/N]` | provisional |
| BUSY 마커 | `Esc to interrupt` | `ctrl-c to interrupt` | provisional |
| IDLE 마커 | `\n> ` | `\n› ` | provisional |

## Phase 3 백엔드 리스크 (TmuxDockerBackend.send_text)
literal text 주입은 FakeBackend엔 충분하나 tmux엔 미확정 케이스가 있다 — 라이브 검증 필요:
- 멀티라인 prompt, paste(bracketed-paste) 모드
- Enter 키 이벤트 vs literal `\n`
- 셸 이스케이프 / 제어문자
- 정확한 idle/busy/waiting 출력 마커 (ANSI 포함 실제 캡처로 보정)

## 검증 방식
- 확정 항목: `axdt/agent_runner/tests/`의 단위 테스트가 계약을 고정.
- provisional 항목: Phase 3에서 실제 CLI 출력 캡처로 마커/플래그를 보정하고 이 표를 갱신.
```

- [ ] **Step 2: Write the package `README.md`**

`WIP/axdt/agent_runner/README.md`:
```markdown
# axdt.agent_runner

**목적:** Claude Code·Codex CLI 에이전트 세션을 동일 인터페이스로 구동하는 공통 agent runner 추상 (Phase 5). 설계: `WIP/specs/2026-06-26-phase5-agent-runner-design.md`.

## 구성
- `state.py` — `AgentState` 통제 어휘 (STARTING/IDLE/BUSY/WAITING_INPUT/STOPPED/ERROR).
- `adapters/base.py` — `PlatformAdapter` ABC (플랫폼 고유 지식).
- `adapters/claude_code.py`, `adapters/codex.py` — 두 어댑터.
- `backend.py` — `SessionBackend` ABC + 테스트용 `FakeBackend`. Phase 3가 `TmuxDockerBackend` 추가.
- `runner.py` — `AgentRunner` (adapter + backend 합성, 동기·폴링 라이프사이클).
- `PLATFORM_MATRIX.md` — 플랫폼별 동작 차이 검증 매트릭스.
- `tests/` — 계약 고정 단위 테스트.

## 핵심 계약
- 합성: `AgentRunner(adapter, backend)`. substrate는 주입 (tmux/Docker는 Phase 3).
- `read_output`/`poll_state`는 **모니터링·liveness 전용** — 작업 결과의 권위는 report 파일 (ADR-0003). runner는 stdout을 결과로 파싱하지 않는다.
- `send_prompt`는 `IDLE`·`WAITING_INPUT`에서만 허용 (그 외 `RuntimeError`); 호출 전 `wait_until_idle`.
- 의도적 `stop()`은 항상 `STOPPED` (강제 종료의 nonzero exit도 ERROR로 뒤집지 않음).
- 동기 + 폴링 (asyncio 아님).

## 네이밍
- 어댑터 클래스: `<Platform>Adapter`. 백엔드: `<Substrate>Backend`. 상태 어휘는 `AgentState`에 고정 (임의 추가 금지 — 변경은 spec 경유).

## 테스트
`cd WIP && python -m pytest axdt/agent_runner -v`
```

- [ ] **Step 3: Verify the docs reference real symbols (no code, sanity only)**

Run: `cd WIP && python -m pytest -q`
Expected: PASS (all suites green — confirms the symbols referenced in the docs exist and the package imports cleanly)

- [ ] **Step 4: Commit**

```bash
git add WIP/axdt/agent_runner/PLATFORM_MATRIX.md WIP/axdt/agent_runner/README.md
git commit -m "docs(phase5): PLATFORM_MATRIX + agent_runner README"
```

---

## Self-Review

**1. Spec coverage** (spec §-by-§):
- §2.1 composition (Runner = Adapter + Backend) → Task 5 `AgentRunner.__init__`. ✓
- §2.2 injected SessionBackend / FakeBackend → Task 4. ✓
- §2.3 read_output monitoring-only / no result parsing → Task 5 `test_stdout_is_not_authoritative_result`. ✓
- §2.4 sync+polling, single `wait_until_idle` → Task 5. ✓ Transcript retention bounded via `TAIL_WINDOW` in `poll_state`. ✓
- §2.5 `.claude/.codex` path-only (no config authoring) → adapters expose `config_dir`; no config files created. ✓
- §3 contract (AgentState, PlatformAdapter, SessionBackend, AgentRunner incl. `_read_cursor`, `_stop_requested`, `INPUT_ACCEPTING`) → Tasks 1,2,4,5. ✓
- §3 behavior rules (drain+cursor, start preconditions, send preconditions, poll_state ordering `_stop_requested`→liveness→detect, detect None keeps last, wait_until_idle, stop idempotent) → Task 5 tests. ✓
- §4 adapters (config_dir, literal format_prompt, detect_state None, provisional flags/markers) → Tasks 2,3 + PLATFORM_MATRIX (Task 6). ✓
- §5 package layout → matches Tasks 1-6 file paths exactly. ✓ (Note: spec listed `tests/test_runner.py`; plan also adds `tests/test_backend.py` for Task 4 — additive, consistent.)
- §6 tests (cursor independence, failure distinction, detect inconclusive, preconditions, send-state, stop normalisation, start-failure, non-authoritative) → Task 5 suite. ✓
- §7 deliverable checklist (interface, both adapters, PLATFORM_MATRIX, tests, pyproject) → Tasks 1-6. ✓ (ADR-0005 is tracked separately — see note below.)

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to" — every code/test step has complete code and exact commands. ✓

**3. Type consistency:** `AgentState` members, `PlatformAdapter` method names (`build_launch_command`/`format_prompt`/`detect_state`/`config_dir`), `SessionBackend` methods (`start`/`send_text`/`read_new_output`/`is_alive`/`exit_code`/`last_error`/`stop`), `AgentRunner` API (`start_session`/`send_prompt`/`read_output`/`poll_state`/`wait_until_idle`/`stop`/`transcript`) are used identically across Tasks 2-6. ✓

**Out-of-plan note (not a code task):** Spec §8 lists `WIP/adr/0005-agent-runner-composition-and-injected-backend.md`. That ADR records the composition/injection decision and should be authored alongside this work, but it is documentation of an already-approved decision, not part of the TDD build — author it as a normal doc commit (it does not gate the tests).
