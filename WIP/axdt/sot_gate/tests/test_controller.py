"""Tests for sot_gate.controller.MergeController — FakeGatePorts + MergeController(§6 test_controller).

1. merge_if_green이 GREEN일 때만 merge_pull_request 호출(호출 기록 검증).
2. RED면 머지하지 않는다.
3. 머지 직전 재평가: 평가와 머지 사이에 포트가 다른 값(승인 철회)을 돌려주면 머지가 일어나지 않는다.
4. 룰셋 구성 점검 실패: verify_ruleset_config가 False면 GREEN 판정이어도 머지하지 않는다(fail-closed).
5. head 고정: merge_pull_request에 그 평가의 inputs.meta.head_sha가 전달된다(머지 시점 재조회값이 아님).
6. 직렬화: 동시 호출이 겹치지 않는다.
7. 감사 기록이 착지 두 키・관측된 결정・승인 이벤트・base를 담는다.
8. read-set 원자성: read-set 도중 head가 이동하면 찢어진 read-set을 폐기하고 재평가한다.
9. 머지 API가 head 불일치로 거부(HeadMovedError)하면 재평가부터 다시 한다.
10. head가 반복해 이동/거부되면 한정 재시도(_MAX_MERGE_ATTEMPTS) 소진 후 fail-closed RED.
"""
import threading
import time

from axdt.git_host.models import PullRequest
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
)
from axdt.sot_gate.ports import FakeGatePorts, Script
from axdt.sot_gate.controller import MergeController, _MAX_MERGE_ATTEMPTS


AUTHOR = "author-1"
REVIEWER = "reviewer-1"
TARGET_REPO = "org/repo"
ALLOWLIST = frozenset({REVIEWER})

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


def _green_ports(**overrides):
    """평가할 때마다 그대로 GREEN이 나는 기본 포트 스크립트(재평가해도 값이 바뀌지 않는다)."""
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


# --- 1. GREEN일 때만 merge_pull_request 호출 ---

class TestMergeOnlyOnGreen:
    def test_green_calls_merge_pull_request_once(self):
        ports = _green_ports()
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        outcome = controller.merge_if_green(PR)

        assert outcome.status == GateStatus.GREEN
        assert len(ports.merge_calls) == 1
        assert ports.merge_calls[0]["pr"] == PR
        assert ports.merge_calls[0]["judgment"] == JUDGMENT
        assert ports.merge_calls[0]["completeness"] == SWEEP


# --- 2. RED면 머지하지 않는다 ---

class TestRedDoesNotMerge:
    def test_no_valid_approval_red_no_merge(self):
        ports = _green_ports(approvals=())
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        outcome = controller.merge_if_green(PR)

        assert outcome.status == GateStatus.RED
        assert ports.merge_calls == []

    def test_pr_not_open_red_no_merge(self):
        ports = _green_ports(pr_metadata=_meta(state=PullRequestState.CLOSED))
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        outcome = controller.merge_if_green(PR)

        assert outcome.status == GateStatus.RED
        assert outcome.reason == "pr not open"
        assert ports.merge_calls == []


# --- 3. 머지 직전 재평가: 승인 철회 ---

class TestReevaluationBeforeMerge:
    def test_approval_revoked_between_earlier_evaluate_and_merge_blocks_merge(self):
        # call #1(controller.evaluate) -> 유효 승인 있음 -> GREEN.
        # call #2(merge_if_green 내부의 신선한 재평가) -> 승인 철회(빈 튜플) -> RED, 머지 없음.
        ports = _green_ports(approvals=Script((_approval(),), ()))
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        earlier = controller.evaluate(PR)
        assert earlier.status == GateStatus.GREEN

        outcome = controller.merge_if_green(PR)

        assert outcome.status == GateStatus.RED
        assert ports.merge_calls == []

    def test_stale_green_from_earlier_evaluate_is_not_reused(self):
        # merge_if_green이 이전 evaluate() 결과를 캐시해 재사용한다면, 승인 철회에도 GREEN이 나
        # 머지될 것이다. 신선한 재평가를 강제한다면 위 케이스처럼 RED로 막힌다 — 같은 스크립트로
        # 그 사실만 다시 못박는다(merge_calls가 정확히 비어 있어야 한다, len 비교로 이중 확인).
        ports = _green_ports(approvals=Script((_approval(),), ()))
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)
        controller.evaluate(PR)

        controller.merge_if_green(PR)

        assert len(ports.merge_calls) == 0


