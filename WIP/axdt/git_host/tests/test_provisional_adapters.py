"""Smoke tests for the provisional GitLab/Forgejo adapters.

These adapters are PROVISIONAL (structure only; exact argv/JSON/maps unverified
until a live host in Phase 9 — see HOST_MATRIX.md). This file asserts only
construction, identity, and that the builders return non-empty argv lists
starting with the adapter's cli. It does NOT assert full argv equality —
doing so would falsely signal "verified" for details that are not.
"""
from axdt.git_host.state import MergeMethod
from axdt.git_host.adapters.gitlab import GitLabAdapter
from axdt.git_host.adapters.forgejo import ForgejoAdapter


def test_gitlab_adapter_identity():
    a = GitLabAdapter()
    assert a.name == "gitlab"
    assert a.cli == "glab"


def test_forgejo_adapter_identity():
    a = ForgejoAdapter()
    assert a.name == "forgejo"
    assert a.cli == "tea"


def test_provisional_adapters_build_nonempty_argv_starting_with_cli():
    for adapter in (GitLabAdapter(), ForgejoAdapter()):
        create = adapter.build_create_pr_command("head", "base", "title", "body")
        assert isinstance(create, list) and create[0] == adapter.cli
        assert adapter.build_get_pr_command(1)[0] == adapter.cli
        assert adapter.build_request_review_command(1, "alice")[0] == adapter.cli
        for method in MergeMethod:
            assert adapter.build_merge_command(1, method)[0] == adapter.cli
