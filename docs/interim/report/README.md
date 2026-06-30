# docs/interim/report/ — Leader 보고 (Report)

> Leader가 자기 task 진척을 **스스로 보고**하는 파일. Leader가 progress에 닿는 유일한 경로.

## 목적
Leader는 progress.md를 직접 고치지 못한다. 진척·완료·블로커를 자신의 report에 적고, Maintainer가 이를 읽어 **수용할 때** progress에 반영된다. 즉 report = Leader의 자기보고(주장), progress = 시스템의 수용(권위).

## 필수 내용
- **task 참조** — 어느 task(`w<n>.t<n>-<slug>`)에 대한 보고인가
- **`report.status`** — Leader의 자기보고 상태(주장값)
- **요약** — 현재 상황
- **완료 내역** — 끝낸 것
- **블로커** — 막힌 것·필요한 의존(Leader 간 직접 조율 금지 → Maintainer 경유)
- **사양 변경 요청** — SoT 변경이 필요하면 여기로(직접 수정 금지)
- **다음** — 다음 단계

## 네이밍
- 파일명: 대상 task id와 동일, `w<n>.t<n>-<slug>.md` (예: `w3.t12-auth-login.md`).

## 참고
- 권위 흐름: `../../sot/rule/report-to-progress-authority.md`
- progress 단일 작성자: `../../sot/rule/progress-single-writer.md`
- Leader 간 조율: `../../sot/rule/leader-coordination-via-maintainer.md`
