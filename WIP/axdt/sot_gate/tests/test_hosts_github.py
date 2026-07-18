"""Tests for sot_gate.hosts.github — GitHubGatePorts(§8 라이브 구현, 결정적 FakeCommandBackend).

gh api 호출 하나하나를 FakeCommandBackend로 스크립트해 계약을 고정한다(실네트워크 없음).
compute_landing_keys/read_ci_artifacts는 이 파일의 범위 밖(NotImplementedError 유지 확인만).
"""
import base64
import json

import pytest

from axdt.git_host.backend import FakeCommandBackend
from axdt.git_host.models import PullRequest, CommandResult, GitHostError
from axdt.git_host.state import PullRequestState

from axdt.sot_gate.keys import JudgmentKey, CompletenessSweepKey, FullBindingKey
from axdt.sot_gate.models import FindingDecision
from axdt.sot_gate.ports import HeadMovedError

from axdt.sot_gate.hosts.github import (
    GitHubGatePorts,
    CriticalPathsBlockError,
    _glob_matches,
)


TARGET_REPO = "org/repo"
PR = PullRequest(number=42, url="https://github.com/org/repo/pull/42", head="sot/x", base="main")

JUDGMENT = JudgmentKey(tree_hash="t1", rule_fingerprint="r1",
                       review_policy_epoch="e1", rule_catalog_manifest_digest="c1")
SWEEP = CompletenessSweepKey(projection_tree_hash="t1", active_catalog_input_digest="ci1",
                             review_policy_epoch="e1")

VALID_CRITICAL_MD = """# protected paths

```axdt-critical-paths
# comment line, ignored
critical docs/sot/**
critical .github/CODEOWNERS
critical WIP/axdt/sot_gate/**
```

more text after the block
"""

MALFORMED_CRITICAL_MD_NO_BLOCK = "# doc\nno block here at all\n"

MALFORMED_CRITICAL_MD_ZERO_LINES = """# doc
```axdt-critical-paths
# only a comment, no critical lines
```
"""

MALFORMED_CRITICAL_MD_BAD_LINE = """# doc
```axdt-critical-paths
critical
```
"""

MALFORMED_CRITICAL_MD_DUPLICATE = """# doc
```axdt-critical-paths
critical docs/sot/**
```

```axdt-critical-paths
critical WIP/axdt/sot_gate/**
```
"""


def _obj(payload, exit_code=0):
    return CommandResult(json.dumps(payload), "", exit_code, [])


def _err(stderr="boom", exit_code=1):
    return CommandResult("", stderr, exit_code, [])


def _contents(text):
    return {"content": base64.b64encode(text.encode("utf-8")).decode("ascii"), "encoding": "base64"}


def _ports(backend):
    return GitHubGatePorts(backend, TARGET_REPO)


# ============================================================================
# constructor
# ============================================================================

class TestConstructor:
    def test_rejects_malformed_target_repo(self):
        with pytest.raises(ValueError):
            GitHubGatePorts(FakeCommandBackend(), "not-a-valid-repo-string")

    def test_accepts_owner_slash_name(self):
        ports = GitHubGatePorts(FakeCommandBackend(), "org/repo")
        assert ports is not None


# ============================================================================
# out-of-scope ports remain NotImplementedError
# ============================================================================

class TestOutOfScopePortsUntouched:
    def test_compute_landing_keys_still_not_implemented(self):
        ports = _ports(FakeCommandBackend())
        with pytest.raises(NotImplementedError):
            ports.compute_landing_keys(PR)

    def test_read_ci_artifacts_still_not_implemented(self):
        ports = _ports(FakeCommandBackend())
        with pytest.raises(NotImplementedError):
            ports.read_ci_artifacts(PR)


# ============================================================================
# glob matcher (module-level, direct)
# ============================================================================

