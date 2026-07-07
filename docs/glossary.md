# AXDT 용어집 (Glossary)

이 문서는 권위본(SoT)이 아닌 사람을 위한 길잡이(guide)다. 각 항목의 정의는 짧은 요약일 뿐이며, 권위는 항목마다 링크한 원본 문서(rule·ADR·TODO)에 있다. 이 글과 원본이 어긋나면 원본이 이긴다. 용어들이 어떤 흐름에서 쓰이는지는 `docs/workflow.md`(워크플로 개관)를 함께 본다.

## 1. 문서 분류 & 저장소 구조

- **SoT (Source of Truth, 권위본)** — `docs/sot/`에 두는 requirements·specification·test-design·rule. Agent가 작성하되 변경은 사용자 게이트 PR로만 한다. 출처: `docs/sot/rule/terminology.md`.
- **Interim (중간 산출물)** — `docs/interim/`에 두는 ADR·plan·report·progress. 작업 중 Agent가 생성·변경하며 원칙적으로 자유롭다(개별 파일에 더 좁은 제약이 있을 수 있음). 출처: `docs/sot/rule/terminology.md`.
- **specification (사양)** — 시스템이 "무엇을 어떻게" 하는지(범위·구성요소·인터페이스·데이터모델·동작·수용기준)를 담는 SoT 문서. 항목 ID는 `SP-n`. 출처: `WIP/TODO.md`(디렉터리 구조 표), `docs/sot/rule/sot-readiness.md`(① 형식).
- **requirements (요구사항)** — "무엇이 왜" 필요한지(목표·기능/비기능 요구·제약·범위외·수용기준)를 담는 SoT 문서. 항목 ID는 `FR-n`(기능)·`NFR-n`(비기능). 출처: `WIP/TODO.md`(디렉터리 구조 표), `docs/sot/rule/sot-readiness.md`(① 형식).
- **test-design (테스트 설계)** — 요구·사양을 "무엇을 어떻게 검증하는가"의 권위 정의. 요구·사양과 동급인 **SoT 4번째 타입**(D16). 테스트 조건(`TD-n`)·블랙박스 커버리지 목표(동등분할·경계값·결정표·상태전이)·스위트 구조·요구↔테스트 추적성·절차 원칙까지 담는다. 구체 케이스·데이터·화이트박스 커버리지는 `test/` 코드의 몫(설계/구현 절단선). 완료 판정에 요구·사양과 함께 묶인다. 출처: `docs/sot/test-design/README.md`, `WIP/adr/0008-test-design-as-sot-type.md`.
- **설계/구현 절단선** — 테스트 설계(SoT)와 테스트 코드(`test/`)의 경계. 코드·실행 없이 문서만으로 확정되고 요구·사양에서 바로 도출되면 SoT, 코드·데이터·실행 환경이 있어야 확정되면 `test/`. 화이트박스 커버리지(결정/분기/MC-DC)는 코드가 있어야 측정되므로 SoT에서 제외한다. 출처: `docs/sot/test-design/README.md`, `WIP/adr/0008-test-design-as-sot-type.md`.
- **rule (규칙)** — 프로젝트가 따르는 규범(용어·네이밍·통신·표준)을 담는 SoT 문서. 규칙문·근거·적용범위·예시 4개 섹션으로 쓴다. 출처: `docs/sot/rule/README.md`.
- **ADR (Architecture Decision Record)** — 비자명한 핵심 설계 결정을 근거·검토한 대안과 함께 기록하는 문서(취향·1차 선택은 대상 아님). AXDT 자체 ADR은 `WIP/adr/`, 대상 프로젝트 ADR은 `docs/interim/ADR/`. 출처: `WIP/TODO.md` D13, `WIP/adr/_TEMPLATE.md`.
- **plan (wave/task)** — 작업의 정의·구조("무엇을 할지")를 담는 interim 문서. Maintainer가 wave/task로 분해·배정하며 상태(status) 필드가 없다. task 정체성·의존·DoD·branch/worktree 이름이 여기서 파생된다. 출처: `docs/sot/rule/terminology.md`.
- **report** — task별 상세 내용과 Leader의 자기보고 상태(`report.status`)를 담는 interim 문서. 그 task에 배정된 Leader만 쓴다. 출처: `docs/sot/rule/terminology.md`, `docs/sot/rule/protected-paths.md`.
- **progress** — 오케스트레이션 색인 + 수용 상태(`progress.status`) + 각 report 포인터를 담는 interim 문서. Maintainer 단독 작성. 출처: `docs/sot/rule/terminology.md`, `docs/sot/rule/progress-single-writer.md`.
- **docs/·src/·test/·WIP/ (D12)** — `docs/`는 SoT·interim 문서 루트, `src/`·`test/`는 이 템플릿으로 만들어지는 대상 프로젝트의 코드·테스트 자리, `WIP/`는 AXDT 자체 구현·기획의 임시 위치다(단, AXDT를 도그푸딩 대상으로 개발할 때는 `WIP/`도 그 대상 프로젝트 plan의 지배를 받는다). 출처: `WIP/TODO.md` D12, `docs/sot/rule/protected-paths.md`.
- **README·_TEMPLATE (D11)** — 문서를 담는 디렉터리마다 목적·필수내용·네이밍을 적은 `README.md`와, Agent가 복제해 채우는 빈 양식 `_TEMPLATE.md`를 둔다. 출처: `WIP/TODO.md` D11, `docs/sot/rule/README.md`, `docs/sot/rule/protected-paths.md`.
- **guide 문서 (이 파일 부류)** — SoT도 interim도 아닌, 사람이 읽도록 만든 비권위 안내 문서. `docs/` 바로 아래 위치하며 정의의 권위는 이 문서가 링크하는 SoT·interim 원본에 있다. 출처: `WIP/TODO.md`(백로그 "용어집 작성" 항목), 이 문서(`docs/glossary.md`) 자체.

