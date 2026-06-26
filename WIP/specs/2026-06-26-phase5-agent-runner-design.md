# Phase 5 — 멀티 플랫폼 Agent 지원: agent runner 추상화 설계

> 상태: **승인됨 (브레인스토밍 합의)** · 작성일 2026-06-26 · 범위: Phase 5 (WIP/TODO.md)
> 산출 깊이: **인터페이스 + 테스트 골격** (실제 프로세스 기동은 mock/stub, 단위 테스트로 계약 고정)
> 관련 결정: D4(공통 인터페이스 + Claude·Codex 둘 다), D9(Python), D12(AXDT 자체 코드는 `WIP/`)
> 관련 ADR: `WIP/adr/0003-agent-communication-model.md`, (신규) `WIP/adr/0005-agent-runner-composition-and-injected-backend.md`

---

## 1. 목표와 비목표

### 목표
- AXDT가 Claude Code·Codex 두 플랫폼의 CLI 에이전트 세션을 **동일한 인터페이스**로 구동할 수 있게 하는 **공통 agent runner 추상**을 정의한다.
- 두 플랫폼 어댑터(`ClaudeCodeAdapter`, `CodexAdapter`)의 **호출 규약**을 구현한다.
- 실제 tmux/Docker substrate(Phase 3) 없이도 **단위 테스트로 계약을 고정**한다.
- 플랫폼별 동작 차이를 **검증 매트릭스 문서**로 남긴다.

### 비목표 (이 Phase에서 하지 않음)
- 실제로 살아있는 Claude Code/Codex 프로세스를 끝까지 구동(→ Phase 3의 `TmuxDockerBackend`가 채움).
- `.claude/`·`.codex/`의 **의미 있는 skills/hooks/settings 내용 작성**(역할 정의가 없는 단계 → Phase 2로 미룸).
- 역할(Maintainer/Leader/…) 프롬프트, worktree 프로비저닝, Docker 격리(→ Phase 2·3).

---

## 2. 핵심 설계 결정

### 2.1 구조 — 상속이 아니라 **3축 합성** (Runner = Adapter + Backend)
플랫폼별 `ClaudeCodeRunner`/`CodexRunner`로 **상속**하지 않고, `AgentRunner`가 **`PlatformAdapter`와 `SessionBackend`를 합성**한다.

**근거:** `start → inject prompt → read output → stop` 라이프사이클은 플랫폼과 무관하게 동일하다. 플랫폼 차이는 두 가지로 좁혀진다.
1. *무엇을 어떻게 띄우고, prompt/출력을 어떻게 포맷·파싱하는가* → **PlatformAdapter**.
2. *어디서 실행되는가(로컬/tmux/Docker)* → **SessionBackend**.

상속 구조는 동일한 라이프사이클을 플랫폼 수만큼 중복시킨다. 합성은 라이프사이클을 1곳에 두고 변하는 축만 갈아 끼운다. → `WIP/adr/0005`.

### 2.2 실행 substrate는 **주입되는 SessionBackend로 분리**
runner는 tmux/Docker를 **직접 소유하지 않는다.** `SessionBackend` 인터페이스로 추상화해 주입한다.
- Phase 3가 `TmuxDockerBackend`(tmux `send-keys` + worktree 컨테이너)를 구현.
- Phase 5(지금)는 `FakeBackend`(인메모리·스크립트형)로 계약을 테스트.

**근거:** Phase 5를 substrate-독립적이고 테스트 가능하게 유지한다. tmux/Docker 호출을 runner 내부에 박으면 계약 경계가 흐려지고 mock하려면 monkeypatch가 필요해진다.

### 2.3 `read_output`은 **권위 결과 채널이 아니다**
`ADR-0003`상 **Leader → Maintainer 권위 채널은 report 파일**이다. 따라서 runner의 `read_output`/`poll_state`는 **모니터링·liveness·readiness 감지**용이다 — 세션 생존 여부, 에이전트가 idle/입력대기 상태인지, 디버그용 transcript 캡처. **작업 결과의 진실은 report에서 읽는다.** (이 구분을 어기면 ADR-0004 권위 흐름과 모순.)

