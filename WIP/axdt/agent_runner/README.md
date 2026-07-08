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
- `send_prompt`는 `IDLE`·`WAITING_INPUT`에서만 허용 (그 외 `RuntimeError`); 호출 전 `wait_until_idle`.
- 의도적 `stop()`은 항상 `STOPPED` (강제 종료의 nonzero exit도 ERROR로 뒤집지 않음).
- 동기 + 폴링 (asyncio 아님). config는 cwd=workdir 기준 해석.

## 네이밍
- 어댑터 클래스: `<Platform>Adapter`. 백엔드: `<Substrate>Backend`. 상태 어휘는 `AgentState`에 고정 (임의 추가 금지 — 변경은 spec 경유).

## 테스트
`cd WIP && py -m pytest axdt/agent_runner -v`
