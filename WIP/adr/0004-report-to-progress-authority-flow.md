---
id: ADR-0004
title: 상태 권위는 report.status에서 progress.status로 한 방향으로 흐른다
status: accepted
date: 2026-06-26
related: [ADR-0001, ADR-0002, ADR-0003, rule-report-to-progress-authority, rule-progress-single-writer]
---

# ADR-0004: 상태 권위는 report.status에서 progress.status로 한 방향으로 흐른다

## 상태
Accepted (2026-06-26) · 관련 결정: 상태 모델(TODO "상태 모델 (status flow)" 섹션)

## 맥락
상태가 여러 곳에 존재한다 — Leader의 자기보고와 오케스트레이터의 수용. 어디를 권위로 삼을지 정하지 않으면 웹·의사결정·복원이 무엇을 믿을지 모른다. 게다가 "Leader의 주장"과 "시스템의 수용"은 본질적으로 **다른 질문**이라, 한 칸에 합치면 정보가 손실된다.

## 결정
상태는 **계층마다 권위 주체를 하나씩** 두고 흐름은 한 방향이다. `report.status`(Leader가 자기 작업을 주장) → Maintainer가 읽고 **검토·수용(게이트)** → `progress.status`(수용된 진실) 기록. 이 승격 지점이 **집계 + 수용 + 필요 시 Reviewer/Tester/사용자 게이트 + wave 롤업**이 일어나는 곳이다. 시스템·웹·의사결정은 **항상 progress를 권위로** 읽는다. report와 progress가 다르면 모순이 아니라 **"수용 대기"** 정상 상태다. (규범 자체는 `rule-report-to-progress-authority`·`rule-progress-single-writer`가 규정하며, 본 ADR은 그 **근거**를 담는다.)

## 결과
**좋은 점**
- 보고와 수용이 분리돼 **검토 게이트가 명시적**이다.
- progress는 색인 + report 포인터 + Maintainer 단독 기록이라 권위가 거기로 단일화된다 — 웹·크래시 복원이 한 기준을 읽는다.
- 모순처럼 보이는 상태를 **정상 워크플로**로 해석할 수 있다.

**대가 / 주의**
- 같은 개념이 두 필드에 표현돼 동기화 지연이 생긴다 — 의도된 것으로, 그 간극이 곧 게이트다.
- progress 쓰기가 Maintainer 단독이어야 본 흐름이 성립한다(`rule-progress-single-writer`).

## 검토한 대안
### 대안 A — 단일 공유 status 필드
모두가 같은 칸을 갱신. · **기각 사유**: 보고와 수용이 뭉개지고 경합한다. 검토 게이트 지점이 사라진다.

### 대안 B — report를 권위로 (progress는 단순 미러)
Leader 보고가 곧 진실. · **기각 사유**: Maintainer의 검토·롤업·사용자 게이트가 무력화된다.

### 대안 C — 양방향 동기화
report↔progress를 양방향으로 맞춤. · **기각 사유**: 권위 방향이 모호해지고 루프·충돌 위험이 생긴다.
