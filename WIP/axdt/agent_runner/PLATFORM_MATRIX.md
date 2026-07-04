# 플랫폼별 동작 차이 검증 매트릭스 (Phase 5)

> 범위: agent runner 어댑터의 플랫폼 차이. **확정** = 단위 테스트로 고정됨.
> **provisional** = Phase 3 TmuxDockerBackend 라이브 검증 시 확정.

| 항목 | ClaudeCodeAdapter | CodexAdapter | 상태 |
|---|---|---|---|
| name | claude-code | codex | 확정 (test_adapters) |
| config_dir_name | .claude | .codex | 확정 |
| config_dir(workdir) | workdir/.claude | workdir/.codex | 확정 |
| build_launch_command | ["claude"] (cwd=workdir로 config 해석) | ["codex"] | 확정(cwd-only) / 명시 플래그 provisional |
| format_prompt(t) | t + "\n" (literal) | t + "\n" (literal) | 확정 (계약) / 제출 키 provisional |
| ERROR 마커 | fatal:, Error: | stream error: | provisional |
| WAITING_INPUT 마커 | Do you want to proceed? | Allow command? [y/N] | provisional |
| BUSY 마커 | Esc to interrupt | ctrl-c to interrupt | provisional |
| IDLE 마커 | "\n> " | "\n› " | provisional |

## Phase 3 백엔드 리스크 (TmuxDockerBackend.send_text)
literal text 주입은 FakeBackend엔 충분하나 tmux엔 미확정 케이스가 있다 — 라이브 검증 필요:
- 멀티라인 prompt, paste(bracketed-paste) 모드
- Enter 키 이벤트 vs literal "\n"
- 셸 이스케이프 / 제어문자
- 정확한 idle/busy/waiting 출력 마커 (ANSI 포함 실제 캡처로 보정)

## 검증 방식
- 확정 항목: axdt/agent_runner/tests/의 단위 테스트가 계약을 고정.
- provisional 항목: Phase 3에서 실제 CLI 출력 캡처로 마커/플래그를 보정하고 이 표를 갱신.
