---
id: rule-sot-change-user-gate
title: SoT 변경은 사용자 게이트 PR로만 한다
status: active
related: [rule-terminology, rule-protected-paths, rule-sot-readiness, ADR-0003]
---

# SoT 변경은 사용자 게이트 PR로만 한다

## 규칙문
> `docs/sot/`(requirements·specification·test-design·rule)의 변경은 **사용자를 Reviewer로 둔 PR**을 통해서만 `main`에 머지된다. Agent는 SoT를 **`main`에 직접(PR 없이) 커밋하지 않으며**, 변경이 필요하면 **`sot/<slug>` 브랜치에서 PR을 생성**하고 **사용자 승인까지 일시정지**한다. 승인·머지되면 재개하고, 반려되면 PR을 수정해 다시 게이트를 거친다.

## 근거
- SoT는 시스템 전체가 권위로 삼는 기준이다. 게이트 없는 변경은 **모든 하위 작업의 전제**를 흔든다.
- 사용자 게이트 PR은 **회색지대 결정에 사람의 승인을 강제**하는 지점이다 — 요구/사양 변경, 중대한 방향 전환이 여기서 멈춘다.

## 적용범위
- **대상**: `docs/sot/` 전체. 변경을 시도하는 모든 역할(주로 Leader의 사양변경요청 → Maintainer가 PR화).
- **브랜치**: SoT PR은 `sot/<slug>` 브랜치(`<slug>` = 소문자 kebab-case)에서 연다. task 브랜치(`w<n>.t<n>-<slug>`, `rule-branch-worktree-naming`)와 네임스페이스가 구분된다. 변경 1건당 새 브랜치를 쓰고 머지·폐기 후 재사용하지 않는다(같은 주제를 다시 고치면 접미로 구분: `sot/auth-2`. force-push 차단·squash 비활성이 걸린 브랜치를 재사용하면 이력이 꼬인다). 이 브랜치의 감사 이력 보존(squash 비활성·force-push 차단)과 소스 브랜치가 `sot/*`여야 한다는 강제는 `rule-sot-readiness` 강제 매핑이 규정한다.
- **강제 지점**: 이 게이트를 우회한 SoT 변경의 차단은 두 층으로 나뉜다 — **task 브랜치에서의 `docs/sot/` 수정**은 `rule-protected-paths` 허브 게이트가 거부하고(`docs/sot/**` = 사용자 게이트 PR로만; 경로·Phase 3), **PR 없는 `main` 직접 push**는 `main` 브랜치 보호(require-PR + ①②③ 머지 게이트)가 거부한다(`rule-sot-readiness` 강제 매핑·Phase 6). clone 내 로컬 수정은 권위가 없어 게이트를 통과하지 못한다(진실의 소스는 `main`).
- **예외**: 없음. interim 문서는 본 규칙 대상이 아니다(자유 변경).

## 예시
**준수 (✓)**
- Leader가 report에 "사양 X 보완 필요" 기록 → Maintainer가 필요 판단 후 SoT PR 생성, 사용자 승인 대기.
- 사용자가 PR 승인·`main` 머지 → Maintainer가 작업 재개. 반려 시 PR 수정 후 재요청(게이트 유지).
- 규칙(`docs/sot/rule/`) 변경도 동일 — rule 문서 수정 역시 PR로만.

**위반 (✗)**
- Agent가 `requirements.md`를 PR 없이 직접 수정·커밋. → 게이트 우회, 권위본을 무통제 변경.
