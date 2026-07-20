# 핸드오프 — Phase 5 런타임 계약 (상태판정 훅 재설계 + runner 원시연산)

> 작성: Phase 5 세션(`PlatformAdapter`·`AgentRunner`·`SessionBackend`·`AgentState`·`PLATFORM_MATRIX` 소유)
> 대상: **phase2 세션**(`protocol/inject`·`converge`·`message` 소비자) · **Phase 3 세션**(컨테이너 이미지·`TmuxDockerBackend`)
> 근거: `WIP/handoff-state-detection-redesign.md`(§8.3a 실측 발견) · 스펙 §9(Phase 5 소유 계약) · 실측 코드 `agent_runner/*`·`protocol/*`
> 상태: 초안. 아래 계약안은 사용자 확인 대기 중이며, 확정 전까지 슬라이스 A 구현에 착수하지 않는다.

## 0. 무엇을 넘기나

Phase 5의 작업 범위를 인계 문서 §3(상태판정만)에서 **스펙 §9의 Phase 5 전체 계약**으로 확장했다(사용자 결정). 이 문서는 그 확장 범위가 무엇을 **동결**하고 무엇을 **바꾸는지**를 고정하고, phase2·Phase 3가 각각 무엇을 이어받는지를 넘긴다.

핵심 사실 하나가 조율 범위를 좁힌다: 재설계는 대부분 `AgentRunner.poll_state() → AgentState` 경계 **뒤**에서 일어난다. phase2 소비 코드(`inject`·`converge`)는 `poll_state()`와 `AgentState`만 부르고 `detect_state()`는 직접 부르지 않으므로, 판정 내부를 화면 마커에서 훅 기반으로 바꿔도 phase2 시그니처는 바뀌지 않는다.

작업은 두 슬라이스로 가른다. **슬라이스 A**(코드+단위 테스트)가 **슬라이스 B**(라이브 측정)의 선행이다(§7).

## 1. 동결한다 — phase2가 의존하는 경계

Phase 5는 아래를 바꾸지 않는다. phase2 코드가 이 두 가지에 의존하기 때문이다.

- `AgentRunner.poll_state() -> AgentState` — 반환 타입·시그니처 유지.
- `AgentState` 6-값 어휘 유지: `STARTING`·`IDLE`·`BUSY`·`WAITING_INPUT`·`STOPPED`·`ERROR`.

근거: `inject.inject()`가 이 여섯 상태를 빠짐없이 분기하고(`IDLE`→진행, `BUSY`·`STARTING`→`DEFERRED`, `WAITING_INPUT`→`NEEDS_HUMAN`, `ERROR`·`STOPPED`→`UNAVAILABLE`), `converge.Observation.session`이 `AgentState` 타입을 받는다. 어휘를 바꾸면 이 분기가 깨진다.

## 2. Phase 5 내부에서 바꾼다 — phase2 미영향

phase2는 아래 함수를 직접 부르지 않으므로(실측: `protocol/*`에서 `detect_state` 호출 없음, `message.py`는 docstring에서 언급만) 이 변경은 phase2 코드를 건드리지 않는다.

- **판정 기반 교체.** `poll_state`/`detect_state`가 "ANSI 제거한 스트림 꼬리에서 마커 부분문자열 찾기"(현재 `runner.py:74`·`base.py:48-68`)를 버리고 "훅이 쓴 상태 파일 읽기"로 바뀐다(§3).
- **`detect_state` 시그니처 변경.** `detect_state(recent_output: str)`에서 상태값(상태 파일에서 읽은 값)을 받는 형태로 바뀐다.
- **마커 폐기.** 어댑터의 `_IDLE/_BUSY/_WAITING/_ERROR_MARKERS`(`base.py`·`claude_code.py`·`codex.py`)를 폐기하고, `PLATFORM_MATRIX.md`의 마커 4행을 "훅 이벤트→상태" 표로 교체한다.
- **`ERROR`·`STOPPED`는 그대로.** 훅으로 안 나오는 두 상태는 지금처럼 `backend.is_alive()`·`exit_code()`·`last_error()`로 판정한다(`runner.py:67-73`).
- **내부 소비자 동반 갱신.** `runner.poll_state`, `tests/test_adapters.py`·`test_runner.py`, `tests/live_probe.py` — 전부 Phase 5 소유. 함께 고친다.