## 2. 역할(Role)

- **Maintainer** — 프로젝트 시작~종료까지 상시 실행되는 장기 tmux 세션. 전체 진척 관리, Leader 생성·배치, tmux send-keys 주입, progress 단독 기록, 사용자 결정 지점에서의 메신저 발송을 맡는다. 출처: `WIP/adr/0001-maintainer-persistent-tmux-session.md`, `docs/sot/rule/progress-single-writer.md`.
- **Watcher** — Cron으로 주기 호출되어 Maintainer의 context 관리(압축·정리)만 전담한다. 출처: `WIP/TODO.md` D1, `WIP/adr/0001-maintainer-persistent-tmux-session.md`.
- **Leader** — 기능 단위 개발을 맡아 worktree 하나에 종속되는(1:1) 역할. 자기 산출물은 report·src·test에 쓰고, Developer/Reviewer/Tester를 호출하는 허브다. 출처: `docs/sot/rule/branch-worktree-naming.md`, `docs/sot/rule/subagent-no-direct-communication.md`.
- **Developer** — Leader가 worktree 내부에서 직접 호출하는 sub-agent. 구현을 맡고 Leader에게만 결과를 반환한다. 출처: `WIP/TODO.md` Phase 2, `docs/sot/rule/subagent-no-direct-communication.md`.
- **Reviewer** — (1) Leader가 호출하는 sub-agent로 코드 리뷰를 담당한다. (2) SoT 변경 게이트에서는 사용자가 그 PR의 Reviewer 역할을 맡는다 — 서로 다른 맥락의 같은 이름이니 혼동하지 않는다. 출처: `WIP/TODO.md` Phase 2, `docs/sot/rule/sot-change-user-gate.md`.
- **Tester** — 유닛·통합 테스트를 담당하는 sub-agent. 출처: `WIP/TODO.md` Phase 2.
- **사용자 (User)** — Maintainer와 메신저·Web으로 소통하고, SoT 변경 PR의 Reviewer이자 완료 판정의 최종 승인자(③ 게이트)다. 출처: `docs/sot/rule/sot-change-user-gate.md`, `docs/sot/rule/sot-readiness.md`, `WIP/TODO.md`(통신 채널 맵).
- **sub-agent** — Developer·Reviewer·Tester처럼 Leader에게만 응답하고 서로 직접 통신하지 않는 하위 에이전트. 출처: `docs/sot/rule/subagent-no-direct-communication.md`.

## 3. 상태 & 워크플로

