# 어댑터 계약 매트릭스 (Phase 5)

> 이 문서는 플랫폼 차이만이 아니라 **agent runner 어댑터의 계약**을 담는다 —
> 각 플랫폼이 역할·권한을 어떻게 보증하는지(`role_artifacts`·`verify_role_provisioned`·
> `artifact_root`)와 상태·입력·능력의 플랫폼별 동작을 함께 고정한다. 결정 근거는
> ADR-0016(상태판정 훅 전환)·ADR-0017(Codex 역할 전달·역할 아티팩트 보증).
> 범위: **확정** = 단위 테스트로 고정됨. **잠정** = 슬라이스 B(Phase 3 라이브 측정)에서 확정.
> 상태판정은 화면 마커 스캔이 아니라 CLI 훅이 쓴 상태 파일을 읽는 방식이다(핸드오프 §3).

| 항목 | ClaudeCodeAdapter | CodexAdapter | 상태 |
|---|---|---|---|
| name | claude-code | codex | 확정 (test_adapters) |
| config_dir_name | .claude | .codex | 확정 |
| config_dir(workdir) | workdir/.claude | workdir/.codex | 확정 |
| build_session_command(role, workdir, subagent_args) | ["claude"] + capability_args + ["--append-system-prompt", role.system_prompt] + (["--model", hint] if hint) + subagent_args (cwd=workdir로 config 해석) | ["codex", "-p", role.name] + capability_args + (["-m", hint] if hint) + subagent_args | 확정(구조·cwd-only) / 명시 플래그 값 잠정 |
| 세션 역할 프롬프트 전달 | `--append-system-prompt` argv (네이티브·workspace 밖·developer급) | `-p <role>` 프로파일 바인딩(결정적) → 프로파일이 얹는 네이티브 표면(후보 `developer_instructions`); 명세는 `role_artifacts`가 계산·보증, fail-closed는 `verify_role_provisioned` 게이트가 강제, Phase 3는 물질화만 — handoff §6·ADR-0017 | Claude 확정 / Codex `-p` 바인딩·게이트 확정, 표면·계층은 후보(슬라이스 B 실측) |
| format_prompt(t) | t (literal, 개행 없음) | t (literal, 개행 없음) | 확정 (계약) — 제출은 `AgentRunner.submit()`이 별도로 보낸다 |
| submit_key() | "Enter" | "Enter" | 계약(제출은 별도 키 이벤트) 확정 / 키 이름은 잠정 — §8.3 실측 |
| clear_key() | "C-u" | "C-u" | 잠정 — §8.3 라이브 측정으로 확정 (Esc 금지, §4.1) |
| role_artifacts(role, root) | `[]` (역할·권한이 argv·`--agents`에 실려 자립) | `[<role>.config.toml]` — `sandbox_mode`·`developer_instructions`(+`model_hint` 있을 때 `model`)를 파일 최상위 키로; 역할·권한 내용의 단일 진실원 | 확정(구조) / 프로파일 키 이름·계층 잠정(슬라이스 B) |
| verify_role_provisioned(role, root) | `role_artifacts=[]`라 통과 | root의 프로파일 존재+내용 일치 검사(메커니즘), 부재·불일치 시 `RoleNotProvisioned`(fail-closed) | 확정 — `start_session`이 `backend.start` 전 호출; 컨테이너 namespace 일치·프로파일 override 미발생은 Phase 3/슬라이스 B 조건 |
| artifact_root(workdir, env) | `workdir/.claude` (`config_dir`) | `$CODEX_HOME` (env `CODEX_HOME`, 없으면 `~/.codex`) | 확정 — 게이트가 `CODEX_HOME` 기준 검사; 컨테이너 호스트↔컨테이너 파일 일치는 Phase 3 정렬/bind mount |

## 능력 등급 → argv (§2.3.1)

SESSION 역할(Maintainer·Leader)은 이 인자가 세션 argv에 직접 실린다.
SUBAGENT 역할(Developer·Reviewer·Tester)은 세션 argv가 아니라 Claude
`--agents` JSON의 `tools`/`disallowedTools`/`permissionMode` 필드에 실린다
(Codex는 물질화 자체가 Phase 3 — 아래 참고).

| `Capability` | ClaudeCodeAdapter.capability_args | CodexAdapter.capability_args | 상태 |
|---|---|---|---|
| READ_ONLY | `--tools Read,Grep,Glob --permission-mode plan` | `-s read-only` | Claude 잠정 / Codex `-s` 값 확정(--help), 세부 잠정 |
| WRITE_WORKSPACE | `--permission-mode dontAsk` | `-s workspace-write` | Claude 잠정(`--allowedTools`/`--disallowedTools` 세부 미결) / Codex `-s` 값 확정, `.rules` 잠정 |
| HOST_CONTROL | `--permission-mode dontAsk` | `-s danger-full-access` | Claude 잠정(호스트 명령 허용 목록 미결) / Codex `-s` 값 확정, 승인 정책 잠정 |

Claude `prepare_subagents(workdir, roles)`는 `["--agents", <json>]`을 반환한다
— JSON은 `role.name`을 키로, 값은 `description`·`prompt`(+ `model_hint`가
있으면 `model`) 및 위 표의 capability 필드(`tools`/`permissionMode`)를 담는다.
`--agents`의 정확한 스키마는 잠정이다.

Codex `prepare_subagents`는 **빈 목록을 반환한다** — Codex SUBAGENT는 세션
argv에 실리지 않기 때문이다(argv 기여 없음). 각 역할(SESSION·SUBAGENT)의
프로파일 명세는 `role_artifacts`가 계산·보증하고, `$CODEX_HOME` 아래 실제 디스크
물질화(배치·쓰기·권한)는 Phase 3가 한다(`handoff-phase5-runtime-contract.md`
§6, spec §2.3.3). `.rules`(WRITE_WORKSPACE 규칙 파일)의 역할별 의미·본문 계산도
어댑터가 소유하는 게 맞으나 형식이 미확정이라 `role_artifacts`의 향후 확장
대상이다(형식은 슬라이스 B 확정).

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

어휘 정합: 훅은 `SessionStart`에 `idle`을 쓴다. `start`는 `_STATE_MAP`에 남긴 하위호환 별칭으로 `idle`과 함께 `IDLE`로 매핑되므로 훅이 `start`를 써도 동작은 같다. Phase 3는 `SessionStart`에 `idle`을 쓰면 된다.

## Phase 3 백엔드 리스크 (TmuxDockerBackend.send_text)
literal text 주입은 FakeBackend엔 충분하나 tmux엔 미확정 케이스가 있다 — 라이브 검증 필요:
- 멀티라인 prompt, paste(bracketed-paste) 모드
- Enter 키 이벤트 vs literal "\n"
- 셸 이스케이프 / 제어문자

## 검증 방식
- 확정 항목: axdt/agent_runner/tests/의 단위 테스트가 계약을 고정.
- 잠정 항목: Phase 3 슬라이스 B에서 실 CLI를 띄워 ① 훅 상태 파일 전이(어느 훅 이벤트가 어느 상태값을 쓰는지) ② 제출·클리어 키 이벤트 수용 ③ capability argv 수용을 측정해 잠정 셀을 확정하고 이 표를 갱신.
