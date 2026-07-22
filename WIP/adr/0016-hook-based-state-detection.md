---
id: ADR-0016
title: 상태판정을 화면 마커 스캔에서 CLI 훅이 쓴 상태 파일 읽기로 바꾼다
status: accepted
date: 2026-07-21
decision: D4
related: [ADR-0005]
---

# ADR-0016: 상태판정을 화면 마커 스캔에서 CLI 훅이 쓴 상태 파일 읽기로 바꾼다

## 상태
Accepted (2026-07-21) · 관련 결정 D4

## 맥락
`poll_state`/`detect_state`는 원래 화면 출력의 꼬리에서 마커 부분문자열을 찾아 세션 상태를 판정했다. §8.3a 라이브 측정에서 이 방식이 현재 CLI(claude 2.1.209)에 맞지 않음이 드러났다.

- 캐럿·푸터가 IDLE과 BUSY에서 같은 문자열을 쓴다 — 마커로 두 상태를 가를 수 없다.
- 스피너 프레임이 무작위라 고정 마커로 매칭되지 않는다.
- statusLine에 상태값이 실리지 않는다.

2차 확인 수단으로 `/btw`(문서화된 명령)를 검토했으나, 실행 중 TUI 세션에 접근할 out-of-band 제어 채널이 없다. `/btw`도 실제 프롬프트와 같은 제출 경로(`send_text`+제출 키)로 넣을 수밖에 없고, 그 제출이 `UserPromptSubmit`을 발화시켜 확인하려던 IDLE을 BUSY로 바꾼다. 확인 행위가 확인 대상을 바꾸는 자기모순이라 2차 확인으로 쓸 수 없다.

## 결정
- `poll_state`/`detect_state`를 화면 마커 스캔에서 "CLI 훅이 쓴 상태 파일 읽기"로 바꾼다. 훅이 전이 시점에 한 줄 JSON `{"state", "ts"}`를 원자적으로 쓰고(핸드오프 §3), 백엔드가 읽는다. `detect_state`는 추출된 상태값(`idle`·`busy`·`waiting`·`start`)을 `AgentState`로 매핑한다.
- 낡음 확인은 `/btw`가 아니라 하트비트로 한다. `PreToolUse`·`PostToolUse`가 매 도구 호출마다 `busy`를 갱신해, 긴 BUSY 구간에도 상태 파일이 신선하게 유지되어 "진짜 idle"과 "Stop 훅 누락"을 가른다.
- 훅으로 나오지 않는 `ERROR`·`STOPPED`는 상태 파일이 아니라 프로세스 생존(`is_alive`·`exit_code`·`last_error`)으로 판정한다.
- `/btw` 2차 확인은 폐기한다. 비교란 여부만 슬라이스 B 측정 항목으로 남긴다.

이 변경은 `AgentRunner.poll_state() -> AgentState` 경계 뒤에서 일어난다. phase2 소비 코드(`inject`·`converge`)는 `poll_state`와 `AgentState`만 부르므로 판정 내부 교체에 영향받지 않는다.

## 결과
**좋은 점**
- 판정이 결정적이다. 화면 출력 포맷에 대한 결합이 사라진다.
- 하트비트가 `Stop` 훅 누락과 진짜 idle을 가른다 — 마커 방식엔 없던 구제책이다.
- 계약 경계 뒤 변경이라 phase2 시그니처가 그대로다.

**대가 / 주의**
- 세션이 상태를 방출하려면 이미지에 훅 설정이 구워져 있어야 한다 — 라이브 동작은 Phase 3(훅 굽기)가 선행이다.
- `ts` 순서·역행 정책과 하트비트 임계, codex의 `SessionStart`·`Stop` 훅 발화, 제출·클리어 키는 슬라이스 B(실 CLI 측정)까지 잠정이다.

## 검토한 대안
### 대안 A — 화면 마커 스캔 유지
출력 꼬리에서 마커를 찾아 판정. · **기각 사유**: §8.3a 실측에서 캐럿·푸터가 IDLE/BUSY를 공유하고 스피너가 무작위라 오판한다.

### 대안 B — `/btw`로 2차 확인
실행 중 세션에 `/btw`를 넣어 응답으로 생존·상태 확인. · **기각 사유**: 제출이 `UserPromptSubmit`을 발화시켜 확인하려던 IDLE을 BUSY로 바꾸는 자기모순. out-of-band 제어 채널이 없어 교란 없는 확인이 불가능하다.

### 대안 C — statusLine·출력 폴링
화면을 주기적으로 폴링해 상태를 읽음. · **기각 사유**: 현재 CLI가 statusLine에 상태를 싣지 않고, 출력 결합 문제가 대안 A와 같다.
