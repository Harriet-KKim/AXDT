# 핸드오프 — 상태판정(state detection) 재설계 (§8.3a 실측 발견)

> 작성: phase2 세션(역할·통신 프로토콜 설계) · 대상: **Phase 5 세션**(`PlatformAdapter`·`detect_state`·`poll_state`·`PLATFORM_MATRIX` 소유)
> 근거: §8.3a 라이브 측정 실측(AX-DEV, claude 2.1.209 · codex 0.144.4) · `runner.py`·`adapters/*`·스펙 §8.3a·§9

## 0. 무엇을 넘기나

§8.3a 라이브 측정을 실제 호스트(AX-DEV)에서 착수했더니, 항목별 판정에 이르기 전에 **상태판정 자체가 현재 CLI에서 성립하지 않음**을 실측했다. `PLATFORM_MATRIX.md`의 provisional 화면 마커가 낡았을 뿐 아니라, "누적 스트림 꼬리에서 부분문자열을 찾는" 판정 모델 자체가 claude 2.1.209의 전체화면 재도색 TUI에 부적합하다. 대신 **CLI 훅으로 상태를 방출**하는 방식이 성립함을 실증했다.

넘기는 것은 이 발견과 검증 결과다. `detect_state`/`poll_state`는 Phase 5 소유 공유 계약이므로(스펙 §9), 재설계는 Phase 5가 수행한다. Phase 2는 발견만 넘긴다(사용자 결정: "발견 문서화, 재설계는 Phase 5로"). 측정 하네스가 CLI를 신뢰 다이얼로그 너머로 띄우게 하는 `--workdir-base` 보정은 phase2에서 이미 커밋했다(`live_probe.py`, 신뢰된 폴더 하위에 항목별 workdir 생성 — 신뢰가 하위폴더로 상속됨을 실측).

## 1. 발견 — provisional 마커·판정 모델이 왜 안 되나

- **마커 스테일.** claude IDLE 마커 `"\n> "`(`adapters/claude_code.py:16`)는 실제와 두 곳에서 어긋난다: 프롬프트 기호가 `>`→`❯`(U+276F)로 바뀌었고, 줄구분자가 `\n`이 아니라 `\r`다. BUSY 마커 `"Esc to interrupt"`(`:15`)는 2.1.209 출력에 존재하지 않는다. (codex 마커 `"\n› "`·`"ctrl-c to interrupt"`는 이번에 미검증.)
- **판정 모델 부적합.** `detect_state`(`adapters/base.py:48-68`)는 "IDLE을 나타내는 부분문자열이 있으면 IDLE"이라는 양성 substring 방식이다. 그러나 IDLE의 후보인 입력 캐럿 `❯`와 하단 푸터가 **BUSY에도 그대로 존재**한다(TUI가 입력창·푸터를 항상 그린다). IDLE↔BUSY 차이는 BUSY에만 뜨는 스피너 줄뿐인데, 그 단어가 매번 랜덤이라(`Spinning…`·`Beboppin'…`·`Orbiting…`·`Whatchamacalliting…`) 고정 부분문자열이 없다.
- **판정 기반(substrate) 부적합.** `poll_state`(`runner.py:74`)는 `_strip_ansi(self._transcript)[-2000:]`, 즉 누적 **스트림 꼬리**를 판정 입력으로 쓴다. 이 스트림은 `\r`로 앞줄을 덮어쓰는 전체화면 재도색이라 부분 프레임이 뒤엉키고, `_strip_ansi`(`runner.py:12-16`)는 CSI만 지우고 OSC 하이퍼링크·`\r`·nbsp를 남긴다. 긴 응답 중에는 캐럿·푸터가 2000자 창 밖으로 밀려 아예 사라진다.
- **statusLine으로도 못 실음.** Claude Code statusLine 명령에 넘어가는 JSON에는 활동상태(busy/idle) 필드가 없고, 상태 전이에 재렌더되지 않는다(idle이면 오히려 갱신이 멈춘다). 화면 하단의 "auto mode on"류는 statusLine/내장 표시일 뿐 신뢰할 상태 신호가 아니다.

