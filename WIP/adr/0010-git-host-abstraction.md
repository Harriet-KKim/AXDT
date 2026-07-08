---
id: ADR-0010
title: Git 호스트는 어댑터+백엔드 합성으로 추상화하고 게이트 재개는 리뷰 커서로 판정한다
status: accepted
date: 2026-07-07
decision: D5
related: [ADR-0003, ADR-0004, ADR-0005]
---

# ADR-0010: Git 호스트는 어댑터+백엔드 합성으로 추상화하고 게이트 재개는 리뷰 커서로 판정한다

## 상태
Accepted (2026-07-07) · 관련 결정 D5

이 ADR은 0010이다 — 0008은 test-design(SoT 4번째 타입, `ADR-0008`)이 선점했고, 0006(git 격리)은 main에 병합돼 accepted, 0007(층 강제)은 main에 병합됐으나 status=proposed(콘텐츠·경로 게이트 CODE 후속까지)다. 강제(호스트 브랜치 보호)는 이 클라이언트 증분과 별개의 후속 증분이며, 0007 확장이 아니라 신규 `ADR-0009`로 번호를 뗀다.

## 맥락
Phase 6은 GitHub·GitLab·Forgejo 세 호스트에 대해 SoT 사용자 게이트(PR 열기 → 리뷰어 지정 → 상태·리뷰 폴링 → 머지)를 공통 인터페이스로 제공해야 한다(D5, GitHub 우선). 세 호스트의 수명주기는 동일하고, 차이는 (1) 어떤 CLI를 어떤 argv로 호출하며 JSON 필드명·값 맵을 어떻게 해석하는가, (2) 명령을 어디서·어떻게 실행하는가(실제 프로세스 대 테스트용 스크립트)뿐이다. Phase 5(`ADR-0005`)가 이미 같은 두 축 분리(플랫폼 지식을 담은 어댑터 + 주입되는 실행 백엔드)를 정립했으므로 이를 재사용한다.

추가로 실 호스트 없이도 GitHub만으로 계약을 문서 대조 검증해야 하고(Phase 6 (b) 범위), 실제 네트워크 없이 결정적으로 테스트돼야 한다. 또한 GitHub의 리뷰 재요청은 기존 `CHANGES_REQUESTED` 판정을 지우지 않는다(해제는 dismiss 또는 리뷰어의 새 리뷰 제출뿐) — 그래서 "재요청 후 재개 대기"를 집계 상태 비교로 구현하면 낡은 판정이 잘못 재개를 트리거하거나, 반대로 재발한 변경요청을 못 잡는 경우가 생긴다.

## 결정
`GitHostClient`(수명주기 소유)는 `GitHostAdapter`(호스트 데이터: 필드명·값 맵·argv 빌더; `parse_*`는 base에 구체 구현)와 주입된 `CommandBackend`(1회성 실행; `FakeCommandBackend`/`SubprocessBackend`)를 합성한다. 상태는 통제 어휘(`PullRequestState`/`ReviewDecision`/`MergeMethod`)로 고정한다.

PR 핸들은 create→view 단일 JSON 파싱으로 얻는다 — 세 호스트 모두 create가 JSON을 내지 않으므로(`gh pr create`는 URL 한 줄), create로는 참조만 얻고 `PullRequest`는 뒤이은 view 조회에서 구성한다.

게이트 재개는 집계 상태 리셋이 아니라 리뷰 id 커서 + `reviews` 스트림 위치로 판정한다. 대기 시작 시 대상 리뷰어의 최신 리뷰 id를 커서로 포착하고, 그 커서보다 스트림상 나중 위치에 종결 판정(APPROVED/CHANGES_REQUESTED)이 나타나면 재개한다(`terminal_after`). `COMMENTED`는 비종결이다.

GitHub는 `gh` 공식 문서 대조로 기능완성이다. GitLab/Forgejo는 구조만 선언한 provisional이며, 잔여 검증 항목은 `HOST_MATRIX.md`에 기록한다. 조회 결과는 권위 있는 작업 결과가 아니라 신호일 뿐이다(`ADR-0003`/`ADR-0004`) — 권위는 progress에 있다.

## 결과
**좋은 점**
- 수명주기 로직이 한 곳에 있고 변하는 축(어댑터·백엔드)만 교체된다 — Phase 5와 동일한 중복 제거 이득.
- 실 네트워크·라이브 호스트 없이도 결정적으로 테스트된다.
- 새 호스트 추가는 데이터 전용 서브클래스(`build_*` 4개 + 필드명·값 맵) 하나로 끝난다.
- 리뷰 커서 판정이 "재요청이 판정을 리셋한다"는 틀린 전제를 배제해, 낡은 판정의 오재개나 재발 변경요청 누락을 막는다.

**대가 / 주의**
- GitLab/Forgejo는 Phase 9 라이브 검증 전까지 provisional이라 위험을 안고 있다(`HOST_MATRIX.md`).
- 강제(호스트 브랜치 보호: required check·승인+dismiss-stale·`main` require-PR 등)는 이 클라이언트 증분의 범위 밖이며, 별도 증분과 `ADR-0009`로 명시적으로 분리된다.
- 객체 3개(client/adapter/backend)로 간접성이 늘어난다(수용 범위).

## 검토한 대안
### 대안 A — 호스트별 client 상속 (GitHubClient/GitLabClient/ForgejoClient)
각 호스트가 수명주기 전체를 구현. · **기각 사유**: 동일 수명주기를 호스트 수만큼 중복시킨다(`ADR-0005`의 대안 A와 동일 사유).

### 대안 B — 집계 리뷰 상태(`reviewDecision`) 리셋으로 게이트 재개 판정
재요청 시 기존 판정이 초기화된다고 가정하고 단순 enum 비교로 재개를 판정. · **기각 사유**: GitHub에서는 재요청만으로 `CHANGES_REQUESTED`가 해제되지 않는다(해제는 dismiss 또는 새 리뷰 제출뿐). 재요청만으로 차단이 풀린다고 가정하면 보안 구멍이 되고, 반대로 재발한 변경요청을 못 잡는 경우도 생긴다.

### 대안 C — GitLab/Forgejo를 이번 증분에서 완전 구현
provisional로 남기지 않고 정확한 argv·JSON 스키마까지 확정. · **기각 사유**: 라이브 호스트 없이 확정하면 검증되지 않은 세부를 "검증됨"으로 오인시킨다. 구조만 선언하고 잔여 검증 항목은 `HOST_MATRIX.md`에 명시한 뒤 Phase 9에서 라이브로 확정한다.
