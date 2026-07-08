from axdt.git_host.state import MergeMethod
from axdt.git_host.adapters.base import GitHostAdapter


class ForgejoAdapter(GitHostAdapter):
    """Forgejo adapter — PROVISIONAL. argv follow spec §4 (tea CLI); exact flags, JSON field names,
    and value maps are unverified against a live Forgejo until Phase 9 (see HOST_MATRIX.md)."""

    name = "forgejo"
    cli = "tea"

    _STATE_MAP = {}   # PROVISIONAL: Forgejo PR state values unverified → base maps to UNKNOWN.

    _MERGE_FLAGS = {  # PROVISIONAL
        MergeMethod.MERGE: "--style=merge",
        MergeMethod.SQUASH: "--style=squash",
        MergeMethod.REBASE: "--style=rebase",
    }

    def build_create_pr_command(self, head, base, title, body):
        return [self.cli, "pulls", "create",
                "--head", head, "--base", base,
                "--title", title, "--description", body]

    def build_get_pr_command(self, ref):
        return [self.cli, "pulls", str(ref), "--output", "json"]

    def build_request_review_command(self, number, reviewer):
        return [self.cli, "pulls", "edit", str(number), "--add-reviewers", reviewer]

    def build_merge_command(self, number, method):
        return [self.cli, "pulls", "merge", str(number), self._MERGE_FLAGS[method]]