## 3. 새 계약 — 상태 파일 (Phase 3와 공유하는 substrate)

훅이 상태를 파일에 쓰고, 백엔드(호스트)가 그 파일을 읽는다. 파일 형식은 **Phase 3(쓰는 쪽, 훅 명령)와 Phase 5(읽는 쪽, poll_state)의 공유 계약**이므로 여기서 고정한다.

- **경로.** 환경변수 `AXDT_STATE_FILE`이 절대경로를 지정한다. Phase 3가 이미지에서 이 변수를 설정하고, 그 경로가 컨테이너·호스트 양쪽에서 접근 가능하게 보장한다(§8.3b HOME 위치·`/tmp` tmpfs 결정과 연동, `handoff-83b-container-measurement.md`). 경로를 환경변수로 두어 §8.3b 결정과 분리한다.
- **형식.** 한 줄 JSON: `{"state": "<상태>", "ts": <epoch 초, 소수 포함>}`. `<상태>`는 `start`·`busy`·`idle`·`waiting` 중 하나.
- **원자적 쓰기.** 훅 명령은 임시 파일에 쓴 뒤 같은 파일시스템 안에서 `mv`(원자적 rename)로 대상에 놓는다. 부분 기록을 읽는 경합을 없앤다.
- **순서·최신성.** 읽는 쪽은 `ts`로 최신성을 판단한다 — 더 큰 `ts`가 더 최근. `mv`가 last-write-wins를 주므로 근접한 두 전이는 나중 것이 남는다. (`ts` 해상도가 같은 틱 안 다중 이벤트를 못 가르는 것으로 판명되면 단조 증가 `seq` 필드를 추가한다 — 슬라이스 B 측정으로 확인.)
  - **순서 가드는 슬라이스 B로 미룬다.** 슬라이스 A의 `poll_state`는 `ts`를 읽어 저장만 하고 최신성·순서 판정에는 쓰지 않는다. `ts` 역행(BUSY 뒤 더 작은 `ts`의 IDLE)을 무시하는 가드는 뒤로 간 시계에 세션이 BUSY로 고착하는 엣지를 낳는데, 그 엣지는 age 기반 stuck 감지로만 구제되고 그 정책도 슬라이스 B다. 따라서 순서 가드와 age 정책은 훅 시계 실측과 함께 한 몸으로 착지한다. 슬라이스 A엔 라이브 훅 writer가 없어(테스트만 파일을 씀) 무영향이다.
- **상태값→`AgentState` 매핑(poll_state 내부).** `start`·`idle`→`IDLE`(SessionStart는 "수신 준비됨"이므로 `IDLE`. `STARTING`은 첫 훅 발화 전, 즉 파일 부재 시 유지), `busy`→`BUSY`, `waiting`→`WAITING_INPUT`. `ERROR`·`STOPPED`는 파일이 아니라 프로세스 생존으로 판정(§2). 훅은 `SessionStart`에 `idle`을 쓰고, `start`는 `_STATE_MAP`에 남긴 하위호환 별칭이다(둘 다 `IDLE`) — `PLATFORM_MATRIX` 훅 이벤트표와 정합.

## 4. 확인 메커니즘 — `/btw`가 아니라 하트비트

훅은 전이 시점에 한 번 쏘는 "밀어내기(push)" 신호다. 훅이 누락되거나(측정에서 codex `Stop`이 창 안에 미발화한 사례) 파일이 낡으면 오판이 난다. 이를 막는 2차 확인을 **세션을 교란하지 않고** 넣는다.

