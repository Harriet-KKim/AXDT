---
id: ADR-0007
title: 규칙 강제는 컨테이너가 접근할 수 없는 호스트/허브 층에 둔다
status: accepted
date: 2026-07-01
decision: D15
related: [ADR-0003, ADR-0006, rule-protected-paths, rule-progress-single-writer, rule-sot-change-user-gate, rule-branch-workspace-naming]
---

# ADR-0007: 규칙 강제는 컨테이너가 접근할 수 없는 호스트/허브 층에 둔다

## 상태
Accepted (2026-07-13; 최초 제안 2026-07-01) · 관련 결정 D15

메커니즘은 허브 모델(`ADR-0006`)에 의존한다. 강제 지점 중 (a) 수신 ref allowlist는 Phase 3 CODE(`hub.install_gate`)로 구현됐고, (b) 콘텐츠·경로 게이트도 Phase 3 CODE로 구현한다(설계 §6.1a `hubgate`). 이 결정 자체는 확정됐다(`accepted`) — status를 코드 병합에 결속하지 않는다(프로젝트 관례: 결정 확정 = `accepted`). (b) CODE 구현 진척은 아래 '구현 상태' 문장과 progress가 추적한다. ADR 번호 0005는 phase5(agent runner), 0006은 phase3(git 격리)다.

## 맥락
규칙(progress 단일 작성자·SoT 사용자 게이트·plan 배정·네이밍)은 문서로만 존재하고 집행 장치가 없다. 각 컨테이너 안의 git pre-commit 훅으로 강제하려 하면, 에이전트가 자기 workspace에 쓰기 권한을 가지므로 `--no-verify`나 훅 편집으로 무력화한다.

강제의 성립 여부는 검사가 실행되는 층으로 결정된다. Leader의 쓰기 가능 컨테이너 안에서 실행되는 검사는 그 Leader가 수정할 수 있어 자기집행이 불가능하다. 컨테이너가 접근할 수 없는 호스트/허브 층의 검사는 우회할 수 없다. Maintainer가 강제 주체가 되는 근거도 같다 — 에이전트 여부가 아니라 호스트 층에 상주해 Leader 컨테이너가 접근할 수 없다는 점이다.

## 결정
강제를 세 지점에 둔다. 지점마다 보호 대상이 다르다.

1. **물리 격리(유닛 간)** — Docker 마운트(D3)·독립 clone(`ADR-0006`). Leader 컨테이너는 자기 작업본만 RW로 마운트하며 다른 유닛의 파일에 접근할 수 없다. `progress.md`·`docs/sot/`·`plan/`처럼 각 clone에 함께 포함되는 보호 경로는 이 층으로 보호되지 않는다.
2. **로컬 훅(권고)** — 각 컨테이너의 git pre-commit 훅. 네이밍·보호 경로 위반을 즉시 알려 실수를 조기에 잡는다. 에이전트가 우회할 수 있으므로 강제가 아니다.
3. **권위 게이트(강제)** — 컨테이너가 접근할 수 없는 호스트/허브 층의 검사. 허브 bare repo의 서버사이드 `pre-receive` 훅이 push를 받을 때 **두 신원-무관 규칙**을 적용한다:
   - **(a) 수신 ref allowlist(default-deny)** — task 브랜치 형식 `refs/heads/w<n>.t<n>-<slug>`(`rule-branch-workspace-naming`)만 허용하고, 그 외 모든 ref — `refs/heads/main`·`refs/heads/sot/*`·기타 장수명/릴리스 브랜치·`refs/tags/*`·미러로 유입될 수 있는 `refs/remotes/*`·notes 등 비-task 네임스페이스 — 와 **삭제(수신값 zero-SHA)** 를 거부한다. 이로써 무인증 허브라도 어떤 클론이든 `main` 등 보호 ref를 push로 직접 오염시킬 수 없다.
   - **(b) 콘텐츠·경로 게이트** — 허용된 task 브랜치 push라도 보호 경로 diff·네이밍·SoT 위반을 거부한다. 정책(`rule-protected-paths` 표·기계용 블록)은 신뢰 ref인 `main`의 tip에서 읽고, 검사 코드는 후보가 접근할 수 없는 호스트 설치본으로 실행해, 후보 브랜치가 정책·검사 코드를 수정하지 못하게 한다.

     구현 상태: (a)는 CODE(`hub.install_gate`)로 구현됐다. (b) 콘텐츠·경로 게이트는 `rule-protected-paths` 표·기계용 블록(신뢰 ref = `main` tip)을 읽어 push diff를 검사하는 CODE를 **Phase 3에서 구현한다**(설계 §6.1a `hubgate`). 규칙은 SoT에 실재하므로(의존 충족) 남은 것은 검사 코드뿐이다.

   보호 ref(`main` 등)의 정상 갱신은 push가 아니라 허브 내부 `git fetch`/`git update-ref`로 이뤄진다(receive-pack 비경유 → allowlist 자기차단 없음, §결과). Phase 6 이후 호스트 branch protection이 그 위에 얹힌다. 정확한 구현은 Phase 3에서 `ADR-0006`과 함께 확정한다.

