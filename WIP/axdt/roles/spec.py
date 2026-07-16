"""역할 선언의 단일 정의원 (순수 — IO는 프롬프트 파일 로드뿐).

책임 경계(누가 어디에 쓰는가·강제 등급)의 단일 명세는
`docs/sot/rule/role-responsibilities.md`다. 이 모듈은 그 표를 코드
(:class:`RoleSpec`)로, `prompts/<role>.md`는 그 표의 규범을 시스템 프롬프트
문구로 각각 번역한다. rule이 바뀌면 여기가 따라 바뀌고, 그 반대는 아니다
(설계: WIP/specs/2026-07-09-phase2-roles-and-protocol-design.md §2.2·§3·§5).

`ROLES`는 다섯 종(maintainer·leader·developer·reviewer·tester)만 담는다.
Watcher는 LLM이 아니고 세션도 sub-agent도 아니므로 `RoleSpec` 밖이다(§2.4·§3).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping

__all__ = [
    "RoleKind",
    "Capability",
    "Enforcement",
    "RoleSpec",
    "ROLES",
    "SUBAGENT_ROLES",
]

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    """``prompts/<name>.md`` 를 UTF-8로 읽어 시스템 프롬프트 본문으로 삼는다."""
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


class RoleKind(Enum):
    """역할의 실행 형태. SESSION(장기 대화형)과 SUBAGENT(상위 세션 안) 둘뿐이다."""

    SESSION = "session"
    SUBAGENT = "subagent"


class Capability(Enum):
    """플랫폼 중립 능력 등급. 어댑터가 각자의 인자로 번역한다(§2.3.1)."""

    READ_ONLY = "read-only"
    WRITE_WORKSPACE = "write-workspace"
    HOST_CONTROL = "host-control"


class Enforcement(Enum):
    """쓰기 제한이 실제로 무엇에 의해 지켜지는가(§2.3.2).

    능력(capability)이 아니라 writable_paths에 대한 강제 등급이다.
    """

    MECHANICAL = "mechanical"  # 도구 부재·샌드박스
    GATED = "gated"  # 승인 게이트가 거부
    ADVISORY = "advisory"  # 프롬프트가 지시, 상위 주체의 리뷰가 잡음
    ABSENT = "absent"  # 기계도 게이트도 잡을 상위 주체도 없다


@dataclass(frozen=True)
class RoleSpec:
    name: str  # leader|developer|reviewer|tester|maintainer
    kind: RoleKind
    capability: Capability
    enforcement: Enforcement
    rule_refs: tuple[str, ...]  # docs/sot/rule/ 의 id — 실재 검사 대상(§8)
    system_prompt: str
    model_hint: str | None  # 어댑터가 --model / -m 으로 전달
    writable_paths: tuple[str, ...]  # role-responsibilities.md 표와 등가 대조(§8.2)


ROLES: Mapping[str, RoleSpec] = {
    "maintainer": RoleSpec(
        name="maintainer",
        kind=RoleKind.SESSION,
        capability=Capability.HOST_CONTROL,
        # 부재 = 강제의 결여. Maintainer는 허브 push를 거치지 않아 경로 강제도
        # 허브 게이트도 적용되지 않고, 검토할 상위 주체도 없다(role-responsibilities.md 각주 ¹).
        enforcement=Enforcement.ABSENT,
        rule_refs=(
            "rule-role-responsibilities",
            "rule-progress-single-writer",
            "rule-report-to-progress-authority",
            "rule-sot-change-user-gate",
        ),
        system_prompt=_load_prompt("maintainer"),
        model_hint=None,
        writable_paths=(
            "docs/interim/progress.md",
            "docs/interim/plan/**",
            "docs/interim/sot-readiness-review.md",
            "docs/interim/**/README.md",
            "docs/interim/**/_TEMPLATE.md",
            # ADR 본문 기록은 Maintainer가 한다 — Leader는 report로 제안하고
            # Maintainer가 기록한다(plan과 같은 제안→기록 패턴, §2.6·각주 ⁵).
            "docs/interim/ADR/*.md",
        ),
    ),
    "leader": RoleSpec(
        name="leader",
        kind=RoleKind.SESSION,
        capability=Capability.WRITE_WORKSPACE,
        enforcement=Enforcement.GATED,
        rule_refs=(
            "rule-role-responsibilities",
            "rule-protected-paths",
            "rule-subagent-no-direct-communication",
            "rule-leader-coordination-via-maintainer",
        ),
        system_prompt=_load_prompt("leader"),
        model_hint=None,
        writable_paths=(
            "src/**",
            "test/**",
            "docs/interim/report/${task}.md",
        ),
    ),
    "developer": RoleSpec(
        name="developer",
        kind=RoleKind.SUBAGENT,
        capability=Capability.WRITE_WORKSPACE,
        # 권고(역할 간 경로 구분). rule-protected-paths가 src/**·test/**를 "자유"로
        # 두어 허브 게이트가 모르고, 능력 등급도 Developer·Tester를 가르지 않는다.
        enforcement=Enforcement.ADVISORY,
        rule_refs=(
            "rule-role-responsibilities",
            "rule-subagent-no-direct-communication",
        ),
        system_prompt=_load_prompt("developer"),
        model_hint=None,
        writable_paths=("src/**", "test/**"),
    ),
    "reviewer": RoleSpec(
        name="reviewer",
        kind=RoleKind.SUBAGENT,
        capability=Capability.READ_ONLY,
        # GATED — MECHANICAL이 아니다. §2.3.2/§3의 현재 보수적 서술을 따른 값이며,
        # READ_ONLY가 실제로 도구 집합에서 쓰기를 제거하는지(기계 등급) 승인
        # 게이트가 시도만 거부하는지(게이트 등급)는 §8.3a 항목 7의 측정 대상이다.
        # 그 측정은 Phase 5 훅 판정기 재설계 이후로 재-시퀀싱됐다
        # (handoff-state-detection-redesign.md). 측정 전이므로 여기를 MECHANICAL로
        # 올리지 않는다(role-responsibilities.md 각주 ⁴).
        enforcement=Enforcement.GATED,
        rule_refs=(
            "rule-role-responsibilities",
            "rule-subagent-no-direct-communication",
        ),
        system_prompt=_load_prompt("reviewer"),
        model_hint=None,
        writable_paths=(),
    ),
    "tester": RoleSpec(
        name="tester",
        kind=RoleKind.SUBAGENT,
        capability=Capability.WRITE_WORKSPACE,
        # 권고(역할 간 경로 구분) — developer와 같은 이유.
        enforcement=Enforcement.ADVISORY,
        rule_refs=(
            "rule-role-responsibilities",
            "rule-subagent-no-direct-communication",
        ),
        system_prompt=_load_prompt("tester"),
        model_hint=None,
        writable_paths=("test/**",),
    ),
}

SUBAGENT_ROLES: tuple[RoleSpec, ...] = tuple(
    role for role in ROLES.values() if role.kind is RoleKind.SUBAGENT
)