- **report.status** — Leader가 자기 작업을 스스로 주장하는 상태값. Leader 소유. 출처: `docs/sot/rule/terminology.md`, `docs/sot/rule/report-to-progress-authority.md`.
- **progress.status** — Maintainer가 report를 검토·수용한 뒤 기록하는, 시스템이 참으로 삼는 상태값. 출처: `docs/sot/rule/progress-single-writer.md`, `docs/sot/rule/report-to-progress-authority.md`.
- **status flow (상태 흐름)** — 상태 권위가 `report.status`(Leader 자기보고) → `progress.status`(Maintainer 수용)로 한 방향으로만 흐르는 모델. 둘이 다르면 모순이 아니라 "수용 대기"라는 정상 상태다. 출처: `docs/sot/rule/report-to-progress-authority.md`, `WIP/adr/0004-report-to-progress-authority-flow.md`.
- **승격 (promotion, report→progress)** — report의 자기보고가 progress의 수용된 진실로 올라가는 지점. 이 지점이 곧 Maintainer의 검토·게이트 지점이다. 출처: `docs/sot/rule/report-to-progress-authority.md`.
- **수용 (acceptance, 게이트)** — Maintainer가 report를 읽고 그 내용을 progress에 반영할지 판단하는 행위. 출처: `docs/sot/rule/progress-single-writer.md`, `WIP/adr/0004-report-to-progress-authority-flow.md`.
- **wave 롤업** — 승격 지점에서 일어나는 집계·수용·(필요시) Reviewer/Tester/사용자 게이트와 함께, wave 단위로 진척을 묶어 올리는 것. 출처: `docs/sot/rule/report-to-progress-authority.md`, `WIP/adr/0004-report-to-progress-authority-flow.md`.
- **마일스톤 커밋 (D10)** — progress는 git으로 추적하되, wave/task 완료 마일스톤 경계에서만 커밋해 이력을 보존하고 churn을 줄인다. 출처: `WIP/TODO.md` D10, `WIP/adr/0002-no-separate-db-or-queue.md`.

## 4. 완료 판정(SoT readiness) & 게이트

메커니즘 전체는 `docs/sot/rule/sot-readiness.md`에 있다. 아래는 이 문서·스킬에 쓰이는 용어가 무슨 뜻인지 한 줄로만 짚는다.

- **완료 (readiness)** — requirements·specification·test-design이 개발을 자동 시작해도 되는 상태. ① 형식 ∧ ② 정합성·공백 검토 ∧ ③ 사용자 승인이 **동일한 SoT 콘텐츠**에 대해 모두 성립해야 참이다. 요구·사양이 완료되려면 대응 test-design도 함께 완료돼야 한다. 출처: `docs/sot/rule/sot-readiness.md`.
- **① 형식 검증** — 문서 존재·항목 ID(요구 `FR-n`·`NFR-n`, 사양 `SP-n`, 테스트 `TD-n`)·참조 무결성·플레이스홀더/금지어 없음 등을 기계가 결정적으로 검사하는 필요조건. 출처: `docs/sot/rule/sot-readiness.md`.
- **② 정합성·공백 검토** — `sot-readiness-review` 스킬이 requirements·specification·test-design을 항목 단위로 대조하는 LLM 검토. 호스트 CI가 콘텐츠당 1회 자동 실행한다. 출처: `docs/sot/rule/sot-readiness.md`, `.claude/skills/sot-readiness-review/SKILL.md`.
- **③ 사용자 승인** — `rule-sot-change-user-gate`의 게이트 PR을 사용자가 승인하는 마지막 관문. ①②를 대신하지 못한다. 출처: `docs/sot/rule/sot-readiness.md`.
- **판정 키 (트리 해시 + 적용 rule 지문)** — ② 판정과 각 finding이 결속되는 두 성분 키. 두 성분 중 하나라도 바뀌면 이전 판정은 무효가 된다. 출처: `docs/sot/rule/sot-readiness.md`.
- **완전 결속 키** — 판정 키에 `F-n + finding 내용 digest`를 더한, finding 단위 사용자 표시·대조용 키. 출처: `docs/sot/rule/sot-readiness.md`.
- **적용 rule 지문** — 그 문서에 적용되는 각 rule 파일 전체 내용의 해시. 호스트가 그 PR의 제안된 머지 결과 상태에서 계산한다(에이전트 산출은 신뢰하지 않음). 출처: `docs/sot/rule/sot-readiness.md`.
- **트리 해시** — 검토 대상 SoT 콘텐츠(requirements·specification·test-design 트리)의 해시. 출처: `docs/sot/rule/sot-readiness.md`.
- **finding** — ② 검토가 찾아낸 지적 하나. 축·심각도·참조(문서·항목 ID)·설명·상태로 구성된다. 출처: `.claude/skills/sot-readiness-review/SKILL.md`.
- **F-n** — finding의 회차 간 안정 ID. 출처: `.claude/skills/sot-readiness-review/SKILL.md`.
- **finding 내용 digest** — finding의 (축 + 참조 문서·항목 ID + 심각도 + 설명 본문)을 정규화해 취한 해시. 출처: `docs/sot/rule/sot-readiness.md`.
- **검토 축 (축1~4)** — ② 검토가 보는 네 관점: 축1 커버리지·추적성(요구→사양→테스트 3원 매트릭스), 축2 짝 정합성, 축3 교차 정합성, 축4 완결성·공백(+ test-design 절단선 위반 검사). 출처: `.claude/skills/sot-readiness-review/SKILL.md`.
- **review_clear** — ② 판정값. blocking finding이 없거나 모두 resolved다. 출처: `.claude/skills/sot-readiness-review/SKILL.md`.
- **review_blocked** — ② 판정값. open인 blocking finding이 하나 이상 있다. 출처: `.claude/skills/sot-readiness-review/SKILL.md`.
- **blocking** — 착수 전 반드시 닫아야 하는 finding 심각도. 출처: `.claude/skills/sot-readiness-review/SKILL.md`.
- **open** — finding이 아직 닫히지 않은 상태(검토가 매김). 출처: `.claude/skills/sot-readiness-review/SKILL.md`.
- **resolved** — SoT 트리 변경으로 finding이 실제 해소된 상태(검토가 매김). 감사 표기일 뿐 게이트 입력은 아니다. 출처: `docs/sot/rule/sot-readiness.md`, `.claude/skills/sot-readiness-review/SKILL.md`.
- **accepted** — 사용자가 호스트 채널에서 blocking finding의 위험을 인지하고 수용한다는 결정. 출처: `docs/sot/rule/sot-readiness.md`.
- **rejected** — 사용자가 호스트 채널에서 blocking finding을 오판으로 판단해 기각한다는 결정. 출처: `docs/sot/rule/sot-readiness.md`.
- **fail-closed** — 검사 상태가 없거나 현재 판정 키에 대한 것이 아니면 미완료로 처리하는 원칙. 출처: `docs/sot/rule/sot-readiness.md`.
- **dismiss-stale** — 판정 키가 바뀌면 기존 ③ 승인을 무효화하는 호스트 보호(최신 push에 대한 재승인 요구). 출처: `docs/sot/rule/sot-readiness.md`.
- **필수 검사 (required check)** — ①·②의 판정을 호스트가 머지 게이트에 결속하는 방식. 출처: `docs/sot/rule/sot-readiness.md`.
- **사용자 채널** — `accepted`·`rejected` 표시가 이뤄지는 곳(그 SoT 변경 PR의 호스트 채널). 완전 결속 키를 참조해 표시한다. 출처: `docs/sot/rule/sot-readiness.md`.
- **scope (global/local)** — rule의 재검토 범위 표시. `local`은 그 rule을 `rules`에 선언한 req·spec만, `global`(용어·네이밍 등 횡단)은 완료된 req·spec 전량이 재검토 대상이다. 미기재는 global로 취급한다. 출처: `docs/sot/rule/_TEMPLATE.md`, `docs/sot/rule/sot-readiness.md`.

