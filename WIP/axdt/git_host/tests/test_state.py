from axdt.git_host.state import PullRequestState, ReviewDecision, MergeMethod, TERMINAL_DECISIONS


def test_pullrequeststate_names():
    """PullRequestState name set is exactly {"OPEN","MERGED","CLOSED","UNKNOWN"}."""
    names = {member.name for member in PullRequestState}
    assert names == {"OPEN", "MERGED", "CLOSED", "UNKNOWN"}


def test_reviewdecision_names():
    """ReviewDecision name set is exactly {"PENDING","APPROVED","CHANGES_REQUESTED","COMMENTED"}."""
    names = {member.name for member in ReviewDecision}
    assert names == {"PENDING", "APPROVED", "CHANGES_REQUESTED", "COMMENTED"}


def test_mergemethod_names():
    """MergeMethod name set is exactly {"MERGE","SQUASH","REBASE"}."""
    names = {member.name for member in MergeMethod}
    assert names == {"MERGE", "SQUASH", "REBASE"}


def test_pullrequeststate_values_are_lowercase_names():
    """For every member of PullRequestState, member.value == member.name.lower()."""
    for member in PullRequestState:
        assert member.value == member.name.lower()


def test_reviewdecision_values_are_lowercase_names():
    """For every member of ReviewDecision, member.value == member.name.lower()."""
    for member in ReviewDecision:
        assert member.value == member.name.lower()


def test_mergemethod_values_are_lowercase_names():
    """For every member of MergeMethod, member.value == member.name.lower()."""
    for member in MergeMethod:
        assert member.value == member.name.lower()


def test_terminal_decisions():
    """TERMINAL_DECISIONS contains APPROVED and CHANGES_REQUESTED, excludes COMMENTED and PENDING."""
    assert TERMINAL_DECISIONS == frozenset({ReviewDecision.APPROVED, ReviewDecision.CHANGES_REQUESTED})
    assert ReviewDecision.APPROVED in TERMINAL_DECISIONS
    assert ReviewDecision.CHANGES_REQUESTED in TERMINAL_DECISIONS
    assert ReviewDecision.COMMENTED not in TERMINAL_DECISIONS
    assert ReviewDecision.PENDING not in TERMINAL_DECISIONS
