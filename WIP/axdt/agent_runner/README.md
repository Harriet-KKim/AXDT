# axdt.agent_runner

**목적:** Claude Code·Codex CLI 에이전트 세션을 동일 인터페이스로 구동하는 공통 agent runner 추상 (Phase 5). 설계: `WIP/specs/2026-06-26-phase5-agent-runner-design.md`.

## 구성
- `state.py` — `AgentState` 통제 어휘 (STARTING/IDLE/BUSY/WAITING_INPUT/STOPPED/ERROR).
- `adapters/base.py` — `PlatformAdapter` ABC (플랫폼 고유 지식).
- `adapters/claude_code.py`, `adapters/codex.py` — 두 어댑터.
- `backend.py` — `SessionBackend` ABC + 테스트용 `FakeBackend`. Phase 3가 `TmuxDockerBackend` 추가.
- `runner.py` — `AgentRunner` (adapter + backend 합성, 동기·폴링 라이프사이클).
- `PLATFORM_MATRIX.md` — 플랫폼별 동작 차이 검증 매트릭스.
- `tests/` — 계약 고정 단위 테스트.

## 핵심 계약
- 합성: `AgentRunner(adapter, backend)`. substrate는 주입 (tmux/Docker는 Phase 3).
- `read_output`/`poll_state`는 **모니터링·liveness 전용** — 작업 결과의 권위는 report 파일 (ADR-0003). runner는 stdout을 결과로 파싱하지 않는다.
- `format_prompt`는 리터럴 본문만 돌려준다(제출 개행 없음); 제출 키는 `AgentRunner.submit()`이 별도로 보낸다.
- `send_prompt`는 `IDLE` 단독에서만 허용 (그 외 `RuntimeError`) — 제출이 붙었으므로 `WAITING_INPUT`에서 받으면 권한 프롬프트를 자동 승인하게 된다. 호출 전 `wait_until_idle`.
- CLI(`maintainer send`/`leader send`)가 쓰는 안전한 주입 경로는 `send_when_idle(text)` — 재폴링이 IDLE일 때만 `clear_input` → `send_text` → `submit` 하고 `True`, 아니면 예외 없이 `False`.
- 역할 정체성: Claude는 `--append-system-prompt` argv로 전달하고, Codex는 전용 플래그가 없어 `send_role_bootstrap()`이 `role.system_prompt`를 세션 기동 후 **독립 첫 주입**으로 심는다. `leader.up`이 IDLE 도달 후·attach 주입 이전에 호출한다(`up`과 `send`는 별도 프로세스라 attach 런너엔 role이 없다 — attach는 부트스트랩 완료를 가정). Codex 라이브 세션·실제 호출 배선은 Phase 3.
- 의도적 `stop()`은 항상 `STOPPED` (강제 종료의 nonzero exit도 ERROR로 뒤집지 않음).
- 동기 + 폴링 (asyncio 아님). config는 cwd=workdir 기준 해석.

## 네이밍
- 어댑터 클래스: `<Platform>Adapter`. 백엔드: `<Substrate>Backend`. 상태 어휘는 `AgentState`에 고정 (임의 추가 금지 — 변경은 spec 경유).

## 테스트
`cd WIP && py -m pytest axdt/agent_runner -v`