# --- 4. 룰셋 구성 점검 실패 -> fail-closed ---

class TestRulesetConfigVerificationFailure:
    def test_ruleset_invalid_blocks_merge_even_when_otherwise_green(self):
        ports = _green_ports(verify_ruleset_config=False)
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        outcome = controller.merge_if_green(PR)

        assert outcome.status == GateStatus.RED
        assert ports.merge_calls == []

    def test_ruleset_invalid_short_circuits_before_reading_gate_inputs(self):
        # fail-closed는 GateInputs를 구성하지도 않고 즉시 RED다 — 읽기 5포트 전부(compute_landing_keys・
        # read_pr_metadata・read_ci_artifacts・read_channel_decisions・read_approvals) 호출하지 않는다.
        ports = _green_ports(verify_ruleset_config=False)
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        controller.merge_if_green(PR)

        assert ports._call_counts["compute_landing_keys"] == 0
        assert ports._call_counts["read_pr_metadata"] == 0
        assert ports._call_counts["read_ci_artifacts"] == 0
        assert ports._call_counts["read_channel_decisions"] == 0
        assert ports._call_counts["read_approvals"] == 0


# --- 5. head 고정 ---

class TestHeadShaFixation:
    def test_merge_pull_request_receives_the_fresh_evaluations_head_sha(self):
        # call #1(controller.evaluate, 잠금 밖) -> head_sha="sha-old".
        # merge_if_green 내부: 시도1의 build(call #2)="sha-new", read-set 끝 괄호(call #3)="sha-new"
        # -> 안정 -> 머지. merge_pull_request에 전달되는 값은 그 안정된 재평가의 head_sha라야 한다.
        ports = _green_ports(
            pr_metadata=Script(
                _meta(head_sha="sha-old"), _meta(head_sha="sha-new"), _meta(head_sha="sha-new"),
            ),
        )
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        earlier = controller.evaluate(PR)
        assert earlier.status == GateStatus.GREEN

        outcome = controller.merge_if_green(PR)

        assert outcome.status == GateStatus.GREEN
        assert len(ports.merge_calls) == 1
        assert ports.merge_calls[0]["head_sha"] == "sha-new"


# --- 8/9/10. 한정 재평가 루프: read-set 괄호치기 + head 이동 재평가 + 소진 시 fail-closed ---

