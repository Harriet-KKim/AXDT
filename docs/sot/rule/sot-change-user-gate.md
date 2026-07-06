---
id: rule-sot-change-user-gate
title: SoT 변경은 사용자 게이트 PR로만 한다
status: active
related: [rule-terminology, rule-protected-paths, rule-sot-readiness, ADR-0003]
---

# SoT 변경은 사용자 게이트 PR로만 한다

## 규칙문
> `docs/sot/`(specification·requirements·rule)의 변경은 **사용자를 Reviewer로 둔 PR**을 통해서만 `main`에 머지된다. Agent는 SoT를 **`main`에 직접(PR 없이) 커밋하지 않으며**, 변경이 필요하면 PR을 생성하고 **사용자 승인까지 일시정지**한다. 승인·머지되면 재개하고, 반려되면 PR을 수정해 다시 게이트를 거친다.

## 근거
- SoT는 시스템 전체가 권위로 삼는 기준이다. 게이트 없는 변경은 **모든 하위 작업의 전제**를 흔든다.
- 사용자 게이트 PR은 **회색지대 결정에 사람의 승인을 강제**하는 지점이다 — 요구/사양 변경, 중대한 방향 전환이 여기서 멈춘다.

## 적용범위
- **대상**: `docs/sot/` 전체. 변경을 시도하는 모든 역할(주로 Leader의 사양변경요청 → Maintainer가 PR화).
- **강제 지점**: 이 게이트를 우회한 SoT 변경(PR 없는 `main` 직접 push, task 브랜치에서의 `docs/sot/` 수정)의 차단은 `rule-protected-paths`의 허브 게이트가 담당한다(`docs/sot/**` = 사용자 게이트 PR로만). clone 내 로컬 수정은 권위가 없어 게이트를 통과하지 못한다(진실의 소스는 `main`).
- **예외**: 없음. interim 문서는 본 규칙 대상이 아니다(자유 변경).

## 예시
**준수 (✓)**
- Leader가 report에 "사양 X 보완 필요" 기록 → Maintainer가 필요 판단 후 SoT PR 생성, 사용자 승인 대기.
- 사용자가 PR 승인·`main` 머지 → Maintainer가 작업 재개. 반려 시 PR 수정 후 재요청(게이트 유지).
- 규칙(`docs/sot/rule/`) 변경도 동일 — rule 문서 수정 역시 PR로만.

**위반 (✗)**
- Agent가 `requirements.md`를 PR 없이 직접 수정·커밋. → 게이트 우회, 권위본을 무통제 변경.
