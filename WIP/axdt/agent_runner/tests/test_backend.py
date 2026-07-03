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