`/btw`로 확인하는 안은 폐기한다. 근거:
- **증상:** `/btw`는 실존하는 명령이나(문서화, v2.1.212+), 외부 오케스트레이터가 쓸 별도 제출 경로가 없다.
- **원인:** 실행 중 TUI 세션에 접근할 out-of-band 제어 채널(소켓·파이프·HTTP·SDK-attach)이 문서상 존재하지 않는다(검증: Claude Code 문서). 유일한 입력 경로는 터미널 키 입력이다. `/btw`도 실제 프롬프트와 같은 `send_text`+`submit` 경로로 넣을 수밖에 없고, 그 제출은 `UserPromptSubmit`을 발화시킬 개연성이 크다(문서 미확정).
- **영향:** 확인하려는 `IDLE`이 확인 행위로 `BUSY`가 될 수 있다. 자동 경로에서 자기모순이라 2차 확인으로 못 쓴다.
- **조치:** `/btw`의 실제 교란 여부(=`UserPromptSubmit` 발화·모델 점유)는 슬라이스 B 라이브 측정 항목으로 이월한다. 비교란으로 판명되면 나중에 선택적 2차 확인으로 되살릴 수 있으나, 계약은 여기 의존하지 않는다.

대신 확인은 아래로 구성한다:
1. **하트비트 최신성(ts 판독).** `poll_state`가 상태 파일의 `ts`를 읽어 상태 나이를 안다. 단, `idle` 파일은 활동이 없어 정상적으로 낡으므로 "오래되면 무시"는 세션을 `STARTING`에 가두는 오류를 낳는다 — 정확한 임계·정책(주로 `busy` 하트비트가 끊긴 stuck 세션 판정)은 슬라이스 B의 하트비트 주기 실측으로 튜닝한다. 슬라이스 A는 `ts` 판독 기계만 넣고 정책은 유보한다.
2. **BUSY 하트비트 훅.** `PreToolUse`·`PostToolUse`가 매 도구 호출마다 발화한다(검증: Claude Code 훅 문서) → `busy`를 `ts` 갱신과 함께 다시 쓴다. 긴 BUSY 구간에도 파일이 계속 신선해져 "진짜 idle"과 "`Stop` 누락"을 가른다.
3. **프로세스 생존 교차검사.** `is_alive()`·`exit_code()` — 이미 `poll_state`에 있다.
4. **`inject.py`의 2단 방어(이미 설계됨).** 게이트 통과 후 `clear_input` 직전 재폴링(§4.1 step 2) + 제출 후 `IDLE` 이탈 관측(step 6). 주입 직전·직후로 상태를 한 번씩 더 확인한다.

## 5. phase2가 이어받는 것

phase2에 **강제 변경은 없다.** 아래는 통보와 해금이다.

- **`message.py` `render_note` 제약 — 근거 소멸(정리는 phase2 판단).**
  - 증상: `render_note` docstring(97-100행)과 스펙 §4.1(591·717행)이 "자유 텍스트에 `Error:` 같은 마커가 섞이면 `detect_state`가 transcript에서 찾아 판정이 오염된다"를 근거로 제약을 건다.
  - 원인: 훅 기반으로 바뀌면 `detect_state`가 transcript를 스캔하지 않는다.
  - 영향: 제약을 남겨도 오작동은 없다(불필요한 과잉방어). 방치 시 낡은 근거가 문서에 남아 다음 독자를 오도한다.
  - 조치: phase2가 자기 파일에서 완화·삭제 여부를 판단한다. Phase 5는 고치지 않는다(소유권 경계).
