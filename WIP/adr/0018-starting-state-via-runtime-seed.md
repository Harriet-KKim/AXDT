---
id: ADR-0018
title: 세션 초기 상태(STARTING)를 파일 부재로 추론하지 않고 런타임 seed로 명시한다
status: accepted
date: 2026-07-22
decision: D4
related: [ADR-0016, ADR-0019]
---

# ADR-0018: 세션 초기 상태(STARTING)를 파일 부재로 추론하지 않고 런타임 seed로 명시한다

## 상태
Accepted (2026-07-22) · 관련 결정 D4 · 배선·세부는 슬라이스 B/Phase 3

## 맥락
상태판정은 CLI 훅이 쓴 상태 파일을 읽어 한다(ADR-0016). 세션을 막 기동한 직후, 첫 훅(`SessionStart`)이 터지기 전에는 상태 파일이 없다. 슬라이스 A는 이 "파일 부재"를 그대로 `STARTING`으로 취급한다 — `poll_state`가 `_last_state`를 `STARTING`으로 초기화하고, 읽을 값이 없으면 그 초기값을 돌려준다.

이 결합이 실패 모드를 가린다. "파일 부재"가 두 가지를 동시에 뜻하기 때문이다.
- 정상적으로 아직 기동 중(STARTING).
- 상태 파일 배선이 깨짐 — 경로 오설정, 훅 미설치, 권한 문제.

둘을 못 가르므로, 배선이 깨진 세션이 "STARTING인 채로 영원히" 정상처럼 보인다. "정의 안 됨(파일 부재)"과 "초기값(STARTING)"이 한 덩어리로 묶여 있다.

## 결정
- **STARTING을 파일 부재로 추론하지 않고, 런타임이 명시적으로 쓴 값으로 표현한다.**
  - 어휘에 값 `starting`을 추가하고 `starting`→`STARTING`으로 매핑한다. 이와 함께 상태 파일 값을 `AgentState.value`와 1:1로 통일한다 — `start` 별칭을 없애고(`idle`만 남김) `waiting`을 `waiting_input`으로 맞춘다(`_STATE_MAP` 항등화). 쓰는 쪽(훅·seed)이 모두 우리 코드라 방출 값을 처음부터 `AgentState.value`로 쓴다(어휘 통일 결정은 ADR-0019).
  - Phase 3 세션 기동 스텝(엔트리포인트)이 CLI를 exec 하기 직전에 `{"state":"starting","ts":<지금>}`을 원자적으로 seed한다. **이미지 레이어에 파일을 굽지 않는다**(대안 A).
- **읽는 쪽은 "파일 부재"를 정상 STARTING이 아니라 미프로비저닝(비정상)으로 본다.** `AgentState` 6값은 phase2 소비 코드가 분기 의존해 동결이므로(핸드오프 §1: `inject`·`converge`) 새 상태를 추가하지 않고, 부재는 `ERROR`로 매핑한다. 단, 부재·읽기불가·형식위반·미지값 각각을 즉시 `ERROR`로 볼지 짧은 유예를 둘지는 슬라이스 B 타이밍 실측으로 정한다(순서·역행 정책과 같은 성격). 부재를 즉시 `ERROR`로 보면 phase2 `inject`가 그 창을 `UNAVAILABLE`로 처리하는데(핸드오프 §1: `ERROR`→`UNAVAILABLE`), 이는 STARTING의 `DEFERRED`와 달라 정상 기동 창이 잠깐 `UNAVAILABLE`로 비칠 수 있다 — 유예 폭을 정할 때 이 영향을 함께 본다.
- `start_session` 호출 전(poll_state의 pre-start 경로)은 파일과 무관하게 `STARTING`을 반환한다 — 이 경로는 그대로다.

## 결과
**좋은 점**
- "정의 안 됨(파일 부재)"과 "초기값(STARTING)"이 분리된다. 배선이 깨진 세션이 STARTING으로 위장되지 않고 드러난다.
- STARTING이 명시 값이라 런타임 seed가 tmpfs 마운트 위든 컨테이너 재기동이든 항상 맞다 — 매 기동마다 값·`ts`를 새로 쓴다.

**대가 / 주의**
- Phase 3가 엔트리포인트 seed를 배선해야 한다(신규 작업).
- 부재의 정확한 처리(즉시 `ERROR` vs 짧은 유예)는 슬라이스 B(실 CLI 측정)에서 확정한다. `starting`은 엔트리포인트 seed가 쓰고 CLI(codex 포함)는 읽지도 쓰지도 않는다 — 슬라이스 B에서 확인할 것은 codex `SessionStart` 훅이 실제로 발화해 seed된 `starting`을 `idle`로 덮는지와 seed 배선이 동작하는지다.
- 훅 자체가 깨진 경우(seed는 됐는데 `SessionStart` 훅이 미발화)는 "starting에 고착"으로 남는다. `busy` 하트비트는 STARTING 중엔 안 뛰므로 이 고착을 못 잡는다 — seed `ts` 기준 STARTING 최대 지속시간을 넘기면 `ERROR`로 보는 age 임계로만 잡힌다(슬라이스 B 확정, 오라클은 `PLATFORM_MATRIX` 순서·역행 절 ③). seed는 "파이프 없음"과 "정상 초기"를 가르는 데까지다.
- 어휘·`_STATE_MAP`(항등화 + `starting` 포함)은 이번에 슬라이스 A 코드로 반영한다(ADR-0019) — 방출자가 아직 없어 동작 변화는 없고 매핑만 준비된다. 부재→`STARTING` 유지 코드는 런타임 seed가 배선되기 전까지 잠정 유지하고, 부재→`ERROR` 전환은 슬라이스 B/Phase 3에서 한다.

## 검토한 대안
### 대안 A — 이미지 레이어에 초기 상태 파일 굽기
빌드 시점에 상태 파일을 이미지에 넣어 둠. · **기각 사유**: 세 시나리오에서 깨진다. (1) 경로가 tmpfs면(§8.3b `/tmp` tmpfs 안) 런타임 마운트가 구운 파일을 가려 부재가 된다. (2) `ts`가 빌드 시각으로 굳어, 읽는 쪽의 최신성·순서 판정이 방금 뜬 세션을 낡음으로 오판한다. (3) `--rm` 없이 재기동하는 컨테이너에선 쓰기 레이어에 남은 이전 세션 마지막 값이 읽혀 STARTING으로 안 돌아간다. 런타임 seed는 셋을 다 피한다.

### 대안 B — 현행 유지 (파일 부재 = STARTING)
부재를 계속 STARTING으로 취급. · **기각 사유**: 배선 고장과 정상 초기를 구분 못 해, 미프로비저닝 세션이 정상 STARTING으로 위장된다.

### 대안 C — `start` 값을 STARTING으로 재정의
새 값 대신 기존 `start`를 STARTING에 매핑. · **기각 사유**: 어휘를 `AgentState.value`와 통일하면서(ADR-0019) `start` 별칭은 아예 없애므로 재정의할 대상 자체가 사라진다. STARTING은 자기 값 `starting`(=`STARTING.value`)을 갖는다 — 항등 규칙과도 맞다.
