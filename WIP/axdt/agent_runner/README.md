# axdt.agent_runner

**목적:** Claude Code·Codex CLI 에이전트 세션을 동일 인터페이스로 구동하는 공통 agent runner 추상 (Phase 5). 현행 계약: `WIP/adr/0016-hook-based-state-detection.md`·`WIP/adr/0017-codex-role-via-profile-binding.md`·`PLATFORM_MATRIX.md`·`WIP/handoff-phase5-runtime-contract.md`. 초기 설계 `WIP/specs/2026-06-26-phase5-agent-runner-design.md`는 슬라이스 A 재설계 전 문서다(상태판정·인터페이스는 위 현행 계약이 우선).

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
- 역할 정체성: Claude는 `--append-system-prompt` argv(네이티브·workspace 밖)로 전달한다. Codex는 `build_session_command`이 `-p <role.name>`으로 역할↔프로파일을 바인딩하고, `role_artifacts`가 그 프로파일(역할 프롬프트·권한)을 계산해 역할·권한 내용의 단일 진실원이 된다. 부재·불일치 시 기동 거부(fail-closed)는 `verify_role_provisioned` 게이트가 강제하며 `start_session`이 `backend.start` 전에 `artifact_root`(Codex는 `$CODEX_HOME`) 기준으로 호출한다. Phase 3는 명세를 물질화만 한다. 정확한 프로파일 표면(후보 `developer_instructions`)·계층은 슬라이스 B 실측(handoff §6·ADR-0017). 역할 규범(책임·권한)의 SoT는 `docs/sot/rule/role-responsibilities.md`, 프롬프트 문구의 정본은 `roles/prompts/<role>.md`다(roles/spec.py 계층).
- 의도적 `stop()`은 항상 `STOPPED` (강제 종료의 nonzero exit도 ERROR로 뒤집지 않음).
- 동기 + 폴링 (asyncio 아님). config는 cwd=workdir 기준 해석.

## 네이밍
- 어댑터 클래스: `<Platform>Adapter`. 백엔드: `<Substrate>Backend`. 상태 어휘는 `AgentState`에 고정 (임의 추가 금지 — 변경은 spec 경유).

## 테스트
`cd WIP && py -m pytest axdt/agent_runner -v`
