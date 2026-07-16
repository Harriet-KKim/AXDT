---
id: rule-report-to-progress-authority
title: 상태 권위는 report에서 progress로 한 방향으로만 흐른다
status: active
scope: local
related: [rule-progress-single-writer, ADR-0004]
---

# 상태 권위는 report에서 progress로 한 방향으로만 흐른다

## 규칙문
> 상태의 권위는 **`report.status`(Leader 자기보고) → `progress.status`(Maintainer가 수용한 진실)** 한 방향으로만 흐른다. 시스템·웹·의사결정은 **항상 progress를 권위로** 읽는다. 둘이 다르면 모순이 아니라 **"Maintainer 처리/수용 대기"** 라는 정상 상태다.

## 근거
- `report.status`는 "Leader가 **어떻게 보고하는가**", `progress.status`는 "오케스트레이터가 **무엇을 참으로 수용했는가**" — 서로 다른 질문에 답한다. 한 칸으로 합치면 보고와 수용이 뭉개진다.
- report→progress 승격이 곧 Maintainer의 **검토/게이트 지점**이다(집계·수용·필요시 Reviewer/Tester/사용자 게이트·wave 롤업). 설계 논증은 `ADR-0004`.

## 적용범위
- **대상**: 모든 task의 report와 진행 기록 progress.
- **예외**: 없음. progress를 쓰는 주체는 Maintainer 단독이어야 본 흐름이 성립한다(→ `rule-progress-single-writer`).

## 예시
**준수 (✓)**
- `report.status=done`인데 `progress.status=in-review` → 정상(수용 대기). 웹은 progress(in-review)를 권위로 표시.

**위반 (✗)**
- progress를 보지 않고 `report.status`만 보고 task를 완료 처리. → 승격·게이트를 건너뛰고 비권위 상태를 진실로 취급.

> `done`·`in-review` 등 status 값은 예시다. 확정된 통제 status 어휘는 progress 스키마(D7)에서 정의한다.
