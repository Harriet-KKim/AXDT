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

**report 경로 소유권:** `AgentRunner`는 report 파일 경로·세션 메타데이터를 **소유하지 않는다.** report 위치 지정·생성은 **오케스트레이션/Maintainer 층(Phase 8)** 의 책임이며, 필요 시 prompt 내용에 담겨 `send_prompt`로 전달될 뿐이다. runner는 stdout을 결과로 파싱하지 않는다(테스트로 고정 — §6).

### 2.4 동기 + 폴링 모델
전 시스템이 tmux/파일/폴링 기반(asyncio 아님)이므로 runner도 **동기 + 폴링**으로 둔다. 블로킹 편의는 primitive 위에 얹은 `wait_until_idle(timeout)` **하나만** 제공하고, 폴링을 완전히 은닉하는 blocking run은 만들지 않는다.

`_transcript`는 Phase 5에선 전량 보관(테스트·디버그 용이). 장기 세션의 무한 증가 대비 **향후 max-size/log-sink 옵션**은 Phase 3+에서 추가하되, `detect_state`는 항상 **유계 꼬리 윈도**에만 적용한다.

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
        """에이전트 CLI 세션을 띄우는 argv. config_dir = workdir/config_dir_name 을 가리키는 플래그 포함."""

    @abstractmethod
    def format_prompt(self, text: str) -> str:
        """주입용 prompt 렌더. 반환값은 send_text에 그대로 넘길 literal text(제출 개행 포함)."""

    @abstractmethod
    def detect_state(self, recent_output: str) -> "AgentState | None":
        """ANSI/제어문자 정규화된 꼬리 윈도에서 상태를 추론. 불확정이면 None(→ runner가 직전 상태 유지)."""

class SessionBackend(ABC):
    """실행 substrate. Phase 3=TmuxDockerBackend, 지금=FakeBackend."""
    @abstractmethod
    def start(self, command: list[str], cwd: Path,
              env: Mapping[str, str] | None = None) -> None:
        """세션 기동. **런타임 기동 실패(command-not-found 등)는 raise하지 않고** is_alive()=False + last_error()로 표면화(→ poll_state가 ERROR). 동기적으로 못 띄우는 경우만 예외 가능."""
    @abstractmethod
    def send_text(self, text: str) -> None:
        """literal text 주입(format_prompt 결과 그대로). 터미널 키이벤트 뉘앙스는 백엔드 책임(§4 리스크)."""
    @abstractmethod
    def read_new_output(self) -> str:
        """마지막 read 이후의 증분 출력. (runner의 _drain만 호출)"""
    @abstractmethod
    def is_alive(self) -> bool: ...
    @abstractmethod
    def exit_code(self) -> "int | None":
        """종료 코드. 미종료=None, 정상=0, 실패=≠0. (clean stop vs crash 구분용)"""
    @abstractmethod
    def last_error(self) -> "str | None":
        """start 실패/I-O 오류 메시지. 없으면 None."""
    @abstractmethod
    def stop(self) -> None:
        """멱등. 이미 정지면 no-op."""

class AgentRunner:
    """공통 agent runner 인터페이스 = adapter + backend 합성체.
    내부 상태: _transcript(누적 전체), _read_cursor(read_output 전달 위치),
    _last_state, _stop_requested(stop() 의도적 종료 표식)."""
    INPUT_ACCEPTING = {AgentState.IDLE, AgentState.WAITING_INPUT}   # send_prompt 허용 상태
    def __init__(self, adapter: PlatformAdapter, backend: SessionBackend): ...
    def start_session(self, workdir: Path,
                      env: Mapping[str, str] | None = None) -> None: ...
    def send_prompt(self, text: str) -> None: ...   # 현재 상태 ∉ INPUT_ACCEPTING 이면 RuntimeError
    def read_output(self) -> str: ...               # _drain 후 transcript[_read_cursor:] 반환·커서 전진
    def poll_state(self) -> AgentState: ...
    def wait_until_idle(self, timeout: float,
                        poll_interval: float = 0.5) -> AgentState: ...
    def stop(self) -> None: ...                     # 멱등
    @property
    def transcript(self) -> str: ...                # 누적 출력 전체(읽기 전용)
