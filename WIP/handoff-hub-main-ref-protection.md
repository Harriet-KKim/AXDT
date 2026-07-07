# 핸드오프 — 허브 `main` ref 보호 (직교 결함)

> **RESOLVED (2026-07-07, main 병합 시점).** 권고의 실질이 main에 흡수됐다: 병합된 `ADR-0007`(§결정 3 — 수신 ref allowlist + 보호 ref는 receive-pack 비경유 out-of-band 갱신)과 `WIP/axdt/infra/hub.py`(default-deny allowlist로 `main`/`sot/*`/태그/삭제 daemon push 거부)가 이 오염 경로를 막는다. **잔여(비차단):** §4의 `rule-protected-paths`에 허브 `main` ref 행 추가는 미반영(현 표는 경로 축만) — Phase 3의 의도적 스코핑일 수 있어 별도 확인. 아래 본문은 역사 기록으로 보존한다.
>
> 작성: phase5-agent-runner 세션(Phase 6 설계 중) · 대상: **Phase 3 세션**(phase3-isolation-infra)
> 근거: `ADR-0006`(로컬 bare 허브)·`ADR-0007`(층 강제)·`rule-sot-readiness` 강제 매핑. Phase 6 설계 §8과 상호참조.

## 0. 무엇을 넘기나

Phase 6 귀속 정합화(호스트 브랜치 보호 = Phase 6) 리뷰 중 Fable이 발견한 **직교 결함**이다. 귀속 결정(A/B)과는 무관하며 어느 쪽으로 정해도 안 덮인다. 성격상 **허브 층 = Phase 3 몫**이라 넘긴다. 이 문서는 draft가 아니라 **결함 보고 + 권고**다. Phase 6 브랜치는 이 결함을 코드/규칙으로 고치지 않았고, Phase 6 설계 §8·§9에 "Phase 3 몫"으로만 포인터를 남겼다.

## 1. 결함

`rule-sot-readiness` 강제 매핑은 "`SoT PR로만 — main 직접 push 축` → `main` 브랜치 보호(require-PR) → **Phase 6**"이라 적는다. 그러나 이 require-PR은 **인증된 git 호스트(GitHub 등)의 `main`에만** 성립한다.

`ADR-0006`이 명시하듯 시스템의 권위 상태는 **로컬 bare 허브**이고, 허브의 `git daemon`은 **설계상 무인증**이다("`receive-pack`을 켜면 어떤 클론이든 임의 ref를 push할 수 있다"). 즉 **허브에도 `main` ref가 있고**(각 작업본 clone의 base), 컨테이너/작업본이 **허브 `main`을 직접 밀어** 다른 Leader가 그걸 fetch하는 **오염 경로**가 열려 있다. 호스트측 require-PR은 이 경로를 전혀 막지 못한다 — 호스트에 도달하지도 않기 때문이다.

`rule-protected-paths`의 적용범위는 "task 브랜치/worktree에서의 push"(경로 축)로 쓰여 있어, **허브 `main` ref 자체에 대한 push 정책은 어느 문서에도 명시돼 있지 않다.** Phase 6(호스트)과 Phase 3(허브 경로) 사이 이음새로 떨어진다.

## 2. 왜 Phase 3이며, 왜 강제 가능한가

핵심 구분(강제 능력의 축):
- **신원 무관 규칙**(경로 규칙, **균일 ref 규칙**)은 무인증 허브의 `pre-receive` 훅으로 **강제 가능**하다. 훅은 갱신되는 모든 ref와 커밋 내용을 받아 push 전체를 거부할 수 있고, `git daemon`의 `receive-pack`도 대상 repo의 훅을 실행한다(인증 부재와 훅 실행은 별개).
- **신원 기반 규칙**("Leader A는 A의 ref만")은 pusher 인증이 필요해 무인증 허브에서 **advisory**다(`ADR-0006`, 하드닝 단계로 연기).

허브 `main` 보호는 **신원 무관 균일 규칙**이다 — "`refs/heads/main`(및 지정 보호 ref)으로의 daemon 직접 push는 전부 거부"는 누가 미는지 몰라도 강제된다. 따라서 **Phase 3의 허브 pre-receive 층에서 강제 가능**하며, `ADR-0007`의 "허브는 보호 ref에 서버사이드 훅 거부를 켜야 한다"와 결이 같다.

## 3. 권고 메커니즘

1. **균일 거부**: 허브 `pre-receive`가 `refs/heads/main`(+ `sot/*` 등 보호 대상으로 정할 ref)에 대한 **모든 daemon push를 거부**한다. 신원 무관이라 무인증에서도 성립.
2. **정상 갱신 경로**: 허브 `main`은 **Maintainer가 out-of-band로만** 갱신한다 — 파일시스템 직접 조작(bare repo에 로컬 `git` 연산) 또는 **호스트(GitHub)에서 미러 동기화**(`git fetch`/`push --mirror`). 이 경로는 daemon receive-pack을 타지 않으므로 1의 거부에 걸리지 않는다.
3. 결과: 작업본→허브 `main` 직접 오염이 막히고, 승인된 상태만 호스트를 거쳐(또는 Maintainer를 거쳐) 허브 `main`에 도달한다.

(주의: 이건 SoT 완료 강제(①②③)가 아니라 **허브 무결성** 보호다. 완료 강제는 여전히 호스트 브랜치 보호 = Phase 6 강제 증분/ADR 0009 몫.)

## 4. Phase 3 세션이 정할 것

- **귀속 수용**: 이 결함을 Phase 3(허브 층)이 소유하는지 확인. 소유하면 아래를 반영.
- **문서 반영**: `ADR-0007`(층 강제)에 "허브 보호 ref = 균일 규칙 거부"를 명시하고, `rule-protected-paths` 적용범위에 **허브 `main`(및 보호 ref) 직접 push 거부** 행을 추가.
- **보호 ref 집합 확정**: `refs/heads/main`만인지, `sot/*`·릴리스 ref도 포함인지.
- **Maintainer 갱신 경로 확정**: 파일시스템 직접 vs 호스트 미러 동기화 vs 둘 다. `ADR-0001`(Maintainer 상주 세션)과 접점.

## 참조
- `ADR-0006`(worktree-phase3-isolation-infra): 무인증 daemon·허브=권위 상태·ref 격리 advisory.
- `ADR-0007`: 허브 pre-receive(경로/ref) = Phase 3 baseline vs 호스트 브랜치 보호 = 상위 층.
- `rule-sot-readiness` 강제 매핑(phase1): "main 직접 push 축 → Phase 6"은 호스트 main 한정.
- `rule-protected-paths`(phase1): 현 적용범위 = task 경로 축(허브 main ref 미포함).
- Phase 6 설계 `WIP/specs/2026-07-05-phase6-git-host-design.md` §8(허브 main ref 보호)·§9.
