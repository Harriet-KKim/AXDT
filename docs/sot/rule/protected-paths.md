---
id: rule-protected-paths
title: 보호 경로는 지정된 주체만 수정한다
status: active
scope: local
related: [rule-role-responsibilities, rule-adr-recording, rule-progress-single-writer, rule-sot-change-user-gate, rule-sot-readiness, rule-report-to-progress-authority, rule-branch-workspace-naming, rule-terminology, ADR-0007]
---

# 보호 경로는 지정된 주체만 수정한다

## 규칙문
> 저장소의 일부 경로는 **쓰기 권한이 특정 주체로 제한된 "보호 경로"**다. 그 외 역할이 자신의 task 브랜치/workspace에서 보호 경로를 수정하면 위반이며, **컨테이너가 접근할 수 없는 호스트/허브 측 게이트가 해당 push를 거부**한다. 어떤 경로가 보호 대상이고 그 예외(쓰기 허용) 주체가 무엇인지는 아래 표가 **경로 축 단일 명세**다. 강제 스크립트와 그 정책 표는 신뢰 ref(base) 버전으로 읽어 검사하며, 후보 브랜치가 검사 규칙·검사 코드를 수정하지 못하게 한다.

**역할 축과 경로 축은 서로 다른 단일 명세를 갖는다.** 이 문서의 표는 **경로 축** 명세다 — 무엇이 보호 대상이고 허브 게이트가 무엇을 막는가. 반면 **역할 → 쓰기 경로** 매핑(어느 역할이 어디에 쓰는가)의 단일 명세는 `rule-role-responsibilities`이며, 계약 검사가 파싱하는 역할 축 오라클도 그 문서다. 이 문서는 역할 축 파싱 대상이 아니다. 두 문서의 명세가 겹칠 때는 **더 제한적인(더 좁은 권한) 쪽이 이긴다.** 특히 아래 표에서 `src/**`·`test/**`를 "자유(보호 대상 아님)"로 두는 것은 경로 축 판정이며, 그 경로들에 대한 역할 간 구분(Developer=`src/**`·`test/**`(주로 `src/`), Tester=`test/**`)은 `rule-role-responsibilities`가 권고로 명세한다. `docs/interim/ADR/*.md`(본문)는 Maintainer 소유 거버넌스 경로다(아래 표) — 초안의 "자유(Leader)" 배치에서 옮겼다.

## 근거
- 규범(progress 단일 작성자·SoT 사용자 게이트·plan 배정)이 여러 규칙에 흩어져 있으면 강제 장치가 참조할 **기계가 읽을 단일 목록**이 없다. 이 규칙이 그 목록을 한곳에 모은다.
- clone 격리 모델(`ADR-0006`)에서는 보호 경로(`progress.md`·`docs/sot/`·`plan/` 등)가 각 Leader clone에 함께 포함돼 로컬 수정이 가능하다. 물리 마운트(D3)는 유닛 간 격리만 담당하고 clone 내부의 이 경로들은 보호하지 못하므로, 호스트/허브 측 게이트가 유일한 강제 지점이다(`ADR-0007`). 로컬 훅은 권고 수준이며 우회할 수 있다.
- 게이트가 읽는 정책(이 표)이 후보 브랜치 버전이면 에이전트가 검사 규칙을 수정해 우회할 수 있으므로, 게이트는 신뢰 ref의 표로 검사한다.
- 검토 정책(검토 스킬·실행기·프롬프트 스캐폴드)이 보호되지 않으면, 일반 PR로 검토를 "항상 통과"로 약화한 뒤 다음 SoT PR에서 쓰는 2단계 우회가 가능하다 — 그래서 검토 정책 파일도 ③ 승인자 승인을 요구한다. 무력화 탐지는 ③ diff 검토가, 기존 판정 무효화는 `review_policy_epoch`가 담당한다(`rule-sot-readiness`).

## 적용범위
**대상**: 모든 task 브랜치/workspace에서의 커밋·push. 보호 경로 명세 — **행이 겹치면 더 제한적인(더 좁은 권한) 행이 우선**한다:

