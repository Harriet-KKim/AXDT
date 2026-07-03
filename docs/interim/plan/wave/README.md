# docs/interim/plan/wave/ — wave (마일스톤)

> 여러 task를 묶은 마일스톤. wave 단위로 의존·종료를 관리한다.

## 목적
관련된 task들을 하나의 마일스톤으로 묶어, 어떤 task 묶음이 어떤 순서로 완료돼야 다음으로 넘어가는지 정의한다.

## 필수 내용
- **wave id** — `w<n>`
- **목표** — 이 wave가 끝나면 달성되는 것
- **포함 task** — 소속 task 목록(`w<n>.t<n>-<slug>`)
- **의존** — 선행 wave
- **종료 기준** — wave 완료 판정 조건

> 상태 필드 없음 — 진척은 progress.md(Maintainer)가 담는다.

## 네이밍
- 파일명: `w<n>-<slug>.md` (예: `w1-foundation.md`).
- frontmatter `id`: `w<n>` (예: `w1`).

## 참고
- 템플릿: `_TEMPLATE.md` (Phase 1에서 작성)
- 식별자 규격: `../../../sot/rule/branch-workspace-naming.md`
- 소속 task: `../task/`