class TestGlobMatcher:
    def test_trailing_doublestar_matches_directory_itself(self):
        assert _glob_matches("docs/sot/**", "docs/sot")

    def test_trailing_doublestar_matches_nested_path(self):
        assert _glob_matches("docs/sot/**", "docs/sot/requirements/foo.md")

    def test_trailing_doublestar_does_not_match_sibling_prefix(self):
        # a common glob-matcher bug: "docs/sot/**" must not match "docs/sotxyz/..."
        assert not _glob_matches("docs/sot/**", "docs/sotxyz/foo.md")

    def test_exact_path_no_wildcard(self):
        assert _glob_matches(".github/CODEOWNERS", ".github/CODEOWNERS")
        assert not _glob_matches(".github/CODEOWNERS", ".github/CODEOWNERS2")

    def test_star_within_segment_does_not_cross_slash(self):
        assert _glob_matches("a/*.py", "a/b.py")
        assert not _glob_matches("a/*.py", "a/b/c.py")


# ============================================================================
# read_pr_metadata
# ============================================================================

class TestReadPrMetadata:
    def _pr_payload(self, **overrides):
        payload = {
            "user": {"login": "author-1"},
            "head": {"ref": "sot/x", "sha": "sha-abc", "repo": {"full_name": TARGET_REPO}},
            "state": "open",
            "merged": False,
        }
        payload.update(overrides)
        return payload

    def _backend(self, pr_payload, files_payload, critical_md):
        return FakeCommandBackend(results=[
            _obj(pr_payload),
            _obj(files_payload),
            _obj(_contents(critical_md)),
        ])

    def test_happy_path_open_state_no_sot_no_enforcement(self):
        backend = self._backend(self._pr_payload(), [], VALID_CRITICAL_MD)
        ports = _ports(backend)

        meta = ports.read_pr_metadata(PR)

        assert meta.author == "author-1"
        assert meta.head_ref == "sot/x"
        assert meta.head_repo == TARGET_REPO
        assert meta.head_sha == "sha-abc"
        assert meta.state == PullRequestState.OPEN
        assert meta.touches_sot is False
        assert meta.touches_enforcement_surface is False

    def test_state_maps_closed_and_merged_true_to_merged(self):
        payload = self._pr_payload(state="closed", merged=True)
        backend = self._backend(payload, [], VALID_CRITICAL_MD)
        ports = _ports(backend)

        assert ports.read_pr_metadata(PR).state == PullRequestState.MERGED

    def test_state_maps_closed_and_merged_false_to_closed(self):
        payload = self._pr_payload(state="closed", merged=False)
        backend = self._backend(payload, [], VALID_CRITICAL_MD)
        ports = _ports(backend)

        assert ports.read_pr_metadata(PR).state == PullRequestState.CLOSED

    def test_state_unknown_value_maps_to_unknown(self):
        payload = self._pr_payload(state="weird")
        backend = self._backend(payload, [], VALID_CRITICAL_MD)
        ports = _ports(backend)

        assert ports.read_pr_metadata(PR).state == PullRequestState.UNKNOWN

    def test_touches_sot_true_for_requirements_change(self):
        files = [{"filename": "docs/sot/requirements/foo.md"}]
        backend = self._backend(self._pr_payload(), files, VALID_CRITICAL_MD)
        ports = _ports(backend)

        assert ports.read_pr_metadata(PR).touches_sot is True

    def test_touches_sot_false_for_readme_only(self):
        files = [{"filename": "docs/sot/requirements/README.md"},
                 {"filename": "docs/sot/specification/_TEMPLATE.md"}]
        backend = self._backend(self._pr_payload(), files, VALID_CRITICAL_MD)
        ports = _ports(backend)

        assert ports.read_pr_metadata(PR).touches_sot is False

    def test_touches_sot_false_for_unrelated_path(self):
        files = [{"filename": "src/main.py"}]
        backend = self._backend(self._pr_payload(), files, VALID_CRITICAL_MD)
        ports = _ports(backend)

        assert ports.read_pr_metadata(PR).touches_sot is False

    def test_touches_enforcement_surface_true_for_critical_glob(self):
        files = [{"filename": "WIP/axdt/sot_gate/gate.py"}]
        backend = self._backend(self._pr_payload(), files, VALID_CRITICAL_MD)
        ports = _ports(backend)

        assert ports.read_pr_metadata(PR).touches_enforcement_surface is True

    def test_touches_enforcement_surface_false_for_unrelated_path(self):
        files = [{"filename": "src/unrelated/file.py"}]
        backend = self._backend(self._pr_payload(), files, VALID_CRITICAL_MD)
        ports = _ports(backend)

        assert ports.read_pr_metadata(PR).touches_enforcement_surface is False

    def test_touches_enforcement_surface_does_not_falsely_match_sibling_prefix(self):
        files = [{"filename": "docs/sotxyz/file.md"}]
        backend = self._backend(self._pr_payload(), files, VALID_CRITICAL_MD)
        ports = _ports(backend)

        assert ports.read_pr_metadata(PR).touches_enforcement_surface is False

    def test_touches_enforcement_surface_rename_defense_old_path_matches(self):
        files = [{"filename": "src/moved.py", "previous_filename": "WIP/axdt/sot_gate/old.py"}]
        backend = self._backend(self._pr_payload(), files, VALID_CRITICAL_MD)
        ports = _ports(backend)

        assert ports.read_pr_metadata(PR).touches_enforcement_surface is True

    def test_touches_enforcement_surface_rename_defense_new_path_matches(self):
        files = [{"filename": "WIP/axdt/sot_gate/new.py", "previous_filename": "src/old.py"}]
        backend = self._backend(self._pr_payload(), files, VALID_CRITICAL_MD)
        ports = _ports(backend)

        assert ports.read_pr_metadata(PR).touches_enforcement_surface is True

    def test_missing_head_repo_raises_githosterror(self):
        payload = self._pr_payload(head={"ref": "sot/x", "sha": "s", "repo": None})
        backend = self._backend(payload, [], VALID_CRITICAL_MD)
        ports = _ports(backend)

        with pytest.raises(GitHostError):
            ports.read_pr_metadata(PR)

    @pytest.mark.parametrize("bad_md", [
        MALFORMED_CRITICAL_MD_NO_BLOCK,
        MALFORMED_CRITICAL_MD_ZERO_LINES,
        MALFORMED_CRITICAL_MD_BAD_LINE,
        MALFORMED_CRITICAL_MD_DUPLICATE,
    ])
    def test_malformed_critical_block_is_fail_closed_signal(self, bad_md):
        backend = self._backend(self._pr_payload(), [], bad_md)
        ports = _ports(backend)

        with pytest.raises(CriticalPathsBlockError):
            ports.read_pr_metadata(PR)


