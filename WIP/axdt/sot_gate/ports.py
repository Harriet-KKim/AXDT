"""GateHostPorts(ABC) + FakeGatePorts(테스트 더블) — 게이트가 호스트에서 읽고 머지하는 접점(§3).

읽기 5포트(GateInputs를 채움) + 룰셋 구성 점검(GateInputs를 채우지 않는 머지 직전 관문) +
머지 실행. 결정권자 명단은 호스트가 아니라 컨트롤러 도메인 구성으로 주입한다(§2.7, MergeController).
포트는 PullRequest(축소된 공유 어휘: number・url・head・base)만 인자로 받는다 — 공유 모델은
손대지 않는다(§3 머릿글).
"""
import threading
from abc import ABC, abstractmethod

from axdt.git_host.models import PullRequest

from axdt.sot_gate.keys import JudgmentKey, CompletenessSweepKey
from axdt.sot_gate.models import (
    ConsistencyArtifact,
    CompletenessArtifact,
    ChannelDecision,
    ApprovalEvent,
    PRMetadata,
)


class HeadMovedError(Exception):
    """머지 API가 head 고정 파라미터(sha) 불일치로 머지를 거부했다(§2.5). head가
    평가~머지 사이에 이동했다는 뜻 — 컨트롤러는 재평가부터 다시 한다."""


class GateHostPorts(ABC):
    """게이트가 호스트에서 읽고, 머지하는 것. GitHub 구현은 provisional(Phase 9 라이브)."""

    @abstractmethod
    def compute_landing_keys(self, pr: "PullRequest") -> "tuple[JudgmentKey, CompletenessSweepKey]":
        """제안된 머지 결과 상태에서 착지 두 키(판정 키 4성분・완전성 스윕 키 3성분)를 계산(§2.3)."""

    @abstractmethod
    def read_pr_metadata(self, pr: "PullRequest") -> "PRMetadata":
        """author・head_ref・head_repo・head_sha・state・touches_sot・touches_enforcement_surface.
        head_sha는 이 평가 스냅샷의 head 커밋(머지 head 고정용, §2.5). 두 touches_*는
        제안된 머지 결과 변경분으로 판정(§2.6). 공유 모델은 안 건드림."""

    @abstractmethod
    def read_ci_artifacts(self, pr: "PullRequest") -> "tuple[ConsistencyArtifact | None, CompletenessArtifact | None]":
        """②검토 CI의 두 신뢰 산출물(정합성・완전성). 각자 없거나 파싱 실패면 그 자리 None(fail-closed)."""

    @abstractmethod
    def read_channel_decisions(self, pr: "PullRequest") -> "tuple[ChannelDecision, ...]":
        """PR 구조화 코멘트(append-only) -> 결정들. 각 author의 원시 사실(현재 role_name,
        사람 계정 여부)과 편집・삭제 흔적(updated_at/deleted)을 채운다. 결정권 논리곱은
        코어가 inputs.allowlist와 함께 계산한다 — 포트가 admin∧명단∧사람을 접지 않는다(§2.7)."""

    @abstractmethod
    def read_approvals(self, pr: "PullRequest") -> "tuple[ApprovalEvent, ...]":
        """승인 리뷰 스트림 전체. approver의 원시 사실(role_name・사람 여부)을 채우고,
        approved_judgment・approved_completeness(두 키 모두)는 §2.3 (ㄱ) base 복원 또는
        (ㄴ) 구조화 스탬프로 취득한다(재계산 금지). 어느 승인이 유효한지는 게이트가 판정한다."""

    @abstractmethod
    def merge_pull_request(self, pr: "PullRequest", judgment: "JudgmentKey",
                           completeness: "CompletenessSweepKey", head_sha: str) -> None:
        """머지 커밋 방식으로 머지. judgment・completeness는 감사 기록용(착지 두 키). head_sha는
        평가에 쓴 스냅샷값(inputs.meta.head_sha)이며 머지 시점 재조회가 아니다 — 이를 머지 API의
        head 고정 파라미터(sha)로 전달한다. head가 그새 움직여 호스트가 거부하면 HeadMovedError를
        던진다(반환값은 여전히 None) — 컨트롤러는 재평가부터 다시 한다(§2.5). base 부동은 RS-A
        배타성+직렬화가 보장."""

    @abstractmethod
    def verify_ruleset_config(self) -> bool:
        """라이브 룰셋 구성이 선언 상태(RS-A/RS-B 분리・RS-B bypass 공백・필수 파라미터)와
        일치하는가(§4.1). 불일치면 False → 컨트롤러가 fail-closed로 머지 거부."""