class TestBoundedReevaluationLoop:
    def test_head_moved_mid_read_set_discards_torn_read_set_and_lands_on_stable_head(self):
        # 발견2: read-set 원자성. 시도1 — build(call#1)="sha-A", 끝 괄호(call#2)="sha-B" -> 불일치
        # -> 찢어진 read-set 폐기. 시도2 — build(call#3)="sha-B", 끝 괄호(call#4)="sha-B" -> 안정
        # -> 머지. 찢어진 sha-A로는 절대 머지하지 않는다.
        ports = _green_ports(
            pr_metadata=Script(
                _meta(head_sha="sha-A"), _meta(head_sha="sha-B"),
                _meta(head_sha="sha-B"), _meta(head_sha="sha-B"),
            ),
        )
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        outcome = controller.merge_if_green(PR)

        assert outcome.status == GateStatus.GREEN
        assert len(ports.merge_calls) == 1
        assert ports.merge_calls[0]["head_sha"] == "sha-B"
        # C3: 찢어진 시도도 read-set 전체를 새로 읽었는지(캐시 아님) — 2시도 x 1회.
        assert ports._call_counts["compute_landing_keys"] == 2
        assert ports._call_counts["read_ci_artifacts"] == 2
        assert ports._call_counts["read_channel_decisions"] == 2
        assert ports._call_counts["read_approvals"] == 2
        assert ports._call_counts["read_pr_metadata"] == 4

    def test_host_rejects_first_merge_on_head_mismatch_then_lands_after_reevaluation(self):
        # 발견1: 시도1 — build/끝 괄호 모두 "sha-B"(안정) -> 머지(sha-B) -> 호스트가 HeadMovedError로
        # 거부(merge_calls에 기록 안 됨) -> 재평가. 시도2 — build/끝 괄호 모두 "sha-C"(안정) ->
        # 머지(sha-C) 성공. 거부된 sha-B는 merge_calls에 남지 않는다.
        ports = _green_ports(
            pr_metadata=Script(
                _meta(head_sha="sha-B"), _meta(head_sha="sha-B"),
                _meta(head_sha="sha-C"), _meta(head_sha="sha-C"),
            ),
            reject_merge_head_shas=frozenset({"sha-B"}),
        )
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        outcome = controller.merge_if_green(PR)

        assert outcome.status == GateStatus.GREEN
        assert len(ports.merge_calls) == 1
        assert ports.merge_calls[0]["head_sha"] == "sha-C"
        # C3: 거부 후 재평가도 read-set 전체를 새로 읽었는지(캐시 아님) — 2시도 x 1회.
        assert ports._call_counts["compute_landing_keys"] == 2
        assert ports._call_counts["read_ci_artifacts"] == 2
        assert ports._call_counts["read_channel_decisions"] == 2
        assert ports._call_counts["read_approvals"] == 2
        assert ports._call_counts["read_pr_metadata"] == 4

    def test_head_repeatedly_moved_exhausts_retries_and_fails_closed(self):
        # head가 매번 "sha-Z"로 안정적으로 읽히지만 호스트가 매번 거부한다면(계속 이동을 시뮬레이션),
        # 한정 횟수(_MAX_MERGE_ATTEMPTS)만 재시도하고 fail-closed RED — 무한 루프가 아니다.
        # 시도당 read_pr_metadata 2회(build + 끝 괄호) x 3시도 = 6회로 한정을 못박는다.
        ports = _green_ports(
            pr_metadata=_meta(head_sha="sha-Z"),
            reject_merge_head_shas=frozenset({"sha-Z"}),
        )
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        outcome = controller.merge_if_green(PR)

        assert outcome.status == GateStatus.RED
        assert ports.merge_calls == []
        assert ports._call_counts["read_pr_metadata"] == 2 * _MAX_MERGE_ATTEMPTS
        # C3: 캐시하지 않고 매 시도 read-set 전체를 새로 읽는지 4개 read 포트도 못박는다.
        assert ports._call_counts["compute_landing_keys"] == _MAX_MERGE_ATTEMPTS
        assert ports._call_counts["read_ci_artifacts"] == _MAX_MERGE_ATTEMPTS
        assert ports._call_counts["read_channel_decisions"] == _MAX_MERGE_ATTEMPTS
        assert ports._call_counts["read_approvals"] == _MAX_MERGE_ATTEMPTS


# --- C1 회귀 가드: read-set의 첫 읽기는 read_pr_metadata ---