class TestPaginationConcatenation:
    """gh api --paginate가 배열을 페이지별로 이어붙여 내는 것을 흉내낸 stdout(단일 호출,
    두 JSON 배열이 그대로 이어붙음)이 하나의 평탄화된 리스트로 파싱되는지 확인한다."""

    def test_multi_page_array_concatenation_is_flattened(self):
        page1 = [{"id": 1, "body": "no stamp here", "user": {"login": "a"},
                 "created_at": "t", "updated_at": "t"}]
        page2 = [{"id": 2, "body": "also no stamp", "user": {"login": "b"},
                 "created_at": "t", "updated_at": "t"}]
        concatenated_stdout = json.dumps(page1) + json.dumps(page2)
        backend = FakeCommandBackend(results=[CommandResult(concatenated_stdout, "", 0, [])])
        ports = _ports(backend)

        decisions = ports.read_channel_decisions(PR)

        assert decisions == ()
        # 두 페이지 모두 소비됐음을 간접 확인: comments 목록 호출은 1회뿐이고(role/human
        # 조회는 스탬프가 없어 아예 발생하지 않는다), 예외 없이 끝까지 파싱됐다.
        assert len(backend.calls) == 1


# ============================================================================
# read_channel_decisions
# ============================================================================

class TestReadChannelDecisions:
    JUDGMENT_STAMP = (
        "```axdt-decision\n"
        "key: judgment\n"
        "tree_hash: t1\n"
        "rule_fingerprint: r1\n"
        "review_policy_epoch: e1\n"
        "rule_catalog_manifest_digest: c1\n"
        "finding: F-1\n"
        "digest: " + "a" * 64 + "\n"
        "decision: accepted\n"
        "```"
    )
    COMPLETENESS_STAMP = (
        "```axdt-decision\n"
        "key: completeness\n"
        "projection_tree_hash: t1\n"
        "active_catalog_input_digest: ci1\n"
        "review_policy_epoch: e1\n"
        "finding: F-2\n"
        "digest: " + "b" * 64 + "\n"
        "decision: rejected\n"
        "```"
    )

    def _comment(self, comment_id, body, login="reviewer-1",
                created="2026-01-01T00:00:00Z", updated=None):
        return {
            "id": comment_id, "body": body, "user": {"login": login},
            "created_at": created, "updated_at": updated or created,
        }

    def test_valid_judgment_decision_parsed(self):
        comments = [self._comment(101, self.JUDGMENT_STAMP)]
        backend = FakeCommandBackend(results=[
            _obj(comments),
            _obj({"role_name": "admin"}),
            _obj({"type": "User"}),
        ])
        ports = _ports(backend)

        decisions = ports.read_channel_decisions(PR)

        assert len(decisions) == 1
        d = decisions[0]
        assert d.decision == FindingDecision.ACCEPTED
        assert d.key == FullBindingKey(review_key=JUDGMENT, finding_id="F-1", content_digest="a" * 64)
        assert d.author == "reviewer-1"
        assert d.comment_id == 101
        assert d.author_role == "admin"
        assert d.author_is_human is True

    def test_valid_completeness_decision_parsed(self):
        comments = [self._comment(102, self.COMPLETENESS_STAMP)]
        backend = FakeCommandBackend(results=[
            _obj(comments),
            _obj({"role_name": "admin"}),
            _obj({"type": "User"}),
        ])
        ports = _ports(backend)

        decisions = ports.read_channel_decisions(PR)

        assert len(decisions) == 1
        d = decisions[0]
        assert d.decision == FindingDecision.REJECTED
        assert d.key == FullBindingKey(review_key=SWEEP, finding_id="F-2", content_digest="b" * 64)

    def test_malformed_or_absent_stamp_is_skipped(self):
        comments = [
            self._comment(103, "just a regular comment, no stamp at all"),
            self._comment(104, "```axdt-decision\nkey: judgment\n```"),   # missing required fields
        ]
        backend = FakeCommandBackend(results=[_obj(comments)])
        ports = _ports(backend)

        decisions = ports.read_channel_decisions(PR)

        assert decisions == ()
        assert len(backend.calls) == 1   # no role/human lookups for skipped comments

    def test_tampered_decision_surfaces_updated_at_differs_as_raw_fact(self):
        comments = [self._comment(105, self.JUDGMENT_STAMP,
                                   created="2026-01-01T00:00:00Z",
                                   updated="2026-01-02T00:00:00Z")]
        backend = FakeCommandBackend(results=[
            _obj(comments),
            _obj({"role_name": "admin"}),
            _obj({"type": "User"}),
        ])
        ports = _ports(backend)

        decisions = ports.read_channel_decisions(PR)

        assert len(decisions) == 1
        assert decisions[0].created_at != decisions[0].updated_at

    def test_author_role_lookup_404_defaults_to_empty_raw_fact(self):
        comments = [self._comment(106, self.JUDGMENT_STAMP, login="outsider")]
        backend = FakeCommandBackend(results=[
            _obj(comments),
            _err(stderr="gh: Not Found (HTTP 404)", exit_code=1),   # collaborators/permission 404
            _obj({"type": "User"}),
        ])
        ports = _ports(backend)

        decisions = ports.read_channel_decisions(PR)

        assert len(decisions) == 1
        assert decisions[0].author_role == ""


