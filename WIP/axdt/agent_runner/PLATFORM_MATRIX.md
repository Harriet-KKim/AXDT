# 어댑터 계약 매트릭스 (Phase 5)

> 이 문서는 플랫폼 차이만이 아니라 **agent runner 어댑터의 계약**을 담는다 —
> 각 플랫폼이 역할·권한을 어떻게 보증하는지(`role_artifacts`·`verify_role_provisioned`·
> `artifact_root`)와 상태·입력·능력의 플랫폼별 동작을 함께 고정한다. 결정 근거는
> ADR-0016(상태판정 훅 전환)·ADR-0017(Codex 역할 전달·역할 아티팩트 보증).
> 범위: **확정** = 단위 테스트로 고정됨. **잠정** = 슬라이스 B(Phase 3 라이브 측정)에서 확정.
> 상태판정은 화면 마커 스캔이 아니라 CLI 훅이 쓴 상태 파일을 읽는 방식이다(아래 '상태 파일 계약' 절).

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

## 상태 파일 계약

상태판정 훅(쓰는 쪽 — Phase 3가 이미지에 굽는다)과 `poll_state`(읽는 쪽 — `agent_runner`가 구현)가 공유하는 파일 계약이다. 정본은 이 절이고, ADR-0016·이 문서 머리말은 이 절을 가리킨다. 양쪽 구현은 이 절 하나에 맞춘다.

| 항목 | 계약 | 상태 |
|---|---|---|
| 경로 | 환경변수 `AXDT_STATE_FILE`이 절대경로를 지정한다. Phase 3가 이미지에서 이 변수를 설정하고, 그 경로가 컨테이너·호스트 양쪽에서 접근 가능하게 보장한다(컨테이너 HOME·tmpfs 위치 결정과 연동 — Phase 3). 경로를 환경변수로 둬서 그 위치 결정과 분리한다. | 확정(변수명·역할) / 실제 경로값은 Phase 3 배선 |
| 형식 | 한 줄 JSON: `{"state": "<상태>", "ts": <epoch 초, 소수 포함>}`. `<상태>`는 `starting`·`idle`·`busy`·`waiting_input` 중 하나로, 값이 그대로 `AgentState.value`다(항등 매핑, `_STATE_MAP`, ADR-0019). `starting`은 엔트리포인트 seed가 쓰고(ADR-0018), 나머지는 훅이 쓴다. `stopped`·`error`는 상태 파일에 안 실린다 — 프로세스 생존으로 판정(ADR-0016). | 확정 |
| 원자적 쓰기 | 훅 명령은 임시 파일에 쓴 뒤 같은 파일시스템 안에서 `mv`(원자적 rename)로 대상에 놓는다. 부분 기록을 읽는 경합을 없앤다. | 확정(계약) |
| 순서·최신성 | 읽는 쪽은 `ts`로 최신성을 판단한다 — 더 큰 `ts`가 더 최근. `mv`가 last-write-wins를 주므로 근접한 두 전이는 나중 것이 남는다. | `ts` 필드 존재 확정 / 순서 판정 사용은 잠정(아래) |

### 순서·역행 정책 — 슬라이스 B 확정

`poll_state`는 지금 `ts`를 읽어 저장만 하고 최신성·순서 판정에는 쓰지 않는다. 역행(뒤로 간 `ts`) 무시 가드를 단독으로 넣으면 뒤로 간 시계에 세션이 BUSY로 고착하는 엣지가 열리고, 이 엣지는 age 기반 stuck 감지로만 풀린다. 따라서 순서 가드와 age 정책은 한 몸으로 착지한다. 같은 age 정책이 STARTING 고착도 다룬다 — seed됐지만 `SessionStart`가 미발화하면 `starting`에 머무는데, `busy` 하트비트는 STARTING 중엔 안 뛰므로 이 고착은 seed `ts` 기준 최대 지속시간을 넘길 때 `ERROR`로 봐야 잡힌다(ADR-0018). 슬라이스 B가 다음 순서로 이 정책을 닫는다.

