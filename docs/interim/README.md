# docs/interim/ — 중간 산출물 (Interim)

> Agent가 작업 중 자유롭게 쓰는 **가변·비권위** 문서. SoT처럼 사용자 게이트를 거치지 않는다.

## 목적
개발 과정에서 생성되는 결정 기록·작업 분해·보고·진척을 담는다. 권위본(SoT)이 아니므로 Agent가 직접 쓰고 갱신한다. 단, **plan은 Maintainer가 분해·배정하고(Leader는 읽기만), 진행 기록은 Maintainer만** 작성한다.

## 필수 내용
- **`ADR/`** — 대상 프로젝트의 아키텍처 결정 기록
- **`plan/`** — wave/task 작업 분해 (**Maintainer** 작성, 상태 필드 없음)
- **`report/`** — Leader의 task 보고 (`report.status` 포함)
- **`progress.md`** — Maintainer 진행 기록 (단일 작성자, D7 스키마)

## 네이밍
- 각 하위 디렉터리 README의 규약을 따른다.

## 참고
- progress 단일 작성자: `../sot/rule/progress-single-writer.md`
- report→progress 권위 흐름: `../sot/rule/report-to-progress-authority.md`
- **주의**: 이 `ADR/`는 대상 프로젝트의 아키텍처 결정 기록 자리다(D12/D13).
