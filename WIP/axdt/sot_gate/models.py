"""게이트 순수 코어의 dataclass·enum 계약(§3). 필드·기본값·타입은 스펙 §3이 정본이다."""
from dataclasses import dataclass
from enum import Enum

from axdt.git_host.state import PullRequestState

from axdt.sot_gate.keys import JudgmentKey, FullBindingKey


class GateStatus(Enum):
    GREEN = "green"                    # 머지해도 좋다
    RED = "red"                        # 막힘(fail-closed 포함)


class FindingDecision(Enum):
    ACCEPTED = "accepted"              # 위험 인지 후 수용
    REJECTED = "rejected"              # 오판


@dataclass(frozen=True)
class BlockingFinding:
    """② CI 신뢰 산출물의 open blocking 하나."""
    key: FullBindingKey


@dataclass(frozen=True)
class CIArtifact:
    """②검토 CI가 낸 신뢰 산출물.
    불변식: review_clear == (open_blocking == ()). 위반 산출물은 기형이라 RED."""
    judgment: JudgmentKey
    format_ok: bool                    # ①형식 결과
    review_clear: bool                 # open blocking 없음
    open_blocking: "tuple[BlockingFinding, ...]"


@dataclass(frozen=True)
class ChannelDecision:
    """호스트 채널(PR 코멘트) 하나의 결정 표시(append-only)."""
    key: FullBindingKey
    decision: FindingDecision
    author: str
    comment_id: int                    # 스트림 순서 = comment_id (최신 유효본 승)
    created_at: str                    # ISO8601
    updated_at: str                    # created_at과 다르면 편집됨
    deleted: bool = False              # 삭제 감지
    author_role: str = ""              # 원시 사실: role_name(평가 시점 현재 값). admin 판정은 코어
    author_is_human: bool = False      # 원시 사실: 기계 계정 아님
    # 결정권(admin ∧ 명단 ∧ 사람)은 코어가 inputs.allowlist와 함께 계산한다(§2.7)


@dataclass(frozen=True)
class ApprovalEvent:
    """③ 승인 리뷰 하나. 판정은 게이트가 한다 — 어느 승인을 대표로 쓸지 포트가 고르지 않는다."""
    approver: str
    approved_judgment: JudgmentKey     # 승인 시점 상태에 고정(재계산 금지, §2.3). 취득: §2.3 (ㄱ)/(ㄴ)
    seq: int                           # review id
    approver_role: str = ""            # 원시 사실: role_name(평가 시점 현재 값). admin 판정은 코어
    approver_is_human: bool = False    # 원시 사실: 기계 계정 아님
    dismissed: bool = False            # 호스트가 철회(dismiss-stale 등)
    # 결정권(admin ∧ 명단 ∧ 사람)은 코어가 inputs.allowlist와 함께 계산한다(§2.7)


@dataclass(frozen=True)
class PRMetadata:
    """전용 통로로 읽는 PR 메타데이터. 공유 모델 PullRequest에는 author가 없다."""
    author: str
    head_ref: str                      # PR 소스 브랜치
    head_repo: str                     # "owner/name" — 포크 판별
    head_sha: str                      # 평가 시점 head 커밋 SHA(스냅샷). 머지 head 고정용(§2.5)
    state: "PullRequestState"          # (b) 통제 어휘
    touches_sot: bool                  # 제안된 머지 결과가 SoT 트리를 바꾸는가(§2.6)
    touches_enforcement_surface: bool = False  # 강제-필수 경로를 바꾸는가(§2.6 세 번째 분기)


@dataclass(frozen=True)
class GateInputs:
    landing_judgment: JudgmentKey      # 컨트롤러가 제안된 머지 결과에서 계산(§2.3)
    target_repo: str                   # "owner/name"
    allowlist: "frozenset[str]"        # 결정권자 명단(컨트롤러 도메인 구성, 저장소 밖·§2.7)
    meta: PRMetadata
    artifact: "CIArtifact | None"      # None = 산출물 없음(fail-closed)
    decisions: "tuple[ChannelDecision, ...]"
    approvals: "tuple[ApprovalEvent, ...]"


@dataclass(frozen=True)
class GateOutcome:
    status: GateStatus
    reason: str                        # red 사유(진단; green이면 "")


SOT_BRANCH_RE = r"^sot/[a-z0-9]+(?:-[a-z0-9]+)*$"   # 규칙의 소스 브랜치 조항과 일치