class _CallOrderTrackingPorts(FakeGatePorts):
    """각 read 포트 호출마다 메서드명을 self.call_order에 append한 뒤 super()로 위임한다
    (§C1 회귀 가드). _build_inputs가 read_pr_metadata를 compute_landing_keys보다 먼저
    부르는지, 실제 호출 순서로 검증한다."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_order: "list[str]" = []

    def compute_landing_keys(self, pr):
        self.call_order.append("compute_landing_keys")
        return super().compute_landing_keys(pr)

    def read_pr_metadata(self, pr):
        self.call_order.append("read_pr_metadata")
        return super().read_pr_metadata(pr)

    def read_ci_artifacts(self, pr):
        self.call_order.append("read_ci_artifacts")
        return super().read_ci_artifacts(pr)

    def read_channel_decisions(self, pr):
        self.call_order.append("read_channel_decisions")
        return super().read_channel_decisions(pr)

    def read_approvals(self, pr):
        self.call_order.append("read_approvals")
        return super().read_approvals(pr)


class TestReadSetStartsWithMetadata:
    def test_build_inputs_reads_pr_metadata_before_compute_landing_keys(self):
        # read_pr_metadata가 read-set의 첫 읽기라야 merge_if_green의 끝-괄호(다시 읽은
        # head_sha)가 compute_landing_keys를 포함한 read-set 전체를 덮는다(C1).
        ports = _CallOrderTrackingPorts(
            landing_keys=(JUDGMENT, SWEEP),
            pr_metadata=_meta(),
            ci_artifacts=(_consistency(), _completeness()),
            decisions=(),
            approvals=(_approval(),),
            verify_ruleset_config=True,
        )
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        controller.evaluate(PR)

        first_metadata_idx = ports.call_order.index("read_pr_metadata")
        first_landing_keys_idx = ports.call_order.index("compute_landing_keys")
        assert first_metadata_idx < first_landing_keys_idx


# --- 6. 직렬화 ---

class _ConcurrencyTrackingPorts(FakeGatePorts):
    """merge_if_green의 전역 직렬화(§2.5)를 검증하려고 verify_ruleset_config 하나에서만
    균형(try/finally)잡힌 계측을 한다. verify_ruleset_config는 임계구역 진입 직후 정확히 1회
    호출되므로(루프・RED・재시도와 무관), 여기 균형 계측이면 재시도・RED 경로에서도 누수 없이
    임계구역 동시 진입을 검출한다. 직렬화가 깨지면 여러 스레드가 동시에 verify의 sleep 창에
    들어와 max_active>1."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active = 0
        self.max_active = 0
        self._counter_lock = threading.Lock()

    def verify_ruleset_config(self):
        with self._counter_lock:
            self._active += 1
            self.max_active = max(self.max_active, self._active)
        try:
            time.sleep(0.05)
            return super().verify_ruleset_config()
        finally:
            with self._counter_lock:
                self._active -= 1


