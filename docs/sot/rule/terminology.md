---
id: rule-terminology
title: 모든 문서는 SoT와 Interim으로 구분하고, interim은 정해진 작성자만 쓴다
status: active
related: [rule-sot-change-user-gate, rule-progress-single-writer, rule-report-to-progress-authority]
---

# 모든 문서는 SoT와 Interim으로 구분하고, interim은 정해진 작성자만 쓴다

## 규칙문
> 모든 문서는 **SoT(Source of Truth, 권위본)** 와 **Interim(중간 산출물)** 중 하나로 분류되며, 위치·변경통제·작성자가 분류에 따라 정해진다.

- **SoT** = `docs/sot/` (specification·requirements·rule). 권위본 — **Agent가 작성**하되 **변경은 사용자 게이트 PR로만**.
- **Interim** = `docs/interim/` (ADR·plan·report·progress). 작업 중 **Agent가 생성·변경**(원칙적으로 자유, 단 개별 파일에 더 좁은 제약 가능 — 아래 표).

interim 파일별 작성자·상태 보유는 다음으로 고정한다.

| 파일 | 역할 | 작성자 | status |
|---|---|---|---|
| plan (wave/task) | 작업 정의·구조 | Agent (제약 없음) | 없음 |
| report | task별 상세 + Leader 자기보고 | Leader | `report.status` |
| progress | 오케스트레이션 색인 + 수용 상태 + 각 report 포인터 | Maintainer 단독 | `progress.status` |

## 근거
- 핵심 구분은 "**권위본이라 변경이 통제되는가(SoT)** vs **작업 중 자유롭게 바뀌는가(interim)**"다. 이 한 줄이 변경통제·작성권한·신뢰도를 가른다.
- interim은 사람이 아니라 **Agent의 작업 공간**이다. 누가 무엇을 쓰는지 고정해야 권위 흐름과 크래시 복원이 성립한다.

## 적용범위
- **대상**: `docs/` 하위 전체 문서. 모든 역할.
- **예외**: AXDT 자체 설계 문서(자체 구현 D12·자체 ADR D13)는 `WIP/`에 두며 본 분류와 별개.

## 예시
**준수 (✓)**
- requirements 변경은 SoT라 사용자 게이트 PR로 처리. report는 Leader가 자유롭게 갱신.

**위반 (✗)**
- Leader가 progress를 직접 수정(작성자 위반) / spec을 PR 없이 직접 편집(SoT 변경통제 위반).