```

### 동작 규약 (요약)
- **단일 drain + 별도 커서 규칙:** `backend.read_new_output()`(증분)은 runner 내부 `_drain()` **한 곳에서만** 호출해 `_transcript`에 누적한다. `read_output`과 `poll_state`는 둘 다 `_drain()`을 거치되, **`read_output` 전용 `_read_cursor`** 로 전달 위치를 따로 추적한다 → `poll_state()`가 먼저 drain해도 이후 `read_output()`은 `_transcript[_read_cursor:]` 를 반환하므로 출력을 잃지 않는다. `poll_state`는 커서를 전진시키지 않는다.
- `start_session(workdir)` → `backend.start(adapter.build_launch_command(workdir), workdir, env)`, 상태 `STARTING`. 재호출(이미 기동)·정지 후 기동은 `RuntimeError`.
- `send_prompt(text)` → `backend.send_text(adapter.format_prompt(text))`. **선조건:** 현재 상태가 `INPUT_ACCEPTING`(=`IDLE`·`WAITING_INPUT`)이 아니면 `RuntimeError`. 즉 `STARTING`/`BUSY`/`STOPPED`/`ERROR`에서의 주입은 거부 — 호출자는 먼저 `wait_until_idle`로 준비 상태를 확인한다(첫 prompt도 동일: start_session 직후 idle 도달 후 주입).
- `read_output()` → `_drain()` 후 `_transcript[_read_cursor:]` 반환하고 커서를 끝으로 전진. 미기동 시 빈 문자열.
- `poll_state()` → `_drain()` 후:
  - **`_stop_requested`(stop() 호출됨)이면 무조건 `STOPPED`** (의도적 종료는 exit 코드/시그널과 무관하게 clean — BUSY 중 강제 stop이 nonzero exit을 내도 ERROR로 뒤집지 않는다).
  - 아니고 `is_alive()`가 False면 → `last_error()` 있거나 `exit_code() not in (None, 0)` 이면 **`ERROR`**, 아니면 **`STOPPED`** (예기치 않은 실패와 정상종료 구분).
  - 살아있으면 → 꼬리 윈도(ANSI 정규화)에 `adapter.detect_state` 적용. **`None`(불확정)이면 직전 상태(`_last_state`) 유지.**
- `wait_until_idle(timeout)` → `poll_state`를 `poll_interval` 간격으로 반복, `IDLE`/`WAITING_INPUT`/`ERROR` 또는 timeout 시 마지막 상태 반환.
- `stop()` → `_stop_requested=True` 설정 후 `backend.stop()`(멱등), 상태 `STOPPED`. 이후 `poll_state`도 항상 `STOPPED`.

---

## 4. 어댑터 (호출 규약 구현)

| 항목 | ClaudeCodeAdapter | CodexAdapter |
|---|---|---|
| `name` | `claude-code` | `codex` |
| `config_dir_name` | `.claude` | `.codex` |
| `config_dir` (해석) | `workdir / ".claude"` | `workdir / ".codex"` |
| `build_launch_command` | `["claude", ...]` (위 config_dir·workdir 지정 플래그) | `["codex", ...]` (동등) |
| `format_prompt` | 텍스트 + 제출 개행 (literal) | 텍스트 + 제출 개행 (literal) |
| `detect_state` | ANSI 정규화 꼬리 윈도 → AgentState/None | 동등 |

> **확정 항목**: config_dir = `workdir/config_dir_name`, format_prompt는 literal text 반환, detect_state는 유계 꼬리 윈도 + 불확정시 None.
> **Phase 3 라이브 검증 확정(provisional)**: 정확한 CLI 플래그, idle/busy/waiting 출력 마커, 그리고 **tmux 제출 뉘앙스**(멀티라인 prompt, paste 모드, Enter 키 vs literal `\n`, 셸 이스케이프, 제어문자) — 이는 `TmuxDockerBackend.send_text` 책임으로 `PLATFORM_MATRIX.md`에 리스크로 기재한다.

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

- **test_adapters**: `build_launch_command` argv(claude vs codex), `config_dir`=`workdir/config_dir_name`, `format_prompt` 출력, `detect_state` 샘플 출력 → 상태 매핑, **불확정 출력 → `None`**.
- **test_runner** (FakeBackend 사용):
  - 라이프사이클: `start_session → send_prompt → read_output → poll_state → stop`.
  - `read_output` 증분 누적 + `transcript` 일치.
  - **커서 독립성(#1)**: `poll_state()` 먼저 호출해도 이어진 `read_output()`이 새 출력을 반환.
  - **실패 구분(#2)**: start 실패/`exit_code≠0`/`last_error` → `poll_state`가 `ERROR`; 정상 종료(exit 0) → `STOPPED`.
  - **detect_state 불확정(#3)**: `None` 반환 시 직전 상태 유지.
  - **선조건(#8)**: 미기동 `send_prompt`→`RuntimeError`, 정지 후 `send_prompt`→`RuntimeError`, `start` 재호출→`RuntimeError`, `stop` 멱등, 미기동 `read_output`→빈 문자열.
  - **send 허용 상태(R2-2)**: `STARTING`/`BUSY` 상태에서 `send_prompt`→`RuntimeError`; `IDLE`·`WAITING_INPUT`에서는 성공.
  - **stop 정규화(R2-1)**: `BUSY` 중 `stop()` 후 backend가 nonzero `exit_code`를 보고해도 `poll_state`는 `ERROR`가 아니라 `STOPPED`.
  - **start 실패 거동(R2-3)**: backend가 기동 실패를 `is_alive()=False`+`last_error()`로 보고(예외 아님) → `poll_state`가 `ERROR`.
  - **결과 비권위(#4)**: stdout 텍스트가 권위 결과로 취급되지 않음(runner는 결과 파싱 안 함).
  - `wait_until_idle`: (a) idle 마커 → `IDLE`, (b) 미도달 → timeout 후 마지막 상태.
- **test_state**: 어휘 안정성(역할/매핑이 깨지지 않는지).

`FakeBackend`는 큐에 스크립트된 출력·종료코드·오류를 넣고 `send_text`/`start` 인자(command·cwd·env)를 기록해, substrate 없이 결정적으로 검증한다.

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

---

## 9. Codex 리뷰 반영 (2026-06-26)
Codex 설계 리뷰를 받아 반영함:
- **#1** read_output 전용 `_read_cursor` 분리 — drain과 전달 위치를 분리해 출력 잠식 제거.
- **#2** `SessionBackend.exit_code()`/`last_error()` 추가 — 실패=ERROR, 정상종료=STOPPED 구분.
- **#3** `detect_state -> AgentState | None` — 불확정시 직전 상태 유지, ANSI 정규화·꼬리 윈도 명시.
- **#4** report 경로 소유권을 오케스트레이션 층으로 명시, stdout 비권위 테스트 추가.
- **#5** (부분) prompt 제출은 literal text 계약 유지 + tmux 키이벤트 뉘앙스를 Phase 3 백엔드 리스크로 기재.
- **#6** `config_dir = workdir/config_dir_name` 확정.
- **#7/#8/#9** 테스트 확장(커서·실패·선조건·비권위), 라이프사이클 선조건(RuntimeError·멱등), transcript 무한증가 주석.

**라운드2 (상태머신 갭 3건):**
- **R2-1** `_stop_requested` 도입 — 의도적 `stop()`은 exit 코드/시그널과 무관히 `STOPPED`(BUSY 중 강제 stop이 ERROR로 뒤집히던 문제 제거).
- **R2-2** `send_prompt` 허용 상태를 `INPUT_ACCEPTING`(IDLE·WAITING_INPUT)로 명시, 그 외 RuntimeError.
- **R2-3** `start()` 런타임 기동 실패는 비-raise + `is_alive()=False`/`last_error()`로 표면화(=poll_state ERROR), 선조건 위반만 RuntimeError. 각 항목 테스트 추가.

> **참조 파일 주의(#10):** 이 spec이 인용한 `WIP/adr/0003`, `WIP/TODO.md` 등은 현재 worktree 브랜치엔 없다(초기 커밋이 README만 포함). 메인 체크아웃엔 untracked로 존재. `WIP/adr/0005`는 본 Phase 5 구현 산출물로 신규 작성 예정. → 참조 정합성은 **기존 설계 파일 커밋 여부(사용자 결정)** 와 연동.
