---
id: ADR-0006
title: git 격리는 로컬 bare repo 허브 + 독립 클론으로 구현한다
status: accepted
date: 2026-06-29
decision: D3
related: [ADR-0002, ADR-0003]
---

# ADR-0006: git 격리는 로컬 bare repo 허브 + 독립 클론으로 구현한다

## 상태
Accepted (2026-06-29) · 관련 결정 D3(Docker 격리)

## 맥락
D3은 "worktree당 컨테이너 1개, **해당 worktree만 read-write 마운트, 그 외 차단**"을 요구한다. 그러나 `git worktree`의 `.git`은 메인 repo의 `.git/worktrees/<name>`을 가리키는 포인터일 뿐이라, worktree 폴더만 컨테이너에 마운트하면 **컨테이너 안에서 git이 동작하지 않는다.** TODO/D3에서 "독립 `.git` 처리 또는 remote push 방식"을 Phase 3 설계로 미뤄두었다.

## 결정
각 Leader 작업본을 **`git worktree`가 아니라 bare 허브에서 clone한 독립 작업 디렉터리**로 만든다.

- 호스트에 통합 허브 `.axdt/hub/project.git`(bare) 1개 — **머지 전 Leader push를 보유하는 권위 상태**.
- 각 작업본 `worktrees/<id>/`는 허브에서 clone된 **완전한 `.git`**을 가져 컨테이너 안에서 git이 그대로 동작한다.
- 원격을 둘로 분리: 호스트용 `hub`(=`file://<허브>`, clone·teardown 검사), 컨테이너 내부 push용 `origin`(=`git://host.docker.internal:<port>` 또는 file 폴백 `file:///hub`).
- 컨테이너는 **자기 작업본만 RW 마운트**(D3). 허브 접근은 파일시스템 교차 마운트가 아니라 **git 프로토콜**(`git daemon`)로 → 다른 Leader 작업본을 못 본다.

## 결과
**좋은 점**
- 컨테이너 안에서 git 전 기능이 동작하고, 작업본 외 마운트가 없어 **파일시스템 격리(D3)가 강제**된다.
- GitHub 없이 **오프라인 로컬만으로 개발 루프가 완결**된다(허브가 통합 지점). GitHub 연동(Phase 6, D5)은 그 위에 얹는다.
- 허브가 곧 git이라 별도 DB/큐 없이 상태·이력이 보존된다(`ADR-0002`와 정합).

**대가 / 주의**
- 허브는 **권위 상태**다 — 재생성·삭제 금지. 신규 허브는 canonical repo에서 `git push --mirror`로 seed해야 한다.
- 로컬 `git daemon`은 **설계상 무인증**(단일 호스트·단일 사용자)이라 `receive-pack`을 켜면 어떤 클론이든 임의 ref를 push할 수 있다 → **Leader 간 git-ref 수준 격리는 advisory이며 강제되지 않는다.** 강제하려면 인증(SSH/ACL) 도입이 필요하고 **하드닝 단계로 연기**한다.
- 디스크: worktree 공유 대비 독립 클론이라 사용량이 늘 수 있다(local clone hardlink로 완화 가능).

## 검토한 대안
### 대안 A — worktree + `.gitdir` 마운트 재작성
worktree 폴더 + `.git/worktrees/<name>`을 함께 마운트하고 `commondir`를 재작성. · **기각 사유**: 메인 `.git`의 **모든 ref가 컨테이너에 노출**돼 격리가 깨지고, 공유 `.git`에 RW가 생겨 D3 "작업본만 RW" 원칙과 충돌한다.

### 대안 B — GitHub를 1차 통합 지점으로
컨테이너가 곧장 GitHub로 push. · **기각 사유**: 핵심 개발 루프가 **온라인·외부 계정에 종속**된다. 로컬 도그푸딩·오프라인이 막힌다. GitHub는 Phase 6에서 허브 위에 얹는 게 의존 순서에 맞다.

### 대안 C — 컨테이너에 bare 허브를 직접 RW 마운트(file transport)
file:// 로 단순화. · **부분 채택(폴백)**: 네트워킹이 까다로운 환경의 폴백으로 둔다. 단 작업본 외 마운트가 1개 늘어 **D3 격리의 명시적 예외**이므로 기본은 daemon(strict)으로 한다.
