from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from axdt.agent_runner.state import AgentState
from axdt.roles.spec import Capability, RoleSpec


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

    @abstractmethod
    def capability_args(self, cap: Capability) -> list[str]:
        """능력 등급 → 플랫폼 인자 (§2.3.1). 값은 잠정 — §8.3 라이브 측정으로 확정."""

    @abstractmethod
    def prepare_subagents(self, workdir: Path, roles: Sequence[RoleSpec]) -> list[str]:
        """SUBAGENT 역할을 플랫폼 형식으로 준비하고 세션 argv에 실을 인자를 반환 (§2.3.3)."""

    @abstractmethod
    def build_session_command(self, role: RoleSpec, workdir: Path,
                              subagent_args: Sequence[str] = ()) -> list[str]:
        """SESSION 역할 실행 argv — capability·model·subagents 조립(§9 811).
        역할 시스템 프롬프트 전달은 플랫폼별이다: Claude는 `--append-system-prompt`
        argv로 싣고, Codex는 `-p <role>` 프로파일이 고르는 외부 역할 아티팩트로
        전달한다(argv에 직접 싣지 않음, Phase 3 물질화·handoff §6).
        build_launch_command를 대체."""

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