게이트는 경로·ref 기반(무엇을·어디에) 검사이므로 무인증 허브에서도 성립하며, 이것이 Phase 3 baseline이다. 주체 식별(누가, 예: ref 위장 방지)은 인증·provenance가 필요하므로 하드닝으로 연기한다(`ADR-0006`).

**런치 가드** — 역할이 격리 밖에서 실행됐는지는 커밋으로 검증할 수 없다(커밋에 실행 소속 정보가 없다). 대신 기동을 통제한다. 격리 러너/entrypoint를 컨테이너 마운트·허브 네트워크 경로의 유일 부여자로 두면, 그 밖에서 기동된 프로세스는 workspace 마운트를 얻지 못한다. 무인증 허브(`ADR-0006`)에서는 포트에 도달하는 임의 클론이 push할 수 있어 ref 위장 차단은 인증 하드닝 전까지 advisory이며, 도달한 push도 콘텐츠 게이트가 경로 위반을 거부한다. Maintainer는 tmux·docker 제어를 위해 호스트에 상주하므로 예외다. 완전한 런타임 provenance 검증은 하드닝으로 연기한다.

## 결과
**좋은 점**
- 강제가 컨테이너가 접근할 수 없는 층에 있어 우회할 수 없다.
- 지점별 보호 대상(유닛 간 격리 vs clone 내부 보호 경로)이 분리돼, 물리 마운트가 clone 내부 경로를 보호한다는 오해를 배제한다.
- 게이트가 `rule-protected-paths`의 기계용 블록을 신뢰 ref(`main` tip)로 읽어 명세 기반이며 자기수정이 불가능하다.

**대가 / 주의**
- 허브가 무인증(`ADR-0006`)이면 `receive-pack`으로 임의 ref push가 가능하다. 게이트 성립을 위해 허브 `pre-receive`는 (a) 수신 ref allowlist와 (b) 보호 경로 콘텐츠 거부를 켠다(§결정 3). 두 검사 모두 신원이 아니라 push 대상 ref·내용만 보므로 인증 없이 성립하는 Phase 3 baseline이며 auth 하드닝 대상이 아니다.
- 보호 ref(`main` 등)의 **정상 갱신은 push(`receive-pack`)가 아니라 허브 내부 `git fetch`/`git update-ref`** 로 out-of-band 처리한다. `pre-receive`는 로컬·`--mirror` push를 포함한 **모든** push에 발동하므로(실증 확인), 보호 ref를 push로 갱신하려 하면 자기 자신(관리자·seed)까지 거부된다 — 그래서 갱신 경로를 receive-pack 밖에 둔다. 신규 허브 seed도 같은 이유로 `git clone --mirror`(receive-pack 비경유)로 만든다(`ADR-0006`).
- 어느 주체가 어느 ref로 push하는지의 통제(ref 위장 방지)는 인증(SSH/ACL)이 필요하므로 하드닝으로 연기한다.
- 신뢰 루트는 호스트 층(Maintainer·허브 훅)이다. 이 층이 침해되면 강제 전체가 무너진다(가정: 단일 사용자·단일 호스트, `ADR-0006`과 동일 신뢰 경계).
- 세 지점의 구현·유지 비용. 실제 스크립트는 Phase 3(CODE).

## 검토한 대안
### 대안 A — in-container 훅만
각 컨테이너에 pre-commit 훅만 둔다. · **기각**: 에이전트가 쓰기 권한을 가져 `--no-verify`·훅 편집으로 무력화할 수 있다. 권고이며 강제가 아니다.

### 대안 B — 물리 마운트만 신뢰
D3 마운트로 충분하다고 본다. · **기각**: `progress.md`·`docs/sot/`·`plan/`은 각 clone에 포함돼 보호되지 않는다. 마운트는 유닛 간 격리만 담당한다.

### 대안 C — Maintainer가 push 후 사후 검토
게이트 없이 허브에 반영된 ref를 사후에 검토한다. · **기각**: 오염 ref가 이미 공유 허브에 반영된 뒤이므로(다른 Leader가 fetch 가능) 예방이 아니다. 거부는 push 시점에 서버사이드에서 이뤄져야 한다.

### 대안 D — 게이트가 후보 브랜치의 정책을 읽음
검사 대상 브랜치의 `protected-paths` 표를 사용한다. · **기각**: 에이전트가 검사 규칙을 편집해 우회할 수 있다. 정책은 신뢰 ref인 `main`의 tip에서 읽는다(merge-base 커밋이 아니다 — 분기점을 옛 커밋으로 골라 정책을 무력화하는 우회를 막는다).
