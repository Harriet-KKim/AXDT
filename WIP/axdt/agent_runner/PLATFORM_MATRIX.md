# 플랫폼별 동작 차이 검증 매트릭스 (Phase 5)

> 범위: agent runner 어댑터의 플랫폼 차이. **확정** = 단위 테스트로 고정됨.
> **잠정** = 슬라이스 B(Phase 3 라이브 측정)에서 확정.
> 상태판정은 화면 마커 스캔이 아니라 CLI 훅이 쓴 상태 파일을 읽는 방식이다(§3).

| 항목 | ClaudeCodeAdapter | CodexAdapter | 상태 |
|---|---|---|---|
| name | claude-code | codex | 확정 (test_adapters) |
| config_dir_name | .claude | .codex | 확정 |
| config_dir(workdir) | workdir/.claude | workdir/.codex | 확정 |
| build_launch_command | ["claude"] (cwd=workdir로 config 해석) | ["codex"] | 확정(cwd-only) / 명시 플래그 잠정 |
| format_prompt(t) | t + "\n" (literal) | t + "\n" (literal) | 확정 (계약) / 제출 키 잠정 |

## 훅 이벤트 → 상태

상태 파일에 훅이 쓰는 값(`start`·`busy`·`idle`·`waiting`)은 `PlatformAdapter.detect_state`가 `AgentState`로 매핑한다(양 CLI 공통 매핑, base.py). 아래는 어느 훅 이벤트가 어느 값을 쏘는지의 매트릭스다.

| 훅 이벤트 | 상태값 | 상태 |
|---|---|---|
| `SessionStart` | `idle` | claude 실측 확정 / codex 미확정(matcher) — 잠정 |
| `UserPromptSubmit` | `busy` | 양 CLI 실측 확정 |
| `Stop` | `idle` | claude 실측 확정 / codex 미확정 — 잠정 |
| `Pre/PostToolUse` | `busy`(하트비트) | 미확정 — 잠정 |
| `Notification` | `waiting` | 미확정 — 잠정 |
| (훅 아님) 프로세스 사망 | — | `ERROR`/`STOPPED`는 훅이 아니라 `is_alive()`·`exit_code()`·`last_error()`로 판정 |

잠정 표기 행은 슬라이스 B(Phase 3, 실 CLI 라이브 측정)로 확정되기 전까지의 임시 값이다.

## Phase 3 백엔드 리스크 (TmuxDockerBackend.send_text)
literal text 주입은 FakeBackend엔 충분하나 tmux엔 미확정 케이스가 있다 — 라이브 검증 필요:
- 멀티라인 prompt, paste(bracketed-paste) 모드
- Enter 키 이벤트 vs literal "\n"
- 셸 이스케이프 / 제어문자
- 정확한 idle/busy/waiting 출력 마커 (ANSI 포함 실제 캡처로 보정)

## 검증 방식
- 확정 항목: axdt/agent_runner/tests/의 단위 테스트가 계약을 고정.
- provisional 항목: Phase 3에서 실제 CLI 출력 캡처로 마커/플래그를 보정하고 이 표를 갱신.
