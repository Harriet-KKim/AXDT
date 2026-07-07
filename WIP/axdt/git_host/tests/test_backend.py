import sys

import pytest

from axdt.git_host.backend import CommandBackend, FakeCommandBackend, SubprocessBackend
from axdt.git_host.models import CommandResult


def test_commandbackend_is_abstract():
    """CommandBackend cannot be instantiated directly (abstract method run)."""
    with pytest.raises(TypeError):
        CommandBackend()


def test_fakecommandbackend_scripts_records_and_surfaces_nonzero_exit():
    """FakeCommandBackend returns scripted results FIFO, records calls, and surfaces exit!=0 without raising."""
    backend = FakeCommandBackend(results=[
        CommandResult("out1", "", 0, []),
        CommandResult("", "boom", 2, []),
    ])

    first = backend.run(["gh", "pr", "create"])
    second = backend.run(["gh", "pr", "view", "1"])

    assert first.stdout == "out1"
    assert first.exit_code == 0
    assert second.exit_code == 2
    assert second.stderr == "boom"

    assert backend.calls == [
        (["gh", "pr", "create"], None, None),
        (["gh", "pr", "view", "1"], None, None),
    ]

    # argv stamping: the scripted [] is replaced with the actual argv passed in.
    assert first.argv == ["gh", "pr", "create"]


def test_fakecommandbackend_returns_default_when_results_exhausted():
    """FakeCommandBackend returns the default result (with argv stamped) once scripted results run out."""
    backend = FakeCommandBackend(default=CommandResult("d", "", 0, []))

    first = backend.run(["x"])
    second = backend.run(["x"])

    assert first.stdout == "d"
    assert first.argv == ["x"]
    assert second.stdout == "d"
    assert second.argv == ["x"]


def test_fakecommandbackend_raises_when_exhausted_without_default():
    """FakeCommandBackend with no results and no default raises AssertionError on run()."""
    backend = FakeCommandBackend()

    with pytest.raises(AssertionError):
        backend.run(["x"])


def test_subprocessbackend_captures_stdout_exit_and_argv():
    """SubprocessBackend captures stdout, exit_code, and stamps argv for a successful command."""
    argv = [sys.executable, "-c", "print('hi')"]

    result = SubprocessBackend().run(argv)

    assert "hi" in result.stdout
    assert result.exit_code == 0
    assert result.argv == argv


def test_subprocessbackend_surfaces_nonzero_exit_without_raising():
    """SubprocessBackend surfaces a non-zero exit code and stderr without raising."""
    argv = [sys.executable, "-c", "import sys; sys.stderr.write('bad'); sys.exit(3)"]

    result = SubprocessBackend().run(argv)

    assert result.exit_code == 3
    assert "bad" in result.stderr
