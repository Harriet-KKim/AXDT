"""Tests for sot_gate.ports — GateHostPorts(ABC) + FakeGatePorts(§6 test_ports).

- FakeGatePorts가 7포트를 모두 만족한다(추상 미구현이 있으면 인스턴스화 자체가 TypeError).
- read_ci_artifacts가 어느 산출물이든 None을 돌려주면 MergeController.evaluate -> RED.
- merge_pull_request는 reject_merge_head_shas에 든 head_sha에 대해 HeadMovedError를 던지고
  merge_calls에 기록하지 않는다(§2.5 head 이동 거부 시뮬레이션).
"""
import pytest

from axdt.git_host.models import PullRequest
from axdt.git_host.state import PullRequestState

from axdt.sot_gate.keys import JudgmentKey, CompletenessSweepKey
from axdt.sot_gate.models import (
    GateStatus,
    ConsistencyArtifact,
    CompletenessArtifact,
    PRMetadata,
    ApprovalEvent,
)
from axdt.sot_gate.ports import GateHostPorts, FakeGatePorts, Script, HeadMovedError
from axdt.sot_gate.controller import MergeController


AUTHOR = "author-1"
REVIEWER = "reviewer-1"
TARGET_REPO = "org/repo"

JUDGMENT = JudgmentKey(
    tree_hash="t1", rule_fingerprint="r1",
    review_policy_epoch="e1", rule_catalog_manifest_digest="c1",
)
SWEEP = CompletenessSweepKey(
    projection_tree_hash="t1", active_catalog_input_digest="ci1", review_policy_epoch="e1",
)
PR = PullRequest(number=1, url="https://example.com/pull/1", head="sot/x", base="main")


def _meta(**overrides):
    fields = dict(
        author=AUTHOR, head_ref="sot/x", head_repo=TARGET_REPO, head_sha="sha-1",
        state=PullRequestState.OPEN, touches_sot=True, touches_enforcement_surface=False,
    )
    fields.update(overrides)
    return PRMetadata(**fields)


def _consistency(**overrides):
    fields = dict(judgment=JUDGMENT, format_ok=True, review_clear=True, open_blocking=())
    fields.update(overrides)
    return ConsistencyArtifact(**fields)


def _completeness(**overrides):
    fields = dict(sweep_key=SWEEP, completeness_clear=True, open_blocking=())
    fields.update(overrides)
    return CompletenessArtifact(**fields)


def _approval(**overrides):
    fields = dict(
        approver=REVIEWER, approved_judgment=JUDGMENT, approved_completeness=SWEEP, seq=1,
        approver_role="admin", approver_is_human=True, dismissed=False,
    )
    fields.update(overrides)
    return ApprovalEvent(**fields)


def _make_ports(**overrides):
    fields = dict(
        landing_keys=(JUDGMENT, SWEEP),
        pr_metadata=_meta(),
        ci_artifacts=(_consistency(), _completeness()),
        decisions=(),
        approvals=(_approval(),),
        verify_ruleset_config=True,
    )
    fields.update(overrides)
    return FakeGatePorts(**fields)


class TestFakeGatePortsSatisfiesABC:
    def test_is_instance_of_gatehostports(self):
        # ABC 인스턴스화 자체가 7 abstractmethod 전부 구현을 요구한다 — 미구현이면 여기서 TypeError.
        ports = _make_ports()
        assert isinstance(ports, GateHostPorts)

    def test_cannot_instantiate_gatehostports_directly(self):
        with pytest.raises(TypeError):
            GateHostPorts()

    def test_all_seven_ports_callable_and_return_scripted_values(self):
        ports = _make_ports()

        assert ports.compute_landing_keys(PR) == (JUDGMENT, SWEEP)

        meta = ports.read_pr_metadata(PR)
        assert meta.author == AUTHOR
        assert meta.head_sha == "sha-1"

        consistency, completeness = ports.read_ci_artifacts(PR)
        assert consistency.judgment == JUDGMENT
        assert completeness.sweep_key == SWEEP

        assert ports.read_channel_decisions(PR) == ()
        approvals = ports.read_approvals(PR)
        assert len(approvals) == 1
        assert approvals[0].approver == REVIEWER

        assert ports.verify_ruleset_config() is True

        ports.merge_pull_request(PR, JUDGMENT, SWEEP, "sha-1")
        assert ports.merge_calls == [
            {"pr": PR, "judgment": JUDGMENT, "completeness": SWEEP, "head_sha": "sha-1"},
        ]


class TestScriptScripting:
    """§6 재평가・head 이동 시나리오의 기반 — 호출 순서별로 다른 값을 낼 수 있어야 한다."""

    def test_plain_value_repeats_every_call(self):
        ports = _make_ports(verify_ruleset_config=True)
        assert ports.verify_ruleset_config() is True
        assert ports.verify_ruleset_config() is True

    def test_script_steps_through_values_then_repeats_last(self):
        ports = _make_ports(approvals=Script((_approval(),), ()))
        assert len(ports.read_approvals(PR)) == 1     # call #1
        assert ports.read_approvals(PR) == ()          # call #2 (승인 철회)
        assert ports.read_approvals(PR) == ()          # call #3 — 소진 후 마지막 값 반복

    def test_plain_tuple_value_is_not_mistaken_for_a_multi_step_script(self):
        # decisions=()는 "빈 튜플 하나"이지 "0개의 스텝"이 아니다 — 매 호출 ()를 낸다.
        ports = _make_ports(decisions=())
        assert ports.read_channel_decisions(PR) == ()
        assert ports.read_channel_decisions(PR) == ()


class TestMergePullRequestHeadMovedRejection:
    """§2.5: 머지 API가 head 고정 파라미터 불일치로 거부하면 HeadMovedError를 던진다."""

    def test_rejected_head_sha_raises_head_moved_error_and_is_not_recorded(self):
        ports = _make_ports(reject_merge_head_shas=frozenset({"sha-1"}))

        with pytest.raises(HeadMovedError):
            ports.merge_pull_request(PR, JUDGMENT, SWEEP, "sha-1")

        assert ports.merge_calls == []

    def test_head_sha_outside_reject_set_still_merges_normally(self):
        ports = _make_ports(reject_merge_head_shas=frozenset({"sha-other"}))

        ports.merge_pull_request(PR, JUDGMENT, SWEEP, "sha-1")

        assert ports.merge_calls == [
            {"pr": PR, "judgment": JUDGMENT, "completeness": SWEEP, "head_sha": "sha-1"},
        ]


class TestReadCiArtifactsNoneIsFailClosedRed:
    """read_ci_artifacts가 어느 산출물이든 None을 돌려주면 MergeController.evaluate -> RED(§6)."""

    def test_consistency_none_red(self):
        ports = _make_ports(ci_artifacts=(None, _completeness()))
        controller = MergeController(ports, TARGET_REPO, frozenset({REVIEWER}))
        assert controller.evaluate(PR).status == GateStatus.RED

    def test_completeness_none_red(self):
        ports = _make_ports(ci_artifacts=(_consistency(), None))
        controller = MergeController(ports, TARGET_REPO, frozenset({REVIEWER}))
        assert controller.evaluate(PR).status == GateStatus.RED

    def test_both_artifacts_none_red(self):
        ports = _make_ports(ci_artifacts=(None, None))
        controller = MergeController(ports, TARGET_REPO, frozenset({REVIEWER}))
        assert controller.evaluate(PR).status == GateStatus.RED
