"""Tests for git_host.adapters.base — GitHostAdapter ABC + concrete parse_* (consensus A-E)."""
import json

import pytest

from axdt.git_host.adapters.base import GitHostAdapter
from axdt.git_host.state import PullRequestState, ReviewDecision, MergeMethod
from axdt.git_host.models import (
    CommandResult,
    PullRequest,
    ReviewEvent,
    ReviewSnapshot,
    GitHostError,
)


class _StubAdapter(GitHostAdapter):
    name = "stub"
    cli = "stub"
    _STATE_MAP = {"OPEN": PullRequestState.OPEN, "MERGED": PullRequestState.MERGED,
                  "CLOSED": PullRequestState.CLOSED}
    _REVIEW_STATE_MAP = {"APPROVED": ReviewDecision.APPROVED,
                         "CHANGES_REQUESTED": ReviewDecision.CHANGES_REQUESTED,
                         "COMMENTED": ReviewDecision.COMMENTED}

    def build_create_pr_command(self, head, base, title, body):
        return ["stub", "create"]

    def build_get_pr_command(self, ref):
        return ["stub", "get", str(ref)]

    def build_request_review_command(self, number, reviewer):
        return ["stub", "review", str(number), reviewer]

    def build_merge_command(self, number, method):
        return ["stub", "merge", str(number), method.value]


def _json_result(payload):
    return CommandResult(json.dumps(payload), "", 0, ["stub", "get"])


# --- Abstract base ---------------------------------------------------------

def test_githostadapter_cannot_be_instantiated_directly():
    """GitHostAdapter is abstract (4 abstract build_* methods)."""
    with pytest.raises(TypeError):
        GitHostAdapter()


def test_subclass_missing_a_build_method_still_abstract():
    """A subclass that fails to implement all 4 build_* methods remains abstract."""

    class _IncompleteAdapter(GitHostAdapter):
        name = "incomplete"
        cli = "incomplete"

        def build_create_pr_command(self, head, base, title, body):
            return []

        def build_get_pr_command(self, ref):
            return []

        def build_request_review_command(self, number, reviewer):
            return []

        # build_merge_command intentionally omitted

    with pytest.raises(TypeError):
        _IncompleteAdapter()


# --- parse_create_ref --------------------------------------------------------

def test_parse_create_ref_returns_stripped_stdout():
    adapter = _StubAdapter()
    result = CommandResult("https://github.com/o/r/pull/7\n", "", 0, ["stub", "create"])
    assert adapter.parse_create_ref(result) == "https://github.com/o/r/pull/7"


def test_parse_create_ref_returns_last_non_empty_line():
    adapter = _StubAdapter()
    result = CommandResult("https://github.com/o/r/pull/7\n\n   \n", "", 0, ["stub", "create"])
    assert adapter.parse_create_ref(result) == "https://github.com/o/r/pull/7"


def test_parse_create_ref_empty_stdout_raises_githosterror():
    adapter = _StubAdapter()
    result = CommandResult("   \n\n", "", 0, ["stub", "create"])
    with pytest.raises(GitHostError):
        adapter.parse_create_ref(result)


# --- parse_pr ----------------------------------------------------------------

def test_parse_pr_valid_json_returns_pullrequest_with_head_base_preserved():
    adapter = _StubAdapter()
    result = _json_result({"number": 7, "url": "u"})
    pr = adapter.parse_pr(result, head="feature", base="main")
    assert pr == PullRequest(number=7, url="u", head="feature", base="main")


def test_parse_pr_missing_number_raises_githosterror():
    adapter = _StubAdapter()
    result = _json_result({"url": "u"})
    with pytest.raises(GitHostError):
        adapter.parse_pr(result, head="feature", base="main")


def test_parse_pr_non_int_number_raises_githosterror():
    adapter = _StubAdapter()
    result = _json_result({"number": "abc", "url": "u"})
    with pytest.raises(GitHostError):
        adapter.parse_pr(result, head="feature", base="main")


def test_parse_pr_non_dict_json_raises_githosterror():
    adapter = _StubAdapter()
    result = CommandResult("[]", "", 0, ["stub", "get"])
    with pytest.raises(GitHostError):
        adapter.parse_pr(result, head="feature", base="main")


# --- parse_pr_state -----------------------------------------------------------

def test_parse_pr_state_open():
    adapter = _StubAdapter()
    assert adapter.parse_pr_state(_json_result({"state": "OPEN"})) == PullRequestState.OPEN


def test_parse_pr_state_merged():
    adapter = _StubAdapter()
    assert adapter.parse_pr_state(_json_result({"state": "MERGED"})) == PullRequestState.MERGED


def test_parse_pr_state_unmapped_returns_unknown():
    adapter = _StubAdapter()
    assert adapter.parse_pr_state(_json_result({"state": "DRAFT"})) == PullRequestState.UNKNOWN


