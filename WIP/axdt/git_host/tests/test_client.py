"""Tests for git_host.client — GitHostClient lifecycle + wait_for_decision cursor loop (§6 test_client a-h)."""
import json

import pytest

from axdt.git_host.client import GitHostClient
from axdt.git_host.state import PullRequestState, ReviewDecision, MergeMethod
from axdt.git_host.models import (
    PullRequest,
    ReviewEvent,
    GateResult,
    GitHostError,
    CommandResult,
)
from axdt.git_host.adapters.github import GitHubAdapter
from axdt.git_host.backend import FakeCommandBackend


REVIEWER = "alice"
PR = PullRequest(7, "https://github.com/o/r/pull/7", "feature", "main")


def _view(payload, exit_code=0):
    return CommandResult(json.dumps(payload), "", exit_code, [])


def _err(stderr="boom", exit_code=1):
    return CommandResult("", stderr, exit_code, [])


def _review_item(review_id, state, login=REVIEWER):
    return {"author": {"login": login}, "id": review_id, "state": state}


def _client(fake):
    return GitHostClient(GitHubAdapter(), fake)


# --- open_pull_request: create -> view composition (2 calls) -----------------

def test_open_pull_request_is_create_then_view_two_calls():
    fake = FakeCommandBackend(results=[
        CommandResult("https://github.com/o/r/pull/7", "", 0, []),
        _view({"number": 7, "url": "https://github.com/o/r/pull/7", "state": "OPEN",
               "reviews": [], "reviewRequests": []}),
    ])
    client = _client(fake)

    pr = client.open_pull_request("feature", "main", "T", "B")

    assert pr.number == 7
    assert pr.url == "https://github.com/o/r/pull/7"
    assert pr.head == "feature"
    assert pr.base == "main"
    assert len(fake.calls) == 2
    assert fake.calls[0][0] == GitHubAdapter().build_create_pr_command("feature", "main", "T", "B")
    assert fake.calls[1][0] == GitHubAdapter().build_get_pr_command("https://github.com/o/r/pull/7")


# --- request_review: single call; failure -> GitHostError --------------------

def test_request_review_records_single_call():
    fake = FakeCommandBackend(results=[CommandResult("", "", 0, [])])
    client = _client(fake)

    client.request_review(PR, REVIEWER)

    assert len(fake.calls) == 1
    assert fake.calls[0][0] == GitHubAdapter().build_request_review_command(7, REVIEWER)


def test_request_review_nonzero_exit_raises_githosterror():
    fake = FakeCommandBackend(results=[_err()])
    client = _client(fake)

    with pytest.raises(GitHostError) as exc_info:
        client.request_review(PR, REVIEWER)
    assert type(exc_info.value) is GitHostError


# --- poll_state / poll_review mapping -----------------------------------------

def test_poll_state_maps_merged():
    fake = FakeCommandBackend(results=[_view({"state": "MERGED"})])
    client = _client(fake)

    assert client.poll_state(PR) == PullRequestState.MERGED


def test_poll_review_returns_target_reviewer_events():
    fake = FakeCommandBackend(results=[
        _view({"reviews": [_review_item("r1", "APPROVED")], "reviewRequests": []}),
    ])
    client = _client(fake)

    snap = client.poll_review(PR, REVIEWER)

    assert ReviewEvent("r1", ReviewDecision.APPROVED) in snap.events


# --- wait_for_decision: (a) cursor=None -> new APPROVED -----------------------

def test_wait_for_decision_a_cursor_none_new_approved():
    fake = FakeCommandBackend(results=[
        _view({"reviews": []}),                                       # cursor poll_review, cursor=None
        _view({"state": "OPEN"}),                                     # loop poll_state
        _view({"reviews": [_review_item("r1", "APPROVED")]}),         # loop poll_review
    ])
    client = _client(fake)

    result = client.wait_for_decision(PR, REVIEWER, timeout=1000, poll_interval=0)

    assert result == GateResult(False, PullRequestState.OPEN, ReviewDecision.APPROVED)


# --- (b) terminal strictly AFTER cursor wins over a prior terminal ------------