# ============================================================================
# read_approvals
# ============================================================================

class TestReadApprovals:
    STAMP = (
        "```axdt-approval\n"
        "judgment_tree_hash: t1\n"
        "judgment_rule_fingerprint: r1\n"
        "judgment_review_policy_epoch: e1\n"
        "judgment_rule_catalog_manifest_digest: c1\n"
        "completeness_projection_tree_hash: t1\n"
        "completeness_active_catalog_input_digest: ci1\n"
        "completeness_review_policy_epoch: e1\n"
        "```"
    )

    def _review(self, review_id, state, body="", login="reviewer-1"):
        return {"id": review_id, "state": state, "body": body, "user": {"login": login}}

    def test_approval_with_valid_stamp_included(self):
        reviews = [self._review(1, "APPROVED", self.STAMP)]
        backend = FakeCommandBackend(results=[
            _obj(reviews),
            _obj({"role_name": "admin"}),
            _obj({"type": "User"}),
        ])
        ports = _ports(backend)

        approvals = ports.read_approvals(PR)

        assert len(approvals) == 1
        a = approvals[0]
        assert a.approver == "reviewer-1"
        assert a.seq == 1
        assert a.dismissed is False
        assert a.approver_role == "admin"
        assert a.approver_is_human is True
        assert a.approved_judgment == JUDGMENT
        assert a.approved_completeness == SWEEP

    def test_approval_without_stamp_excluded(self):
        reviews = [self._review(2, "APPROVED", body="looks good, approving")]
        backend = FakeCommandBackend(results=[_obj(reviews)])
        ports = _ports(backend)

        approvals = ports.read_approvals(PR)

        assert approvals == ()
        assert len(backend.calls) == 1   # no role/human lookup for an excluded approval

    def test_dismissed_approval_with_stamp_is_flagged(self):
        reviews = [self._review(3, "DISMISSED", self.STAMP)]
        backend = FakeCommandBackend(results=[
            _obj(reviews),
            _obj({"role_name": "admin"}),
            _obj({"type": "User"}),
        ])
        ports = _ports(backend)

        approvals = ports.read_approvals(PR)

        assert len(approvals) == 1
        assert approvals[0].dismissed is True

    def test_non_approval_state_ignored(self):
        reviews = [self._review(4, "COMMENTED", self.STAMP)]
        backend = FakeCommandBackend(results=[_obj(reviews)])
        ports = _ports(backend)

        approvals = ports.read_approvals(PR)

        assert approvals == ()
        assert len(backend.calls) == 1