1. **측정.** 실 CLI·훅으로 상태 파일을 쓰게 하고 ⓐ 훅 시계가 단조 증가하는지(연속 전이의 `ts`가 항상 커지는지) ⓑ `ts` 해상도가 같은 틱 안 다중 이벤트를 가르는지 ⓒ `busy` 하트비트 주기(`PreToolUse`·`PostToolUse` 간격)를 잰다.
2. **결정.** ⓐ가 깨지거나 ⓑ가 같은 틱을 못 가르면 순서 키를 `ts`에서 단조 증가 `seq` 필드로 바꾼다. 그다음 "역행 기록 무시" 가드와, 그 가드가 낳는 고착을 푸는 age 기반 stuck 감지 임계(주로 `busy` 하트비트가 ⓒ의 몇 배 이상 끊기면 stuck)를 함께 정한다.
3. **오라클(구현 전 red 테스트).** ① 더 작은 `ts`(또는 `seq`)의 IDLE이 BUSY를 역행시키지 않는다 ② 시각이 뒤로 간 뒤에도 stuck 임계 안에서는 정상 전이가 반영되고, 임계를 넘긴 stuck은 감지된다 ③ seed 후 `SessionStart`가 미발화해 `starting`에 고착하면, seed `ts` 기준 STARTING 최대 지속시간을 넘길 때 `ERROR`로 감지된다.
4. **반영.** 확정 정책을 이 절과 `runner.py:poll_state` 주석에 반영하고, 하트비트 주기·순서 키를 위 표의 확정 행으로 올린다.

## 훅 이벤트 → 상태

상태 파일에 쓰이는 값(`starting`·`idle`·`busy`·`waiting_input`)은 `PlatformAdapter.detect_state`가 `AgentState`로 매핑한다 — 값이 그대로 `AgentState.value`와 같다(항등, 양 CLI 공통, base.py `_STATE_MAP`). 아래는 어느 훅 이벤트가 어느 값을 쏘는지의 매트릭스다(`starting`은 훅이 아니라 엔트리포인트 seed가 쓴다 — 아래 부재 행 참조).

| 훅 이벤트 | 상태값 | 상태 |
|---|---|---|
| `SessionStart` | `idle` | claude 실측 확정 / codex 미확정(matcher) — 잠정 |
| `UserPromptSubmit` | `busy` | 양 CLI 실측 확정 |
| `Stop` | `idle` | claude 실측 확정 / codex 미확정 — 잠정 |
| `Pre/PostToolUse` | `busy`(하트비트) | 미확정 — 잠정 |
| `Notification` | `waiting_input` | 미확정 — 잠정 |
| (훅 아님) 상태 파일 부재 | — | 슬라이스 A(잠정): 첫 유효 훅 레코드 전까지 `STARTING` 유지(`poll_state` 초기 `_last_state`). 목표(ADR-0018): STARTING은 런타임 seed한 `starting` 값으로 명시, 부재는 미프로비저닝→`ERROR`(정확한 처리는 슬라이스 B) |
| (훅 아님) 프로세스 사망 | — | `ERROR`/`STOPPED`는 훅이 아니라 `is_alive()`·`exit_code()`·`last_error()`로 판정. 단 목표(ADR-0018)에선 상태 파일 부재(미프로비저닝)도 `ERROR`의 두 번째 발생원이다 — 부재→`ERROR` 전환은 슬라이스 B/Phase 3. |

잠정 표기 행은 슬라이스 B(Phase 3, 실 CLI 라이브 측정)로 확정되기 전까지의 임시 값이다.

어휘 정합: 상태 파일 값은 `AgentState.value`와 1:1로 같다(항등 매핑, `_STATE_MAP`, ADR-0019). 쓰는 쪽(훅·seed)이 모두 우리 코드라 방출 값을 처음부터 `AgentState.value`에 맞춘다 — `start`·`waiting` 같은 별도 별칭은 두지 않는다. 훅은 `SessionStart`에 `idle`, `Notification`에 `waiting_input`을 쓰고, Phase 3 엔트리포인트는 CLI exec 직전에 `starting`을 seed한다 — 초기 상태를 파일 부재로 추론하지 않기 위해서다(ADR-0018).

## Phase 3 백엔드 리스크 (TmuxDockerBackend.send_text)
literal text 주입은 FakeBackend엔 충분하나 tmux엔 미확정 케이스가 있다 — 라이브 검증 필요:
- 멀티라인 prompt, paste(bracketed-paste) 모드
- Enter 키 이벤트 vs literal "\n"
- 셸 이스케이프 / 제어문자

## 검증 방식
- 확정 항목: axdt/agent_runner/tests/의 단위 테스트가 계약을 고정.
- 잠정 항목: Phase 3 슬라이스 B에서 실 CLI를 띄워 ① 훅 상태 파일 전이(어느 훅 이벤트가 어느 상태값을 쓰는지) ② 제출·클리어 키 이벤트 수용 ③ capability argv 수용을 측정해 잠정 셀을 확정하고 이 표를 갱신.
