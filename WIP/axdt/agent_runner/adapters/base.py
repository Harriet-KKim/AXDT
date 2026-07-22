from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from axdt.agent_runner.state import AgentState
from axdt.roles.spec import Capability, RoleSpec


@dataclass(frozen=True)
class RoleArtifact:
    """기동 전 물질화돼야 하는 아티팩트 하나(경로·내용·권한 힌트)."""

    path: Path        # root(artifact_root가 준 실제 물질화 위치) 기준 상대 경로 (예: Path("leader.config.toml"))
    content: str      # 역할 프롬프트·권한을 담은 본문
    mode: int = 0o400 # 물질화 시 권한 힌트(읽기전용). 실제 적용은 Phase 3(OS 권한).

    def __post_init__(self) -> None:
        # path는 root 기준 상대 경로 계약이다 — 절대경로나 상위 디렉터리
        # 이탈(..)은 root 밖에 쓰라는 뜻이라 여기서 즉시 거부한다. anchor는
        # 절대경로뿐 아니라 Windows의 루트/드라이브 상대 경로(예: "\evil.toml",
        # "C:evil.toml")도 함께 잡는다 — is_absolute()만으로는 새는 경우다.
        if self.path.anchor or ".." in self.path.parts:
            raise ValueError(
                f"RoleArtifact.path must be relative with no '..': {self.path!r}"
            )


class RoleNotProvisioned(Exception):
    """역할 아티팩트가 없거나 어댑터 계산본과 내용이 다르다(fail-closed)."""


class PlatformAdapter(ABC):
    """Platform-specific knowledge (Claude Code / Codex).

    A CLI hook writes the session state to a file; the backend reads it
    (SessionBackend.read_state); the runner extracts the state value and
    passes it to detect_state, which maps it to an AgentState. Subclasses
    normally declare only config_dir_name + build_session_command; the hook
    state names are shared across platforms, so detect_state only needs
    overriding when a platform's hook emits different names (Phase 3).
    """

    name: str
    config_dir_name: str

    def config_dir(self, workdir: Path) -> Path:
        """Resolved config dir = workdir / config_dir_name."""
        return workdir / self.config_dir_name

    def artifact_root(self, workdir: Path, env: Mapping[str, str]) -> Path:
        """role_artifacts / verify_role_provisioned가 실제로 쓰는 물질화 root.
        기본값은 workspace의 config_dir다. 플랫폼이 다른 위치(예: Codex의
        $CODEX_HOME)를 읽는다면 override한다 — 게이트가 실제 조회 위치를
        검사해야 fail-closed가 성립한다."""
        return self.config_dir(workdir)

    @abstractmethod
    def capability_args(self, cap: Capability) -> list[str]:
        """능력 등급 → 플랫폼 인자 (§2.3.1). 값은 잠정 — §8.3 라이브 측정으로 확정."""

    @abstractmethod
    def prepare_subagents(self, workdir: Path, roles: Sequence[RoleSpec]) -> list[str]:
        """SUBAGENT 역할을 플랫폼 형식으로 준비하고 세션 argv에 실을 인자를 반환 (§2.3.3)."""

    @abstractmethod
    def role_artifacts(self, role: RoleSpec, root: Path) -> list[RoleArtifact]:
        """이 역할이 기동 전 물질화돼야 하는 아티팩트(경로·내용·권한).
        어댑터가 역할·권한 내용의 단일 진실원이다. 물질화(디스크 쓰기)는
        Phase 3가 이 명세를 받아 수행한다.

        `.rules`(Codex WRITE_WORKSPACE 규칙 파일)의 역할별 의미·본문 계산도
        어댑터가 소유하는 게 맞으나 형식이 미확정이다 — role_artifacts의
        향후 확장 대상이다(형식은 슬라이스 B 확정). Phase 3는 그 결과를
        배치·쓰기만 한다. 지금은 프로파일 아티팩트만 반환한다."""

    @abstractmethod
    def build_session_command(self, role: RoleSpec, workdir: Path,
                              subagent_args: Sequence[str] = ()) -> list[str]:
        """SESSION 역할 실행 argv — capability·model·subagents 조립(§9 811).
        역할 시스템 프롬프트 전달은 플랫폼별이다: Claude는 `--append-system-prompt`
        argv로 싣고, Codex는 `-p <role>` 프로파일이 고르는 외부 역할 아티팩트로
        전달한다(argv에 직접 싣지 않음, Phase 3 물질화·handoff §6).
        build_launch_command를 대체."""

    def verify_role_provisioned(self, role: RoleSpec, root: Path) -> None:
        """기동 전 fail-closed 게이트: role_artifacts 명세와 실제 디스크 상태를
        대조한다. 아티팩트가 없거나(디렉터리인 경우 포함) 내용이 다르면
        RoleNotProvisioned를 낸다. 파일 권한(mode) 검증은 하지 않는다 — OS별로
        달라 Phase 3(실 권한 적용) 몫이다. role_artifacts가 빈 목록이면 검증할
        게 없어 통과한다.

        이 검증은 external role artifacts(예: Codex 프로파일 파일)만 대상이다.
        SUBAGENT의 argv 보증(prepare_subagents 결과가 세션 argv에 실림)은 이
        검증과 별개다 — 그건 build_session_command 호출자가 실어 나른다."""
        for artifact in self.role_artifacts(role, root):
            target = root / artifact.path
            if not target.is_file():
                raise RoleNotProvisioned(
                    f"role {role.name!r}: artifact not provisioned: {target}"
                )
            try:
                # read_bytes + 명시 decode: read_text의 universal-newline
                # 정규화는 디스크의 CRLF를 LF로 뭉개 CRLF≠LF 불일치를 통과시킨다.
                # OSError(권한 없음 등 읽기 실패)도 함께 감싼다 — is_file()을
                # 통과해도 읽기가 실패할 수 있고, fail-closed엔 예외 타입이
                # RoleNotProvisioned로 통일돼야 한다.
                actual = target.read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise RoleNotProvisioned(
                    f"role {role.name!r}: artifact not readable: {target}"
                ) from exc
            if actual != artifact.content:
                raise RoleNotProvisioned(
                    f"role {role.name!r}: artifact content mismatch: {target}"
                )

    def format_prompt(self, text: str) -> str:
        """Render a prompt for injection. Returns literal text passed verbatim
        to SessionBackend.send_text. The submit key is sent separately by
        AgentRunner.submit(), so this returns the literal body only. Override
        if a platform needs a different body rendering (Phase 3)."""
        return text

    def submit_key(self) -> str:
        return "Enter"

    def clear_key(self) -> str:
        return "C-u"   # Esc 금지 (§4.1); 실제 값은 §8.3 라이브 측정으로 확정

    _STATE_MAP: dict[str, AgentState] = {
        "idle": AgentState.IDLE,
        "start": AgentState.IDLE,
        "busy": AgentState.BUSY,
        "waiting": AgentState.WAITING_INPUT,
    }

    def detect_state(self, raw_state: str | None) -> AgentState | None:
        """Map a hook-emitted state value to an AgentState.

        raw_state is the already-extracted state value (e.g. "busy"), not
        screen output and not the raw JSON line. Unknown values (including
        None) return None — inconclusive, so the runner keeps its previous
        state. Override if a platform's hook emits different state names."""
        if raw_state is None:
            return None
        return self._STATE_MAP.get(raw_state)