## 5. 격리·인프라·네이밍

- **worktree (git 기능)** — 한 저장소에서 브랜치별로 별도 작업 디렉터리를 두는 git 기능. task 하나 = Leader 하나 = worktree 하나 = container 하나로 1:1 대응한다. 출처: `docs/sot/rule/branch-worktree-naming.md`, `WIP/TODO.md` D3.
- **container** — worktree당 배정되는 Docker 컨테이너 1개. 그 worktree만 read-write로 마운트하고 나머지는 차단한다. 출처: `WIP/TODO.md` D3, `WIP/adr/0007-layered-enforcement.md`.
- **Leader clone** — 각 Leader에게 배정되는 저장소 복제본(작업본). 물리 마운트는 유닛 간 격리만 담당하므로, clone 안에 함께 들어오는 `progress.md`·`docs/sot/`·`plan/` 같은 보호 경로는 이 격리로 보호되지 않는다. 출처: `docs/sot/rule/protected-paths.md`, `WIP/adr/0007-layered-enforcement.md`.
- **w<n>.t<n>-<slug> (D14)** — branch·worktree 디렉터리·컨테이너를 동일하게 명명하는 단일 식별자 규격(`w`=wave 번호, `t`=task 번호, `slug`=kebab-case 작업명). 슬래시는 쓰지 않는다. 출처: `docs/sot/rule/branch-worktree-naming.md`, `WIP/TODO.md` D14.
- **브랜치/worktree/컨테이너 네이밍** — 셋 다 `w<n>.t<n>-<slug>` 식별자를 그대로 쓰되, 컨테이너 이름에만 `axdt-` 접두를 붙인다. 출처: `docs/sot/rule/branch-worktree-naming.md`.
- **보호 경로 (protected paths)** — 쓰기 권한이 특정 주체로 제한된 경로. 다른 역할이 자기 task 브랜치에서 이를 수정하면, 컨테이너가 접근할 수 없는 허브/호스트 게이트가 그 push를 거부한다. 출처: `docs/sot/rule/protected-paths.md`.
- **허브/호스트 게이트** — 컨테이너가 접근할 수 없는 층에서 이뤄지는 강제 검사(권위 게이트). 로컬 훅과 달리 우회할 수 없다. 출처: `WIP/adr/0007-layered-enforcement.md`, `docs/sot/rule/protected-paths.md`.
- **pre-receive 훅** — 허브 bare repo의 서버사이드 git 훅. push된 ref의 콘텐츠(경로·ref 기반)를 검사해 무인증으로도 보호 경로 위반을 거부한다. 출처: `WIP/adr/0007-layered-enforcement.md`, `docs/sot/rule/sot-readiness.md`.
- **런치 가드** — 격리 러너/entrypoint를 컨테이너 마운트·허브 네트워크 경로의 유일한 부여자로 두는 통제(Maintainer는 호스트 상주라 예외). 출처: `WIP/adr/0007-layered-enforcement.md`.
- **신뢰 ref (trusted ref)** — 게이트가 검사 코드·정책(보호 경로 표 등)을 읽는 기준이 되는, 후보 브랜치가 수정할 수 없는 base ref. 출처: `docs/sot/rule/protected-paths.md`, `WIP/adr/0007-layered-enforcement.md`.
- **물리 격리** — 강제 3층의 첫 층. Docker 마운트(D3)·독립 clone으로 유닛(task/Leader) 간 격리를 이룬다. clone 내부에 함께 포함되는 보호 경로는 이 층으로 보호되지 않는다. 출처: `WIP/adr/0007-layered-enforcement.md`.
- **강제 3층 (D15)** — 규칙 강제를 ① 물리 격리 ② 로컬 pre-commit 훅(권고) ③ 허브/호스트 게이트(강제)의 세 지점에 나눠 두는 결정. 실제 강제력은 컨테이너가 접근할 수 없는 ③에만 있다. 출처: `WIP/TODO.md` D15, `WIP/adr/0007-layered-enforcement.md`.