class Script:
    """FakeGatePorts 생성자에 넘겨 호출 순서별로 다른 값을 스크립트한다(§6 test_controller의
    "머지 직전 재평가"・"head 고정" 시나리오 — evaluate 호출 횟수에 따라 다른 값을 돌려줘야
    승인 철회・head 이동을 검증할 수 있다). 값이 소진되면 마지막 값을 반복하므로 정확한
    호출 횟수를 몰라도 앞부분만 스크립트하면 된다."""

    def __init__(self, *values):
        if not values:
            raise ValueError("Script requires at least one value")
        self._values = list(values)

    def _at(self, call_index: int):
        idx = min(call_index, len(self._values) - 1)
        return self._values[idx]


def _as_script(value) -> Script:
    """상수 하나는 매 호출 동일값을 내는 1값 Script로 감싼다. 이미 Script면 그대로 쓴다.
    (평범한 튜플 값 — 가령 decisions=() — 을 "여러 스텝"으로 오해하지 않기 위해 다단 스크립트는
    반드시 명시적 Script(...)로만 표현한다.)"""
    return value if isinstance(value, Script) else Script(value)


class FakeGatePorts(GateHostPorts):
    """결정적 테스트 더블(§6 test_ports・test_controller). 각 포트를 상수값 또는 Script(...)로
    스크립트한다 — Script를 쓰면 호출마다 다른 값을 낸다(재평가・head 이동 검증용). merge_pull_request
    호출은 인자(head_sha・두 키 포함)와 함께 self.merge_calls에 기록해 테스트가 검증할 수 있게 한다.
    reject_merge_head_shas에 든 head_sha로 merge_pull_request가 불리면 merge_calls에 기록하지
    않고 HeadMovedError를 던진다(§2.5 head 이동 거부 시뮬레이션 — 한정 재평가 루프 테스트용)."""

    def __init__(self, *, landing_keys, pr_metadata, ci_artifacts,
                 decisions=(), approvals=(), verify_ruleset_config=True,
                 reject_merge_head_shas=frozenset()):
        self._scripts = {
            "compute_landing_keys": _as_script(landing_keys),
            "read_pr_metadata": _as_script(pr_metadata),
            "read_ci_artifacts": _as_script(ci_artifacts),
            "read_channel_decisions": _as_script(decisions),
            "read_approvals": _as_script(approvals),
            "verify_ruleset_config": _as_script(verify_ruleset_config),
        }
        self._call_counts = {name: 0 for name in self._scripts}
        self._counts_lock = threading.Lock()   # call_count 증가의 스레드 안전(§6 직렬화 테스트가 동시 호출)
        self._reject_merge_head_shas = frozenset(reject_merge_head_shas)
        self.merge_calls: "list[dict]" = []

    def _next(self, name):
        with self._counts_lock:
            idx = self._call_counts[name]
            self._call_counts[name] += 1
        return self._scripts[name]._at(idx)

    def compute_landing_keys(self, pr):
        return self._next("compute_landing_keys")

    def read_pr_metadata(self, pr):
        return self._next("read_pr_metadata")

    def read_ci_artifacts(self, pr):
        return self._next("read_ci_artifacts")

    def read_channel_decisions(self, pr):
        return self._next("read_channel_decisions")

    def read_approvals(self, pr):
        return self._next("read_approvals")

    def verify_ruleset_config(self):
        return self._next("verify_ruleset_config")

    def merge_pull_request(self, pr, judgment, completeness, head_sha):
        if head_sha in self._reject_merge_head_shas:
            # head가 평가~머지 사이에 이동한 것으로 시뮬레이션 — merge_calls에 남기지 않는다.
            raise HeadMovedError(
                f"host rejected merge: head moved (head_sha={head_sha!r} no longer current)"
            )
        self.merge_calls.append({
            "pr": pr,
            "judgment": judgment,
            "completeness": completeness,
            "head_sha": head_sha,
        })
