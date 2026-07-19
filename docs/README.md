# docs/ — 문서 루트

> AXDT의 모든 프로젝트 문서가 모이는 루트. **SoT(권위본)** 와 **interim(중간 산출물)** 을 구분한다(사람을 위한 **길잡이(guide)** 문서는 AXDT 자체 설계라 `WIP/`에 둔다).

## 목적
이 저장소로 개발되는 **대상 프로젝트의 문서**를 담는다. 문서는 권위 수준에 따라 나뉜다.

- **`sot/`** — Source of Truth. 변경은 사용자 게이트 PR로만. 시스템이 "참"으로 삼는 기준.
- **`interim/`** — Agent가 쓰는 가변 산출물(ADR·plan·report·progress). 비권위. 단, 작성 주체 제약 있음 — **plan은 Maintainer**(분해·배정, Leader는 읽기만), **progress는 Maintainer 단독**.
- **길잡이(guide) 문서** — 사람을 위한 비권위 안내(용어집·워크플로)는 AXDT 자체 설계 문서라 `docs/`가 아니라 `WIP/`(`WIP/glossary.md`·`WIP/workflow.md`)에 둔다(`rule-terminology`의 WIP/ 예외 — `docs/` 하위는 SoT 아니면 interim). 정의·흐름의 권위는 이들이 링크하는 SoT·ADR 원본에 있다.

## 필수 내용
- 새 문서는 해당 하위 디렉터리의 `README.md`와 `_TEMPLATE.md`를 따른다.
- SoT/interim 구분을 흐리지 않는다 — 권위가 필요한 내용은 SoT로 승격(PR), 작업 중 메모는 interim에 둔다.

## 네이밍
- 디렉터리·파일명은 각 하위 README의 규약을 따른다.

## 참고
- 전체 용어 사전: `WIP/glossary.md`
- 문서·작업 워크플로 개관: `WIP/workflow.md`
- 용어(SoT/Interim) 정의: `sot/rule/terminology.md`
- 변경 권위 규칙: `sot/rule/sot-change-user-gate.md`
