import dataclasses
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path

from axdt.git_host.models import CommandResult


class CommandBackend(ABC):
    """Host-CLI execution substrate. Tests use FakeCommandBackend, real use SubprocessBackend. One-shot."""

    @abstractmethod
    def run(self, argv: list[str], cwd: "Path | None" = None,
            env: "Mapping[str, str] | None" = None) -> CommandResult:
        """Run argv, return the result (argv included). Process failure is NOT raised —
        it is surfaced as exit_code != 0."""


class FakeCommandBackend(CommandBackend):
    """Deterministic backend for tests. Returns scripted results FIFO and records every call.

    results: an iterable of CommandResult returned in order, one per run() call.
    default: returned when the scripted results are exhausted (e.g. a polling loop that
        runs longer than the script). If default is None and results run out, run() raises
        AssertionError so mis-scripting is caught.
    The actual argv passed to run() is stamped onto each returned result (via dataclasses.replace),
    so scripted results need only set stdout/stderr/exit_code — the argv you pass in is authoritative.
    """

    def __init__(self, results=None, default: "CommandResult | None" = None):
        self._results = list(results or [])
        self._default = default
        self.calls: list = []   # list of (argv, cwd, env) tuples, in call order

    def run(self, argv: list[str], cwd: "Path | None" = None,
            env: "Mapping[str, str] | None" = None) -> CommandResult:
        self.calls.append((list(argv), cwd, env))
        if self._results:
            result = self._results.pop(0)
        elif self._default is not None:
            result = self._default
        else:
            raise AssertionError(
                f"FakeCommandBackend: no scripted result for call #{len(self.calls)}: {argv}")
        return dataclasses.replace(result, argv=list(argv))


class SubprocessBackend(CommandBackend):
    """Real one-shot execution via subprocess.run. Non-zero exit surfaced (check=False);
    OSError (missing executable, etc.) is also surfaced as exit_code != 0, never raised.
    stdout/stderr are decoded as UTF-8 (errors='replace') to match host CLI (e.g. gh) output
    regardless of the OS code page.

    Note: `env`, if given, REPLACES the whole environment (subprocess.run semantics) — it is
    not merged. Passing a partial env drops PATH and the host CLI may not be found; callers
    that need to add a var must copy os.environ first.
    """

    def run(self, argv: list[str], cwd: "Path | None" = None,
            env: "Mapping[str, str] | None" = None) -> CommandResult:
        try:
            completed = subprocess.run(
                argv, cwd=cwd, env=env,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
        except OSError as exc:
            # Process could not be started (missing exe, etc.). Contract: never raise
            # on process failure — surface it as a non-zero exit (spec §153).
            return CommandResult(
                stdout="", stderr=str(exc),
                exit_code=127, argv=list(argv),
            )
        return CommandResult(
            stdout=completed.stdout, stderr=completed.stderr,
            exit_code=completed.returncode, argv=list(argv),
        )