- **`inject()` 배선 *코드 작성*은 해금 — *라이브 동작*은 아직.** 확장된 Phase 5가 runner 원시연산(`submit`·`clear_input`·`send_when_idle`·`attach`)과 훅 기반 `poll_state`를 모두 내놓으므로, phase2는 `inject.py:93`의 `NotImplementedError` 스켈레톤을 실제 배선으로 **채우고 `FakeBackend`로 단위테스트할 수 있다**(호출할 API가 존재한다). 이는 phase2의 원래 자기 작업이지 Phase 5가 강제하는 수정이 아니다.
  - **단, `inject()`가 실제 라이브 세션에서 동작하려면 두 선행이 남는다:** ① 청크 ④ — `TmuxDockerBackend`가 `read_state()`(poll_state가 상태를 읽음)·`send_key()`(clear/submit이 키를 보냄)를 구현하고 이미지에 훅이 구워져 상태 파일이 생겨야 한다. ② 슬라이스 B — 훅 발화(codex `Stop` 등 미검증)와 잠정 `clear_key`/`submit_key`·상태 파일 값을 실측으로 확정해야 한다. 요약: **코드는 지금, 라이브 동작은 Phase 3(④)+슬라이스 B 이후.**

## 6. Phase 3가 이어받는 것

- **이미지에 훅 설정 굽기.** 세션이 상태를 방출하려면 이미지에 훅 설정이 구워져 있어야 한다. 이 작업은 **이미 main에 병합된** `WIP/axdt/infra/docker/leader.Dockerfile`을 수정하는 것이다(신규 인프라 구축이 아님 — 격리 인프라는 병합 완료). claude는 `.claude/settings.json`의 hooks, codex는 `~/.codex/hooks.json` + `features.hooks=true` + 훅 신뢰(`config.toml [hooks.state]`의 `trusted_hash`). 자격증명을 굽지 않는 §4.1 제약과 같은 방식으로 훅 설정만 굽는다. 각 훅 명령은 §3의 형식으로 상태 파일을 원자적으로 쓴다.
- **상태 파일 경로 접근성.** `AXDT_STATE_FILE`을 이미지에서 설정하고, 그 경로가 컨테이너·호스트 양쪽에서 접근 가능하게 한다(§8.3b 연동).
- **agent_runner 계약의 infra 통합.** 슬라이스 A(①②③)가 `agent_runner`에 정의·착지시킨 계약을 infra에 잇는다. Phase 5 세션에서 하지 않은 이유: 전부 컨테이너/이미지 지식이 필요하다.
  - `SessionBackend` ABC 통합 — `infra/backend.py`의 인라인 ABC를 제거하고 `agent_runner.backend.SessionBackend`를 import(§2.5 3단계). `TmuxDockerBackend`가 새 추상 `read_state()`(상태 파일 읽기, §3)·`send_key()`(tmux `send-keys -t <win> <key>`, `-l` 아님)를 구현한다.
    - **예외 단일 진실원.** `SessionBackend.attach` docstring이 참조하는 `NotStarted`는 현재 `infra/backend.py`에만 정의돼 있다. ABC를 통합할 때 `NotStarted`(및 형제 예외 `AlreadyStarted`·`SessionDead`)를 ABC 옆(`agent_runner.backend`)으로 옮겨 단일 진실원을 둔다. 그러지 않으면 계약 문서가 이름만 가리키는 예외가 두 모듈에 갈린다.
  - **Codex 세션 역할 프롬프트 = 물질화한 네이티브 파일(런타임 주입 아님).** 역할 프롬프트 텍스트의 SoT는 `docs/sot/rule/role-responsibilities.md`이고 `roles/prompts/<role>.md`가 그 규범을 담는다. Phase 3가 이 텍스트를 Codex 네이티브 파일로 **이미지 빌드 시점에 물질화**한다 — `$CODEX_HOME` 아래(workspace 밖, 스펙 line 213) 읽기전용으로 굽거나 `rule-protected-paths`로 보호해 에이전트가 못 고치게 한다(자가수정 차단, line 344). Codex가 그 파일을 네이티브로 로드하므로 런타임 주입이 필요 없다. 서브에이전트 물질화(§2.3.3)와 같은 계층이라 자연스럽고, `up`(start_session)과 `assign`/`send`(attach)가 별도 프로세스여서 생기던 부트스트랩 타이밍 문제를 아예 없앤다.
    - **실측 확정(Phase 3/슬라이스 B).** 세션 역할을 담을 정확한 Codex 파일(예: `$CODEX_HOME`/전역 `~/.codex/AGENTS.md` 대 `-p <profile>`)과 대화형 세션에서의 로드 신뢰성은 실 CLI로 확인한다. 스펙 §CLI표(line 151)가 "전용 플래그 없음 → 본문 선두 주입"으로 적은 전제는 이 파일 기반 결정으로 대체되므로 phase2 스펙 소유자가 그 표를 갱신한다. Claude는 `--append-system-prompt` argv(네이티브·workspace 밖)를 그대로 쓴다. agent_runner에는 런타임 주입 프리미티브(`send_role_bootstrap` 등)를 두지 않는다.
  - `leader.up(platform)` 필수·`cli --platform`(기본 `claude-code`) — 스펙 §9 892~897행. `leader.up`이 `adapter.prepare_subagents`→`build_session_command`→`start_session(role, …)`을 실제로 배선한다(현재 `leader-placeholder.sh` 대체). `leader-placeholder.sh`의 `build_launch_command` 주석도 `build_session_command`로 고친다.
  - Codex `prepare_subagents` — `$CODEX_HOME` 아래 프로파일·프롬프트·`.rules` 물질화 + `axdt-subagent` 래퍼를 이미지에 굽는다(§2.3.3). 어댑터의 이 메서드는 현재 `NotImplementedError` 스텁이다.
  - `live_probe.py` 재작성 — 현재 낡음(구 `start_session(workdir)`·`detect_state(window)` 호출). 훅 기반 측정 하네스로 재작성하며, 실 CLI 측정과 한 몸이라 아래 슬라이스 B와 함께 한다.
