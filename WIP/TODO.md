# AXDT 프로젝트 완성 TODO

> **목표 범위**: 전체 비전 (6개 역할, Docker 격리, Tmux, Cron Watcher, Claude Code + Codex 동시 지원, GitHub/GitLab/Forgejo 연동, Local Web 브리핑, 메신저 양방향 연동)
>
> AI Agent들이 역할을 분담하여 문서(SoT) 기반으로 소프트웨어 개발을 자동 수행하는 워크플로 템플릿.
>
> 작성일: 2026-06-26 · 갱신: 2026-07-07 (D1~D16 확정 · test-design SoT 타입 도입 · Phase 1 템플릿 8종) · 상태: 초안

---

## ✅ 확정된 결정사항

### D1. 오케스트레이터 실행 형태
- **Maintainer** = 프로젝트 시작~종료까지 **상시 실행되는 장기 tmux 세션**.
- **Watcher** = **Cron으로 주기 호출**되어 Maintainer의 **context 관리(압축/정리)** 만 담당.

### D2. Agent 간 통신
- **Maintainer → Leader**: tmux `send-keys`로 **prompt 직접 주입**. 별도 파일 채널 없음.
- **Leader → Maintainer**: **report 파일** (역방향 tmux 채널이 없으므로). 상향 통신 + 요약(summary) 겸용.
- **Leader ⇆ Leader**: 직접 통신 지양 → 의존성 조율은 **Maintainer 경유** (격리 원칙).
- **Leader ⇄ Developer/Reviewer/Tester**: Leader가 호출하고 결과를 돌려받는 **허브 구조**. sub-agent는 Leader에게만 응답하며 **상호 통신 없음**(sub-agent 간 직접 통신 불가) → Leader가 산출물을 중계하고 구현→리뷰→수정 루프를 매개.
- **사용자 ↔ Maintainer**: 메신저(양방향) + Local Web 브리핑.

### 상태 저장 — 별도 DB/큐 없음
- 영속 상태는 이미 **interim 파일** 안에 존재. 새 DB/큐/이벤트 로그를 만들지 않는다.
- 메신저 알림은 Maintainer가 상시 세션이므로 **결정 지점에서 직접 발송** (이벤트 큐 불필요).
- 메신저 inbound는 **stateless webhook 브릿지**가 받아 tmux `send-keys`로 Maintainer에 전달.

### D3. Docker 격리 수준
- **workspace당 컨테이너 1개** (Leader:workspace = 1:1). **해당 workspace만 read-write 마운트**, 그 외 차단.
- ⚠️ 구현 주의: `git worktree`는 메인 repo의 `.git`을 공유하므로, worktree 폴더만 마운트하면 컨테이너 내부에서 git이 안 됨 → Phase 3에서 **독립 `.git` 처리 또는 remote push 방식** 별도 설계.

### D4. Claude Code ↔ Codex 추상화
- 공통 **agent runner 인터페이스** + **Claude Code·Codex 어댑터를 둘 다 구현** (세션 기동/prompt 주입/출력 읽기).

### D5. 1차 Git 호스트
- **GitHub 우선** (`gh` CLI). GitLab·Forgejo는 어댑터로 확장.

### D6. 자동 개발 시작 트리거
- **세 트리거 모두 지원**: (주) **SoT PR이 main에 merge** / (보조) **명시적 시작 명령·플래그** / (보조) **마커 파일 존재**.

### D7. progress 파일 포맷
- **엄격 스키마 Markdown 테이블**. 파싱 안정성을 위해 **고정 컬럼 + 통제된 `status` 어휘**로 스키마를 엄격히 고정.

### D8. 1차 메신저
- **Discord** (webhook/봇). Slack·Lark는 어댑터로 확장.

### D9. 구현 언어 (Web 브리핑 + glue)
- **Python**. 브리핑 서버 + 메신저 브릿지 + workspace/docker/cron glue 스크립트를 한 언어로 통일.

### D10. progress git 추적
- **추적하되 wave/task 완료 마일스톤 경계에서만 커밋** (이력 보존 + churn 최소).