## 6. 통신 & 트리거

- **send-keys (tmux)** — Maintainer가 Leader의 tmux 세션에 prompt를 직접 주입하는 하향 통신 경로. 별도 파일 채널이 없다. 출처: `WIP/adr/0003-agent-communication-model.md`, `WIP/TODO.md` D2.
- **허브 구조** — Leader가 Developer/Reviewer/Tester를 호출하고 결과를 중계하는 별형(star) 상호작용 구조. sub-agent끼리는 직접 통신하지 않는다. 출처: `docs/sot/rule/subagent-no-direct-communication.md`, `WIP/adr/0003-agent-communication-model.md`.
- **report 채널** — Leader에서 Maintainer로 올라가는 상향 통신 경로. 역방향 tmux 채널이 없어 report 파일이 상태 기록과 통신을 겸한다. 출처: `WIP/adr/0003-agent-communication-model.md`, `WIP/TODO.md` D2.
- **webhook 브릿지** — 메신저 inbound를 받아 tmux send-keys로 Maintainer에 전달하는 stateless 브릿지. 출처: `WIP/adr/0002-no-separate-db-or-queue.md`, `WIP/TODO.md`.
- **Discord/메신저 (D8)** — 1차 메신저는 Discord(webhook/봇)로 하고, Slack·Lark는 어댑터로 확장한다. 출처: `WIP/TODO.md` D8.
- **Local Web 브리핑** — interim 파일을 read-only로 read-time 렌더링하는 로컬 웹 서버(Python). 출처: `WIP/adr/0002-no-separate-db-or-queue.md`, `WIP/TODO.md` D9·Phase 7.
- **개발 시작 트리거 3종 (D6)** — 자동 개발 시작을 여는 세 경로: (주) SoT PR이 main에 merge, (보조) 명시적 시작 명령·플래그, (보조) 마커 파일 존재. 출처: `WIP/TODO.md` D6.
- **Docker (D3)** — worktree당 컨테이너 1개, 해당 worktree만 read-write로 마운트하고 그 외는 차단하는 격리 수준 결정. 출처: `WIP/TODO.md` D3.
- **Cron (Watcher)** — Watcher를 Cron으로 주기 호출해 Maintainer의 context를 압축·정리하는 트리거. 출처: `WIP/TODO.md` D1, `WIP/adr/0001-maintainer-persistent-tmux-session.md`.