- **라이브 측정 수행(슬라이스 B).** 재작성한 `live_probe.py`와 측정 프로토콜로 실제 CLI(claude 2.1.209·codex 0.144.4)를 띄워 미확정 셀을 닫고 `PLATFORM_MATRIX`를 확정한다(§7). 라이브 측정의 집을 Phase 3로 두는 이유: 훅을 구운 실제 이미지와 `TmuxDockerBackend`가 여기서 준비되고, 훅 굽기 자체가 Phase 3 계약이기 때문이다.

## 7. 슬라이스 구분

**슬라이스 A — Phase 5 agent_runner (완료, phase5-runtime 브랜치)**
세 청크로 착지했다. 전부 `WIP/axdt/agent_runner/` 안, `FakeBackend`·가짜 상태 파일로 단위 테스트(전체 스위트 통과). 미확정 값은 `PLATFORM_MATRIX`에 잠정 표기.
- ① 상태판정 재설계(§2·§3) — `poll_state`가 `read_state()`로 상태 파일을 읽어 `AgentState`로 매핑, `detect_state` 시그니처 변경, 마커 폐기.
- ② 입력 원시연산 — `submit`·`clear_input`·`attach`·`send_when_idle`·`send_key`, `submit_key`/`clear_key`(잠정), `format_prompt` 개행 분리, `send_prompt` IDLE 전용+`submit`.
- ③ 역할별 실행 — `capability_args`·`prepare_subagents`(Claude `--agents`)·`build_session_command`(Claude는 `--append-system-prompt`로 역할 프롬프트 전달; Codex 세션 역할은 Phase 3가 네이티브 파일로 물질화 — §6), `build_launch_command` 대체, `start_session(role, …)`.

**청크 ④ — agent_runner 계약의 infra 통합 (Phase 3)**
§6의 'agent_runner 계약의 infra 통합' 항목. 컨테이너/이미지 지식이 필요해 Phase 3 몫이다: `SessionBackend` ABC 통합·`TmuxDockerBackend`의 새 추상(`read_state`/`send_key`) 구현·`leader.up(platform)`·`cli --platform`·Codex `$CODEX_HOME` 물질화·`live_probe.py` 재작성. 슬라이스 A가 정의한 계약(추상 시그니처·`AgentState`·상태 파일 형식)을 단일 진실원으로 삼아 소비자 쪽만 구현한다.

