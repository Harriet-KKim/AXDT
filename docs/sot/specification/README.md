# docs/sot/specification/ — 사양 (Specification)

> 대상 시스템이 **무엇을 어떻게** 하는가 — 동작·인터페이스·데이터의 권위 정의.

## 목적
구현 가능한 수준으로 시스템의 동작·인터페이스·데이터 모델을 확정한다. Developer/Tester가 코드와 테스트를 짜는 직접 근거가 된다. (요구사항 = 왜/무엇, 사양 = 무엇/어떻게.)

## 필수 내용
- **범위** — 이 사양이 다루는 경계
- **구성요소** — 주요 모듈/컴포넌트
- **인터페이스** — API·CLI·이벤트 등 경계 계약
- **데이터 모델** — 엔티티·스키마·상태
- **동작** — 흐름·시나리오·에지 케이스
- **수용 기준** — 충족 여부 판정 기준
- **참조** — 관련 requirements·rule·외부 표준

## 네이밍
- 파일명: 주제 기반 kebab-case, `<topic>.md` (예: `auth-login.md`). 번호 미사용.
- frontmatter `id`: 소문자 `spec-<topic>` (예: `spec-auth-login`).

## 참고
- 템플릿: `_TEMPLATE.md` (Phase 1에서 작성)
- 짝이 되는 요구사항: `../requirements/`
