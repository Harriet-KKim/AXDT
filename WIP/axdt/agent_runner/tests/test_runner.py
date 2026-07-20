from pathlib import Path

import pytest

from axdt.agent_runner.state import AgentState
from axdt.agent_runner.backend import FakeBackend
from axdt.agent_runner.adapters.claude_code import ClaudeCodeAdapter
from axdt.agent_runner.runner import AgentRunner, _strip_ansi
from axdt.roles.spec import ROLES

LEADER = ROLES["leader"]


def make(backend=None):
    backend = backend or FakeBackend()
    return AgentRunner(ClaudeCodeAdapter(), backend), backend


def test_start_session_invokes_backend_with_launch_command():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"), {"K": "V"})
    expected_command = ClaudeCodeAdapter().build_session_command(LEADER, Path("/wt"))
    assert backend.start_calls == [(expected_command, Path("/wt"), {"K": "V"})]


def test_strip_ansi_removes_escape_sequences():
    assert _strip_ansi("\x1b[31mred\x1b[0m> ") == "red> "


def test_read_output_increments_and_accumulates_transcript():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
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
    runner.start_session(LEADER, Path("/wt"))
    backend.script_output("hello")
    runner.poll_state()                      # drains "hello" into transcript
    assert runner.read_output() == "hello"   # still delivered


def test_start_twice_raises():
    runner, _ = make()
    runner.start_session(LEADER, Path("/wt"))
    with pytest.raises(RuntimeError):
        runner.start_session(LEADER, Path("/wt"))


def test_start_after_stop_raises():
    runner, _ = make()
    runner.start_session(LEADER, Path("/wt"))
    runner.stop()
    with pytest.raises(RuntimeError):
        runner.start_session(LEADER, Path("/wt"))


def test_stop_is_idempotent():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    runner.stop()
    runner.stop()  # no raise
    assert backend.stopped is True


def test_poll_state_detects_idle_from_state():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_state("idle")
    assert runner.poll_state() is AgentState.IDLE


def test_poll_state_keeps_previous_when_detect_inconclusive():
    # R1-#3: detect_state -> None must preserve the previous state.
    class SilentAdapter(ClaudeCodeAdapter):
        def detect_state(self, raw_state):
            return None  # always inconclusive

    backend = FakeBackend()
    runner = AgentRunner(SilentAdapter(), backend)
    runner.start_session(LEADER, Path("/wt"))
    backend.script_state("idle")  # the real adapter would say IDLE here
    assert runner.poll_state() is AgentState.STARTING  # None -> keep previous


def test_poll_state_maps_failure_to_error():
    # R1-#2: dead with non-zero exit / last_error -> ERROR.
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_exit(2)
    assert runner.poll_state() is AgentState.ERROR


def test_poll_state_clean_exit_is_stopped():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_exit(0)
    assert runner.poll_state() is AgentState.STOPPED


def test_poll_state_before_start_is_starting():
    # Pre-start poll must read STARTING, not STOPPED (backend not alive yet).
    runner, _ = make()
    assert runner.poll_state() is AgentState.STARTING


def test_poll_state_recovers_from_busy_to_idle():
    # A fresh idle state after busy recovers, not sticks.
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_state("busy")
    assert runner.poll_state() is AgentState.BUSY
    backend.script_state("idle")
    assert runner.poll_state() is AgentState.IDLE


def test_stop_normalises_even_with_nonzero_exit():
    # R2-1: intentional stop() must not be reclassified ERROR.
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_exit(137)   # e.g. killed
    runner.stop()
    assert runner.poll_state() is AgentState.STOPPED


def test_send_prompt_rejected_in_starting_and_busy():
    # R2-2: STARTING and BUSY are not input-accepting.
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))           # STARTING
    with pytest.raises(RuntimeError):
        runner.send_prompt("hi")
    backend.script_state("busy")                # -> BUSY
    with pytest.raises(RuntimeError):
        runner.send_prompt("hi")


def test_send_prompt_accepted_in_idle_and_rejected_in_waiting_input():
    # send_prompt is now IDLE-only (spec §9): submit() is folded in, so
    # accepting WAITING_INPUT would auto-approve a permission prompt.
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_state("idle")                # -> IDLE
    runner.send_prompt("a")
    runner.send_prompt("b")
    assert backend.sent == ["a", "b"]
    assert backend.keys == ["Enter", "Enter"]
    backend.script_state("waiting")              # -> WAITING_INPUT
    with pytest.raises(RuntimeError):
        runner.send_prompt("c")


def test_submit_sends_submit_key():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_state("idle")
    runner.submit()
    assert backend.keys == ["Enter"]


def test_clear_input_sends_clear_key():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    runner.clear_input()
    assert backend.keys == ["C-u"]


def test_send_when_idle_clears_sends_submits():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_state("idle")
    assert runner.send_when_idle("m") is True
    assert backend.keys == ["C-u", "Enter"]
    assert backend.sent == ["m"]


def test_send_when_idle_returns_false_when_not_idle():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))            # STARTING
    assert runner.send_when_idle("m") is False
    backend.script_state("busy")                 # -> BUSY
    assert runner.send_when_idle("m") is False
    assert backend.sent == []
    assert backend.keys == []


