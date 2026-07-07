"""Tests for git_host.models — dataclasses and ReviewSnapshot cursor logic."""
import dataclasses
import pytest

from axdt.git_host.models import (
    PullRequest,
    CommandResult,
    ReviewEvent,
    ReviewSnapshot,
    GateResult,
    GitHostError,
)
from axdt.git_host.state import ReviewDecision, PullRequestState


class TestFrozenDataclasses:
    """Verify all dataclasses are frozen (immutable)."""

    def test_pullrequest_frozen(self):
        pr = PullRequest(number=1, url="http://example.com", head="main", base="develop")
        with pytest.raises(dataclasses.FrozenInstanceError):
            pr.number = 2

    def test_commandresult_frozen(self):
        cmd = CommandResult(stdout="out", stderr="err", exit_code=0, argv=["gh"])
        with pytest.raises(dataclasses.FrozenInstanceError):
            cmd.exit_code = 1

    def test_reviewevent_frozen(self):
        rev = ReviewEvent(review_id="r1", decision=ReviewDecision.APPROVED)
        with pytest.raises(dataclasses.FrozenInstanceError):
            rev.review_id = "r2"

    def test_reviewsnapshot_frozen(self):
        snap = ReviewSnapshot(events=(), awaiting=False)
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.awaiting = True

    def test_gateresult_frozen(self):
        gate = GateResult(timed_out=False, state=PullRequestState.OPEN, decision=ReviewDecision.APPROVED)
        with pytest.raises(dataclasses.FrozenInstanceError):
            gate.timed_out = True


class TestCommandResultArgv:
    """CommandResult.argv field is preserved."""

    def test_argv_preserved(self):
        argv = ["gh", "pr", "view"]
        cmd = CommandResult(stdout="out", stderr="err", exit_code=0, argv=argv)
        assert cmd.argv == ["gh", "pr", "view"]


class TestGitHostError:
    """GitHostError initialization and fields."""

    def test_githosterror_fields(self):
        e = GitHostError(["gh", "x"], 2, "out", "err")
        assert e.argv == ["gh", "x"]
        assert e.exit_code == 2
        assert e.stdout == "out"
        assert e.stderr == "err"

    def test_githosterror_message(self):
        e = GitHostError(["gh", "x"], 2, "out", "err")
        msg = str(e)
        assert "exit 2" in msg
        assert "gh x" in msg

    def test_githosterror_from_result(self):
        result = CommandResult(stdout="o", stderr="e", exit_code=3, argv=["a", "b"])
        e = GitHostError.from_result(result)
        assert e.argv == ["a", "b"]
        assert e.exit_code == 3
        assert e.stdout == "o"
        assert e.stderr == "e"


class TestLatestReviewId:
    """ReviewSnapshot.latest_review_id property."""

    def test_latest_review_id_empty(self):
        snap = ReviewSnapshot(events=(), awaiting=False)
        assert snap.latest_review_id is None

    def test_latest_review_id_single(self):
        ev = ReviewEvent("r1", ReviewDecision.APPROVED)
        snap = ReviewSnapshot(events=(ev,), awaiting=False)
        assert snap.latest_review_id == "r1"

    def test_latest_review_id_multiple(self):
        ev1 = ReviewEvent("r1", ReviewDecision.COMMENTED)
        ev2 = ReviewEvent("r2", ReviewDecision.APPROVED)
        ev3 = ReviewEvent("r3", ReviewDecision.CHANGES_REQUESTED)
        snap = ReviewSnapshot(events=(ev1, ev2, ev3), awaiting=False)
        assert snap.latest_review_id == "r3"


class TestTerminalAfter:
    """ReviewSnapshot.terminal_after cursor logic (consensus D, §2.8)."""

    def test_terminal_after_cursor_none_first_terminal(self):
        # cursor=None -> scan all events for the first terminal decision
        c = ReviewEvent("rc", ReviewDecision.COMMENTED)
        x = ReviewEvent("rx", ReviewDecision.CHANGES_REQUESTED)
        a = ReviewEvent("ra", ReviewDecision.APPROVED)
        snap = ReviewSnapshot((c, x, a), False)
        assert snap.terminal_after(None) == ReviewDecision.CHANGES_REQUESTED

    def test_terminal_after_only_after_cursor(self):
        # Only terminal AFTER cursor position returned
        c = ReviewEvent("rc", ReviewDecision.COMMENTED)
        x = ReviewEvent("rx", ReviewDecision.CHANGES_REQUESTED)
        a = ReviewEvent("ra", ReviewDecision.APPROVED)
        snap = ReviewSnapshot((c, x, a), False)
        assert snap.terminal_after("rx") == ReviewDecision.APPROVED

    def test_terminal_after_before_cursor_ignored(self):
        # Terminal BEFORE cursor position ignored -> None
        x = ReviewEvent("rx", ReviewDecision.CHANGES_REQUESTED)
        c = ReviewEvent("rc", ReviewDecision.COMMENTED)
        snap = ReviewSnapshot((x, c), False)
        assert snap.terminal_after("rc") is None

    def test_terminal_after_nonterminal_after_cursor(self):
        # COMMENTED after cursor is non-terminal -> None
        x = ReviewEvent("rx", ReviewDecision.CHANGES_REQUESTED)
        c = ReviewEvent("rc", ReviewDecision.COMMENTED)
        snap = ReviewSnapshot((x, c), False)
        assert snap.terminal_after("rx") is None

    def test_terminal_after_cursor_not_found(self):
        # cursor_id not in events -> None
        x = ReviewEvent("rx", ReviewDecision.CHANGES_REQUESTED)
        a = ReviewEvent("ra", ReviewDecision.APPROVED)
        snap = ReviewSnapshot((x, a), False)
        assert snap.terminal_after("nope") is None
