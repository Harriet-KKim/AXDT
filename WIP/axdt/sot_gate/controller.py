"""MergeController — GateHostPorts + evaluate_gate 합성체(§2.4, §2.5, §2.9, §3).
전역 직렬화 하에 머지 직전 재평가 후 머지. 대상 저장소 밖에서 돌며, 머지 토큰은 여기에만 있다.
"""
import threading
from dataclasses import dataclass

from axdt.git_host.models import PullRequest
from axdt.sot_gate.gate import evaluate_gate
from axdt.sot_gate.models import GateInputs, GateOutcome, GateStatus
from axdt.sot_gate.ports import GateHostPorts, HeadMovedError


@dataclass(frozen=True)
class DecisionSnapshot:
    """관측된 결정 하나의 감사 기록 스냅샷(§2.9): 완전 결속 키・author・comment_id."""
    key: "object"          # FullBindingKey
    author: str
    comment_id: int


@dataclass(frozen=True)
class AuditRecord:
    """머지 하나의 불변 감사 기록(§2.9) — 착지 두 키・관측 결정 스냅샷・승인 이벤트・base를 담는다.
    이 리스트(MergeController.audit_log)가 "대상 저장소 밖의 컨트롤러 도메인" 기록을 대체한다
    (실제 영속 저장소·서명은 이 증분 범위 밖).

    observed_decisions는 "반영된"(blocking을 닫은 winner) 결정이 아니라 이 머지를 위해 읽은
    채널 결정 전량 — 관측된 그대로다. gate.py의 winner 선정(항목 8·11·9)은 비공개 헬퍼
    (_resolve_open_blocking)라 "실제로 어느 결정이 어느 blocking을 닫았는지"를 여기서
    재도출하지 않는다 — 재도출은 순수 코어 로직의 이중 구현이 되어 두 구현이 어긋날 위험을
    만든다(§2.2의 "단일 구현" 원칙과 같은 이유)."""
    landing_judgment: "object"        # JudgmentKey
    landing_completeness: "object"    # CompletenessSweepKey
    observed_decisions: "tuple[DecisionSnapshot, ...]"
    approvals: "tuple"                # tuple[ApprovalEvent, ...]
    base: str
    # pr.base(브랜치명)를 기록한다. §2.9가 요구하는 "그 머지의 base SHA"의 라이브 해석(main
    # 현재 tip을 SHA로 resolve하는 방법)은 GateHostPorts 7포트 계약에 없는 정보라 이 증분(순수
    # 코어 실행부)에서는 얻을 수 없다 — GitHubGatePorts 라이브 구현에서 provisional로 채운다(§8).


_MAX_MERGE_ATTEMPTS = 3   # 모듈 상수. head가 계속 움직이면 무한 재시도하지 않는다(§2.5 신선성).


