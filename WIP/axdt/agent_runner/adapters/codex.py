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

    def build_session_command(self, role: RoleSpec, workdir: Path,
                              subagent_args: Sequence[str] = ()) -> list[str]:
        # 역할↔네이티브 선택자 바인딩: `-p <role.name>`이 $CODEX_HOME/<role.name>.config.toml
        # 프로파일을 고른다(스펙 line 155·§2.3.3). 세션 역할 시스템 프롬프트는 argv나
        # 런타임 주입이 아니라 그 프로파일이 얹는 네이티브 표면으로 전달된다 — 정확한
        # 표면(후보: developer_instructions)·계층·로드는 Phase 3 실측(handoff §6).
        # 주의: `-p`는 결정적 바인딩일 뿐 fail-closed 자체 보장이 아니다 — Codex
        # 0.144.3은 부재 프로파일도 기본값으로 진행한다(실측). 부재·불일치 시 기동
        # 거부는 Phase 3가 존재 검사로 강제한다(handoff §6 미결 4).
        command = ["codex", "-p", role.name] + self.capability_args(role.capability)
        if role.model_hint:
            command += ["-m", role.model_hint]
        command += list(subagent_args)
        return command
