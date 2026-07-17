"""GitHubGatePorts — GateHostPorts의 GitHub provisional 스켈레톤(스펙 §8).

gh api 스키마(코멘트 조회・role_name・리뷰 스트림・머지 API 거부 코드)・룰셋 조회 스키마・
승인 두 키 취득 방식(§2.3 (ㄱ)/(ㄴ))・산출물 저장소 쓰기 신뢰 모델・제안된 머지 결과 취득 방법・
touches_sot/touches_enforcement_surface 판정(axdt-critical-paths 블록 glob 매칭)은 모두
provisional이며 Phase 9 라이브 도그푸딩에서 gh api 실증으로 확정한다(§8). 여기서는 계약
시그니처・docstring만 고정해 import 가능하게 하고, 본체는 아직 구현하지 않는다 — 이 클래스는
테스트에서 직접 호출하지 않는다.
"""
from axdt.git_host.models import PullRequest

from axdt.sot_gate.keys import JudgmentKey, CompletenessSweepKey
from axdt.sot_gate.models import (
    ConsistencyArtifact,
    CompletenessArtifact,
    ChannelDecision,
    ApprovalEvent,
    PRMetadata,
)
from axdt.sot_gate.ports import GateHostPorts


class GitHubGatePorts(GateHostPorts):
    """GateHostPorts의 GitHub 구현 — provisional 스켈레톤(Phase 9 라이브 확정 전, §8).
    gh api 호출은 아직 검증되지 않았다. 각 메서드는 계약(시그니처・docstring)만 고정하고
    본체는 NotImplementedError를 낸다."""

    def compute_landing_keys(self, pr: "PullRequest") -> "tuple[JudgmentKey, CompletenessSweepKey]":
        """제안된 머지 결과 상태에서 착지 두 키(판정 키 4성분・완전성 스윕 키 3성분)를 계산한다
        (§2.3). gh api로 "제안된 머지 결과"(merge(base, head))를 얻는 방법과 두 키 성분(트리
        해시・적용 rule 지문・review_policy_epoch・카탈로그 manifest digest 등)의 정확한 계산은
        provisional(§8) — gh api 미검증."""
        raise NotImplementedError("GitHubGatePorts.compute_landing_keys — Phase 9 라이브 확정 전(provisional)")

    def read_pr_metadata(self, pr: "PullRequest") -> "PRMetadata":
        """gh api로 author・head_ref・head_repo・head_sha・state를 읽고, touches_sot・
        touches_enforcement_surface는 제안된 머지 결과의 변경 경로 집합을 axdt-critical-paths
        블록의 critical glob과 매칭해 판정한다(§2.6). 블록이 main에 없거나 기형이면 강제-필수
        판정을 pass-through로 흘리지 않고 사전 fail-closed RED로 처리해야 한다(§7 활성화
        전제조건 (ㅁ)) — 이 처리는 evaluate_gate 이전의 컨트롤러 쪽 관문으로 두거나 여기서
        예외로 신호해야 하며, 정확한 방식은 provisional(§8) — gh api 미검증."""
        raise NotImplementedError("GitHubGatePorts.read_pr_metadata — Phase 9 라이브 확정 전(provisional)")

    def read_ci_artifacts(self, pr: "PullRequest") -> "tuple[ConsistencyArtifact | None, CompletenessArtifact | None]":
        """② 검토 CI가 쓴 두 신뢰 산출물(정합성・완전성)을 산출물 저장소에서 읽는다. 각자
        없거나 파싱 실패면 그 자리 None(fail-closed, §2.6 항목 4). 산출물 저장 위치와 "신뢰된
        CI 신원만 쓸 수 있다"는 쓰기 통제(또는 CI 신원 서명)는 하중을 받는 보안 요소이며
        provisional(§4.2, §8) — gh api 미검증."""
        raise NotImplementedError("GitHubGatePorts.read_ci_artifacts — Phase 9 라이브 확정 전(provisional)")

    def read_channel_decisions(self, pr: "PullRequest") -> "tuple[ChannelDecision, ...]":
        """gh api로 PR 구조화 코멘트(append-only) 스트림을 읽어 결정으로 파싱한다. 각 author의
        원시 사실(현재 role_name・사람 계정 여부)과 편집・삭제 흔적(updated_at/deleted)을 채운다
        — 결정권 논리곱(admin∧명단∧사람)은 코어가 계산하므로 여기서 접지 않는다(§2.7). 코멘트
        조회 스키마와 편집・삭제 감지 방식(타임스탬프 비교 대 이벤트)은 provisional(§8) —
        gh api 미검증."""
        raise NotImplementedError("GitHubGatePorts.read_channel_decisions — Phase 9 라이브 확정 전(provisional)")

    def read_approvals(self, pr: "PullRequest") -> "tuple[ApprovalEvent, ...]":
        """승인 리뷰 스트림 전체를 gh api로 읽는다. approver의 원시 사실(role_name・사람 여부)을
        채운다. approved_judgment・approved_completeness(두 키 모두)의 취득은 이 스켈레톤에서
        **§2.3 (ㄴ) 구조화 스탬프**를 의도한다 — 승인 리뷰 본문에 두 키를 모두 명시하는
        기계판독 스탬프를 요구하고, 두 키 스탬프가 모두 갖춰지지 않은 승인은 무효로 처리한다
        (재계산 금지, §2.3). GitHub 승인 리뷰 객체가 승인 시점 base를 기록하지 않아 (ㄱ) base
        복원 대신 (ㄴ)을 골랐다 — 다만 (ㄱ)/(ㄴ) 중 실제 채택은 스펙 §8이 여전히 provisional로
        열어 두므로 라이브 구현 시점에 재확인한다. 어느 승인이 유효한지 판정은 게이트가 한다
        (이 포트는 판정하지 않는다). gh api 리뷰 스트림 스키마는 provisional(§8) — 미검증."""
        raise NotImplementedError("GitHubGatePorts.read_approvals — Phase 9 라이브 확정 전(provisional)")

    def merge_pull_request(self, pr: "PullRequest", judgment: "JudgmentKey",
                           completeness: "CompletenessSweepKey", head_sha: str) -> None:
        """머지 커밋 방식(gh api PUT /merge, merge_method=merge)으로 머지한다. judgment・
        completeness는 감사 기록용(착지 두 키). head_sha는 평가에 쓴 스냅샷값
        (inputs.meta.head_sha)이며 머지 시점 재조회가 아니다 — 이를 머지 API의 head 고정
        파라미터(sha)로 전달한다. head가 그새 움직였으면 호스트가 거부하고, 컨트롤러는
        재평가부터 다시 한다(§2.5). head 불일치 거부(gh api 405 등)는 ports.HeadMovedError로
        번역해 던진다 — 컨트롤러의 한정 재평가 루프가 이를 잡는다. gh api의 정확한 스키마・
        거부 코드 처리(405 등)는 provisional(§8) — gh api 미검증."""
        raise NotImplementedError("GitHubGatePorts.merge_pull_request — Phase 9 라이브 확정 전(provisional)")

    def verify_ruleset_config(self) -> bool:
        """라이브 룰셋(RS-A/RS-B)이 선언 상태(ENFORCEMENT_MATRIX — RS-A/RS-B 분리・RS-B
        bypass_actors == []・필수 파라미터 존재)와 일치하는지 gh api로 조회해 대조한다(§4.1).
        불일치면 False → 컨트롤러가 fail-closed로 머지를 거부한다. 라이브 룰셋 조회 스키마와
        외부 admin의 룰셋 변경 TOCTOU 창을 좁히는 호스트 수준 보장은 provisional(§8) —
        gh api 미검증."""
        raise NotImplementedError("GitHubGatePorts.verify_ruleset_config — Phase 9 라이브 확정 전(provisional)")