class MergeController:
    """포트 + evaluate_gate 합성체. 전역 직렬화 하에 머지 직전 재평가 후 머지(§2.5).
    대상 저장소 밖에서 돌며, 머지 토큰은 여기에만 있다.

    §4.1의 기동 시 룰셋 점검, 그리고 (기동·매 머지) 룰셋 점검 실패의 불일치 경보·실패 감사는
    컨트롤러 호스팅·기동 증분(§8) 몫이며, 이 순수 코어 실행부는 매 머지의 잠금 안 점검으로
    fail-closed RED만 반환한다."""

    def __init__(self, ports: "GateHostPorts", target_repo: str, allowlist: "frozenset[str]"):
        self._ports = ports
        self._target_repo = target_repo
        self._allowlist = allowlist
        self._lock = threading.Lock()          # 전역 직렬화(§2.5) — merge_if_green 전용
        self._audit_log: "list[AuditRecord]" = []   # 추가 전용(§2.9) — 비공개, 공개 접근은 audit_log 프로퍼티

    @property
    def audit_log(self) -> "tuple[AuditRecord, ...]":
        """추가 전용 감사 기록의 읽기전용 뷰(§2.9). tuple이라 외부에서 append・삭제로 변형할 수 없다."""
        return tuple(self._audit_log)

    def _build_inputs(self, pr: "PullRequest") -> GateInputs:
        """읽기 포트 5개 + 주입된 allowlist로 GateInputs를 구성한다. 부작용 없음.
        read_pr_metadata를 read-set의 첫 읽기로 두어, merge_if_green의 끝-괄호(다시 읽은
        head_sha)가 compute_landing_keys를 포함한 read-set 전체를 덮게 한다."""
        meta = self._ports.read_pr_metadata(pr)
        landing_judgment, landing_completeness = self._ports.compute_landing_keys(pr)
        consistency_artifact, completeness_artifact = self._ports.read_ci_artifacts(pr)
        decisions = self._ports.read_channel_decisions(pr)
        approvals = self._ports.read_approvals(pr)
        return GateInputs(
            landing_judgment=landing_judgment,
            landing_completeness=landing_completeness,
            target_repo=self._target_repo,
            allowlist=self._allowlist,
            meta=meta,
            consistency_artifact=consistency_artifact,
            completeness_artifact=completeness_artifact,
            decisions=decisions,
            approvals=approvals,
        )

    def evaluate(self, pr: "PullRequest") -> GateOutcome:
        """읽기 포트 5개 + 주입된 allowlist로 GateInputs 구성 -> evaluate_gate.
        부작용 없음(표시 갱신용)."""
        return evaluate_gate(self._build_inputs(pr))

    def merge_if_green(self, pr: "PullRequest") -> GateOutcome:
        """직렬화 잠금 획득 -> verify_ruleset_config(불일치면 fail-closed RED, §4.1)
        -> 한정 재평가 루프(최대 _MAX_MERGE_ATTEMPTS회, §2.5 신선성 불변식):
          1) read-set을 읽고(_build_inputs) read-set 끝에서 head_sha를 다시 읽어 괄호친다 —
             시작과 끝의 head_sha가 다르면 read-set이 읽는 도중 head가 움직여 찢어진 것이므로
             그 결과를 버리고 재시도한다(read-set 원자성, 미평가 head 착지 방지).
          2) 안정된 read-set으로 evaluate_gate. GREEN이 아니면 그 결과를 즉시 반환한다(재시도 안 함).
          3) GREEN이면 merge_pull_request(착지 두 키 + 그 평가의 inputs.meta.head_sha를 그대로
             전달, 재조회 금지). 호스트가 head 불일치로 거부(HeadMovedError)하면 재평가부터
             다시 한다.
          4) 머지가 성사되면 감사 기록(§2.9)을 남기고 그 GateOutcome을 반환한다.
        한정 횟수를 다 써도 안정된 head로 착지하지 못하면(head가 반복해 이동) fail-closed RED를
        반환한다 — 무한 재시도하지 않는다.
        잠금 밖에서 계산한 결과・잠금 밖에서 읽은 head_sha는 재사용하지 않는다 — 이 메서드 안에서
        새로 읽고 새로 계산한 값만 쓴다.

        잔여 한계(ABA, 코드로 미해소): read-set 괄호치기는 head가 단조 전진할 때(표본 사이에
        이전 SHA로 되돌아오지 않을 때) read-set 원자성을 보장한다. sot/* 소스 브랜치는
        비보호(§2.8)라 외부 force-push로 head가 A→B→A로 롤백되면 시작・끝 표본이 모두 A라
        괄호가 통과하나 중간 읽기는 B를 봤을 수 있다 — 이 ABA 잔여 창의 완전 해소는 읽기를
        캡처한 head SHA에 결속하는 §3 계약 개정 또는 sot/* 소스 ref force-push 차단(§2.8 개정)이며,
        스펙 결정 안건으로 남긴다."""
        with self._lock:
            if not self._ports.verify_ruleset_config():
                # 룰셋 구성 점검 실패 — GateInputs를 구성하지도 않고 fail-closed RED(§4.1).
                return GateOutcome(status=GateStatus.RED, reason="ruleset config verification failed")

            for _ in range(_MAX_MERGE_ATTEMPTS):
                inputs = self._build_inputs(pr)                                # read-set 시작
                end_head_sha = self._ports.read_pr_metadata(pr).head_sha       # read-set 끝 괄호
                if inputs.meta.head_sha != end_head_sha:
                    continue    # read-set 도중 head 이동 -> 찢어진 read-set 폐기, 재평가

                outcome = evaluate_gate(inputs)
                if outcome.status is not GateStatus.GREEN:
                    return outcome    # RED는 즉시 반환(재시도 안 함)

                try:
                    self._ports.merge_pull_request(
                        pr, inputs.landing_judgment, inputs.landing_completeness, inputs.meta.head_sha,
                    )
                except HeadMovedError:
                    continue    # 호스트가 head 불일치로 거부 -> 재평가

                self._record_audit(pr, inputs)
                return outcome

            # 한정 횟수 소진: head가 반복해 이동 -> fail-closed(머지 안 함).
            return GateOutcome(
                status=GateStatus.RED,
                reason="head moved during re-evaluation; merge retries exhausted",
            )

    def _record_audit(self, pr, inputs: GateInputs) -> None:
        """§2.9: 착지 두 키・관측 결정 스냅샷(완전 결속 키・author・comment_id)・승인 이벤트・base를
        추가 전용으로 기록한다."""
        observed = tuple(
            DecisionSnapshot(key=d.key, author=d.author, comment_id=d.comment_id)
            for d in inputs.decisions
        )
        self._audit_log.append(AuditRecord(
            landing_judgment=inputs.landing_judgment,
            landing_completeness=inputs.landing_completeness,
            observed_decisions=observed,
            approvals=inputs.approvals,
            base=pr.base,
        ))
