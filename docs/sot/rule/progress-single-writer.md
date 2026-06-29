---
id: rule-progress-single-writer
title: progress 원장은 Maintainer만 기록한다 (단일 작성자)
status: active
related: [rule-report-to-progress-authority, ADR-0004, ADR-0003]
---

# progress 원장은 Maintainer만 기록한다 (단일 작성자)

## 규칙문
> `docs/interim/progress.md` 를 **쓰고 갱신하는 주체는 Maintainer 단 하나**다. 다른 어떤 역할(Leader·Developer·Reviewer·Tester·Watcher)도 progress를 직접 수정하지 않는다.

Leader가 진척을 알리는 경로는 **자신의 report 파일**뿐이다. 그 내용이 progress에 반영될지는 Maintainer가 report를 읽고 **수용할 때** 결정된다.

## 근거
- progress는 "시스템이 참으로 수용한 상태"를 담는 **권위 원장**이다. 작성자가 여럿이면 동시 기록 경합·상호 덮어쓰기로 권위가 깨진다.
- 단일 작성자는 progress를 **직렬화된 단일 권위 색인**으로 만들어, Web 브리핑·의사결정·상태 복원이 progress를 단일 기준점으로 삼게 한다(복원 시 progress가 가리키는 report까지 함께 읽는다).
- 쓰기 주체를 Maintainer로 못박으면 Leader의 자기보고(report)와 시스템의 수용(progress)이 **다른 주체·다른 파일**로 분리된다. 둘 사이의 권위 흐름은 `rule-report-to-progress-authority`가 별도로 규정한다(이 규칙은 "누가 쓰는가"에 한정).

## 적용범위
- **대상**: `docs/interim/progress.md`의 **내용·상태·각 report 포인터 기록/갱신**(모든 대상 프로젝트). 쓰기 권한은 Maintainer 역할에 한정. (초기 빈 양식/스캐폴딩 생성은 Phase 0·1의 1회성 셋업으로 본 규칙과 별개.)
- **예외**: 없음. (Leader의 상태 주장은 report에만 기록한다.)

## 예시
**준수 (✓)**
- Leader가 task를 끝내고 자기 report를 `report.status: done` 으로 갱신 → Maintainer가 report를 읽고 수용 판단 후 progress 행을 `done` 으로 승격.

**위반 (✗)**
- Leader가 `progress.md` 에서 자기 task 행을 직접 `done` 으로 고침. → 권위 원장을 우회한 자기수용. 다른 Leader 기록과 경합하고 Maintainer 게이트를 건너뛴다.

> 위 `done`·`report.status` 등 status 값은 예시다. 확정된 통제 status 어휘는 progress 스키마(D7)에서 정의한다.