이 결과는 스펙이 조건부로 남겨둔 지점을 확정한다 — 스펙 :546 "게이트의 신뢰도는 상태 마커의 신뢰도이고 그것은 아직 provisional이므로 '막는다'가 아니라 '줄인다'로 적는다. §8.3이 확정하기 전까지 이 문장은 조건부다."(같은 취지 :595·:628) §8.3a가 그 조건을 확정했고, 결과는 "현재 마커·모델로는 성립하지 않는다"이다.

## 2. 검증된 해법 — 훅 기반 상태 방출

CLI 훅이 상태 전이 시점에 명령을 실행하게 하고, 그 명령이 상태 파일을 쓰게 한다. 외부(백엔드)는 화면을 긁는 대신 그 파일을 읽는다.

| 상태 | 훅 이벤트 | claude 2.1.209 | codex 0.144.4 |
|---|---|---|---|
| 초기 IDLE | `SessionStart` | ✅ 실측 발화 | matcher `startup\|resume\|clear` — 미확정 |
| BUSY | `UserPromptSubmit` | ✅ 실측 발화 | ✅ 실측 발화 |
| IDLE(완료) | `Stop` | ✅ 실측 발화 | 미확정(느린 응답으로 창 내 미발화) |
| WAITING_INPUT | `Notification` | 후보 — auto mode라 승인물음 미유발, 미검증 | 동등 조사 필요 |
| ERROR | (훅 없음) | `runner` `is_alive()`/`exit_code()` 유지 | 동일 |

실측 방법·관측(AX-DEV, 신뢰된 `…/AXDT/.axdt-probe/` 하위 workdir):

- **claude.** 워크dir의 `.claude/settings.json`에 `SessionStart`/`UserPromptSubmit`/`Stop` 훅이 상태 파일을 쓰게 설정 → 기동 직후 `state=start`, 프롬프트 제출 중 `state=busy`, 응답 완료 후 `state=idle`로 전이. 신뢰된 폴더의 프로젝트 훅은 **승인 물음 없이** 실행됐다(프로덕션 이미지에 구워도 물음 없이 작동한다는 뜻).
- **codex.** 훅 형식·이벤트명이 claude와 동일하다(`~/.codex/hooks.json`: `SessionStart`·`UserPromptSubmit`·`Stop`·`Pre/PostToolUse`·`Pre/PostCompact`). 프로젝트 `.codex/hooks.json` + `-c 'hooks.files=[…]'` + `-c features.hooks=true` + `--dangerously-bypass-hook-trust`로 격리 실행 시 프롬프트 제출 중 `state=busy` 전이를 확인했다(훅 로드·발화 입증). 훅 신뢰는 per-hook `trusted_hash`(`config.toml`의 `[hooks.state]`)로 지속되거나 `--dangerously-bypass-hook-trust`로 우회한다. codex는 별도로 `notify` 프로그램(`config.toml`의 `notify=[…]`)과 `codex exec --json`(JSONL 이벤트 스트림)도 갖는다.
- **ERROR.** 훅으로는 안 나온다. 프로세스 사망 기반 판정(`runner.py`의 `is_alive()`·`exit_code()`)을 그대로 쓴다. 화면 ERROR 마커(`"Error:"`·`"fatal:"`)는 스펙도 살아 있는 세션의 오탐 위험 때문에 약한 신호로만 규정했다(스펙 §4.5·:229·:532).

## 3. Phase 5가 재설계할 것