# ============================================================================
# merge_pull_request
# ============================================================================

class TestMergePullRequest:
    def test_merge_success_returns_none_and_sends_head_pinned_argv(self):
        backend = FakeCommandBackend(results=[_obj({"merged": True, "sha": "merge-sha"})])
        ports = _ports(backend)

        result = ports.merge_pull_request(PR, JUDGMENT, SWEEP, "head-sha-1")

        assert result is None
        assert len(backend.calls) == 1
        argv = backend.calls[0][0]
        assert argv == [
            "gh", "api", "--method", "PUT",
            f"repos/{TARGET_REPO}/pulls/42/merge",
            "-f", "sha=head-sha-1",
            "-f", "merge_method=merge",
        ]

    def test_merge_409_raises_head_moved_error(self):
        backend = FakeCommandBackend(results=[
            _err(stderr="gh: Head branch was modified. Review and try the merge again. (HTTP 409)",
                 exit_code=1),
        ])
        ports = _ports(backend)

        with pytest.raises(HeadMovedError):
            ports.merge_pull_request(PR, JUDGMENT, SWEEP, "head-sha-1")

    def test_merge_405_raises_githosterror_not_head_moved(self):
        backend = FakeCommandBackend(results=[
            _err(stderr="gh: New changes require approval from someone other than the "
                        "last pusher (HTTP 405)", exit_code=1),
        ])
        ports = _ports(backend)

        with pytest.raises(GitHostError):
            ports.merge_pull_request(PR, JUDGMENT, SWEEP, "head-sha-1")

    def test_merge_other_error_raises_githosterror(self):
        backend = FakeCommandBackend(results=[_err(stderr="boom", exit_code=1)])
        ports = _ports(backend)

        with pytest.raises(GitHostError):
            ports.merge_pull_request(PR, JUDGMENT, SWEEP, "head-sha-1")


# ============================================================================
# verify_ruleset_config
# ============================================================================

