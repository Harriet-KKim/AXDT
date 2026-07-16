# 핸드오프 — SoT 완료 판정(`rule-sot-readiness`) 도입에 따른 교차-Phase 의존

> **RESOLVED (2026-07-07, main 병합 시점).** §3 귀속 충돌은 (A) Phase 6 흡수로 정합화됐고, 병합된 `docs/sot/rule/sot-readiness.md`의 강제 매핑 표(호스트 브랜치 보호 = Phase 6)와 phase6 스펙 §9 "귀속(Phase1 정합): 호스트 브랜치 보호 강제 = Phase 6"이 일치한다. §1 전문의 "현재 Phase 6 설계는 강제 = Phase 3이라 적었다"는 스테일(정합화 완료). **잔여(비차단):** §1의 강제 층 자체(집계 게이트 + 감사 이력 보존)는 아직 미구현 — Phase 6 강제 증분(`ADR-0009`, 미작성)으로 남는다. 아래 본문은 역사 기록으로 보존한다.
>
> **아키텍처 supersede (2026-07-13, D27·D28·`ADR-0014`).** 아래 **§0·§1·§3**의 다음 서술은 **현행 `rule-sot-readiness`가 정본이며 supersede됐다** — 역사 기록으로만 읽어라: (a) **키 정의** = 단일 판정 키·완전 결속 키(§0의 "SoT 트리 해시 + 적용 rule 지문")가 아니라 **두 키**(정합성 판정 키 4성분 + 선언 완전성 스윕 키); (b) **검사 결속** = ①·② verdict를 각각 required check로 거는 것(§1-1·§1-2·§1-6, §3의 "①②③ 필수 검사")이 아니라 **비필수 증거 검사 + 단일 필수 집계 게이트 `sot-readiness-gate`**; (c) **재검토 범위** = "지문만 변경 → 축3 한정 재검토"(§1-3)나 초기 마이그레이션의 "축3 스윕"(§1-8) 같은 부분 타겟팅이 아니라 **키가 바뀌면 projection 전량 홀리스틱**; (d) ① 형식의 미치환 표기는 `<...>`가 아니라 **`{{...}}`**(A2·D24). Phase 5/6 구현 세션은 §0·§1·§3이 아니라 현행 rule·`ADR-0014`·`ADR-0015`를 참조하라.
>
> 작성: phase1 세션 · 대상: **Phase3 세션**(phase3-isolation-infra) · **Phase5 세션**(phase5-agent-runner)
> 소스: `phase1` 브랜치 커밋 `a770050`. 원문은 `git show phase1:docs/sot/rule/sot-readiness.md`, `git show phase1:.claude/skills/sot-readiness-review/SKILL.md`로 읽을 수 있음.
>
> **갱신 (2026-07-07, D16·`ADR-0008`)**: 완료 트리에 **test-design(4번째 SoT 타입)** 이 추가됐다. 완료 문서류 = requirements·specification·**test-design** 셋이다. 아래 §1의 ① 형식 검사·재검토·D6 트리거는 모두 세 문서류 기준이다(테스트 설계 항목 ID = `TD-n`).

## 0. 무엇이 커밋됐나 (배경)

`phase1`에 문서 완료 판정 체계(코드네임 B)를 규칙+스킬로 도입했다. 핵심:

- **완료 = ① 형식 ∧ ② 정합성·공백 검토 ∧ ③ 사용자 승인**. 셋 다 **동일한 판정 키**에서 성립해야 참.
- **판정 키 = (SoT 트리 해시 + 적용 rule 지문)**. finding 단위 표시·대조에는 여기에 `(F-n + 내용 digest)`를 더한 **완전 결속 키**를 쓴다.
- 신뢰 모델: 감사 로그(`docs/interim/sot-readiness-review.md`)는 **사람이 읽는 비신뢰 사본**. 권위는 **호스트 필수 검사 상태**.
- 이 규칙은 "무엇이 완료인가"만 정의하고 **강제는 호스트 층에 위임**한다 — 그 위임 대상이 아래 두 세션의 작업이다.