### D11. 디렉터리 문서화 방식
- 각 디렉터리에 **`README.md`** (목적 · 꼭 들어갈 내용 · 네이밍 규칙) + 문서를 담는 디렉터리엔 **`_TEMPLATE.md`** (Agent가 복제해 채우는 빈 양식).

### D12. src/·test/ 의 정체 & AXDT 자체 코드 위치
- **`src/`·`test/` = 이 템플릿으로 만들어지는 "대상 프로젝트"의 코드/테스트 자리.**
- AXDT 자체 구현(오케스트레이션 스크립트·웹서버·브릿지 등)은 **우선 `WIP/`에** 둔다(임시 위치).

### D13. 설계 결정 기록 방식 (ADR 정책)
- **비자명한 핵심 결정만 ADR**로 근거+대안 기록 (취향·1차 선택은 ADR 안 함 — rule/TODO로 충분).
- 규범적 규칙은 `docs/sot/rule/`(모든 프로젝트 전파), AXDT 자체 ADR은 `WIP/adr/`(D12 self-doc), 대상 프로젝트 ADR은 `docs/interim/ADR/`.

### D14. Branch/Workspace/Container 네이밍
- 한 작업 단위(task = Leader = workspace = container, 1:1)를 **단일 식별자 `w<n>.t<n>-<slug>`** 로 명명.
- 이 식별자가 **branch · workspace 디렉터리 · 컨테이너 이름을 일관되게** 결정 — branch·workspace 디렉터리 이름은 식별자와 동일, 컨테이너만 `axdt-` 접두. 슬래시(`/`) 미사용.
- 토큰 형식(`w<n>`/`t<n>`/`<slug>`)은 plan(wave/task) 템플릿의 id와 정합. 규칙: `docs/sot/rule/branch-workspace-naming.md`.

### D15. 규칙 강제 지점
- 강제는 **컨테이너가 손댈 수 없는 호스트/허브 층**에 둔다 — ① 물리 격리(유닛 간, D3) ② 로컬 pre-commit 훅(권고) ③ **호스트/허브 게이트**(강제: 허브 서버사이드 훅/branch protection, push 시 보호 경로·네이밍·SoT 위반 거부).
- 물리 마운트는 *유닛 간 격리*만 지킴 — `progress.md`·`sot/`·`plan/`은 clone 안에 들어오므로 **게이트가 유일 강제**. 게이트는 정책을 **신뢰 ref**에서 읽음. **런치 가드**로 격리 러너를 허브 자격의 유일 경로화(Maintainer는 호스트 상주 예외).
- 정확한 메커니즘은 **Phase 3에서 `ADR-0006`과 함께 확정**. 명세 = `docs/sot/rule/protected-paths.md`, 근거 = `WIP/adr/0007`(proposed).

### D16. 테스트 설계 = SoT 4번째 타입
- **테스트 설계**를 `docs/sot/test-design/`에 두고 requirements·specification과 **동급인 4번째 SoT 타입**으로 다룬다. 완료 판정에 포함 — 요구·사양과 함께 테스트 설계가 완료되어야 개발에 착수한다.
- 설계(SoT)/구현(`test/` 코드) 분리: SoT = 테스트 조건 · 블랙박스 커버리지 목표 · 스위트 구조 · 요구↔테스트 추적성 · 절차 원칙. `test/` = 구체 케이스 · 데이터 · 픽스처 · 스크립트 · 환경(D12, Tester 소관).
- 필수: 화이트박스 커버리지(결정/분기/MC-DC)는 SoT에서 제외(코드 없이 명세 불가 → 개발 전 완료 영구 미충족). 조건(SoT) vs 케이스(코드) 절단선을 template·rule에 명시.
- 근거·대안·대가: `WIP/adr/0008-test-design-as-sot-type.md`.

> 📌 현재 미결 결정: **없음**. 구현 중 새 갈림길이 생기면 여기에 D17~ 로 추가한다.

---

## 📖 용어 정의  *(→ `docs/sot/rule/` 편입 확정 — D13)*