class TestVerifyRulesetConfig:
    def _rs_a(self, id_=1, bypass_count=1):
        return {
            "id": id_, "name": "RS-A",
            "rules": [{"type": "update"}],
            "bypass_actors": [{"actor_type": "Integration", "actor_id": 999,
                              "bypass_mode": "always"}] * bypass_count,
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        }

    def _rs_b(self, id_=2, bypass_actors=None, pr_param_overrides=None):
        params = dict(
            required_approving_review_count=1,
            dismiss_stale_reviews_on_push=True,
            require_last_push_approval=True,
            allowed_merge_methods=["merge"],
        )
        if pr_param_overrides:
            params.update(pr_param_overrides)
        return {
            "id": id_, "name": "RS-B",
            "rules": [
                {"type": "pull_request", "parameters": params},
                {"type": "non_fast_forward"},
                {"type": "deletion"},
            ],
            "bypass_actors": bypass_actors if bypass_actors is not None else [],
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        }

    def _rs_c(self, id_=3, bypass_actors=None):
        return {
            "id": id_, "name": "RS-C",
            "rules": [{"type": "non_fast_forward"}, {"type": "deletion"}],
            "bypass_actors": bypass_actors if bypass_actors is not None else [],
            "conditions": {"ref_name": {"include": ["refs/heads/sot/**"], "exclude": []}},
        }

    def _backend(self, rulesets):
        results = [_obj([{"id": rs["id"], "name": rs["name"]} for rs in rulesets])]
        for rs in rulesets:
            results.append(_obj(rs))
        return FakeCommandBackend(results=results)

    def test_true_when_config_matches_declared_state(self):
        backend = self._backend([self._rs_a(), self._rs_b(), self._rs_c()])
        ports = _ports(backend)

        assert ports.verify_ruleset_config() is True

    def test_false_when_ruleset_missing(self):
        backend = self._backend([self._rs_a(), self._rs_b()])   # RS-C missing
        ports = _ports(backend)

        assert ports.verify_ruleset_config() is False

    def test_false_when_rs_a_and_rs_b_merged_into_one_ruleset(self):
        merged = self._rs_a()
        merged["rules"] = [
            {"type": "update"},
            {"type": "pull_request", "parameters": dict(
                required_approving_review_count=1,
                dismiss_stale_reviews_on_push=True,
                require_last_push_approval=True,
                allowed_merge_methods=["merge"],
            )},
            {"type": "non_fast_forward"},
            {"type": "deletion"},
        ]
        backend = self._backend([merged, self._rs_c()])
        ports = _ports(backend)

        assert ports.verify_ruleset_config() is False

    def test_false_when_rs_b_has_bypass_actors(self):
        backend = self._backend([
            self._rs_a(),
            self._rs_b(bypass_actors=[{"actor_type": "User", "actor_id": 1, "bypass_mode": "always"}]),
            self._rs_c(),
        ])
        ports = _ports(backend)

        assert ports.verify_ruleset_config() is False

    def test_false_when_rs_c_has_bypass_actors(self):
        backend = self._backend([
            self._rs_a(), self._rs_b(),
            self._rs_c(bypass_actors=[{"actor_type": "User", "actor_id": 1, "bypass_mode": "always"}]),
        ])
        ports = _ports(backend)

        assert ports.verify_ruleset_config() is False

    def test_false_when_rs_b_missing_required_param(self):
        backend = self._backend([
            self._rs_a(),
            self._rs_b(pr_param_overrides={"allowed_merge_methods": ["merge", "squash"]}),
            self._rs_c(),
        ])
        ports = _ports(backend)

        assert ports.verify_ruleset_config() is False

    def test_false_when_rs_a_bypass_actors_empty(self):
        backend = self._backend([self._rs_a(bypass_count=0), self._rs_b(), self._rs_c()])
        ports = _ports(backend)

        assert ports.verify_ruleset_config() is False

    def test_false_when_detail_fetch_fails(self):
        backend = FakeCommandBackend(results=[
            _obj([{"id": 1, "name": "RS-A"}]),
            _err(exit_code=1),
        ])
        ports = _ports(backend)

        assert ports.verify_ruleset_config() is False

    def test_false_when_listing_fetch_fails(self):
        backend = FakeCommandBackend(results=[_err(exit_code=1)])
        ports = _ports(backend)

        assert ports.verify_ruleset_config() is False
