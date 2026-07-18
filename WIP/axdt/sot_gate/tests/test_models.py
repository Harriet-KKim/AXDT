"""Tests for sot_gate.models — dataclass immutability + GateInputs/GateOutcome construction (§3, §6 test_models)."""
import dataclasses
import re

import pytest

from axdt.git_host.state import PullRequestState

from axdt.sot_gate.keys import JudgmentKey, CompletenessSweepKey, FullBindingKey
from axdt.sot_gate.models import (
    GateStatus,
    FindingDecision,
    BlockingFinding,
    ConsistencyArtifact,
    CompletenessArtifact,
    ChannelDecision,
    ApprovalEvent,
    PRMetadata,
    GateInputs,
    GateOutcome,
    SOT_BRANCH_RE,
)


JUDGMENT = JudgmentKey(
    tree_hash="t1", rule_fingerprint="r1",
    review_policy_epoch="e1", rule_catalog_manifest_digest="c1",
)
SWEEP = CompletenessSweepKey(
    projection_tree_hash="t1", active_catalog_input_digest="ci1", review_policy_epoch="e1",
)
KEY = FullBindingKey(review_key=JUDGMENT, finding_id="F-1", content_digest="d1")
SWEEP_KEY = FullBindingKey(review_key=SWEEP, finding_id="F-2", content_digest="d2")


class TestEnums:
    def test_gatestatus_names(self):
        assert {m.name for m in GateStatus} == {"GREEN", "RED"}

    def test_gatestatus_values(self):
        assert GateStatus.GREEN.value == "green"
        assert GateStatus.RED.value == "red"

    def test_findingdecision_names(self):
        assert {m.name for m in FindingDecision} == {"ACCEPTED", "REJECTED"}

    def test_findingdecision_values(self):
        assert FindingDecision.ACCEPTED.value == "accepted"
        assert FindingDecision.REJECTED.value == "rejected"


class TestFrozenDataclasses:
    def test_blockingfinding_frozen(self):
        bf = BlockingFinding(key=KEY)
        with pytest.raises(dataclasses.FrozenInstanceError):
            bf.key = KEY

    def test_consistencyartifact_frozen(self):
        art = ConsistencyArtifact(judgment=JUDGMENT, format_ok=True, review_clear=True, open_blocking=())
        with pytest.raises(dataclasses.FrozenInstanceError):
            art.format_ok = False

    def test_completenessartifact_frozen(self):
        art = CompletenessArtifact(sweep_key=SWEEP, completeness_clear=True, open_blocking=())
        with pytest.raises(dataclasses.FrozenInstanceError):
            art.completeness_clear = False

    def test_channeldecision_frozen(self):
        d = ChannelDecision(
            key=KEY, decision=FindingDecision.ACCEPTED, author="reviewer-1",
            comment_id=1, created_at="t0", updated_at="t0",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.deleted = True

    def test_approvalevent_frozen(self):
        a = ApprovalEvent(approver="reviewer-1", approved_judgment=JUDGMENT, approved_completeness=SWEEP, seq=1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.dismissed = True

    def test_prmetadata_frozen(self):
        m = PRMetadata(
            author="author-1", head_ref="sot/x", head_repo="org/repo",
            head_sha="sha-1", state=PullRequestState.OPEN, touches_sot=True,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            m.author = "author-2"

    def test_gateinputs_frozen(self):
        inputs = _make_gate_inputs()
        with pytest.raises(dataclasses.FrozenInstanceError):
            inputs.target_repo = "org/other"

    def test_gateoutcome_frozen(self):
        out = GateOutcome(status=GateStatus.GREEN, reason="")
        with pytest.raises(dataclasses.FrozenInstanceError):
            out.status = GateStatus.RED


class TestChannelDecisionDefaults:
    def test_defaults(self):
        d = ChannelDecision(
            key=KEY, decision=FindingDecision.ACCEPTED, author="reviewer-1",
            comment_id=1, created_at="t0", updated_at="t0",
        )
        assert d.deleted is False
        assert d.author_role == ""
        assert d.author_is_human is False


class TestApprovalEventDefaults:
    def test_defaults(self):
        a = ApprovalEvent(approver="reviewer-1", approved_judgment=JUDGMENT, approved_completeness=SWEEP, seq=1)
        assert a.approver_role == ""
        assert a.approver_is_human is False
        assert a.dismissed is False


class TestPRMetadataDefaults:
    def test_touches_enforcement_surface_default_false(self):
        m = PRMetadata(
            author="author-1", head_ref="sot/x", head_repo="org/repo",
            head_sha="sha-1", state=PullRequestState.OPEN, touches_sot=True,
        )
        assert m.touches_enforcement_surface is False


class TestSotBranchRe:
    def test_matches_simple_slug(self):
        assert re.match(SOT_BRANCH_RE, "sot/x")

    def test_matches_hyphenated_slug(self):
        assert re.match(SOT_BRANCH_RE, "sot/my-feature-1")

    def test_rejects_uppercase_or_underscore(self):
        assert not re.match(SOT_BRANCH_RE, "sot/A_B")

    def test_rejects_extra_path_segment(self):
        assert not re.match(SOT_BRANCH_RE, "sot/x/y")

    def test_rejects_empty_slug(self):
        assert not re.match(SOT_BRANCH_RE, "sot/")


def _make_gate_inputs():
    consistency = ConsistencyArtifact(judgment=JUDGMENT, format_ok=True, review_clear=True, open_blocking=())
    completeness = CompletenessArtifact(sweep_key=SWEEP, completeness_clear=True, open_blocking=())
    meta = PRMetadata(
        author="author-1", head_ref="sot/x", head_repo="org/repo",
        head_sha="sha-1", state=PullRequestState.OPEN, touches_sot=True,
    )
    approval = ApprovalEvent(
        approver="reviewer-1", approved_judgment=JUDGMENT, approved_completeness=SWEEP, seq=1,
        approver_role="admin", approver_is_human=True,
    )
    return GateInputs(
        landing_judgment=JUDGMENT,
        landing_completeness=SWEEP,
        target_repo="org/repo",
        allowlist=frozenset({"reviewer-1"}),
        meta=meta,
        consistency_artifact=consistency,
        completeness_artifact=completeness,
        decisions=(),
        approvals=(approval,),
    )


class TestGateInputsConstruction:
    def test_construction_fields(self):
        inputs = _make_gate_inputs()
        assert inputs.landing_judgment == JUDGMENT
        assert inputs.landing_completeness == SWEEP
        assert inputs.target_repo == "org/repo"
        assert inputs.allowlist == frozenset({"reviewer-1"})
        assert inputs.consistency_artifact.format_ok is True
        assert inputs.completeness_artifact.completeness_clear is True
        assert inputs.decisions == ()
        assert len(inputs.approvals) == 1


class TestGateOutcomeConstruction:
    def test_green_outcome(self):
        out = GateOutcome(status=GateStatus.GREEN, reason="")
        assert out.status is GateStatus.GREEN
        assert out.reason == ""

    def test_red_outcome_carries_reason(self):
        out = GateOutcome(status=GateStatus.RED, reason="pr not open")
        assert out.status is GateStatus.RED
        assert out.reason == "pr not open"