| 구분 | 위치 | 의미 | 작성 주체 | 변경 |
|---|---|---|---|---|
| **SoT** (Source of Truth) | `docs/sot/` | 초기에 세우는 **권위본** (requirements/specification/test-design/rule) | Agent 작성, **변경은 사용자 게이트 PR로만** | 통제됨 |
| **Interim** (중간 산출물) | `docs/interim/` | 작업 중 생성·변경되는 파일 (ADR/plan/report/progress) | **Agent** (Leader·Maintainer 무관, 단 개별 파일에 더 좁은 제약 가능) | 자유 |

핵심 구분: **"권위본이라 변경이 통제되는가(SoT)" vs "작업 중 만들어지고 자유롭게 바뀌는가(interim)"**.
interim은 사람이 아니라 Agent가 쓰는 작업 공간.

### interim 파일별 역할 & 작성자

| 파일 | 역할 | 작성자 | 상태(status) 보유 |
|---|---|---|---|
| **plan** (wave/task) | 작업 **정의·구조** ("무엇을 할지") | **Maintainer** (분해·배정) | ❌ 없음 |
| **report** | task별 상세 + **Leader 자기보고 상태** | Leader | ✅ `report.status` (Leader 소유) |
| **progress** | 오케스트레이션 **색인 + 수용 상태** (report는 canonical 경로로 판정, 컬럼 아님) | **Maintainer만** (단일 작성자) | ✅ `progress.status` (Maintainer 소유, 시스템 권위) |

---

## 📊 상태 모델 (status flow)

상태는 한 곳에만 사는 게 아니라, **계층마다 권위 주체가 하나씩 있고 흐름은 한 방향**이다.

```
Leader ─(report.status 기록: 자기 작업 주장)─┐
                                            │  Maintainer가 읽고 검토/수용 (게이트)
                                            ▼
Maintainer ─(progress.status 기록: 수용된 진실)─> 시스템·웹·의사결정은 이걸 권위로 읽음
```

- `report.status` 는 **"Leader가 어떻게 보고하는가"**, `progress.status` 는 **"오케스트레이터가 무엇을 참으로 수용했는가"** 에 답한다 — 서로 다른 질문.
- 둘이 다르면 모순이 아니라 **"Maintainer 처리/수용 대기"** 라는 정상 상태. **권위는 항상 progress.**
- report→progress 승격이 곧 **Maintainer의 검토/게이트 지점** (집계 + 수용 + 필요시 Reviewer/Tester/사용자 게이트 + wave 롤업).

---

## 🔀 통신 채널 맵

```
사용자 ⇅ Maintainer          : 메신저(양방향, Phase 7) + Web 브리핑(read-only, Phase 7)
Maintainer → Leader          : tmux send-keys (prompt 주입)
Leader → Maintainer          : report 파일 (상향, 자기보고)
Watcher → Maintainer         : context 점검·정리 (Cron, 제어)
Leader ⇄ Dev/Reviewer/Tester : Leader가 호출·결과 수신 (허브). sub-agent는 Leader에게만 응답
Dev/Reviewer/Tester 상호간   : 직접 통신 없음 (sub-agent 간 통신 불가) → Leader가 산출물 중계
Leader ⇆ Leader              : 직접 통신 지양 → Maintainer 경유
메신저 inbound               : 사용자 → webhook 브릿지 → tmux send-keys → Maintainer
```

---

## 🗃️ 디렉터리 구조 & 문서 요건  (D11·D12)

```
docs/
  sot/                  # 권위본 (변경 = 사용자 게이트 PR)
    specification/
    requirements/
    test-design/
    rule/
  interim/              # 중간 산출물 (가변, Agent 작성)
    ADR/
    plan/
      wave/
      task/
    report/             # 🆕 task별 Leader 보고
    progress.md         # 🆕 단일 진행 기록 (Maintainer 단독)
src/                    # 대상 프로젝트 코드 (D12)
test/                   # 대상 프로젝트 테스트 (D12)
WIP/                    # AXDT 자체 구현·기획 임시 위치 (D12)
```

