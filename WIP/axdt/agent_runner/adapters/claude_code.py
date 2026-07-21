from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from axdt.agent_runner.adapters.base import PlatformAdapter, RoleArtifact
from axdt.roles.spec import Capability, RoleSpec


class ClaudeCodeAdapter(PlatformAdapter):
    name = "claude-code"
    config_dir_name = ".claude"

    def capability_args(self, cap: Capability) -> list[str]:
        # §2.3.1 표. 값은 잠정 — 정밀한 --allowedTools/--disallowedTools 범위
        # 지정과 호스트 명령 허용 목록은 §8.3 라이브 측정으로 확정한다.
        if cap is Capability.READ_ONLY:
            return ["--tools", "Read,Grep,Glob", "--permission-mode", "plan"]
        if cap is Capability.WRITE_WORKSPACE:
            return ["--permission-mode", "dontAsk"]
        if cap is Capability.HOST_CONTROL:
            return ["--permission-mode", "dontAsk"]
        raise ValueError(f"unknown capability: {cap!r}")

    def _subagent_capability_fields(self, cap: Capability) -> dict:
        # SUBAGENT capability는 세션 argv가 아니라 --agents JSON의
        # tools/disallowedTools/permissionMode 필드에 실린다 (spec line 178).
        # 정확한 --agents 스키마는 잠정 — §8.3 라이브 측정으로 확정.
        if cap is Capability.READ_ONLY:
            return {"tools": ["Read", "Grep", "Glob"], "permissionMode": "plan"}
        if cap is Capability.WRITE_WORKSPACE:
            return {"permissionMode": "dontAsk"}
        if cap is Capability.HOST_CONTROL:
            return {"permissionMode": "dontAsk"}
        raise ValueError(f"unknown capability: {cap!r}")

    def prepare_subagents(self, workdir: Path, roles: Sequence[RoleSpec]) -> list[str]:
        # §2.3.3 Claude 쪽: RoleSpec들을 --agents <json> argv로 변환한다.
        obj = {}
        for role in roles:
            entry = {
                "description": f"AXDT {role.name}",
                "prompt": role.system_prompt,
            }
            if role.model_hint:
                entry["model"] = role.model_hint
            entry.update(self._subagent_capability_fields(role.capability))
            obj[role.name] = entry
        return ["--agents", json.dumps(obj)]

    def role_artifacts(self, role: RoleSpec, root: Path) -> list[RoleArtifact]:
        # Claude는 역할 시스템 프롬프트가 build_session_command의
        # --append-system-prompt argv에, SUBAGENT capability가 prepare_subagents의
        # --agents JSON에 실려 이미 어댑터가 보증하므로 외부 물질화 아티팩트가 없다.
        return []

    def build_session_command(self, role: RoleSpec, workdir: Path,
                              subagent_args: Sequence[str] = ()) -> list[str]:
        command = ["claude"] + self.capability_args(role.capability)
        command += ["--append-system-prompt", role.system_prompt]
        if role.model_hint:
            command += ["--model", role.model_hint]
        command += list(subagent_args)
        return command
