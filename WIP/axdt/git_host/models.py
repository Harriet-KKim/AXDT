from dataclasses import dataclass

from axdt.git_host.state import PullRequestState, ReviewDecision, TERMINAL_DECISIONS


@dataclass(frozen=True)
class PullRequest:
    number: int
    url: str
    head: str
    base: str


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int
    argv: list[str]                   # for failure tracing (the argv that was run)


@dataclass(frozen=True)
class ReviewEvent:
    """A single review by the target reviewer (order preserved in the reviews stream)."""
    review_id: str                    # opaque review id (consensus C)
    decision: ReviewDecision


@dataclass(frozen=True)
class ReviewSnapshot:
    """Review sample from the target reviewer's perspective — for gate-cursor comparison (§2.8, consensus A/D).
    events is the ordered (oldest->newest) list of the target reviewer's items picked out of the full reviews history.
    Because a terminal event AFTER the cursor must be judged by stream POSITION, we carry the ordered
    sequence, not just the latest one."""
    events: "tuple[ReviewEvent, ...]"   # stream order (oldest->newest); empty tuple if none
    awaiting: bool                       # is the reviewer still in reviewRequests (request unanswered)

    @property
    def latest_review_id(self):
        return self.events[-1].review_id if self.events else None

    def terminal_after(self, cursor_id):
        """First terminal decision AFTER the cursor (by stream position). None if none (consensus D).
        cursor_id=None -> scan all events for the first terminal decision.
        cursor_id not found in events (dismissed away) -> return None to keep waiting
        — the dismiss fallback is provisional (consensus G, HOST_MATRIX)."""
        started = cursor_id is None
        for ev in self.events:
            if not started:
                if ev.review_id == cursor_id:
                    started = True
                continue
            if ev.decision in TERMINAL_DECISIONS:
                return ev.decision
        return None


@dataclass(frozen=True)
class GateResult:
    """wait_for_decision result. timed_out distinguishes 'decision reached' from 'timed out'."""
    timed_out: bool
    state: PullRequestState
    decision: ReviewDecision


class GitHostError(RuntimeError):
    """Raised when a command expected to succeed failed, or parsing a success stdout failed. Fixed fields."""
    def __init__(self, argv, exit_code, stdout, stderr):
        self.argv, self.exit_code, self.stdout, self.stderr = argv, exit_code, stdout, stderr
        super().__init__(f"command failed (exit {exit_code}): {' '.join(argv)}\n{stderr or stdout}")

    @classmethod
    def from_result(cls, result):
        return cls(result.argv, result.exit_code, result.stdout, result.stderr)