def test_attach_constructs_started_runner():
    backend = FakeBackend()
    backend.start(["claude"], Path("/wt"))
    backend.script_output("seed")
    runner = AgentRunner.attach(ClaudeCodeAdapter(), backend)
    assert runner.transcript == "seed"
    assert runner.read_output() == ""


def test_send_prompt_before_start_raises():
    runner, _ = make()
    with pytest.raises(RuntimeError):
        runner.send_prompt("hi")


def test_send_prompt_after_stop_raises():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    runner.stop()
    with pytest.raises(RuntimeError):
        runner.send_prompt("hi")


def test_start_launch_failure_becomes_error():
    # R2-3: backend reports launch failure non-raising -> poll_state ERROR.
    backend = FakeBackend()
    backend.script_start_failure("command not found")
    runner, _ = make(backend)
    runner.start_session(LEADER, Path("/wt"))   # must not raise
    assert runner.poll_state() is AgentState.ERROR


def test_wait_until_idle_returns_on_idle():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_state("idle")
    assert runner.wait_until_idle(timeout=0.05, poll_interval=0.01) is AgentState.IDLE


def test_wait_until_idle_returns_on_waiting_input():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_state("waiting")
    assert runner.wait_until_idle(timeout=0.05, poll_interval=0.01) is AgentState.WAITING_INPUT


def test_wait_until_idle_returns_on_error():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_exit(2)
    assert runner.wait_until_idle(timeout=0.05, poll_interval=0.01) is AgentState.ERROR


def test_wait_until_idle_returns_on_stopped():
    # Clean exit is terminal — wait_until_idle returns promptly, not on timeout.
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_exit(0)
    assert runner.wait_until_idle(timeout=0.05, poll_interval=0.01) is AgentState.STOPPED


def test_wait_until_idle_times_out():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))   # stays STARTING, no idle marker
    assert runner.wait_until_idle(timeout=0.03, poll_interval=0.01) is AgentState.STARTING


def test_stdout_is_not_authoritative_result():
    # R1-#4: runner exposes no result-parsing API; read_output is raw text.
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_output("RESULT: 42")
    assert runner.read_output() == "RESULT: 42"   # verbatim, unparsed
    assert not hasattr(runner, "result")
    assert not hasattr(runner, "get_result")


def test_poll_state_absent_state_keeps_previous():
    # No hook has written the state file yet -> stays STARTING.
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    assert runner.poll_state() is AgentState.STARTING


def test_poll_state_parses_ts():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_state("busy", ts=1234.5)
    assert runner.poll_state() is AgentState.BUSY
    assert runner._last_state_ts == 1234.5


# --- C3: _parse_state robustness against malformed/adversarial raw state ---

MALFORMED_STATE_RAWS = [
    "{trunc",                                   # broken JSON
    "[]",                                       # non-dict
    '"idle"',                                   # non-dict JSON
    '{"state":"idle"}',                         # ts missing
    '{"ts":1.0}',                                # state missing
    '{"state":123,"ts":1.0}',                   # state wrong type
    '{"state":"idle","ts":"x"}',                # ts wrong type
    '{"state":"idle","ts":true}',               # bool ts
    '{"state":"idle","ts":NaN}',                # json.loads allows NaN -> non-finite
    '{"state":"idle","ts":1e400}',              # -> inf
    '{"state":"idle","ts":1' + "0" * 400 + '}',  # huge int -> OverflowError path
    # 짧은 id를 주지 않으면 pytest가 이 5만-브래킷 원문을 노드 id로 만들어
    # PYTEST_CURRENT_TEST 환경변수 길이 상한(Windows 32767자)을 넘긴다.
    pytest.param("[" * 50000 + "]" * 50000, id="deep_nesting"),  # -> RecursionError
    "",                                          # empty string
    None,                                        # file absent
]


@pytest.mark.parametrize("raw", MALFORMED_STATE_RAWS)
def test_poll_state_malformed_raw_keeps_previous_state_without_raising(raw):
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_state("busy")
    assert runner.poll_state() is AgentState.BUSY  # seed a known state

    backend.script_state_raw(raw)
    assert runner.poll_state() is AgentState.BUSY  # unchanged, no exception


def test_poll_state_raw_valid_json_updates_state():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_state_raw('{"state":"idle","ts":123.0}')
    assert runner.poll_state() is AgentState.IDLE


# --- C9: contract-crossing tests ---

def test_start_session_threads_subagent_args_into_backend_command():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"), subagent_args=("--foo", "bar"))
    command, _cwd, _env = backend.start_calls[0]
    assert command[-2:] == ["--foo", "bar"]


def test_attach_read_output_returns_only_output_seen_after_attach():
    backend = FakeBackend()
    backend.start(["claude"], Path("/wt"))
    backend.script_output("seed")
    runner = AgentRunner.attach(ClaudeCodeAdapter(), backend)
    backend.script_output("NEW")
    assert runner.read_output() == "NEW"


def test_send_when_idle_returns_false_and_sends_nothing_when_waiting_input():
    runner, backend = make()
    runner.start_session(LEADER, Path("/wt"))
    backend.script_state("waiting")  # -> WAITING_INPUT
    assert runner.send_when_idle("m") is False
    assert backend.sent == []
    assert backend.keys == []
