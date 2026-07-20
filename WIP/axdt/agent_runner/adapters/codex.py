from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from axdt.agent_runner.adapters.base import PlatformAdapter
from axdt.roles.spec import Capability, RoleSpec


class CodexAdapter(PlatformAdapter):
    name = "codex"
    config_dir_name = ".codex"

    def capability_args(self, cap: Capability) -> list[str]:
        # §2.3.1 표. -s 값 자체는 --help로 문서 확인됐으나, .rules/approval-policy
        # 세부(특히 HOST_CONTROL의 승인 정책)는 잠정 — §8.3 / Phase 3.
        if cap is Capability.READ_ONLY:
            return ["-s", "read-only"]
        if cap is Capability.WRITE_WORKSPACE:
            return ["-s", "workspace-write"]
        if cap is Capability.HOST_CONTROL:
            return ["-s", "danger-full-access"]
        raise ValueError(f"unknown capability: {cap!r}")

    def prepare_subagents(self, workdir: Path, roles: Sequence[RoleSpec]) -> list[str]:
        """Codex에는 네이티브 sub-agent가 없다. 프로파일·프롬프트·.rules는
        `$CODEX_HOME` 아래 컨테이너 이미지 계층에 물질화된다(§2.3.3) — 이
        어댑터가 아니라 컨테이너 빌드/기동 시점의 책임이다. 이 세션(Phase 5
        agent runner)의 범위 밖이므로 Phase 3에서 구현한다
        (handoff-phase5-runtime-contract.md §6, spec §2.3.3)."""
        raise NotImplementedError(
            "Codex subagent 물질화는 $CODEX_HOME 컨테이너 계층 — "
            "Phase 3 (handoff-phase5-runtime-contract.md §6, spec §2.3.3)"
        )

    def session_bootstrap_prompt(self, role: RoleSpec) -> str:
        # Codex엔 --append-system-prompt 대응 플래그가 없다(스펙 CLI표 line 151:
        # 전용 플래그 없음). build_session_command은 argv로 못 실으므로, 세션이
        # 처음 IDLE에 도달한 뒤 이 프롬프트를 독립(standalone) 첫 주입으로 보내
        # 정체성을 확립한다(AgentRunner.send_role_bootstrap, up 시점 호출).
        return role.system_prompt

    def build_session_command(self, role: RoleSpec, workdir: Path,
                              subagent_args: Sequence[str] = ()) -> list[str]:
        # 역할 프롬프트는 argv가 아니라 session_bootstrap_prompt가 세션 기동 후
        # 독립 첫 주입으로 심는다(스펙 CLI표 line 151). CLI 수용 방식은 §8.3 라이브 측정.
        command = ["codex"] + self.capability_args(role.capability)
        if role.model_hint:
            command += ["-m", role.model_hint]
        command += list(subagent_args)
        return command