def test_wait_for_decision_b_terminal_after_cursor_changes_requested():
    fake = FakeCommandBackend(results=[
        _view({"reviews": [_review_item("ra", "APPROVED")]}),         # cursor="ra"
        _view({"state": "OPEN"}),
        _view({"reviews": [
            _review_item("ra", "APPROVED"),
            _review_item("rx", "CHANGES_REQUESTED"),
        ]}),
    ])
    client = _client(fake)

    result = client.wait_for_decision(PR, REVIEWER, timeout=1000, poll_interval=0)

    assert result == GateResult(False, PullRequestState.OPEN, ReviewDecision.CHANGES_REQUESTED)


# --- (c) PR reaches a CLOSED_STATES member -> return with PENDING decision ---

def test_wait_for_decision_c_merged_returns_pending_decision():
    fake = FakeCommandBackend(results=[
        _view({"reviews": []}),
        _view({"state": "MERGED"}),
        _view({"reviews": []}),
    ])
    client = _client(fake)

    result = client.wait_for_decision(PR, REVIEWER, timeout=1000, poll_interval=0)

    assert result == GateResult(False, PullRequestState.MERGED, ReviewDecision.PENDING)


def test_wait_for_decision_c_closed_returns_pending_decision():
    fake = FakeCommandBackend(results=[
        _view({"reviews": []}),
        _view({"state": "CLOSED"}),
        _view({"reviews": []}),
    ])
    client = _client(fake)

    result = client.wait_for_decision(PR, REVIEWER, timeout=1000, poll_interval=0)

    assert result == GateResult(False, PullRequestState.CLOSED, ReviewDecision.PENDING)


# --- (d) stale regression: terminal AT (not after) cursor must not return ----

def test_wait_for_decision_d_stale_terminal_at_cursor_does_not_return():
    """The cursor itself was already a terminal CHANGES_REQUESTED; steady state repeats it forever.
    That pre-existing terminal must NOT be reported as a fresh decision — expect a timeout instead."""
    fake = FakeCommandBackend(
        results=[_view({"reviews": [_review_item("rx", "CHANGES_REQUESTED")]})],  # cursor="rx"
        default=_view({"state": "OPEN",
                       "reviews": [_review_item("rx", "CHANGES_REQUESTED")],
                       "reviewRequests": []}),
    )
    client = _client(fake)

    result = client.wait_for_decision(PR, REVIEWER, timeout=0, poll_interval=0)

    assert result.timed_out is True
    assert result.decision == ReviewDecision.PENDING


# --- (e) recurrence: a later terminal at a new stream position IS caught -----

def test_wait_for_decision_e_recurrence_after_cursor_is_terminal():
    fake = FakeCommandBackend(results=[
        _view({"reviews": [_review_item("rx", "CHANGES_REQUESTED")]}),  # cursor="rx"
        _view({"state": "OPEN"}),
        _view({"reviews": [
            _review_item("rx", "CHANGES_REQUESTED"),
            _review_item("ry", "CHANGES_REQUESTED"),
        ]}),
    ])
    client = _client(fake)

    result = client.wait_for_decision(PR, REVIEWER, timeout=1000, poll_interval=0)

    assert result.timed_out is False
    assert result.decision == ReviewDecision.CHANGES_REQUESTED


# --- (f) COMMENTED is non-terminal -> keep waiting until timeout -------------

def test_wait_for_decision_f_later_commented_is_non_terminal():
    fake = FakeCommandBackend(
        results=[_view({"reviews": []})],                              # cursor=None
        default=_view({"state": "OPEN",
                       "reviews": [_review_item("rc", "COMMENTED")],
                       "reviewRequests": []}),
    )
    client = _client(fake)

    result = client.wait_for_decision(PR, REVIEWER, timeout=0, poll_interval=0)

    assert result.timed_out is True
    assert result.decision == ReviewDecision.PENDING


# --- (g) timeout is distinct from a reached decision --------------------------

def test_wait_for_decision_g_timeout_with_no_decision():
    fake = FakeCommandBackend(
        default=_view({"state": "OPEN", "reviews": [], "reviewRequests": []}),
    )
    client = _client(fake)

    result = client.wait_for_decision(PR, REVIEWER, timeout=0, poll_interval=0)

    assert result.timed_out is True


# --- (h) transient GitHostError tolerated within limit, propagated beyond ----