**슬라이스 B — 라이브 측정 (Phase 3, 실 CLI 필요)**
- 이 작업은 §6의 '라이브 측정 수행'과 **동일하다**. Docker 이미지 굽기(§6 첫 항목)를 기다리지 않는다 — 원래 §8.3a처럼 로컬 workdir의 `.claude/settings.json` 훅으로 실 CLI를 띄워 측정한다. 유일한 선행은 청크 ④의 `live_probe.py` 재작성이다.
- 닫을 셀(`PLATFORM_MATRIX` 잠정 행 전수): codex `SessionStart`(matcher)·`Stop` 발화, 양 CLI `Notification`→`WAITING_INPUT`, `Pre/PostToolUse` 하트비트 발화, 제출 키(`submit_key`)·클리어 키(`clear_key`) 이름, Claude capability argv(`--allowedTools`/`--disallowedTools` 세부·호스트 명령 허용 목록)·`--agents` 스키마, Codex `-s` 세부(`.rules`·승인 정책), `/btw` 교란 여부.
- 측정 시점 CLI 버전 기록, `PLATFORM_MATRIX` 잠정 행을 확정으로 전환.

### ts 순서·역행 정책 — 슬라이스 B 인계 메모 (`poll_state`)

슬라이스 A는 `poll_state`가 상태 파일의 `ts`를 읽어 저장만 하고, 역행(뒤로 간 `ts`) 무시 가드는 넣지 않았다(리뷰 유보, §3). 슬라이스 B가 다음 순서로 이 정책을 닫는다.

1. **측정.** 실 CLI·훅으로 상태 파일을 쓰게 하고 ⓐ 훅 시계가 단조 증가하는지(연속 전이의 `ts`가 항상 커지는지), ⓑ `ts` 해상도가 같은 틱 안 다중 이벤트를 가르는지, ⓒ `busy` 하트비트 주기(`PreToolUse`·`PostToolUse` 간격)를 잰다.
2. **결정(두 가지를 함께).** ⓐ가 깨지거나(시각 되돌림 관측) ⓑ가 같은 틱을 못 가르면 순서 키를 `ts`에서 단조 증가 `seq` 필드로 바꾼다(§3에서 이미 예고). 그다음 "역행 기록 무시" 가드와, 그 가드가 시각 되돌림에 세션을 BUSY로 고착시키는 엣지를 푸는 age 기반 stuck 감지 임계(주로 `busy` 하트비트가 ⓒ의 몇 배 이상 끊기면 stuck)를 **한 몸으로** 정한다 — 가드만 넣으면 고착이 열린다.
3. **오라클(수용 테스트, 구현 전 red로).** ① 더 작은 `ts`(또는 `seq`)의 IDLE이 BUSY를 역행시키지 않는다. ② 시각이 뒤로 간 뒤에도 stuck 임계 안에서는 정상 전이가 반영되고, 임계를 넘긴 stuck은 감지된다.
4. **반영 위치.** `runner.py:poll_state`의 유보 주석과 §3의 유보 문단을 확정 정책으로 교체하고, `PLATFORM_MATRIX`에 하트비트 주기·순서 키를 확정 행으로 추가한다.

## 참조

- `WIP/handoff-state-detection-redesign.md` — §8.3a 실측 발견(마커·판정 모델 부적합, 훅 기반 채택)
- `WIP/handoff-83b-container-measurement.md` — §8.3b 컨테이너 측정(상태 파일 경로 상호 참조)
- 스펙 `WIP/specs/2026-07-09-phase2-roles-and-protocol-design.md` §9(1287·819·1291·320·888행, Phase 5 계약)·§4.1(591·717행, 마커 오염 제약)
- `WIP/axdt/agent_runner/runner.py`·`adapters/base.py`·`state.py`·`PLATFORM_MATRIX.md`
- `WIP/axdt/protocol/inject.py`·`converge.py`·`message.py`
- Claude Code 훅 문서(`SessionStart`·`UserPromptSubmit`·`Stop`·`Notification`·`Pre/PostToolUse`) · codex `~/.codex/hooks.json`·`config.toml [hooks.state]`