각 디렉터리에 `README.md`(목적·필수내용·네이밍), 문서를 담는 곳엔 추가로 `_TEMPLATE.md`(복제해 채우는 빈 양식).

| 경로 | 목적 | README 필수 내용 | 템플릿 |
|---|---|---|---|
| `docs/` | 문서 루트 | SoT vs interim 구분 안내 | — |
| `docs/sot/` | 권위본 루트 | 권위성·변경은 사용자 게이트 PR로만 | — |
| `docs/sot/specification/` | 시스템이 **무엇을 어떻게** (동작·인터페이스·데이터) | 범위·구성요소·인터페이스·데이터모델·동작·수용기준·참조 | ✅ Spec |
| `docs/sot/requirements/` | **무엇이 왜** 필요 (기능/비기능) | 목표·기능요구·비기능요구·제약·범위외·수용기준 | ✅ Req |
| `docs/sot/test-design/` | 요구·사양을 **어떻게 검증** (조건·커버리지·스위트·추적·절차) | 범위·테스트조건·커버리지목표·스위트·추적성·절차원칙·수용기준·참조 | ✅ TestDesign |
| `docs/sot/rule/` | 프로젝트 규칙 (네이밍·용어·표준) | 규칙문·근거·적용범위·예시 | ✅ Rule |
| `docs/interim/` | 중간 산출물 루트 | 가변·Agent 작성·비권위 안내 | — |
| `docs/interim/ADR/` | 아키텍처 결정 기록 | 번호·제목·상태·맥락·결정·결과·대안 | ✅ ADR |
| `docs/interim/plan/` | 작업 분해 루트 | wave/task 관계, **상태 필드 없음** | — |
| `docs/interim/plan/wave/` | wave (마일스톤=task 묶음) | wave id·목표·포함 task·의존·종료기준 | ✅ Wave |
| `docs/interim/plan/task/` | task (Leader 단위) | task id·상위 wave·목표·범위·의존·DoD·대상 workspace/branch | ✅ Task |
| `docs/interim/report/` | Leader 보고 | task 참조·`report.status`·요약·완료내역·블로커·사양변경요청·다음 | ✅ Report |
| `docs/interim/progress.md` | Maintainer 진행 기록 | 고정 컬럼 MD 테이블 (D7) | ✅ (스키마=양식) |
| `src/` · `test/` | 대상 프로젝트 코드/테스트 | 레이아웃·테스트 규약 | — |

---

## Phase 0 — 기반 정비 (Foundation)

- [x] 파일명 오타 수정: `Initail_Idea.md` → `INITIAL_IDEA.md` (또는 `docs/`로 이동) ✅ 2026-06-30
- [x] 저장소 디렉터리 구조 스캐폴딩 생성 ✅ 2026-06-30
  - [x] `docs/sot/{specification,requirements,rule}`
  - [x] `docs/interim/{ADR,plan/{wave,task},report}` + `docs/interim/progress.md`
  - [x] `src/`, `test/` (대상 프로젝트 자리, D12)
- [x] **각 디렉터리에 `README.md` 작성** (목적·필수내용·네이밍, D11) ✅ 2026-06-30
- [x] `.gitignore` 작성 (Docker, workspace, 런타임 산출물 제외 — **progress는 추적**, D10 마일스톤 커밋) ✅ 2026-06-30
- [x] `LICENSE` 선택 및 추가 ✅ 2026-06-30
- [x] `README.md` 보강 (사용법/빠른 시작 섹션 추가) ✅ 2026-06-30
- [x] 지원 도구/버전 매트릭스 명시 (Docker, tmux, git, **Python**, Claude Code, Codex) ✅ 2026-06-30
- [x] 초기 커밋 + 브랜치 전략 문서화 ✅ 2026-06-30
- [x] **AXDT 베이스 규칙 문서화** (`docs/sot/rule/` — 모든 프로젝트에 전파되는 공통 규칙) ✅ 2026-06-26
  - [x] 용어 정의 (SoT/Interim) → `terminology.md`
  - [x] Branch/Workspace 네이밍 규칙 → `branch-workspace-naming.md` (D14)
  - [x] 통신·상태 규범 (progress 단일 작성자 / sub-agent 직접 통신 금지·Leader 허브 / Leader 간 Maintainer 경유 / SoT 변경=사용자 게이트) → `progress-single-writer`·`subagent-no-direct-communication`·`leader-coordination-via-maintainer`·`sot-change-user-gate`·`report-to-progress-authority`
  - [x] 규칙 "전파" 개념 명시 (베이스 규칙이 신규 프로젝트로 상속) → `propagation.md`
  - [x] 보호 경로 규칙 (role→쓰기허용 경로 명세, 강제 계층) → `protected-paths.md` (D15)