| 경로 | 쓰기 허용 주체 | 강제 종류 |
|---|---|---|
| `docs/sot/**` (README·_TEMPLATE 포함) | **사용자 게이트 PR로만** (`rule-sot-change-user-gate`) | 경로 |
| 검토 정책 — `.claude/skills/sot-readiness-review/**` · **실행기 manifest가 열거하는 경로**(Phase 6에서 실 경로·artifact ID 확정) — manifest는 두 부류를 **구분해 열거**한다: **(a) 보호 + epoch 결속** = 실행기 코드(CI 하니스·입력 직렬화기·응답 파서·판정 키 계산기·프롬프트 스캐폴드), **(b) 보호 전용** = ① 결정적 검사기(`sot-lint`) | **③ 사용자 게이트 승인자 승인 필요** (거버넌스 정책 무력화 방지 — `rule-sot-readiness` ②). manifest는 보호경로 glob과 `review_policy_epoch`의 실행기 revision digest에 **동일 출처**로 쓰이되 — **보호경로 glob은 (a)+(b) 전체**를, **epoch revision digest는 (a)만** 본다(즉 (a)는 보호+epoch 결속, (b)는 보호만). (b) ① 검사기는 키 캐시 없이 매 실행 결정적 재계산이라 보호만 필요하고 epoch엔 안 든다. task 브랜치 자동 수정 금지 | 경로 |
| `docs/interim/progress.md` | **Maintainer 단독** (`rule-progress-single-writer`) | 경로 |
| `docs/interim/plan/**` | **Maintainer** (wave/task 분해·배정) — Leader는 읽기만 (`rule-terminology`) | 경로 |
| `docs/interim/sot-readiness-review.md` | **Maintainer** (감사 로그 기록·수용/기각(accepted·rejected) 사유 반영 조율; 검토 실행은 호스트 CI) — `rule-sot-readiness` ② 감사 로그 | 경로 |
| `docs/interim/**/README.md` · `docs/interim/**/_TEMPLATE.md` | Maintainer / 사용자 게이트 — task 산출물이 구조·규약을 자동 변경 금지 | 경로 |
| `docs/interim/ADR/*.md` (본문) | **Maintainer** — Leader가 report로 설계 결정을 제안하면 Maintainer가 기록(`rule-role-responsibilities` 각주 ⁵) | 경로 |
| 저장소 거버넌스 (`WIP/**` ‡, 루트 `README.md`·`LICENSE`·`.gitignore`) | AXDT 셋업 주체(사람/Maintainer) — task 브랜치 자동 수정 금지 | 경로 |
| `docs/interim/report/<task>.md` | 그 task에 배정된 Leader만 — 다른 task의 report 수정 금지 | 경로·ref + 주체† |
| `src/**` · `test/**` | 해당 task 담당 Leader와 그 sub-agent | (자유 — 보호 대상 아님) |

**강제 종류 — 지금 강제되는 것과 연기되는 것** (`ADR-0007`):
- **경로**(무엇을·어디에) — "task 브랜치 push의 diff가 이 경로를 건드리면 거부." 허브 서버사이드 게이트가 **무인증서도** 판정 → **Phase 3 baseline**으로 강제.
- **ref** — report는 push 대상 ref(`w<n>.t<n>`, `rule-branch-workspace-naming`)와 파일명이 **정합해야** 통과. ref↔경로 규칙도 무인증서 성립.
- **주체 †**(누가) — ref 위장(Leader A가 B의 ref로 push해 B의 report 위조)을 막으려면 **인증/provenance가 필요**하다. 무인증 허브(`ADR-0006`)에선 이 부분은 **하드닝 전까지 advisory**다. 즉 report의 "그 Leader만"은 ref↔경로 정합까지 게이트가 강제하고, ref 위장 차단은 연기된다.

로컬 pre-commit 훅(권고)은 위 모든 보호 경로 위반을 즉시 경고하나 우회할 수 있어 강제가 아니다(강제 종류 열은 강제 지점인 허브 게이트 기준).

