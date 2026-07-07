# Progress — Maintainer 진행 기록

> **단일 작성자: Maintainer.** 다른 어떤 역할도 이 파일을 직접 고치지 않는다(`rule-progress-single-writer`).
> 이 파일은 시스템이 **수용한** task 상태의 단일 권위 색인이다. Leader의 자기보고는 `report/`에만 적고, Maintainer가 수용할 때 여기에 반영된다(`rule-report-to-progress-authority`).

## 진행 표 (빈 양식)

<!--
고정 컬럼(D7). 통제된 status 어휘와 엄격 스키마 검증은 Phase 4에서 확정한다.
Phase 1은 이 컬럼 구조의 빈 양식만 제공한다 — 실제 task 행은 스키마 확정 후 Maintainer가 추가한다.
컬럼: wave/task = 식별자(`w<n>` 또는 `w<n>.t<n>-<slug>`) · progress.status = 수용된 상태(Maintainer 소유) ·
      담당 Leader · report = 해당 report 파일 경로.
-->

| wave/task | progress.status | 담당 Leader | report |
|---|---|---|---|

_현재 추적 중인 task 없음 — 스키마 확정(Phase 4) 후 Maintainer가 행을 추가한다._
