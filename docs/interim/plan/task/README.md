# docs/interim/plan/task/ — task (Leader 작업 단위)

> Leader 1명이 맡는 작업 단위. **task = Leader = workspace = container, 1:1.**

## 목적
한 Leader가 격리된 workspace에서 수행할 작업을 정의한다. 이 문서의 id가 곧 branch·workspace·container 이름을 결정한다(D14).

## 필수 내용
- **task id** — `w<n>.t<n>-<slug>`
- **상위 wave** — 소속 wave(`w<n>`)
- **목표** — 이 task가 달성할 것
- **범위** — 다루는 것 / 다루지 않는 것
- **의존** — 선행 task
- **DoD (Definition of Done)** — 완료 판정 기준
- **대상 workspace/branch** — task id와 동일(컨테이너만 `axdt-` 접두)

> 상태 필드 없음 — 진척은 progress.md(Maintainer)와 report(Leader)가 담는다.

## 네이밍
- 파일명: `w<n>.t<n>-<slug>.md` (예: `w3.t12-auth-login.md`).
- frontmatter `id`: 파일명과 동일(`w3.t12-auth-login`).

## 참고
- 템플릿: `_TEMPLATE.md` (Phase 1에서 작성)
- 식별자·workspace·container 규격: `../../../sot/rule/branch-workspace-naming.md`
- 이 task에 대한 보고: `../../report/`
