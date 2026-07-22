from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from axdt.agent_runner.adapters.base import PlatformAdapter, RoleArtifact
from axdt.roles.spec import Capability, RoleSpec


# TOML basic string 표준 이스케이프(TOML spec) — 이 표에 없는 제어문자는
# \uXXXX로 폴백한다(_toml_basic_string 참고).
_TOML_BASIC_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def _toml_basic_string(value: str) -> str:
    """문자열을 TOML **단일라인** basic string 리터럴(큰따옴표 한 쌍으로 여닫는
    문자열, 여는 따옴표 포함해 반환)로 안전하게 직렬화한다. 큰따옴표·백슬래시·
    모든 제어문자(U+0000~U+001F, U+007F)를 TOML 이스케이프로 바꾼다 — 표준
    이스케이프(\\" \\\\ \\n \\r \\t \\b \\f)가 있는 문자는 그것을, 그 외
    제어문자는 \\uXXXX를 쓴다. 그 외 문자는 원문 그대로 둔다(TOML은 이스케이프
    대상이 아닌 유니코드 문자를 basic string에 그대로 허용한다). 멀티라인
    이스케이프가 필요 없어 "여는 구분자 직후 개행 트리밍" 같은 멀티라인 전용
    규칙에 영향받지 않는다 — 선두 CRLF/LF도 이스케이프돼 그대로 보존된다.
    (tomllib.loads 왕복으로 원문 바이트 보존을 테스트로 확인한다.)"""
    out = ['"']
    for ch in value:
        esc = _TOML_BASIC_ESCAPES.get(ch)
        if esc is not None:
            out.append(esc)
        elif ord(ch) < 0x20 or ch == "\x7f":
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


# capability → Codex sandbox 문자열 단일 매핑. capability_args와 role_artifacts가
# 함께 재사용한다(전에는 role_artifacts가 capability_args(...)[1] 인덱스에
# 의존해 -s 인자 형태가 바뀌면 조용히 깨질 수 있었다).
_SANDBOX_MODE: dict[Capability, str] = {
    Capability.READ_ONLY: "read-only",
    Capability.WRITE_WORKSPACE: "workspace-write",
    Capability.HOST_CONTROL: "danger-full-access",
}


class CodexAdapter(PlatformAdapter):
    name = "codex"
    config_dir_name = ".codex"

    def _sandbox_mode(self, cap: Capability) -> str:
        """capability → Codex `-s` 값의 단일 진실원. capability_args와
        role_artifacts가 함께 재사용한다(§2.3.1). 값 자체는 --help로 문서
        확인됐으나, .rules/approval-policy 세부(특히 HOST_CONTROL의 승인
        정책)는 잠정 — §8.3 / Phase 3."""
        try:
            return _SANDBOX_MODE[cap]
        except KeyError:
            raise ValueError(f"unknown capability: {cap!r}") from None

    def capability_args(self, cap: Capability) -> list[str]:
        return ["-s", self._sandbox_mode(cap)]

    def artifact_root(self, workdir: Path, env: Mapping[str, str]) -> Path:
        # `-p`는 $CODEX_HOME/<role>.config.toml을 읽는다(CODEX_HOME 없으면
        # ~/.codex). 게이트가 workspace의 .codex가 아니라 이 실제 위치를 검사해야
        # fail-closed가 성립한다(재리뷰). Phase 3는 세션 env에 CODEX_HOME을
        # 컨테이너 HOME 아래로 설정해 물질화 위치와 조회 위치를 일치시킨다(handoff §6).
        codex_home = env.get("CODEX_HOME")
        return Path(codex_home) if codex_home else Path.home() / ".codex"

    def prepare_subagents(self, workdir: Path, roles: Sequence[RoleSpec]) -> list[str]:
        # Codex SUBAGENT는 세션 argv에 실리지 않는다(argv 기여 없음) — 물질화
        # 명세는 role_artifacts가 낸다. $CODEX_HOME 아래 실제 디스크 물질화는
        # Phase 3 몫이다(handoff-phase5-runtime-contract.md §6, spec §2.3.3).
        return []

    def role_artifacts(self, role: RoleSpec, root: Path) -> list[RoleArtifact]:
        # `-p <role.name>`이 고르는 <role.name>.config.toml **별도 프로파일 파일**
        # 자체를 이 어댑터가 계산해 반환한다 — 역할·권한 내용의 단일 진실원.
        # SESSION·SUBAGENT 모두 같은 구조이고 capability만 다르다.
        #
        # 스키마: 키는 파일 최상위에 둔다 — [profiles.<name>] 중첩 테이블 헤더를
        # 쓰지 않는다. 근거: Codex 0.134.0+에서 `-p`가 고르는 별도 프로파일 파일은
        # config.toml 안의 [profiles.x] 테이블과 달리 최상위 키를 쓴다(재리뷰
        # 실측·공식 문서). 정확한 키 이름(developer_instructions 여부)·최상위/중첩
        # 구조와, project config(.codex/config.toml)가 이 키를 override할 수
        # 있는지는 슬라이스 B(Phase 3, 실 CLI 실측)에서 확정한다(handoff §6 미결
        # 1). 지금 구조는 잠정이다.
        #
        # 실행 배선 세부(.rules·래퍼 같은 물질화 방식)는 이 아티팩트에 넣지 않는다
        # — `.rules`(Codex WRITE_WORKSPACE 규칙 파일)의 역할별 의미·본문 계산도
        # 어댑터가 소유하는 게 맞으나 형식이 미확정이라 향후 role_artifacts 확장
        # 대상이다(형식은 슬라이스 B 확정); Phase 3는 배치·쓰기만 한다. 지금은
        # 프로파일만 반환한다.
        sandbox_mode = self._sandbox_mode(role.capability)
        lines = [
            f"# axdt {role.name} profile — Phase 5 어댑터가 계산·보증.",
            f"sandbox_mode = {_toml_basic_string(sandbox_mode)}",
        ]
        if role.model_hint:
            lines.append(f"model = {_toml_basic_string(role.model_hint)}")
        lines.append(
            f"developer_instructions = {_toml_basic_string(role.system_prompt)}"
        )
        content = "\n".join(lines) + "\n"
        return [RoleArtifact(path=Path(f"{role.name}.config.toml"), content=content)]

    def build_session_command(self, role: RoleSpec, workdir: Path,
                              subagent_args: Sequence[str] = ()) -> list[str]:
        # 역할↔네이티브 선택자 바인딩: `-p <role.name>`이 $CODEX_HOME/<role.name>.config.toml
        # 프로파일을 고른다(스펙 line 155·§2.3.3). 세션 역할 시스템 프롬프트는 argv나
        # 런타임 주입이 아니라 그 프로파일이 얹는 네이티브 표면으로 전달된다 — 정확한
        # 표면(후보: developer_instructions)·계층·로드는 Phase 3 실측(handoff §6).
        # 주의: `-p`는 결정적 바인딩일 뿐 fail-closed 자체 보장이 아니다 — Codex
        # 0.144.3은 부재 프로파일도 기본값으로 진행한다(실측). 부재·불일치 시 기동
        # 거부는 어댑터의 verify_role_provisioned가 강제한다(fail-closed); Phase 3는
        # role_artifacts 명세를 물질화만 한다.
        command = ["codex", "-p", role.name] + self.capability_args(role.capability)
        if role.model_hint:
            command += ["-m", role.model_hint]
        command += list(subagent_args)
        return command
