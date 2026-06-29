# Phase 5 Agent Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the AXDT common agent runner abstraction — `AgentRunner` composing a `PlatformAdapter` (Claude Code / Codex) and an injected `SessionBackend` — at interface + test-skeleton depth.

**Architecture:** Three-axis composition. `AgentRunner` owns the synchronous, polling lifecycle (start → send → read → poll → stop). `PlatformAdapter` holds platform-specific knowledge (launch argv, prompt formatting, output→state detection). `SessionBackend` is the execution substrate, injected; tests use the in-memory `FakeBackend`, Phase 3 will add `TmuxDockerBackend`. `read_output` is monitoring/liveness only — authoritative results flow through report files (ADR-0003).

**Tech Stack:** Python ≥3.10 (stdlib only: `enum`, `abc`, `re`, `time`, `pathlib`), pytest.

**Spec:** `WIP/specs/2026-06-26-phase5-agent-runner-design.md` (Codex-reviewed READY; plan reconciled to cwd-only launch contract after plan review).

## Global Constraints

- Python `requires-python = ">=3.10"` (uses `X | None` / `list[str]` annotations).
- All code lives under `WIP/` (D12 — AXDT self-implementation, temporary location). Package root = `WIP/`, package = `axdt`.
- Synchronous + polling only — **no asyncio**.
- `AgentState` is a controlled vocabulary: `STARTING, IDLE, BUSY, WAITING_INPUT, STOPPED, ERROR`. Do not add members without updating the spec.
- `read_output`/`poll_state` are monitoring/liveness only; the runner MUST NOT parse stdout into authoritative results.
- Launch contract: `build_launch_command` returns the CLI argv; config is resolved via **cwd=workdir** (`config_dir = workdir/config_dir_name` lives inside the working dir). Explicit config flags are provisional (Phase 3).
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

import pytest

from axdt.agent_runner.state import AgentState
from axdt.agent_runner.adapters.base import PlatformAdapter
from axdt.agent_runner.adapters.claude_code import ClaudeCodeAdapter


def test_platform_adapter_is_abstract():
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

        Config is resolved via cwd=workdir (the backend runs this argv with
        cwd=workdir, and config_dir = workdir/config_dir_name lives inside it).
        Explicit config flags are provisional and verified live in Phase 3
        (PLATFORM_MATRIX.md).
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
    _IDLE_MARKERS = ("\n› ",)  # "\n> " with the codex chevron

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

### Task 5: `AgentRunner` lifecycle (with stubbed `poll_state`)

> Splitting the runner into lifecycle (this task) and state machine (Task 6) keeps TDD honest: Task 5's `poll_state` is a deliberate **stub** that only drains and returns the last state, so Task 6's state-machine tests genuinely fail first against it.

**Files:**
- Create: `WIP/axdt/agent_runner/runner.py`
- Test: `WIP/axdt/agent_runner/tests/test_runner.py`

**Interfaces:**
- Consumes: `AgentState` (Task 1), `ClaudeCodeAdapter` (Task 2), `FakeBackend` (Task 4).
- Produces: module helper `_strip_ansi(text) -> str`; `AgentRunner(adapter, backend)` with `start_session(workdir, env=None)`, `read_output() -> str`, `poll_state() -> AgentState` (**stub** in this task), `stop()`, property `transcript -> str`. Internal state `_transcript`, `_read_cursor`, `_last_state`, `_stop_requested`, `_started`. `send_prompt` / `wait_until_idle` are added in Task 6.

- [ ] **Step 1: Write the failing lifecycle tests**

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
    runner.poll_state()                      # drains "hello" into transcript
    assert runner.read_output() == "hello"   # still delivered


def test_start_twice_raises():
    runner, _ = make()
    runner.start_session(Path("/wt"))
    with pytest.raises(RuntimeError):
        runner.start_session(Path("/wt"))


def test_start_after_stop_raises():
    runner, _ = make()
    runner.start_session(Path("/wt"))
    runner.stop()
    with pytest.raises(RuntimeError):
        runner.start_session(Path("/wt"))