def test_parse_pr_state_missing_field_returns_unknown():
    adapter = _StubAdapter()
    assert adapter.parse_pr_state(_json_result({})) == PullRequestState.UNKNOWN


# --- parse_review: ordered events for target reviewer -------------------------

def test_parse_review_ordered_events_for_target_reviewer():
    adapter = _StubAdapter()
    payload = {
        "reviews": [
            {"author": {"login": "alice"}, "id": "r1", "state": "COMMENTED"},
            {"author": {"login": "alice"}, "id": "r2", "state": "CHANGES_REQUESTED"},
            {"author": {"login": "alice"}, "id": "r3", "state": "APPROVED"},
        ],
        "reviewRequests": [],
    }
    snap = adapter.parse_review(_json_result(payload), reviewer="alice")
    assert snap.events == (
        ReviewEvent("r1", ReviewDecision.COMMENTED),
        ReviewEvent("r2", ReviewDecision.CHANGES_REQUESTED),
        ReviewEvent("r3", ReviewDecision.APPROVED),
    )


def test_parse_review_other_reviewers_excluded():
    adapter = _StubAdapter()
    payload = {
        "reviews": [
            {"author": {"login": "alice"}, "id": "r1", "state": "APPROVED"},
            {"author": {"login": "bob"}, "id": "rb", "state": "APPROVED"},
        ],
        "reviewRequests": [],
    }
    snap = adapter.parse_review(_json_result(payload), reviewer="alice")
    ids = [ev.review_id for ev in snap.events]
    assert "rb" not in ids
    assert ids == ["r1"]


def test_parse_review_awaiting_true_when_reviewer_requested():
    adapter = _StubAdapter()
    payload = {"reviews": [], "reviewRequests": [{"login": "alice"}]}
    snap = adapter.parse_review(_json_result(payload), reviewer="alice")
    assert snap.awaiting is True


def test_parse_review_awaiting_false_when_other_reviewer_requested():
    adapter = _StubAdapter()
    payload = {"reviews": [], "reviewRequests": [{"login": "bob"}]}
    snap = adapter.parse_review(_json_result(payload), reviewer="alice")
    assert snap.awaiting is False


def test_parse_review_login_less_team_item_skipped_not_error():
    adapter = _StubAdapter()
    payload = {"reviews": [], "reviewRequests": [{"name": "my-team"}, {"login": "alice"}]}
    snap = adapter.parse_review(_json_result(payload), reviewer="alice")
    assert snap.awaiting is True


def test_parse_review_no_reviews_for_reviewer_returns_empty_events():
    adapter = _StubAdapter()
    payload = {
        "reviews": [{"author": {"login": "bob"}, "id": "rb", "state": "APPROVED"}],
        "reviewRequests": [],
    }
    snap = adapter.parse_review(_json_result(payload), reviewer="alice")
    assert snap.events == ()


def test_parse_review_empty_reviews_list_returns_empty_events():
    adapter = _StubAdapter()
    payload = {"reviews": [], "reviewRequests": []}
    snap = adapter.parse_review(_json_result(payload), reviewer="alice")
    assert snap.events == ()


def test_parse_review_unmapped_state_becomes_commented_not_dropped():
    adapter = _StubAdapter()
    payload = {
        "reviews": [{"author": {"login": "alice"}, "id": "r9", "state": "DISMISSED"}],
        "reviewRequests": [],
    }
    snap = adapter.parse_review(_json_result(payload), reviewer="alice")
    assert snap.events == (ReviewEvent("r9", ReviewDecision.COMMENTED),)


def test_parse_review_non_json_stdout_raises_githosterror():
    adapter = _StubAdapter()
    result = CommandResult("not json", "", 0, ["stub", "get"])
    with pytest.raises(GitHostError):
        adapter.parse_review(result, reviewer="alice")


def test_parse_review_reviews_not_a_list_raises_githosterror():
    adapter = _StubAdapter()
    result = _json_result({"reviews": 5})
    with pytest.raises(GitHostError):
        adapter.parse_review(result, reviewer="alice")


def test_parse_review_review_requests_not_a_list_raises_githosterror():
    adapter = _StubAdapter()
    result = _json_result({"reviews": [], "reviewRequests": 5})
    with pytest.raises(GitHostError):
        adapter.parse_review(result, reviewer="alice")


def test_parse_review_review_item_not_an_object_raises_githosterror():
    adapter = _StubAdapter()
    result = _json_result({"reviews": ["not-an-object"], "reviewRequests": []})
    with pytest.raises(GitHostError):
        adapter.parse_review(result, reviewer="alice")


def test_parse_review_matched_review_missing_id_raises_githosterror():
    adapter = _StubAdapter()
    payload = {
        "reviews": [{"author": {"login": "alice"}, "state": "APPROVED"}],
        "reviewRequests": [],
    }
    with pytest.raises(GitHostError):
        adapter.parse_review(_json_result(payload), reviewer="alice")
