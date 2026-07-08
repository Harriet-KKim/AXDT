# Phase 4 빌드 순서 / 위임 분할 (thin)

> 정본 설계: `2026-07-05-phase4-progress-tracking-design.md` (4차, Codex+Fable 양 모델 "착수 가능"). 이 문서는 **구현 순서·위임 경계**만 담는다 — 설계·계약·정합 규칙은 스펙이 정본(중복 서술 안 함).
> 구현 위치: `WIP/axdt/progress/` (+ `cli.py`·`config.py` 확장, 테스트는 `WIP/axdt/progress/tests/`). **TDD**(테스트 먼저), phase3 관례.

## 의존 그래프
| 모듈 | 의존 |
|---|---|
| `schema.py` | 없음 (단일 정의원) |
| `config.py`(확장: `progress_path`·`report_dir`) | 없음 |
| `table.py` | schema |
| `lint.py` | schema·table |
| `recover.py` | schema(`pair_severity`)·table |
| `commit.py` | schema·table·git |
| `cli.py`(확장) | lint·recover·commit |

## 빌드 웨이브
- **Wave 0 (기반, 병렬):** `schema.py`(§5 schema 블록 — 어휘·`COLUMNS`·`TERMINAL`·`ALLOWED_TRANSITIONS`·`pair_severity`·`wave_rollup`) · `config.py` 확장(`progress_path`·`report_dir`).
- **Wave 1:** `table.py`(§5 table — `TaskRow`·`Report`·`parse/render_progress`·`parse_report`). schema 확정 후.
- **Wave 2 (병렬 3):** `lint.py` · `recover.py` · `commit.py`. 셋 다 schema+table만 의존 → 동시 진행 가능.
- **Wave 3:** `cli.py`(§7 `lint`/`status`/`commit` 서브커맨드) + 전체 통합 테스트 green.

## 위임 분할 (Sonnet 서브에이전트 · Leader=나 허브)
서브에이전트는 서로 통신 못 함 → **웨이브 경계에서 내가 계약(§5)·산출을 전달·조율**. schema 확정 전엔 Wave 2 착수 금지.

| 위임 | 내용 | 선행 |
|---|---|---|
| D0 | `schema.py` + `config.py` 확장 | — |
| D1 | `table.py` | D0 |
| D2·D3·D4 (병렬) | `lint.py` / `recover.py` / `commit.py` | D1 |
| D5 | `cli.py` 배선 + 전체 pytest green | D2·D3·D4 |

각 위임 = **"§8의 해당 테스트 먼저 → 구현 → green"**. 계약은 §5, 정합 규칙은 §4.

## 모듈별 완료 정의 (스펙 참조)
- **schema**: §5 상수/함수 시그니처 + `wave_rollup` 7규칙(빈·all-superseded·`todo`+`superseded`·`todo`+`accepted`·혼재) + `pair_severity` **§4.3 전 셀**.
- **table**: parse/render 라운드트립 · 유일 테이블 · 2개↑ 오류 · frontmatter 키 누락 예외.
- **lint**: §4.1 구조 · §4.2 참조무결성(고아 report=task 형식만·id/status) · §4.3 매트릭스 findings.
- **recover**: `State` 6집합 분류(§5/§6.2) · `wave_rollup` · 깨진 report→`needs_attention`.
- **commit**: `diff_progress`(최초 base=빈 테이블·신규 행 임의 상태) · 합성-폐포 4종 거부 · 과claim(**커밋 트리 블롭**·accepted만) · `format_milestone_message`(rejected 사유 필수·events=0∧gates) · `milestone_commit`(허브 push 안 함). §8의 "여러 칸 점프 통과"·"앞 커밋 done+무변경 accepted 통과" 반드시 포함.
- **cli**: 3 서브커맨드 · lint ERROR 시 종료코드 · commit `--reason`/`--gate`/`--dry-run`.

## 착수 전 1회 확인
- **Phase 1 경계(§10②):** `docs/interim/progress.md` 정본 빈 양식(**5컬럼**) setup · `report/_TEMPLATE.md` frontmatter 두 키 — 병렬 Phase 1 세션과 파일 경계를 맞춘 뒤 진행.
- **외부 문서 갱신(§10② 목록):** `docs/interim/progress.md` placeholder + `WIP/TODO.md` D7 항목의 6컬럼 표기 → 5컬럼.
- `config.py`에 progress/report 경로 함수 없음 → D0에서 추가.
