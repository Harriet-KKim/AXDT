---
id: ADR-0003
title: 에이전트 통신은 tmux 하향·report 상향·Leader 허브로 구성한다
status: accepted
date: 2026-06-26
decision: D2
related: [ADR-0001, ADR-0002, ADR-0004, rule-subagent-no-direct-communication, rule-leader-coordination-via-maintainer]
---

# ADR-0003: 에이전트 통신은 tmux 하향·report 상향·Leader 허브로 구성한다

## 상태
Accepted (2026-06-26) · 관련 결정 D2

## 맥락
여러 역할(Maintainer·Leader·Developer·Reviewer·Tester)이 협업하되 workspace/컨테이너로 **격리**돼야 한다(D3). 통신 경로를 정해야 했고, 핵심 제약은 **역방향 tmux 채널이 없다**는 점이다 — Maintainer는 Leader 세션에 주입할 수 있으나, Leader는 같은 방식으로 Maintainer에 올릴 수 없다.

이 ADR은 **에이전트 간 통신(D2)** 만 다룬다 — 사용자↔Maintainer(메신저·Web), 메신저 inbound 브릿지, Watcher→Maintainer 경로는 범위 밖이다.

## 결정
- **Maintainer→Leader**: tmux `send-keys`로 prompt 직접 주입(별도 파일 채널 없음).
- **Leader→Maintainer**: **report 파일**(상향 통신 + 요약 겸용).
- **Leader⇆Leader**: 직접 통신 지양 → Maintainer 경유.
- **Leader⇄Developer/Reviewer/Tester**: Leader가 호출·결과 수신하는 **허브**. sub-agent는 Leader에게만 응답하며 상호 통신 없음.

## 결과
**좋은 점**
- 경로가 역할 위상과 일치한다 — 상주 Maintainer가 주입, 격리된 Leader는 파일로 보고.
- 격리가 보존되고 상호작용 그래프가 단순(별형)해진다.
- report가 **상태(`ADR-0004`)와 통신을 한 매체**로 통합한다.

**대가 / 주의**
- 상향이 파일 읽기/폴링에 의존해 즉시성은 tmux 하향보다 낮다.
- Leader가 허브라 sub-agent 루프의 병목이 될 수 있다(범위 내 수용).

## 검토한 대안
### 대안 A — 공유 메시지 버스 (전 에이전트 pub/sub)
모두가 한 버스에 게시·구독. · **기각 사유**: 격리 위반, 별도 인프라 도입(`ADR-0002`와 상충), 직접통신 그래프가 폭발한다.

### 대안 B — 양방향 파일 채널 (하향도 파일로)
Maintainer→Leader도 파일로. · **기각 사유**: 상시 Maintainer엔 tmux 즉시 주입이 더 자연스럽다. 하향까지 파일로 하면 지연·폴링 부담만 는다.

### 대안 C — sub-agent 간 직접 통신 허용
Developer↔Reviewer 직접 교신. · **기각 사유**: 추적·책임이 흐려지고 Leader의 구현→리뷰→수정 루프 통제가 깨진다(`rule-subagent-no-direct-communication`).

### 대안 D — Leader 간 직접 의존성 조율
Leader끼리 직접 협상해 workspace 의존을 맞춤. · **기각 사유**: workspace 격리(D3)를 깨고, 전체 진척을 아는 주체 없이 의존이 얽힌다 → 조율은 Maintainer 경유(`rule-leader-coordination-via-maintainer`).
