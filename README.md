# AXDT

> **AI Agent 기반 문서 주도(document-driven) 개발 워크플로 템플릿.**
> 요구사항·사양 문서를 Source of Truth로 두면, AI 에이전트들이 그 문서로부터 소프트웨어를 개발한다.

이 프로젝트는 AI Agent를 통한 개발을 적용할 수 있는 템플릿입니다.
Claude Code(`.claude/`), Codex(`.codex/`) 모두 지원합니다.

요구사항, 사양, 테스트 문서는 Agent와 함께 정해진 Skill을 통해 작성하며
이후 문서 작성이 완료되면 자동으로 프로젝트 개발을 진행합니다.

개발 진행 과정은 모두 Maintainer에 의해 수행되며, 기본적으로 Git을 통한 이력 관리가 이뤄집니다.
요구사항 또는 사양 변경, 회색지대의 결정 사항 등 사용자의 의사 결정이 필요한 경우에는 사용자가 Reviewer로 지정된 PR 생성 후 일시 중지됩니다.
GitHub, GitLab, Forgejo와의 연동을 지원합니다.

진행 과정은 Local Web Server에서 브리핑하며, 사용자 결정사항 발생 등 이벤트가 발생하는 경우 메신저를 통해 알림을 받을 수 있습니다.
또한 사용자가 원하는 경우 메신저를 통해 Maintainer에게 추가 지시를 내릴 수도 있습니다.
Discord, Slack, Lark 등을 지원합니다.

---

## 역할 (Roles)

| 역할 | 책임 |
|------|------|
| **Maintainer** | 상시 tmux 세션. 전체 진척 관리, Leader 생성·배치, progress 원장 **단독 작성** |
| **Watcher** | Cron 주기 호출. Maintainer의 context 관리(압축/정리) |
| **Leader** | 기능(task) 단위 개발, 격리 worktree에 종속, report로 자기보고 |
| **Developer / Reviewer / Tester** | Leader가 worktree 내부에서 호출하는 하위 역할 |

통신은 **두 허브 층**으로 이뤄진다 — **Maintainer**는 Leader들의 오케스트레이션 허브(Maintainer→Leader는 tmux 하향 주입, Leader→Maintainer는 report 상향, Leader끼리는 직접 통신 없이 Maintainer 경유)이고, 각 **Leader**는 자신의 Developer/Reviewer/Tester를 호출·중계하는 허브다(sub-agent 간 직접 통신 없음). (`docs/sot/rule/` 참조)

## 저장소 구조

```
docs/
  sot/                 # Source of Truth — 변경은 사용자 게이트 PR로만
    specification/     # 무엇을 어떻게 (동작·인터페이스·데이터)
    requirements/      # 무엇이 왜 필요 (기능/비기능)
    rule/              # 규칙 (용어·네이밍·통신). 베이스 규칙은 신규 프로젝트로 전파
  interim/             # 중간 산출물 — Agent가 자유롭게 작성 (비권위)
    ADR/               # 대상 프로젝트의 아키텍처 결정 기록
    plan/{wave,task}/  # 작업 분해 (상태 필드 없음)
    report/            # Leader 자기보고 (report.status)
    progress.md        # Maintainer 진척 원장 (단일 작성자)
src/ · test/           # 대상 프로젝트 코드/테스트 자리
WIP/                   # AXDT 자체 설계·구현 (ADR·TODO·향후 axdt 패키지)
```

각 디렉터리에는 목적·필수내용·네이밍을 설명하는 `README.md`가 있다.

## 문서 모델 — SoT vs Interim

- **SoT (`docs/sot/`)** — 시스템이 "참"으로 삼는 권위 문서. 변경하려면 PR을 올려 **사용자(Reviewer 게이트)** 승인을 받는다.
- **Interim (`docs/interim/`)** — 작업 중 가변 산출물. Agent가 직접 쓴다. 단 `progress.md`는 Maintainer만 기록한다.

> **AXDT 자체** 설계·구현은 `docs/`가 아니라 `WIP/`에 둔다(대상 프로젝트 문서와 분리).

## 시작하기 (Quick Start)

1. 이 저장소를 복제해 새 프로젝트의 출발점으로 삼는다. 베이스 규칙(`docs/sot/rule/`)이 함께 상속된다.
2. `docs/sot/requirements/`·`specification/`에 요구사항·사양을 작성한다(전용 Skill은 구축 중).
3. 문서가 완료 기준을 충족하면 Maintainer가 개발을 시작한다 — Leader를 격리 worktree·컨테이너에 배치하고 tmux로 조율한다.
4. 진행은 Local Web Server 브리핑·메신저 알림으로 추적한다.

> **현재 상태:** 설계 단계다. 베이스 규칙·핵심 ADR·디렉터리 골격(Phase 0)이 갖춰졌고, 격리 인프라·agent runner 등 런타임 자동화는 `WIP/`에서 구축 중이다. 전체 로드맵은 `WIP/TODO.md` 참조.

## 지원 도구 / 버전

| 도구 | 용도 | 버전 |
|------|------|------|
| **Python** | glue 스크립트·CLI·Web (D9) | **3.12+** |
| **git** | 이력 관리·격리(worktree)·통합 허브 | 2.x (권장 최신) |
| **Docker** | Leader 격리 — worktree당 컨테이너 1개 (D3) | 권장 최신 |
| **tmux** | Maintainer↔Leader 세션 오케스트레이션 | 3.x |
| **Claude Code** | 에이전트 플랫폼 (`.claude/`) | 최신 |
| **Codex** | 에이전트 플랫폼 (`.codex/`) | 최신 |

> **실행 환경:** 런타임(tmux·cron·Docker)은 **Linux / WSL2** 기준이다. Windows 네이티브 런타임은 지원하지 않으며, Windows에서는 WSL2로 구동한다.

## 브랜치 전략

병렬로 여러 에이전트 세션이 작업하므로 브랜치 규약을 따른다.

- **`main`** — 통합 브랜치. **직접 작업 금지**, 항상 깨끗하게 유지. 통합은 검토를 거친 병합으로만.
- **phase/기능 브랜치** — 모든 작업은 여기서 한다(예: `phase0`). 병렬 세션은 각자 브랜치/worktree를 쓴다.
- **Leader task 브랜치** — `branch-worktree-naming` 규칙의 단일 식별자 `w<n>.t<n>-<slug>`를 branch·worktree·컨테이너에 일관 적용(`docs/sot/rule/branch-worktree-naming.md`).
- **통합 순서** — Phase 0(기반)이 베이스이며 나머지 작업이 이를 흡수한다. 의존 관계는 `WIP/TODO.md`의 "의존 관계 요약" 참조.
- **사용자 게이트** — SoT 변경·회색지대 결정은 사용자를 Reviewer로 한 PR로 처리한다.

## 라이선스

MIT — `LICENSE` 참조.