- [x] **AXDT 자체 설계 ADR 작성** (`WIP/adr/` — 비자명 결정의 근거+대안, D13) ✅ 2026-06-26
  - [x] D1: Maintainer = 상시 tmux 세션 (왜 무상태/Cron이 아닌가) → `0001`
  - [x] 별도 DB/큐 없음 (report·plan이 상태를 담음, Web은 read-time 렌더) → `0002`
  - [x] D2: 통신 모델 (tmux 하향 / report 상향 / Leader 허브 / sub-agent 비통신) → `0003`
  - [x] 상태 모델: report→progress 단방향 권위 흐름 → `0004`
  - [ ] D15: 강제는 호스트/허브 층 (물리 격리 + 권고 훅 + 권위 게이트) → `0007`

## Phase 1 — SoT 문서 시스템 (Source of Truth)

- [x] 각 문서 디렉터리에 `_TEMPLATE.md` 작성 (frontmatter + 필수 섹션, D11) ✅ 2026-07-02
  - [x] specification `_TEMPLATE.md`
  - [x] requirements `_TEMPLATE.md`
  - [x] test-design `_TEMPLATE.md` ✅ 2026-07-07 (D16)
  - [x] rule `_TEMPLATE.md`
  - [x] ADR `_TEMPLATE.md`
  - [x] plan/wave · plan/task `_TEMPLATE.md` (**상태 필드 없음**)
  - [x] report `_TEMPLATE.md` (`report.status` 포함)
  - [x] progress.md 빈 양식 (고정 컬럼 테이블, D7 — Phase 4와 정합)
- [ ] **요구사항/사양/테스트 설계 작성 Skill** 제작 (Agent와 대화형 작성)
- [x] SoT 변경 워크플로 정의 (Reviewer=사용자 게이트가 있는 PR 기반) — `sot-change-user-gate`(발의·일시정지·재개·`sot/<slug>` 브랜치)·`protected-paths`(task 경로 차단)·`sot-readiness`(머지 판정 ①②③·main require-PR·감사 이력 보존)에 정의 완료, 강제는 Phase 6 ✅ 2026-07-07
- [ ] **문서 완료 판정 기준 정의** (→ 자동 개발 시작 트리거, D6) — `rule-sot-readiness` · 설계·정의 커밋 완료, 강제(①②③ 필수 검사)는 Phase 6
  - [ ] 형식 기준 (기계 검증: 문서 존재·플레이스홀더 없음·필수 섹션·TBD 없음)
  - [ ] 정합성·공백 LLM 검토 Skill (requirements·specification·test-design 3원 정합성 + 누락/미고려 지점 지적) → `.claude/skills/sot-readiness-review/`
  - [ ] 검토 감사 로그 `docs/interim/sot-readiness-review.md` (스킬 생성, 게이트 비신뢰 사본 — 스키마는 스킬이 규정)
  - [ ] 사용자 게이트 최종 판정 연결 (`rule-sot-change-user-gate`)

## Phase 2 — 역할(Role) 정의 & 통신 프로토콜

각 역할별로 책임 / 시스템 프롬프트 / 호출 인터페이스 / Skill 정의.