def test_stop_is_idempotent():
    runner, backend = make()
    runner.start_session(Path("/wt"))
    runner.stop()
    runner.stop()  # no raise
    assert backend.stopped is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'axdt.agent_runner.runner'`

- [ ] **Step 3: Write the lifecycle implementation (stub `poll_state`)**

`WIP/axdt/agent_runner/runner.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_runner.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add WIP/axdt/agent_runner/runner.py WIP/axdt/agent_runner/tests/test_runner.py
git commit -m "feat(phase5): AgentRunner lifecycle (stub poll_state)"
```

---

### Task 6: `AgentRunner` state machine (`poll_state` / `send_prompt` / `wait_until_idle`)

**Files:**
- Modify: `WIP/axdt/agent_runner/runner.py` (replace stub `poll_state`; add `INPUT_ACCEPTING`, `TAIL_WINDOW`, `send_prompt`, `wait_until_idle`; add `import time`)
- Modify: `WIP/axdt/agent_runner/tests/test_runner.py` (append state-machine tests)

**Interfaces:**
- Consumes: Task 5 `AgentRunner` lifecycle, `AgentState`, `ClaudeCodeAdapter`, `FakeBackend`.
- Produces: `AgentRunner.INPUT_ACCEPTING = frozenset({IDLE, WAITING_INPUT})`, `AgentRunner.TAIL_WINDOW = 2000`, `send_prompt(text)`, `wait_until_idle(timeout, poll_interval=0.5) -> AgentState`, and a full `poll_state()` honoring `_stop_requested` → failure → `detect_state`.

- [ ] **Step 1: Write the failing state-machine tests (append to test_runner.py)**

Append to `WIP/axdt/agent_runner/tests/test_runner.py`:
```python
def test_poll_state_detects_idle_from_marker():
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_output("\n> ")
    assert runner.poll_state() is AgentState.IDLE


def test_poll_state_keeps_previous_when_detect_inconclusive():
    # R1-#3: detect_state -> None must preserve the previous state.
    class SilentAdapter(ClaudeCodeAdapter):
        def detect_state(self, recent_output):
            return None  # always inconclusive

    backend = FakeBackend()
    runner = AgentRunner(SilentAdapter(), backend)
    runner.start_session(Path("/wt"))
    backend.script_output("\n> ")  # the real adapter would say IDLE here
    assert runner.poll_state() is AgentState.STARTING  # None -> keep previous


def test_poll_state_maps_failure_to_error():
    # R1-#2: dead with non-zero exit / last_error -> ERROR.
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


def test_send_prompt_rejected_in_starting_and_busy():
    # R2-2: STARTING and BUSY are not input-accepting.
    runner, backend = make()
    runner.start_session(Path("/wt"))           # STARTING
    with pytest.raises(RuntimeError):
        runner.send_prompt("hi")
    backend.script_output("Esc to interrupt")   # -> BUSY
    with pytest.raises(RuntimeError):
        runner.send_prompt("hi")


def test_send_prompt_accepted_in_idle_and_waiting_input():
    # R2-2: IDLE and WAITING_INPUT accept prompts.
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_output("\n> ")                    # -> IDLE
    runner.send_prompt("a")
    backend.script_output("Do you want to proceed?")  # -> WAITING_INPUT
    runner.send_prompt("b")
    assert backend.sent == ["a\n", "b\n"]


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


def test_wait_until_idle_returns_on_waiting_input():
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_output("Do you want to proceed?")
    assert runner.wait_until_idle(timeout=0.05, poll_interval=0.01) is AgentState.WAITING_INPUT


def test_wait_until_idle_returns_on_error():
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_exit(2)
    assert runner.wait_until_idle(timeout=0.05, poll_interval=0.01) is AgentState.ERROR


def test_wait_until_idle_times_out():
    runner, backend = make()
    runner.start_session(Path("/wt"))   # stays STARTING, no idle marker
    assert runner.wait_until_idle(timeout=0.03, poll_interval=0.01) is AgentState.STARTING


