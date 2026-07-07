---
id: rule-protected-paths
title: 보호 경로는 지정된 주체만 수정한다
status: active
related: [rule-progress-single-writer, rule-sot-change-user-gate, rule-sot-readiness, rule-report-to-progress-authority, rule-branch-workspace-naming, rule-terminology, ADR-0007]
---

# 보호 경로는 지정된 주체만 수정한다

## 규칙문
> 저장소의 일부 경로는 **쓰기 권한이 특정 주체로 제한된 "보호 경로"**다. 그 외 역할이 자신의 task 브랜치/workspace에서 보호 경로를 수정하면 위반이며, **컨테이너가 접근할 수 없는 호스트/허브 측 게이트가 해당 push를 거부**한다. 어떤 경로가 누구에게 열려 있는지는 아래 표가 **단일 명세**다. 강제 스크립트와 그 정책 표는 신뢰 ref(base) 버전으로 읽어 검사하며, 후보 브랜치가 검사 규칙·검사 코드를 수정하지 못하게 한다.

## 근거
- 규범(progress 단일 작성자·SoT 사용자 게이트·plan 배정)이 여러 규칙에 흩어져 있으면 강제 장치가 참조할 **기계가 읽을 단일 목록**이 없다. 이 규칙이 그 목록을 한곳에 모은다.
- clone 격리 모델(`ADR-0006`)에서는 보호 경로(`progress.md`·`docs/sot/`·`plan/` 등)가 각 Leader clone에 함께 포함돼 로컬 수정이 가능하다. 물리 마운트(D3)는 유닛 간 격리만 담당하고 clone 내부의 이 경로들은 보호하지 못하므로, 호스트/허브 측 게이트가 유일한 강제 지점이다(`ADR-0007`). 로컬 훅은 권고 수준이며 우회할 수 있다.
- 게이트가 읽는 정책(이 표)이 후보 브랜치 버전이면 에이전트가 검사 규칙을 수정해 우회할 수 있으므로, 게이트는 신뢰 ref의 표로 검사한다.

## 적용범위
**대상**: 모든 task 브랜치/workspace에서의 커밋·push. 보호 경로 명세 — **행이 겹치면 더 제한적인(더 좁은 권한) 행이 우선**한다:

| 경로 | 쓰기 허용 주체 | 강제 종류 |
|---|---|---|
| `docs/sot/**` (README·_TEMPLATE 포함) | **사용자 게이트 PR로만** (`rule-sot-change-user-gate`) | 경로 |
| `docs/interim/progress.md` | **Maintainer 단독** (`rule-progress-single-writer`) | 경로 |
| `docs/interim/plan/**` | **Maintainer** (wave/task 분해·배정) — Leader는 읽기만 (`rule-terminology`) | 경로 |
| `docs/interim/sot-readiness-review.md` | **Maintainer** (감사 로그 기록·수용/기각(accepted·rejected) 사유 반영 조율; 검토 실행은 호스트 CI) — `rule-sot-readiness` ② 감사 로그 | 경로 |
| `docs/interim/**/README.md` · `docs/interim/**/_TEMPLATE.md` | Maintainer / 사용자 게이트 — task 산출물이 구조·규약을 자동 변경 금지 | 경로 |
| 저장소 거버넌스 (`WIP/**` ‡, 루트 `README.md`·`LICENSE`·`.gitignore`) | AXDT 셋업 주체(사람/Maintainer) — task 브랜치 자동 수정 금지 | 경로 |
| `docs/interim/report/<task>.md` | 그 task에 배정된 Leader만 — 다른 task의 report 수정 금지 | 경로·ref + 주체† |
| `src/**` · `test/**` · `docs/interim/ADR/*.md`(본문; README·_TEMPLATE은 위 거버넌스 행 우선) | 해당 task 담당 Leader와 그 sub-agent | (자유 — 보호 대상 아님) |

**강제 종류 — 지금 강제되는 것과 연기되는 것** (`ADR-0007`):
- **경로**(무엇을·어디에) — "task 브랜치 push의 diff가 이 경로를 건드리면 거부." 허브 서버사이드 게이트가 **무인증서도** 판정 → **Phase 3 baseline**으로 강제.
- **ref** — report는 push 대상 ref(`w<n>.t<n>`, `rule-branch-workspace-naming`)와 파일명이 **정합해야** 통과. ref↔경로 규칙도 무인증서 성립.
- **주체 †**(누가) — ref 위장(Leader A가 B의 ref로 push해 B의 report 위조)을 막으려면 **인증/provenance가 필요**하다. 무인증 허브(`ADR-0006`)에선 이 부분은 **하드닝 전까지 advisory**다. 즉 report의 "그 Leader만"은 ref↔경로 정합까지 게이트가 강제하고, ref 위장 차단은 연기된다.

로컬 pre-commit 훅(권고)은 위 모든 보호 경로 위반을 즉시 경고하나 우회할 수 있어 강제가 아니다(강제 종류 열은 강제 지점인 허브 게이트 기준).

**예외**: Phase 0·1의 1회성 스캐폴딩/셋업(빈 양식·디렉터리 생성)은 정상 워크플로 이전이므로 본 규칙과 별개다. 대상 프로젝트가 고유 보호 경로를 추가할 때는 위 표에 행을 더한다.
‡ `WIP/`는 **대상 프로젝트 기준** 보호다 — AXDT를 대상으로 개발(도그푸딩)할 때 `WIP/`는 그 대상의 코드이므로 해당 프로젝트 plan의 지배를 받는다(D12).

## 예시
**준수 (✓)**
- Leader가 `src/`와 자기 task의 `report`를 수정해 커밋. progress·sot·plan은 손대지 않음 → 게이트 통과.
- progress 갱신이 필요하면 Leader는 자기 report에만 쓰고, Maintainer가 수용해 progress를 갱신한다(`rule-report-to-progress-authority`).

**위반 (✗)**
- Leader가 task 브랜치에서 `docs/interim/progress.md`를 직접 고쳐 push → 로컬 훅이 경고(우회 가능), **허브 게이트가 경로 규칙으로 거부**.
- Leader가 자기 `plan/task` 파일의 DoD·의존을 넓혀 자가수정 → plan은 Maintainer 소유, 거부.
- ref `w1.t1`로 push하면서 `report/w1.t2.md`(다른 task)를 수정 → ref↔경로 불일치, 거부.
- Reviewer가 `docs/sot/specification/`를 task 브랜치에서 직접 수정 → 사용자 게이트 PR 우회, 거부.

> **주의(하드닝 연기)**: Leader A가 B의 ref `w1.t2`로 위장 push해 `report/w1.t2.md`를 위조하는 경로는 무인증 허브에서 경로·ref 규칙만으로 차단되지 않으며, 인증/provenance 하드닝의 대상이다(`ADR-0006`·`ADR-0007`).