- [ ] **Maintainer** — 상시 장기 tmux 세션. 전체 진척도 관리, Leader 생성·배치, Tmux 관리, progress 단독 작성 (Skill)
- [ ] **Watcher** — Cron 주기 호출. Maintainer **context 관리(압축/정리)** 전담
- [ ] **Leader** — 기능 단위 개발, workspace 종속, report 작성(자기보고 상태 포함) (Skill)
- [ ] **Developer** — 책임 범위 정의 (Leader가 workspace 내부에서 직접 호출)
- [ ] **Reviewer** — 책임 범위 정의 (코드 리뷰 + 사용자 게이트 연동)
- [ ] **Tester** — 책임 범위 정의 (유닛/통합 테스트 담당)
- [ ] **통신 프로토콜 정의** (D2 반영)
  - [ ] **report 파일** 포맷·위치·라이프사이클 (`report.status` 포함)
  - [ ] Maintainer → Leader **tmux send-keys** 주입 규약
  - [ ] Leader의 Dev/Reviewer/Tester 호출·산출물 중계 규칙 (sub-agent 간 직접 통신 없음, Leader가 허브)
  - [ ] Leader 간 의존성 → Maintainer 경유 조율 규칙

## Phase 3 — 격리 & 인프라 (Isolation / Infra)

> glue 스크립트 = **Python** (D9)

- [ ] Workspace 생성/삭제 자동화 스크립트
- [ ] **Docker 격리** — **workspace당 컨테이너 1개**, 해당 workspace만 마운트 (D3)
  - [ ] `git worktree`의 `.git` 공유 문제 해결 (독립 `.git` 또는 remote push 방식)
- [ ] Leader를 Docker로 배치하는 자동화
- [ ] **Tmux 오케스트레이션** — Maintainer가 다수 Leader 세션 관리 + send-keys 주입
- [ ] **Cron 설정** — Watcher 주기 호출 (context 관리)
- [ ] **규칙 강제(guardrails)** — 호스트/허브 층 (D15, `ADR-0007`; 명세 `rule-protected-paths`)
  - [ ] 런치 가드 — 격리 러너/entrypoint를 허브 쓰기 자격의 **유일 경로**로 (Maintainer 호스트 예외)
  - [ ] 로컬 pre-commit 훅(권고) — 네이밍·보호 경로 위반 즉시 경고
  - [ ] 허브 서버사이드 게이트(강제) — push 시 보호 경로 diff·네이밍·SoT 위반 거부, 정책·검사코드는 **신뢰 ref**에서 읽음. **경로·ref 기반은 무인증 baseline, 주체 인증(ref 위장 방지)은 하드닝 연기**

## Phase 4 — 진척 추적 모델 (Progress / Report)

> 별도 DB 없음. interim 파일 기반.

- [ ] **progress 파일** 설계 — **엄격 스키마 MD 테이블** (D7)
  - [ ] 스키마: 고정 5컬럼(`wave`·`task`·`status`·`leader`·`updated`) + 통제된 status 어휘 (report 포인터 컬럼 없음 — canonical 경로로 판정)
  - [ ] **단일 작성자 = Maintainer** 규칙 명문화
- [ ] **report → progress 승격 흐름** 구현 (Maintainer가 report 읽고 수용 후 progress 갱신)
- [ ] 크래시/컨텍스트 압축 후 **progress·report로부터 상태 복원** 절차
- [ ] progress **마일스톤 커밋** 정책 적용 (D10)

## Phase 5 — 멀티 플랫폼 Agent 지원

> D4: 공통 인터페이스 + **두 어댑터 모두 구현**

- [ ] 공통 **agent runner 인터페이스** 정의 (세션 기동/prompt 주입/출력 읽기)
- [ ] `.claude/` 구성 + Claude Code 어댑터 (skills, settings, hooks)
- [ ] `.codex/` 구성 + Codex 어댑터 (동등 기능)
- [ ] 플랫폼별 동작 차이 검증 매트릭스

## Phase 6 — Git 호스트 연동

- [ ] **GitHub 1차 완성** (D5, `gh` CLI)
- [ ] **사용자 게이트** — 회색지대 결정 시 사용자를 Reviewer로 한 PR 생성 후 일시정지/재개
- [ ] 호스트 추상화 레이어 (PR 생성/리뷰/머지 공통 인터페이스)
- [ ] GitLab 어댑터
- [ ] Forgejo 어댑터