def test_stdout_is_not_authoritative_result():
    # R1-#4: runner exposes no result-parsing API; read_output is raw text.
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_output("RESULT: 42")
    assert runner.read_output() == "RESULT: 42"   # verbatim, unparsed
    assert not hasattr(runner, "result")
    assert not hasattr(runner, "get_result")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_runner.py -v`
Expected: FAIL — the suite is RED (about **12 of the 15 new tests fail**, so pytest exits non-zero). Failures: `send_prompt` / `wait_until_idle` raise `AttributeError` (not defined until Task 6), and `poll_state` returns `STARTING` instead of `IDLE`/`ERROR`/`STOPPED` for the detection and failure/clean-exit cases. Note: 3 of the new tests pass incidentally against the stub — `test_stop_normalises_even_with_nonzero_exit` (the stub's `stop()` itself sets `_last_state = STOPPED`), `test_poll_state_keeps_previous_when_detect_inconclusive` (stub returns STARTING, which is what it asserts), and `test_stdout_is_not_authoritative_result` (read_output works in the stub) — they remain valid contract tests against the full implementation. The red bar is genuine; proceed to Step 3.

- [ ] **Step 3: Replace `runner.py` with the full implementation**

Replace the entire contents of `WIP/axdt/agent_runner/runner.py` with:
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

- [ ] **Step 4: Run the full runner suite to verify it passes**

Run: `cd WIP && python -m pytest axdt/agent_runner/tests/test_runner.py -v`
Expected: PASS (23 passed)

- [ ] **Step 5: Run the whole suite**

Run: `cd WIP && python -m pytest -v`
Expected: PASS (37 passed — state 2 + adapters 7 + backend 5 + runner 23)

- [ ] **Step 6: Commit**

```bash
git add WIP/axdt/agent_runner/runner.py WIP/axdt/agent_runner/tests/test_runner.py
git commit -m "feat(phase5): AgentRunner state machine (R1/R2 contracts)"
```

---

### Task 7: Deliverable docs — `PLATFORM_MATRIX.md` + package `README.md`

**Files:**
- Create: `WIP/axdt/agent_runner/PLATFORM_MATRIX.md`
- Create: `WIP/axdt/agent_runner/README.md`

**Interfaces:**
- Consumes: the final shapes of `ClaudeCodeAdapter` / `CodexAdapter` / `AgentRunner` (Tasks 2-6).
- Produces: documentation only. These are the "플랫폼별 동작 차이 검증 매트릭스" (TODO Phase 5) and the D11 directory README.

- [ ] **Step 1: Write `PLATFORM_MATRIX.md`**

`WIP/axdt/agent_runner/PLATFORM_MATRIX.md`:
```markdown
# 플랫폼별 동작 차이 검증 매트릭스 (Phase 5)

> 범위: agent runner 어댑터의 플랫폼 차이. **확정** = 단위 테스트로 고정됨.
> **provisional** = Phase 3 TmuxDockerBackend 라이브 검증 시 확정.

| 항목 | ClaudeCodeAdapter | CodexAdapter | 상태 |
|---|---|---|---|
| name | claude-code | codex | 확정 (test_adapters) |
| config_dir_name | .claude | .codex | 확정 |
| config_dir(workdir) | workdir/.claude | workdir/.codex | 확정 |
| build_launch_command | ["claude"] (cwd=workdir로 config 해석) | ["codex"] | 확정(cwd-only) / 명시 플래그 provisional |
| format_prompt(t) | t + "\n" (literal) | t + "\n" (literal) | 확정 (계약) / 제출 키 provisional |
| ERROR 마커 | fatal:, Error: | stream error:, error: | provisional |
| WAITING_INPUT 마커 | Do you want to proceed? | Allow command? [y/N] | provisional |
| BUSY 마커 | Esc to interrupt | ctrl-c to interrupt | provisional |
| IDLE 마커 | "\n> " | "\n› " | provisional |

## Phase 3 백엔드 리스크 (TmuxDockerBackend.send_text)
literal text 주입은 FakeBackend엔 충분하나 tmux엔 미확정 케이스가 있다 — 라이브 검증 필요:
- 멀티라인 prompt, paste(bracketed-paste) 모드
- Enter 키 이벤트 vs literal "\n"
- 셸 이스케이프 / 제어문자
- 정확한 idle/busy/waiting 출력 마커 (ANSI 포함 실제 캡처로 보정)

## 검증 방식
- 확정 항목: axdt/agent_runner/tests/의 단위 테스트가 계약을 고정.
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
- 동기 + 폴링 (asyncio 아님). config는 cwd=workdir 기준 해석.

