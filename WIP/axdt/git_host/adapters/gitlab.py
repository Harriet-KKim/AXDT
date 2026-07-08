from axdt.git_host.state import PullRequestState, MergeMethod
from axdt.git_host.adapters.base import GitHostAdapter


class GitLabAdapter(GitHostAdapter):
    """GitLab adapter — PROVISIONAL. argv follow spec §4; exact flags, JSON field names, and
    value maps are unverified against a live GitLab until Phase 9 (see HOST_MATRIX.md)."""

    name = "gitlab"
    cli = "glab"

    # PROVISIONAL: GitLab MR state values are lowercase.
    _STATE_MAP = {
        "opened": PullRequestState.OPEN,
        "merged": PullRequestState.MERGED,
        "closed": PullRequestState.CLOSED,
    }
    # PROVISIONAL JSON field overrides (glab mr view -F json): number=iid, url=web_url.
    _NUMBER_FIELD = "iid"
    _URL_FIELD = "web_url"
    # PROVISIONAL: GitLab uses an approvals model, not a GitHub-style reviews stream. Left empty →
    # base maps every review state to COMMENTED (non-terminal) until the real model is verified.

    _MERGE_FLAGS = {  # PROVISIONAL
        MergeMethod.MERGE: "--merge",
        MergeMethod.SQUASH: "--squash",
        MergeMethod.REBASE: "--rebase",
    }

    def build_create_pr_command(self, head, base, title, body):
        return [self.cli, "mr", "create",
                "--source-branch", head, "--target-branch", base,
                "--title", title, "--description", body]

    def build_get_pr_command(self, ref):
        # PROVISIONAL: glab mr view does not accept a URL → a number must be parsed from a URL upstream.
        return [self.cli, "mr", "view", str(ref), "-F", "json"]

    def build_request_review_command(self, number, reviewer):
        # PROVISIONAL: `+R` ADDS a reviewer; a bare `R` REPLACES. Use `+` for request-review semantics.
        return [self.cli, "mr", "update", str(number), "--reviewer", f"+{reviewer}"]

    def build_merge_command(self, number, method):
        return [self.cli, "mr", "merge", str(number), self._MERGE_FLAGS[method]]
