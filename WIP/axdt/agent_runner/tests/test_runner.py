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


def test_poll_state_before_start_is_starting():
    # Pre-start poll must read STARTING, not STOPPED (backend not alive yet).
    runner, _ = make()
    assert runner.poll_state() is AgentState.STARTING


def test_poll_state_recovers_from_busy_to_idle():
    # Latest-marker-wins: a fresh IDLE prompt after BUSY recovers, not sticks.
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_output("... Esc to interrupt")
    assert runner.poll_state() is AgentState.BUSY
    backend.script_output("\n> ")
    assert runner.poll_state() is AgentState.IDLE


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


def test_wait_until_idle_returns_on_stopped():
    # Clean exit is terminal — wait_until_idle returns promptly, not on timeout.
    runner, backend = make()
    runner.start_session(Path("/wt"))
    backend.script_exit(0)
    assert runner.wait_until_idle(timeout=0.05, poll_interval=0.01) is AgentState.STOPPED


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