## 네이밍
- 어댑터 클래스: `<Platform>Adapter`. 백엔드: `<Substrate>Backend`. 상태 어휘는 `AgentState`에 고정 (임의 추가 금지 — 변경은 spec 경유).

## 테스트
`cd WIP && python -m pytest axdt/agent_runner -v`
```

- [ ] **Step 3: Verify docs reference real symbols (sanity)**

Run: `cd WIP && python -m pytest -q`
Expected: PASS (37 passed — confirms the package imports cleanly and the symbols named in the docs exist)

- [ ] **Step 4: Commit**

```bash
git add WIP/axdt/agent_runner/PLATFORM_MATRIX.md WIP/axdt/agent_runner/README.md
git commit -m "docs(phase5): PLATFORM_MATRIX + agent_runner README"
```

---

### Task 8: ADR-0005 — composition + injected backend

> Spec §7/§8 list this ADR as a deliverable (D13: non-trivial decisions get an ADR with rationale + alternatives). It documents an already-approved decision, so there is no test cycle — it is a documentation commit.

**Files:**
- Create: `WIP/adr/0005-agent-runner-composition-and-injected-backend.md`

**Interfaces:**
- Consumes: the design rationale in the spec (§2.1, §2.2).
- Produces: ADR-0005 (referenced by the spec).

- [ ] **Step 1: Write ADR-0005**

Follow the existing ADR shape (see `WIP/adr/0003-agent-communication-model.md` in the main checkout for the house style: frontmatter `id/title/status/date/decision/related`, then 상태 / 맥락 / 결정 / 결과 / 검토한 대안 sections).

`WIP/adr/0005-agent-runner-composition-and-injected-backend.md`:
```markdown
---
id: ADR-0005
title: agent runner는 어댑터+백엔드 합성과 주입된 실행 백엔드로 구성한다
status: accepted
date: 2026-06-26
decision: D4
related: [ADR-0003]
---

# ADR-0005: agent runner는 어댑터+백엔드 합성과 주입된 실행 백엔드로 구성한다

## 상태
Accepted (2026-06-26) · 관련 결정 D4

## 맥락
D4는 공통 agent runner 인터페이스 + Claude Code·Codex 어댑터 양쪽 구현을 요구한다. 두 플랫폼의 세션 라이프사이클(기동→prompt 주입→출력 읽기→정지)은 동일하고, 차이는 (1) 어떤 CLI를 어떻게 띄우고 prompt/출력을 어떻게 포맷·파싱하는가, (2) 어디서 실행되는가(로컬/tmux/Docker)뿐이다. 또 Phase 5 시점엔 tmux/Docker substrate(Phase 3)가 없어 substrate 없이도 계약을 검증할 수 있어야 한다.

## 결정
- `AgentRunner`는 `PlatformAdapter`(플랫폼 지식)와 `SessionBackend`(실행 substrate)를 **합성**한다. 플랫폼별 runner 상속은 하지 않는다.
- `SessionBackend`는 **주입**된다. Phase 3가 `TmuxDockerBackend`를 구현하고, Phase 5는 `FakeBackend`로 계약을 단위 테스트한다.
- `read_output`/`poll_state`는 모니터링·liveness 전용이며 작업 결과의 권위 채널은 report 파일이다(ADR-0003).

## 결과
**좋은 점**
- 라이프사이클 로직이 한 곳에 있고 변하는 축(어댑터·백엔드)만 교체된다 — 중복 제거.
- substrate-독립적이라 tmux/Docker 없이도 결정적으로 테스트된다.
- 결과 권위가 report에 있어 stdout 파싱 결합을 피한다(ADR-0003·0004와 정합).

**대가 / 주의**
- 객체 3개(runner/adapter/backend)로 간접성이 늘어난다(수용 범위).
- CLI 플래그·출력 마커·tmux 제출 뉘앙스는 Phase 3 라이브 검증까지 provisional.

## 검토한 대안
### 대안 A — 플랫폼별 runner 상속 (ClaudeCodeRunner/CodexRunner)
각 플랫폼이 라이프사이클을 구현. · **기각 사유**: 동일 라이프사이클을 플랫폼 수만큼 중복시킨다.