def test_wait_for_decision_h_transient_errors_tolerated_within_limit():
    approved_view = _view({"state": "OPEN",
                           "reviews": [_review_item("r1", "APPROVED")],
                           "reviewRequests": []})
    fake = FakeCommandBackend(
        results=[
            _view({"reviews": []}),  # cursor poll_review, cursor=None
            _err(),                   # iteration 1 poll_state -> GitHostError, tolerated (1)
            _err(),                   # iteration 2 poll_state -> GitHostError, tolerated (2)
            approved_view,             # iteration 3 poll_state -> succeeds, state=OPEN
        ],
        default=approved_view,         # iteration 3 poll_review (script exhausted) -> APPROVED
    )
    client = _client(fake)

    result = client.wait_for_decision(
        PR, REVIEWER, timeout=1000, poll_interval=0, max_consecutive_errors=3)

    assert result.timed_out is False
    assert result.decision == ReviewDecision.APPROVED


def test_wait_for_decision_h_transient_errors_propagated_beyond_limit():
    fake = FakeCommandBackend(
        results=[_view({"reviews": []})],  # cursor poll_review, cursor=None
        default=_err(),                      # every subsequent poll_state fails
    )
    client = _client(fake)

    with pytest.raises(GitHostError) as exc_info:
        client.wait_for_decision(
            PR, REVIEWER, timeout=1000, poll_interval=0, max_consecutive_errors=2)
    assert type(exc_info.value) is GitHostError


# --- (i) I-B: entry cursor capture is tolerant like the poll loop -------------

def test_wait_for_decision_i_entry_cursor_transient_errors_tolerated_then_progresses():
    """The entry cursor read (poll_review before the poll loop) must tolerate the same
    transient-error budget as the loop itself (I-B): 1-2 failed attempts within
    max_consecutive_errors, then a successful cursor read, then the existing loop
    proceeds normally to a terminal decision."""
    approved_view = _view({"state": "OPEN",
                           "reviews": [_review_item("r1", "APPROVED")],
                           "reviewRequests": []})
    fake = FakeCommandBackend(results=[
        _err(),                    # entry poll_review attempt 1 -> GitHostError, tolerated (1)
        _err(),                    # entry poll_review attempt 2 -> GitHostError, tolerated (2)
        _view({"reviews": []}),    # entry poll_review attempt 3 -> succeeds, cursor=None
        _view({"state": "OPEN"}),  # loop poll_state
        approved_view,              # loop poll_review -> APPROVED
    ])
    client = _client(fake)

    result = client.wait_for_decision(
        PR, REVIEWER, timeout=1000, poll_interval=0, max_consecutive_errors=3)

    assert result.timed_out is False
    assert result.decision == ReviewDecision.APPROVED


def test_wait_for_decision_i_entry_cursor_errors_propagated_beyond_limit():
    fake = FakeCommandBackend(default=_err())  # every entry poll_review call fails

    client = _client(fake)

    with pytest.raises(GitHostError) as exc_info:
        client.wait_for_decision(
            PR, REVIEWER, timeout=1000, poll_interval=0, max_consecutive_errors=2)
    assert type(exc_info.value) is GitHostError


# --- merge: single call; failure -> GitHostError; argv per method ------------

def test_merge_records_single_call():
    fake = FakeCommandBackend(results=[CommandResult("", "", 0, [])])
    client = _client(fake)

    client.merge(PR, MergeMethod.SQUASH)

    assert len(fake.calls) == 1
    assert fake.calls[0][0] == GitHubAdapter().build_merge_command(7, MergeMethod.SQUASH)


def test_merge_nonzero_exit_raises_githosterror():
    fake = FakeCommandBackend(results=[_err()])
    client = _client(fake)

    with pytest.raises(GitHostError) as exc_info:
        client.merge(PR, MergeMethod.SQUASH)
    assert type(exc_info.value) is GitHostError


def test_merge_argv_squash():
    fake = FakeCommandBackend(results=[CommandResult("", "", 0, [])])
    client = _client(fake)

    client.merge(PR, MergeMethod.SQUASH)

    assert fake.calls[0][0] == GitHubAdapter().build_merge_command(7, MergeMethod.SQUASH)


def test_merge_argv_merge():
    fake = FakeCommandBackend(results=[CommandResult("", "", 0, [])])
    client = _client(fake)

    client.merge(PR, MergeMethod.MERGE)

    assert fake.calls[0][0] == GitHubAdapter().build_merge_command(7, MergeMethod.MERGE)


def test_merge_argv_rebase():
    fake = FakeCommandBackend(results=[CommandResult("", "", 0, [])])
    client = _client(fake)

    client.merge(PR, MergeMethod.REBASE)

    assert fake.calls[0][0] == GitHubAdapter().build_merge_command(7, MergeMethod.REBASE)