이 문서가 넘기는 것은 **draft가 아니라 의존/요구 목록**이다. phase1은 다른 브랜치를 건드리지 않았다.

---

## 1. Phase5 세션 (→ Phase 6) — 흡수할 강제 층 [핵심]

`rule-sot-readiness`의 강제 매핑이 **①②③ 강제와 감사 이력 보존을 Phase 6(호스트 브랜치 보호)에 배정**한다. 그런데 현재 Phase 6 설계(`WIP/specs/2026-07-05-phase6-git-host-design.md`)는 이 층을 **비목표**로 두고 "강제 = Phase 3"이라 적었다(§1 비목표, §9 "merge=순수 원시기능", §8 "Phase 6은 소비, Phase 3은 강제"). → **귀속 충돌. 아래 §3 결정 필요.**

Phase 6이 흡수(또는 재귀속)해야 할 요구:

1. **① 형식 = 결정적 필수 검사(required status check)**. 검사 항목: req·spec·test-design 문서 존재, 항목 ID(`FR-n`/`NFR-n`/`SP-n`/`TD-n`), `covers`·`rules` 참조 무결성(dangling 없음; test-design의 `covers`는 요구·사양 항목을 가리킴), 미치환 `<...>` 없음(코드블록 제외), 금지어 없음, 수용 기준 자리 채움. 결정적(같은 콘텐츠=같은 결과).
2. **② 검토 = 호스트 CI 자동 실행**. SoT 콘텐츠가 바뀔 때마다 CI가 `sot-readiness-review` 스킬을 **콘텐츠당 1회** 자동 실행 → verdict(`review_blocked`/`review_clear`)를 required check 상태로 결속. CI 실행이라 작성 세션과 자연 분리(자기검토 편향 방지).
3. **판정 키 계산**. 적용 rule 지문 = **적용되는 각 rule 파일 전체 내용 해시를, 호스트가 그 PR의 제안된 머지 결과 상태에서 계산**(에이전트 산출 비신뢰). 검사 코드·정책 자체는 신뢰 ref(base)에서 읽음. 트리 해시는 **req·spec·test-design 세 문서류 콘텐츠**로 계산한다. 무효화: **req·spec·test-design 트리 변경 → 전체 재검토 / 적용 rule 지문만 변경 → 축3 한정 재검토**. 트리·지문 둘 다 안 바꾸는 커밋(감사 로그 등)은 재발화 안 함.
4. **CI 신뢰 산출물**. CI는 verdict와 함께 **(판정 키 + 각 open blocking finding의 `(F-n + 내용 digest)` 목록)**을 검사 산출로 낸다. 게이트는 감사 로그가 아니라 이 산출을 사용자 표시와 대조. `finding 내용 digest = (축 + 참조 문서·항목 ID + 심각도 + 설명 본문) 정규화 해시`, 정규화 규칙은 검사기가 단일 구현으로 고정.
5. **③ 승인 = 필수 승인 + dismiss-stale + up-to-date-before-merge**. 승인은 **판정 키에 대해서만** 유효 — req·spec·test-design push든 적용 rule 지문 변경이든 판정 키가 바뀌면 무효(dismiss-stale). fail-closed와 같은 키 기준.
6. **머지 게이트식**: `main` 머지 = **① ∧ ② 성립 ∧ ③** (동일 판정 키). **② 성립 = `review_clear` 또는 CI가 낸 open blocking finding 각각이 호스트 채널에서 `accepted`/`rejected` 표시를 받음**. `accepted`(위험수용)·`rejected`(오판)는 사용자 채널 결정이고 게이트가 검사 상태 위에 얹어 계산(② 재실행·상태변경 안 함). 사용자 표시는 완전 결속 키 참조. `main` 브랜치 보호는 **require-PR**(PR 없는 직접 push 거부)을 포함해 SoT가 승인된 PR 머지로만 `main`에 도달하게 한다(비-PR 직접 push 차단; `docs/sot/**`의 task 브랜치 경로 차단은 Phase 3 허브 게이트, §2 참조).
7. **감사 이력 보존 + 소스 브랜치 강제**: `sot/*`·`main` 브랜치 **squash 머지 비활성 + force-push 차단**(merge commit이 승인 head를 부모로 보존). **소스 브랜치가 `sot/*`가 아닌 SoT 변경 PR은 머지 게이트가 거부** — 아니면 감사 이력 보존 패턴이 우회된다(브랜치 규격 정의는 `sot-change-user-gate`, 강제는 이 층).
8. **초기 마이그레이션 스윕**: 이 강제가 활성화되는 시점(Phase 6 도입/뒤늦은 채택)에 그 이전 완료된 req·spec·test-design 전량을 **축3으로 최초 1회 스윕**해 `rules` 선언 완전성을 확립. 아울러 test-design 없이 요구·사양만으로 완료됐던 문서는 fail-closed(미완료)가 되므로 전환 계획이 필요하다(`ADR-0008` 대가).
9. **fail-closed**: 검사 상태가 없거나 현재 판정 키에 대한 것이 아니면 미완료 처리.