### 강제-필수 경로 (머지 관문 축 — Phase 6)
위 표는 **task 브랜치 push**를 허브 pre-receive 게이트가 거부하는 **task-push 축**이다. 이와 **별개 축**으로, **강제 장치 자체**(규칙 파일·② 검토 CI 워크플로·`.github/CODEOWNERS`·게이트 코드)를 바꾸는 PR은 SoT 문서 트리(`requirements`·`specification`·`test-design`)를 건드리지 않아 머지 컨트롤러의 통과(pass-through) 조항에 걸린다. 그래서 이 경로를 바꾸는 PR은 무관문 통과가 아니라 **결정권자 승인**을 요구한다(Phase 6 머지 게이트의 세 번째 분기 — 게이트 코어 로직은 Phase 6 소관). 이 "강제 = 머지 컨트롤러" 결정은 `ADR-0009`(SoT 완료 강제 = 호스트 머지 컨트롤러)에 근거한다 — 현 시점 `ADR-0009`는 아직 `main`에 없고 미머지 `phase6-enforcement` 브랜치(PR #13)에 초안(`proposed`)으로 있으며, `main`에 착지하면 이 인용을 확정 참조로 정리한다. Phase 6 게이트는 아래 블록을 **권위 정의로 읽는다** — 손사본을 두지 않으며, 이 목록을 바꾸는 측이 소비 측(Phase 6)에 통보한다.

```axdt-critical-paths
# 강제 장치 자체를 이루는 경로. 이 경로를 바꾸는 PR은 무관문 통과가 아니라 결정권자 승인 필요(Phase 6 머지 게이트).
# 경로는 저장소 루트 기준. glob: ** = 구분자 포함 0개 이상 세그먼트, * = 한 세그먼트 내 0개 이상 문자.
# critical <glob> : 변경 경로가 glob에 걸리면 그 PR을 '강제-필수'로 분류한다.
critical docs/sot/rule/**
# .github/workflows/** 전체를 강제-필수로 둔다 — '② 검토 CI 워크플로'보다 넓힌 보수적 확장이며
#   (워크플로 파일명 변경·신규 악성 워크플로 추가에 강건; 보안 통제는 과포함이 안전한 쪽 오류). ② CI 파일명이 확정되면 좁힐 수 있다.
critical .github/workflows/**
critical .github/CODEOWNERS
# Phase 3 게이트 코드(hubgate): 구현 예정 경로를 잠정 포함해 과도기 공백을 지금 닫는다(파일 생성 전엔 매칭 없음).
critical WIP/axdt/infra/hubgate.py
# Phase 6 게이트·컨트롤러 코어 코드 경로: 정식 이관 위치 확정 시 Phase 6가 변경 측으로서 통보해 추가한다
#   (현재 미이관 — 게이트 코드가 WIP/axdt/ 안에 있는 동안은 task-push 축의 WIP/** 도그푸딩 제외와 별개 축이며,
#    WIP/ 밖 정식 위치로 이관되면 task-push 축의 deny 대상 여부도 재검토).
#   ※ 전제조건: Phase 6 활성화 전에 반드시 실제 게이트·컨트롤러 코어 코드 경로를 이 블록에 추가한다.
# 결정권자 명단은 저장소 밖에 둔다(코드 무관) — 저장소 안에 두는 구성으로 바뀌면 그 경로도 여기에 추가.
```
`.github/CODEOWNERS`의 코드오너 검토 대상 경로 커버리지는 이 강제-필수 경로를 반영한다. 실제 `.github/CODEOWNERS` 파일 생성은 게이트 코드 경로 확정 + Phase 6 룰셋(`require_code_owner_review`) 활성화 시점에 맞춘다. 현재는 코드오너 다인 구성 전이라 코드오너 검토 강제는 비활성이며, `.github/CODEOWNERS` 경로 자체는 강제-필수로 남는다(파일 생성 시 그 변경도 결정권자 승인 대상).

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