### 2.4 동기 + 폴링 모델
전 시스템이 tmux/파일/폴링 기반(asyncio 아님)이므로 runner도 **동기 + 폴링**으로 둔다. 블로킹 편의는 primitive 위에 얹은 `wait_until_idle(timeout)` **하나만** 제공하고, 폴링을 완전히 은닉하는 blocking run은 만들지 않는다.

### 2.5 `.claude/`·`.codex/` 구성 범위
역할(Phase 2)이 없으면 의미 있는 skills/hooks를 작성할 수 없다. 그래서 어댑터는 **config 디렉터리 경로(`config_dir_name`)만 알고 CLI를 거기 가리키게** 하고, **실제 config 내용 작성은 Phase 2로 미룬다.** 빈 디렉터리를 미리 양산하지 않는다.

---

## 3. 인터페이스 contract

```python
from enum import Enum
from pathlib import Path
from abc import ABC, abstractmethod
from collections.abc import Mapping

class AgentState(Enum):
    """통제된 상태 어휘. adapter.detect_state가 출력 → 이 어휘로 매핑."""
    STARTING = "starting"
    IDLE = "idle"               # prompt 받을 준비됨
    BUSY = "busy"               # 처리 중
    WAITING_INPUT = "waiting_input"   # 사용자/상위 입력 대기
    STOPPED = "stopped"
    ERROR = "error"

class PlatformAdapter(ABC):
    """플랫폼(Claude Code / Codex) 고유 지식."""
    name: str                   # "claude-code" | "codex"
    config_dir_name: str        # ".claude" | ".codex"

    @abstractmethod
    def build_launch_command(self, workdir: Path) -> list[str]:
        """에이전트 CLI 세션을 띄우는 argv."""

    @abstractmethod
    def format_prompt(self, text: str) -> str:
        """주입용 prompt 렌더(제출키/개행 처리 등)."""

    @abstractmethod
    def detect_state(self, recent_output: str) -> AgentState:
        """최근 출력에서 상태를 추론."""

class SessionBackend(ABC):
    """실행 substrate. Phase 3=TmuxDockerBackend, 지금=FakeBackend."""
    @abstractmethod
    def start(self, command: list[str], cwd: Path,
              env: Mapping[str, str] | None = None) -> None: ...
    @abstractmethod
    def send_text(self, text: str) -> None: ...
    @abstractmethod
    def read_new_output(self) -> str:
        """마지막 read 이후의 증분 출력."""
    @abstractmethod
    def is_alive(self) -> bool: ...
    @abstractmethod
    def stop(self) -> None: ...

class AgentRunner:
    """공통 agent runner 인터페이스 = adapter + backend 합성체."""
    def __init__(self, adapter: PlatformAdapter, backend: SessionBackend): ...
    def start_session(self, workdir: Path,
                      env: Mapping[str, str] | None = None) -> None: ...
    def send_prompt(self, text: str) -> None: ...
    def read_output(self) -> str: ...          # transcript 누적
    def poll_state(self) -> AgentState: ...
    def wait_until_idle(self, timeout: float,
                        poll_interval: float = 0.5) -> AgentState: ...
    def stop(self) -> None: ...
    @property
    def transcript(self) -> str: ...           # 누적 출력 전체
```

### 동작 규약 (요약)
- **단일 drain 규칙:** `backend.read_new_output()`(증분)은 runner 내부 `_drain()` **한 곳에서만** 호출해 `transcript`에 누적한다. `read_output`과 `poll_state`는 모두 `_drain()`을 거치므로 증분을 서로 잠식하지 않는다. `detect_state`는 `transcript`의 **꼬리 윈도(최근 N자)** 에 적용한다.
- `start_session(workdir)` → `backend.start(adapter.build_launch_command(workdir), workdir, env)`, 상태 `STARTING`.
- `send_prompt(text)` → `backend.send_text(adapter.format_prompt(text))`.
- `read_output()` → `_drain()` 호출 후, **이번 호출에서 새로 누적된 증분**을 반환.
- `poll_state()` → `_drain()` 후, `is_alive()` 가 False면 `STOPPED`; 아니면 transcript 꼬리 윈도에 `adapter.detect_state` 적용.
- `wait_until_idle(timeout)` → `poll_state`를 `poll_interval` 간격으로 반복, `IDLE`/`WAITING_INPUT`/`ERROR` 또는 timeout 시 반환.
- `stop()` → `backend.stop()`, 상태 `STOPPED`.

