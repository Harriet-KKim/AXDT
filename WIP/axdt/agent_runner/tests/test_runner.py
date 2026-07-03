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