### 대안 B — runner가 tmux/Docker를 직접 소유
substrate를 runner 내부에 박음. · **기각 사유**: Phase 3와 책임이 섞이고, mock하려면 monkeypatch가 필요해 계약 경계가 흐려진다.

### 대안 C — read_output을 권위 결과 채널로 사용
stdout 파싱으로 결과 수용. · **기각 사유**: ADR-0003의 report 권위 흐름과 충돌하고 출력 포맷에 강결합된다.
```

> Note: this file lands in the worktree branch. `WIP/adr/0001-0004` currently exist only as untracked files in the main checkout (per the user's README-only initial commit); reference resolution across branches is the documented #10 caveat in the spec.

- [ ] **Step 2: Commit**

```bash
git add WIP/adr/0005-agent-runner-composition-and-injected-backend.md
git commit -m "docs(phase5): ADR-0005 agent runner composition + injected backend"
```

---

## Self-Review

**1. Spec coverage** (spec §-by-§):
- §2.1 composition → Task 5/6 `AgentRunner`. ✓
- §2.2 injected SessionBackend / FakeBackend → Task 4. ✓
- §2.3 read_output monitoring-only / report ownership outside runner → Task 6 `test_stdout_is_not_authoritative_result`. ✓
- §2.4 sync+polling, single `wait_until_idle`, bounded `TAIL_WINDOW` → Tasks 5/6. ✓
- §2.5 `.claude/.codex` path-only (no config authoring) → adapters expose `config_dir`; no config files created. ✓
- §3 contract (AgentState; PlatformAdapter incl. `config_dir`; SessionBackend incl. `exit_code`/`last_error`; AgentRunner incl. `_read_cursor`, `_stop_requested`, `INPUT_ACCEPTING`, `TAIL_WINDOW`) → Tasks 1,2,4,5,6. ✓
- §3 behavior rules (drain+cursor; start preconditions incl. start-after-stop; send precondition INPUT_ACCEPTING; poll_state ordering `_stop_requested`→liveness→detect; detect None keeps last; wait_until_idle terminals IDLE/WAITING_INPUT/ERROR; stop idempotent) → Tasks 5/6 tests. ✓
- §4 adapters (cwd-only launch, literal format_prompt, detect_state None, provisional markers) → Tasks 2,3 + PLATFORM_MATRIX (Task 7). ✓
- §5 package layout → matches Tasks 1-7 paths (plus additive `tests/test_backend.py`). ✓
- §6 tests (cursor independence, ERROR vs STOPPED, detect inconclusive [genuine via SilentAdapter], non-authoritative, send accepting/rejecting incl. BUSY+WAITING_INPUT, stop normalisation, start-failure, wait_until_idle incl. WAITING_INPUT/ERROR, preconditions) → Task 6. ✓
- §7 deliverables (interface, both adapters, PLATFORM_MATRIX, tests, pyproject, ADR-0005) → Tasks 1-8. ✓
- §8 ADR-0005 → Task 8. ✓

**2. Placeholder scan:** No TBD/vague steps — every code/test step has complete code and exact commands. ✓

**3. Type consistency:** `AgentState` members; `PlatformAdapter` (`build_launch_command`/`format_prompt`/`detect_state`/`config_dir`/`config_dir_name`/`name`); `SessionBackend` (`start`/`send_text`/`read_new_output`/`is_alive`/`exit_code`/`last_error`/`stop` + `script_*`/`start_calls`/`sent`/`started`/`stopped`); `AgentRunner` (`start_session`/`send_prompt`/`read_output`/`poll_state`/`wait_until_idle`/`stop`/`transcript`/`INPUT_ACCEPTING`/`TAIL_WINDOW`/`_strip_ansi`) used identically across Tasks 2-8. ✓

**Test counts:** state 2, adapters 7, backend 5, runner 8 (Task 5) + 15 (Task 6) = 23. Whole suite = 37.

**Review provenance:** spec Codex-reviewed READY (3 rounds); this plan revised after Codex (NOT-READY, 5 items) + Opus (READY, non-blocking) reviews — TDD split (Task 5/6), tautological test fixed (SilentAdapter), BUSY/WAITING_INPUT send + wait_until_idle WAITING_INPUT/ERROR + start-after-stop coverage added, launch contract reconciled to cwd-only (spec §3/§4), ADR-0005 added (Task 8), counts corrected.
