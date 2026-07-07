from axdt.git_host.state import PullRequestState, ReviewDecision, MergeMethod
from axdt.git_host.adapters.base import GitHostAdapter


class GitHubAdapter(GitHostAdapter):
    """GitHub adapter (D5). Feature-complete against the installed `gh` CLI.
    parse_* are inherited from GitHostAdapter; this class supplies data + argv builders."""

    name = "github"
    cli = "gh"

    _STATE_MAP = {
        "OPEN": PullRequestState.OPEN,
        "MERGED": PullRequestState.MERGED,
        "CLOSED": PullRequestState.CLOSED,
    }
    _REVIEW_STATE_MAP = {
        "APPROVED": ReviewDecision.APPROVED,
        "CHANGES_REQUESTED": ReviewDecision.CHANGES_REQUESTED,
        "COMMENTED": ReviewDecision.COMMENTED,
    }
    # gh review states DISMISSED / PENDING are intentionally absent → base maps them to
    # COMMENTED (non-terminal), so they never falsely resume the gate.

    _JSON_FIELDS = "number,url,state,reviews,reviewRequests"

    _MERGE_FLAGS = {
        MergeMethod.MERGE: "--merge",
        MergeMethod.SQUASH: "--squash",
        MergeMethod.REBASE: "--rebase",
    }

    def build_create_pr_command(self, head, base, title, body):
        # gh pr create emits the PR URL on stdout (no --json); reviewers are NOT added here (§2.6).
        return [self.cli, "pr", "create",
                "--head", head, "--base", base,
                "--title", title, "--body", body]

    def build_get_pr_command(self, ref):
        # ref may be a number, URL, or branch — gh pr view accepts all three.
        return [self.cli, "pr", "view", str(ref), "--json", self._JSON_FIELDS]

    def build_request_review_command(self, number, reviewer):
        # Single reviewer; re-call = re-request (not a decision reset, §2.8).
        # NOTE: adding a *team* reviewer needs read:org scope — HOST_MATRIX; single-user is fine.
        return [self.cli, "pr", "edit", str(number), "--add-reviewer", reviewer]

    def build_merge_command(self, number, method):
        return [self.cli, "pr", "merge", str(number), self._MERGE_FLAGS[method]]
