---
id: ADR-0019
title: 상태 파일 값을 AgentState 값과 통일한다 (start·waiting 별칭 폐지)
status: accepted
date: 2026-07-22
decision: D4
related: [ADR-0016, ADR-0018]
---

# ADR-0019: 상태 파일 값을 AgentState 값과 통일한다 (start·waiting 별칭 폐지)

## 상태
Accepted (2026-07-22) · 관련 결정 D4 · 코드는 슬라이스 A(base.py `_STATE_MAP`·단위 테스트)

## 맥락
상태판정은 훅이 쓴 상태 파일의 값을 `_STATE_MAP`이 `AgentState`로 번역해서 한다(ADR-0016). 슬라이스 A는 이 두 어휘를 다르게 뒀다.

- `start`가 `idle`과 함께 `IDLE`로 매핑됐다 — `idle`과 뜻이 겹치는 별칭이다.
- 파일 값 `waiting`이 `WAITING_INPUT`으로 매핑됐는데, 그 enum의 값은 `waiting_input`이다 — 파일 값과 enum 값이 달랐다.

이 분리는 슬라이스 A 첫 커밋에서 정리되지 않은 채 들어왔고, 특정 CLI가 `start`를 방출해서가 아니다. 상태 파일에 쓰는 쪽은 훅 명령과 엔트리포인트 seed인데 둘 다 우리 코드라, 방출 값을 우리가 정한다.

ADR-0018이 seed 값 `starting`(→`STARTING`, 이 enum의 값도 `starting`)을 추가하면서 이 분리가 드러났다. 매트릭스 형식 행이 허용값을 `start`·`busy`·`idle`·`waiting`으로 열거한 뒤 seed 값 `starting`만 덧붙이는 꼴이라, 어휘가 반쪽만 `AgentState.value`와 맞아 자기모순이었다. 또 `start`(→`IDLE`)와 `starting`(→`STARTING`)은 철자가 가까운데 뜻은 반대라 혼동원이 됐다.

## 결정
상태 파일 값을 `AgentState.value`와 1:1(항등)로 맞춘다.

- `_STATE_MAP`을 `{"starting": STARTING, "idle": IDLE, "busy": BUSY, "waiting_input": WAITING_INPUT}`로 둔다. `start` 별칭을 없애고, `waiting`을 `waiting_input`으로 바꾼다.
- 쓰는 쪽이 방출 값을 처음부터 `AgentState.value`로 쓴다. 훅은 `SessionStart`에 `idle`, `Notification`에 `waiting_input`을, 엔트리포인트 seed는 `starting`을 쓴다.
- `_STATE_MAP`은 번역층으로 남긴다. 항등이 기본값이고, 어느 CLI가 실제로 다른 값을 방출함이 슬라이스 B 실측에서 확인되면 그 CLI의 `detect_state`만 override한다. 지금은 그런 사례가 없어 항등이다.
- `stopped`·`error`는 상태 파일에 안 실린다 — 프로세스 생존(`is_alive`·`exit_code`·`last_error`)으로 판정하므로(ADR-0016) `_STATE_MAP`에 두지 않는다.

## 결과
**좋은 점**
- 파일 값과 enum 값이 같아 번역 규칙을 따로 외울 필요가 없다. `start`·`idle` 중복과 `waiting`≠`waiting_input` 불일치가 사라진다.
- ADR-0018 형식 행의 자기모순(넷을 열거한 뒤 `starting`만 덧붙이던 것)이 해소된다 — `starting`이 어휘의 정식 멤버가 된다.
- `start`↔`starting` 혼동원을 우회하지 않고 제거한다. 뜻이 다른 두 값이 철자로 겹치는 상황 자체가 없어진다.

**대가 / 주의**
- 파일 값이 길어진다(`waiting_input`). 미관 대신 항등 규칙을 택한 결과다.
- 슬라이스 A 코드(base.py `_STATE_MAP`·단위 테스트)를 지금 바꾼다. 다만 방출자가 아직 없어(훅·seed 배선은 Phase 3) 동작 변화는 없고 매핑만 준비된다.
- 번역층(`_STATE_MAP`)을 없애지 않는다. 없애면 슬라이스 B에서 CLI별 값 차이가 측정됐을 때 흡수할 자리가 사라진다 — 항등을 기본값으로 담는 얇은 층으로 유지한다.

## 검토한 대안
### 대안 A — 두 어휘 분리 존치
파일 값을 `AgentState.value`와 다르게 두고 `start` 별칭·`waiting`을 유지. · **기각 사유**: 쓰는 쪽이 우리 코드라 값을 우리가 정하므로 분리가 필연이 아니다. 어댑터·번역층이 "갈라질 여지"를 준다는 것과 "지금 값을 다르게 둔다"는 별개다 — 기본값은 항등이어야 하고, 실측된 차이가 있을 때만 그 CLI만 갈라야 한다. 분리 존치는 `start`↔`starting` 혼동원과 `waiting`≠`waiting_input` 불일치를 근거 없이 남긴다.

### 대안 B — seed 값만 다른 이름(예: `seeding`)
STARTING을 표현하는 seed 값을 `starting`이 아닌 별도 이름으로. · **기각 사유**: 파일 값을 `AgentState.value`와 통일하기로 한 이상 STARTING의 파일 값은 `starting`이어야 항등이 성립한다. `seeding`은 다시 파일 값 ≠ enum 값을 만들어, 정리하려던 분리를 STARTING 자리에 되살린다.