class TestSerialization:
    def test_concurrent_merge_if_green_calls_never_overlap(self):
        ports = _ConcurrencyTrackingPorts(
            landing_keys=(JUDGMENT, SWEEP),
            pr_metadata=_meta(),
            ci_artifacts=(_consistency(), _completeness()),
            decisions=(),
            approvals=(_approval(),),
            verify_ruleset_config=True,
        )
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        threads = [threading.Thread(target=controller.merge_if_green, args=(PR,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not any(t.is_alive() for t in threads)
        assert ports.max_active == 1


class _MergeBarrierPorts(FakeGatePorts):
    """첫 호출을 임계구역의 **마지막 연산**인 merge_pull_request 안에서 Event로 정지시킨다.
    그 사이 메인 스레드가 controller._lock을 비차단 획득 시도해 "머지 도중 잠금이 실제로
    쥐여 있는가(=머지가 잠금 안인가)"를 결정적으로 검사한다(sleep·둘째 스레드 경합 없음).
    max_active 계측(verify 진입점)과 read-set 지점 배리어는 잠금이 evaluate 뒤 풀리고 머지가
    잠금 밖인 퇴행을 못 잡는다 — §2.5 직렬화의 요체는 "잠금을 쥔 동안 base를 움직일 주체가
    없다"이고 base를 움직이는 유일 연산이 바로 이 머지이므로, 배리어를 머지에 둬야 머지가
    잠금 안(임계구역 마지막 포트 연산까지 잠금 유지)임이 고정된다. verify 진입점의 동시 진입
    금지는 TestSerialization(max_active)이 함께 보므로, 두 테스트가 verify~머지 전 구간을 덮는다."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._flag_lock = threading.Lock()
        self._first_merge_seen = False
        self.first_reached_merge = threading.Event()   # 첫 호출이 머지(임계구역 마지막)에 도달
        self.release_first = threading.Event()         # 첫 호출을 놓아준다

    def merge_pull_request(self, pr, judgment, completeness, head_sha):
        with self._flag_lock:
            is_first = not self._first_merge_seen
            self._first_merge_seen = True
        if is_first:
            self.first_reached_merge.set()
            self.release_first.wait(timeout=5)
        return super().merge_pull_request(pr, judgment, completeness, head_sha)


class TestLockHeldThroughMerge:
    def test_controller_lock_is_held_during_merge_pull_request(self):
        # 잠금이 verify~머지 전 구간을 감싸는지 결정적으로 검사한다. 첫 호출을 머지(마지막 연산)
        # 안에서 멈춰 세우고, 그때 controller._lock을 비차단 획득 시도한다. 정상 구현이면 t1이
        # 잠금을 쥐고 있어 획득이 실패한다. 잠금이 evaluate 뒤 풀리고 머지가 잠금 밖인 퇴행이면
        # 획득에 성공해 아래 단언이 실패한다 — sleep 타이밍에 의존하지 않는다.
        ports = _MergeBarrierPorts(
            landing_keys=(JUDGMENT, SWEEP),
            pr_metadata=_meta(),
            ci_artifacts=(_consistency(), _completeness()),
            decisions=(),
            approvals=(_approval(),),
            verify_ruleset_config=True,
        )
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        t1 = threading.Thread(target=controller.merge_if_green, args=(PR,))
        t1.start()
        assert ports.first_reached_merge.wait(timeout=5)   # t1이 머지 안에서 정지(잠금 보유 중이어야)

        acquired = controller._lock.acquire(blocking=False)
        if acquired:
            controller._lock.release()

        ports.release_first.set()   # t1 재개 -> 머지 완료 -> 잠금 해제
        t1.join(timeout=5)

        assert not t1.is_alive()
        assert acquired is False     # 머지가 잠금 밖이면 여기서 획득 성공 -> 실패로 잡힌다
        assert len(ports.merge_calls) == 1


# --- 7. 감사 기록 ---

class TestAuditRecord:
    def test_audit_log_captures_landing_keys_decisions_approvals_base(self):
        key = FullBindingKey(review_key=JUDGMENT, finding_id="F-1", content_digest="d1")
        consistency = _consistency(open_blocking=(BlockingFinding(key),), review_clear=False)
        decision = ChannelDecision(
            key=key, decision=FindingDecision.ACCEPTED, author=REVIEWER, comment_id=1,
            created_at="t0", updated_at="t0", author_role="admin", author_is_human=True,
        )
        ports = _green_ports(ci_artifacts=(consistency, _completeness()), decisions=(decision,))
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        outcome = controller.merge_if_green(PR)

        assert outcome.status == GateStatus.GREEN
        assert len(controller.audit_log) == 1

        record = controller.audit_log[0]
        assert record.landing_judgment == JUDGMENT
        assert record.landing_completeness == SWEEP
        assert record.base == "main"

        assert len(record.observed_decisions) == 1
        snapshot = record.observed_decisions[0]
        assert snapshot.key == key
        assert snapshot.author == REVIEWER
        assert snapshot.comment_id == 1

        assert len(record.approvals) == 1
        assert record.approvals[0].approver == REVIEWER
        assert record.approvals[0].approved_judgment == JUDGMENT
        assert record.approvals[0].approved_completeness == SWEEP

    def test_red_does_not_append_audit_record(self):
        ports = _green_ports(approvals=())
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        controller.merge_if_green(PR)

        assert controller.audit_log == ()

    def test_audit_log_is_append_only_across_merges(self):
        ports = _green_ports(
            pr_metadata=Script(_meta(head_sha="sha-1"), _meta(head_sha="sha-1")),
        )
        controller = MergeController(ports, TARGET_REPO, ALLOWLIST)

        controller.merge_if_green(PR)
        controller.merge_if_green(PR)

        assert len(controller.audit_log) == 2