## Phase 7 — 사용자 인터페이스 & 알림 (Web / Messenger)

> Web·브릿지 = **Python** (D9)

- [ ] **Local Web Server 브리핑** — interim 파일 **read-only** 렌더링 (Python)
  - [ ] 개요: progress 파일 1개 읽기
  - [ ] 드릴다운: 클릭 시 해당 report 파일만 읽기
- [ ] **메신저 연동** (양방향)
  - [ ] outbound: Maintainer가 결정 지점에서 직접 알림 발송 (큐 없음)
  - [ ] inbound: webhook 브릿지 → tmux send-keys → Maintainer (stateless)
  - [ ] **Discord 1차 완성** (D8)
  - [ ] 메신저 추상화 레이어
  - [ ] Slack 어댑터
  - [ ] Lark 어댑터

## Phase 8 — 오케스트레이션 / 자동화 엔진

- [ ] 핵심 루프: 문서 완료 → 자동 개발 착수 — **세 트리거 지원** (SoT PR merge / 명시 명령 / 마커 파일, D6)
- [ ] Maintainer 주도 진척도 관리 (Phase 4 progress 활용)
- [ ] Wave/Task 분해 → Leader 배정 로직
- [ ] 일시정지/재개 메커니즘 (사용자 결정 지점, 게이트·메신저 연동)
- [ ] 실패/재시도/에스컬레이션 처리

## Phase 9 — 검증 & 문서화

- [ ] 핵심 스크립트/Skill 유닛 테스트
- [ ] 전체 워크플로 통합 테스트 (문서→개발→PR→브리핑→알림 1사이클)
- [ ] **도그푸딩**: 예제 미니 프로젝트로 템플릿 실제 구동
- [ ] 최종 사용자 가이드 (템플릿 사용법, 셋업, 트러블슈팅)
- [ ] 아키텍처 다이어그램 / 역할 상호작용도 + 통신 채널 맵

---

## 의존 관계 요약

```
Phase 0 ─> Phase 1 ─> Phase 2 ─┐
                                ├─> Phase 8 ─> Phase 9
Phase 3 ─> Phase 4 ─> Phase 7 ─┤
Phase 5 ─> Phase 6 ────────────┘
```

- Phase 0(기반)은 모든 작업의 선행.
- Phase 4(진척 모델)는 Phase 7(Web·메신저)의 선행 — 브리핑이 progress·report에 의존.
- Phase 8(엔진)은 2·4·6·7이 어느 정도 갖춰져야 통합 가능.
- Phase 9(검증)는 마지막이지만, 각 Phase 종료 시 부분 검증 권장.

---

## 🗂️ 백로그 (Backlog)

> Phase 계획에 아직 박히지 않은, 진행 중 떠오른 작업. 우선순위를 표기하고 착수 시점에 적절한 Phase로 편입한다.

- [ ] **[높음] 용어집(glossary) 작성** — AXDT 설계 전반의 용어를 한곳에 정의. 지금은 SoT/Interim 정도만 `terminology.md`·본 TODO에 흩어져 있고, Maintainer·Leader·게이트·readiness·finding(`F-n`)·`review_clear`/`accepted`/`rejected`·트리 해시 등 논의에서 쓰는 용어의 단일 사전이 없어 혼동이 잦다. 위치·형식 미정(`docs/sot/rule/` 편입 vs 별도 glossary 파일).
- [ ] **[높음] 문서 워크플로 도식화** — SoT·interim 각 문서의 생애와 문서 간 관계를 사람이 한 눈에 이해할 도식으로. 지금은 통신 채널 맵·상태 모델(report→progress)·디렉터리 구조·강제 계층이 TODO·`protected-paths`·`ADR-0004` 등에 흩어져 있고, "작성 → 검토(②) → 사용자 게이트(①②③) → 완료 → 개발 트리거"로 이어지는 문서 전체 흐름을 한 장으로 보는 통합 자료가 없다.