> 현재 Phase 6 설계는 1~9 중 어느 것도 다루지 않는다(호스트 클라이언트 = PR 열기·리뷰 요청·리뷰 커서 폴링·merge 원시기능까지). 위는 그 위에 얹히는 **브랜치 보호 + CI 강제 층**이다.

---

## 2. Phase3 세션 (→ Phase 3/4/7) — 델타·접점

- **Phase 3 (허브 게이트)**: `docs/sot/rule/protected-paths.md` 표에 **감사 로그 행 추가**됨 — `docs/interim/sot-readiness-review.md` = Maintainer 소유(수용/기각 사유 반영 조율; 검토 실행은 호스트 CI). 허브 게이트의 경로 강제 대상에 반영 필요.
- **ADR-0007 접점**: 허브 pre-receive는 "SoT는 PR로만"(경로/ref)까지 = Phase 3 baseline. **호스트 브랜치 보호(GitHub required check 등)는 그 위의 별도 층**이며 위 §1의 귀속 논점 대상 — Phase 3 baseline이 아님.
- **Phase 4 (진척)**: 직접 draft 없음. 간접 — **D6 개발 시작 트리거는 requirements·specification·test-design이 변경된 PR에만** 발화(rule/ADR-only PR은 개발 시작 아님). 진척 모델과의 접점만 인지.
- **Phase 7 (메신저/브리핑)**: 직접 draft 없음. 간접 — ②의 `accepted`/`rejected`는 **호스트 채널** 사용자 표시(완전 결속 키 참조)로 결정된다. 게이트 도달 알림·사용자 결정 수집 UX와 접점.

---

## 3. 결정 필요 (양 세션 공통) — 귀속 충돌

**호스트 브랜치 보호(①②③ 필수 검사 + 감사 이력 보존)를 어느 Phase가 소유하는가.**

- `rule-sot-readiness` + ADR-0007 방향: **Phase 6 (호스트 브랜치 보호)**.
- 현행 Phase 6 설계 문서: **비목표 → Phase 3 강제**로 밀어둠.

둘 중 하나로 정합화 필요:
- (A) Phase 6 설계가 이 강제 층을 **흡수**(비목표에서 제외) — rule/ADR 방향 유지.
- (B) 강제 귀속을 **Phase 3**로 두고 `rule-sot-readiness` 강제 매핑의 Phase 표기를 조정.

phase1 세션 견해: ADR-0007이 "허브 pre-receive(경로/ref, 무인증) = Phase 3" vs "호스트 브랜치 보호(required check, 인증 호스트) = 상위 층"으로 이미 층을 나눴으므로 **(A)가 자연스럽다**. 단 최종 귀속은 사용자·양 세션 합의.

---

## 참조
- 규칙: `phase1:docs/sot/rule/sot-readiness.md` (강제 매핑 표·판정 키·재검토 트리거)
- 스킬: `phase1:.claude/skills/sot-readiness-review/SKILL.md` (② 4축·감사 로그 5섹션)
- 경로 정책: `phase1:docs/sot/rule/protected-paths.md` (감사 로그 행)
- 커밋: `a770050` (설계), `4c904c7` (TODO 갱신)