---

## 4. 어댑터 (호출 규약 구현)

| 항목 | ClaudeCodeAdapter | CodexAdapter |
|---|---|---|
| `name` | `claude-code` | `codex` |
| `config_dir_name` | `.claude` | `.codex` |
| `build_launch_command` | `["claude", ...]` (config·workdir 지정 플래그) | `["codex", ...]` (동등) |
| `format_prompt` | 텍스트 + 제출 개행 | 텍스트 + 제출 개행 |
| `detect_state` | 출력 마커 → AgentState | 출력 마커 → AgentState |

> 실제 CLI 플래그·출력 마커는 **Phase 3 라이브 검증 시 확정** 항목으로 매트릭스에 표시한다. 지금은 합리적 기본값 + 단위 테스트로 계약을 고정한다.

---

## 5. 패키지 레이아웃 (D12 → `WIP/`)

```
WIP/
  pyproject.toml                       # 패키지 루트=WIP, pytest 설정
  axdt/
    __init__.py
    agent_runner/
      __init__.py
      state.py            # AgentState
      backend.py          # SessionBackend(ABC) + FakeBackend
      runner.py           # AgentRunner
      adapters/
        __init__.py
        base.py           # PlatformAdapter(ABC)
        claude_code.py    # ClaudeCodeAdapter
        codex.py          # CodexAdapter
      PLATFORM_MATRIX.md  # 산출물: 플랫폼별 동작 차이 검증 매트릭스
      README.md           # D11: 목적·구성·네이밍
      tests/
        __init__.py
        test_state.py
        test_adapters.py
        test_runner.py
```

---

## 6. 테스트 (계약 고정)

- **test_adapters**: `build_launch_command` argv(claude vs codex), `config_dir_name`, `format_prompt` 출력, `detect_state` 샘플 출력 → 상태 매핑.
- **test_runner** (FakeBackend 사용):
  - 라이프사이클: `start_session → send_prompt → read_output → poll_state → stop`.
  - `read_output` 증분 누적 + `transcript` 일치.
  - `wait_until_idle`: (a) FakeBackend가 idle 마커를 내면 `IDLE` 반환, (b) 안 내면 timeout 후 마지막 상태 반환.
  - `is_alive`=False → `poll_state`가 `STOPPED`.
- **test_state**: 어휘 안정성(역할/매핑이 깨지지 않는지).

`FakeBackend`는 큐에 스크립트된 출력을 넣고 `send_text` 기록을 보관해, substrate 없이 결정적으로 검증한다.

---

## 7. 산출물 체크리스트 (TODO Phase 5 매핑)

- [ ] 공통 agent runner 인터페이스 정의 → `runner.py`, `backend.py`, `state.py`, `adapters/base.py`
- [ ] `.claude/` 구성 + Claude Code 어댑터 → `adapters/claude_code.py` (config 경로 참조, 내용은 Phase 2)
- [ ] `.codex/` 구성 + Codex 어댑터 → `adapters/codex.py` (동등)
- [ ] 플랫폼별 동작 차이 검증 매트릭스 → `PLATFORM_MATRIX.md`
- [ ] ADR 기록 → `WIP/adr/0005-...md`
- [ ] 단위 테스트 + `pyproject.toml`

---

## 8. Phase 6 와의 접합 (다음 단계 미리보기)
Phase 6(Git 호스트 연동)은 같은 **합성·주입 패턴**을 재사용한다: `GitHostAdapter`(GitHub/GitLab/Forgejo) + 공통 호스트 인터페이스(PR 생성/리뷰/머지). Phase 5의 어댑터 패턴이 검증되면 Phase 6은 그 형판을 따른다. (별도 spec로 진행)
