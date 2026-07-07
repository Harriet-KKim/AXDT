# Progress — Maintainer 진행 기록

> **단일 작성자: Maintainer.** 다른 어떤 역할도 이 파일을 직접 고치지 않는다(`rule-progress-single-writer`).
> 이 파일은 시스템이 **수용한** task 상태의 단일 권위 색인이다. Leader의 자기보고는 `report/`에만 적고, Maintainer가 수용할 때 여기에 반영된다(`rule-report-to-progress-authority`).

<!--
엄격 스키마 MD 테이블(고정 컬럼 5개 + 통제 status 어휘, D7)은 Phase 4에서 확정했다.
컬럼·어휘·전이·정합의 단일 정의원은 `WIP/axdt/progress/schema.py`이며, 설계 근거는
`WIP/specs/2026-07-05-phase4-progress-tracking-design.md`. report는 컬럼이 아니라
canonical 경로 `docs/interim/report/<task>.md`로 판정한다(pointer 중복 제거).
아래 테이블이 파일 내 유일한 MD 테이블이어야 한다. 실제 task 행은 Maintainer가 추가한다.
-->

| wave | task | status | leader | updated |
|---|---|---|---|---|