- **판정 기반 교체.** `poll_state`/`detect_state`를 "스트림 꼬리 부분문자열" 대신 "훅이 쓴 상태 파일 읽기"로 바꾼다. 상태 파일의 위치·형식·원자적 쓰기·전이 순서·경합 처리는 Phase 5 설계다(예: workdir 내 파일을 백엔드가 읽음).
- **마커 폐기·재정의.** 화면 마커 `_IDLE/_BUSY/_WAITING/_ERROR_MARKERS`(`adapters/base.py`·`claude_code.py`·`codex.py`)는 대부분 폐기하고, `PLATFORM_MATRIX.md`의 마커 행을 "훅 이벤트→상태" 표로 재정의한다.
- **미확정 실측 마무리.** codex `SessionStart`(matcher)·`Stop` 발화, 양 CLI의 `Notification`→WAITING_INPUT을 실측으로 닫는다.
- **어댑터 계약 변경.** `detect_state`가 화면 문자열 대신 상태 파일(또는 상태값)을 받도록 시그니처·문서를 갱신한다. 공유 계약 변경이므로 소비자(runner·테스트·`PLATFORM_MATRIX`)를 함께 갱신한다.

## 4. Phase 3에 딸린 계약 (교차-Phase)

- 컨테이너 이미지가 **훅 설정을 구워야** 세션이 상태를 방출한다: claude는 `.claude/settings.json`의 hooks, codex는 `~/.codex/hooks.json` + `features.hooks=true` + 훅 신뢰(`trusted_hash`). 자격증명을 굽지 않는 §4.1 제약과 같은 방식으로 훅 설정만 굽는다.
- 상태 파일 경로가 **컨테이너와 호스트 양쪽에서 접근 가능**해야 한다 — §8.3b의 HOME 위치·`/tmp` tmpfs 결정(`handoff-83b-container-measurement.md`)과 연동해서 정한다.

## 5. §8.3a 재-시퀀싱 (Phase 2가 지금 하는 것)

- §8.3a 항목 1~10은 전부 초기 IDLE 게이트를 전제한다(`wait_until_idle` 선행). 따라서 **Phase 5의 훅-기반 판정이 나오기 전에는 항목별 판정을 완료할 수 없다.**
- §8.3a의 이번 산출물은 항목별 판정표가 아니라 **"provisional 마커·모델 부적합 → 훅-기반 판정 채택"이라는 방향 확정**이다(위 §2 검증). 항목별 실측(argv 수용·강제 등급 등)은 Phase 5 판정기 재설계 이후로 이월한다.
- 그동안 Phase 2는 측정 비의존 작업을 진행한다 — 역할 5종 Skill, SoT PR 2건, Watcher 별도 설계, 주입 규약·중계 Python 골격. **어댑터 argv·강제 등급 동결**은 §8.3a 항목 실측(Phase 5 판정기 이후)까지 보류한다.
- 이는 "§8.3a는 구현 착수 전 게이트"라는 스펙 전제에 재-시퀀싱을 낳는다: **Phase 5의 판정기 재설계가 §8.3a 완료의 선행**이 된다. 스펙 §8.3·§9의 순서 서술을 이 사실로 갱신해야 한다.

## 참조

- `WIP/axdt/agent_runner/runner.py:60-78`(`poll_state`·판정 창)·`:12-16`(`_strip_ansi` CSI 전용)
- `WIP/axdt/agent_runner/adapters/base.py:48-68`(`detect_state` 양성 substring·latest-wins)
- `WIP/axdt/agent_runner/adapters/claude_code.py:12-16`·`codex.py:12-16`(provisional 마커)
- `WIP/axdt/agent_runner/state.py`(상태 어휘)
- `WIP/axdt/agent_runner/tests/live_probe.py`(§8.3a 하네스, `--workdir-base` 포함)·`live_probe_protocol.md`
- 스펙 `WIP/specs/2026-07-09-phase2-roles-and-protocol-design.md` :546·:595·:628(마커 provisional·조건부)·§8.3a(:1254~)·§9(:9, Phase 5 소유 `PLATFORM_MATRIX`)
- `WIP/handoff-83b-container-measurement.md`(§8.3b 컨테이너 측정 — 이미지 계약 상호 참조)
- Claude Code 훅 문서(`SessionStart`·`UserPromptSubmit`·`Stop`·`Notification`) · codex `~/.codex/hooks.json`·`config.toml [hooks.state]`·`codex exec --json`
