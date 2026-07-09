# sot-lint 스펙 (SoT 완료 판정 ① 형식 검사기)

> 상태: 초안(구현 착수용). 이 문서는 `docs/sot/rule/sot-readiness.md`의 "① 형식(기계 검증)"을 그대로 구현하는 결정적 Python 검사기의 스펙이다. 정본은 rule ①이며, 본 문서와 어긋나면 rule ①이 이긴다.

## 1. 목적·위치

- **역할**: SoT 완료 판정 3조건(① 형식 ∧ ② 정합성·공백 ∧ ③ 사용자 승인) 중 **① 형식**을 검사하는 결정적 스크립트. B-1 저술 스킬이 PR 게이트에 올리기 **직전** 호출해 형식을 사전 정렬한다. 최종 강제는 Phase 6 CI 필수 검사.
- **단일 구현**: 이 스크립트 하나를 B-1 산출물로 지금 만들고 Phase 6에서 `axdt` 패키지로 승격해 CI에 배선한다. 스킬과 CI가 같은 코드를 쓰므로 금지어 목록 등에서 drift가 없다.
- **위치**(결정B): `WIP/axdt/sot_lint/` 패키지. 기존 `WIP/axdt/`의 `agent_runner`·`git_host`·`infra`와 일관. Phase 6에서 `axdt` 하위 명령으로 흡수.
- **실행**(결정B): 독립 모듈 `python -m axdt.sot_lint [경로]`. Phase 6에서 `axdt sot-lint`로 재노출.

## 2. 검사 대상 파일

- 기본 경로 `docs/sot/`. 인자로 경로를 주면 그 하위를 검사(= 검사 루트).
- 종류(디렉터리)로 파일을 분류: `requirements/`·`specification/`·`test-design/`·`rule/`.
- **전역 제외**: 파일명이 `README.md`이거나 `_TEMPLATE.md`로 끝나는 파일은 C1~C6 **전체에서 제외**. rule id 레지스트리(§5) 수집에서도 `rule/_TEMPLATE.md`·`rule/README.md`는 제외.
- `topic` = 파일명 stem(확장자 제외). 예: `requirements/auth.md` → topic `auth`.

## 3. 파싱 모델

### 3.1 frontmatter(YAML)
- 파일 선두 `---` … `---` 블록을 표준 YAML 파서로 읽는다.
- 추출 키: `id`, `items`, `covers`, `rules`. (`related`는 힌트라 읽되 검사하지 않는다.)
- **오류 처리(종료코드 2)**: frontmatter 부재, YAML malformed, 중복 키는 위반이 아니라 **실행 오류**로 처리한다(검사 불능). `--json`에서는 `errors`로 표현(§6).
- **coerce**: `covers`·`rules`·`items`는 리스트로 정규화한다. 스칼라 1개는 1원소 리스트로 받는다(`covers: FR-1` == `covers: [FR-1]`).
- **콤마 문자열 금지(위반)**: `covers: FR-1, FR-2`처럼 한 문자열 안에 콤마로 여러 값을 넣는 표기는 위반으로 잡는다(YAML상 단일 문자열 `"FR-1, FR-2"`가 되어 항목 ID로 해소되지 않기 때문). 리스트(`[FR-1, FR-2]`)나 블록 시퀀스를 쓰게 강제.

### 3.2 본문 항목 ID
- 본문에서 항목 ID(`FR-n`/`NFR-n`/`SP-n`/`TD-n`)를 **볼드 여부와 무관하게** 토큰으로 매칭한다(단어 경계, `n`은 정수). **코드 블록(펜스)만 제외**하고 인라인 코드는 포함한다 — 항목이 인라인 코드로만 언급돼도 "본문에 등장"으로 본다(phantom 오탐 방지). C4·C5와 마스킹 정책이 다르다(§3.3).
- 같은 ID가 본문에 여러 번 등장하는 것은 정상이다(정의 자리·수용 기준·추적성 등). 존재·유일성은 frontmatter `items`로 판정하고, 본문은 `items`와의 **집합 일치**를 대조하는 데만 쓴다(§4 C2). 어느 등장이 "선언"인지 가리지 않는다 — 집합만 비교하므로 선언/참조 구분이 필요 없다.

### 3.3 코드 펜스·인라인 코드 상태머신
- **C4(플레이스홀더)·C5(금지어)**는 코드 블록(``` 펜스)과 인라인 코드(`백틱`) 안을 **모두** 검사에서 제외한다.
- **C2 본문 ID 토큰 매칭**은 코드 블록(펜스)만 제외하고 **인라인 코드는 포함**한다(항목이 인라인 코드로만 등장해도 존재로 인정 — phantom 오탐 방지).
- 라인 단위 스캔에 펜스 상태(진입/이탈)를 유지한다. C4·C5는 추가로 라인 안 인라인 백틱 구간을 마스킹한 뒤 검사한다.

## 4. 검사 항목 (C1~C6)

선언 정본은 frontmatter `items`다. 존재·유일성·참조 무결성은 frontmatter를 대조해 결정적으로 판정한다. 본문은 세 곳에서만 읽는다: (a) `items`↔본문 ID 집합 일치(C2), (b) C6 수용 기준 체크박스, (c) C4·C5 텍스트 스캔.

- **C1 존재** — requirements·specification·test-design **각각**, `items`에 항목을 1개 이상 선언한 문서가 최소 1개 존재(README·`_TEMPLATE` 제외).
  - 종류 전체에 그런 문서가 없으면 위반. 위치는 그 종류 디렉터리 경로, line=null(§7).
  - 개별 문서의 `items`가 비어 있는 것 자체는 위반이 아니다(그 문서는 "항목 선언 없는 문서"로 통과). C1은 종류에 항목 선언 문서가 최소 1개만 있으면 충족.
- **C2 항목 ID + 유일성 + 본문 일치** — 선언 정본 `items` 검사.
  - **종류 규약**: 각 문서 `items`의 ID가 종류 규약을 따른다: 요구 `FR-<정수>`·`NFR-<정수>`, 사양 `SP-<정수>`, 테스트 설계 `TD-<정수>`. 벗어나면 위반.
  - **유일성**: 같은 `(topic, ID)` 조합이 SoT 전체에서 둘 이상 `items`에 선언되면 위반(중복 선언은 참조 대상을 모호하게 만든다). topic=파일 stem이라 한 문서 내 `items` 중복이 곧바로 걸린다.
  - **본문↔items 집합 일치**: 그 문서 **종류의 ID**(요구=FR/NFR, 사양=SP, 테스트설계=TD)를 본문에서 토큰 매칭(§3.2, 코드펜스만 제외)해 집합을 만들고 `items`와 대조한다. 본문에 있으나 `items`에 없는 ID → 위반(미선언). `items`에 있으나 본문 어디에도 등장하지 않는 ID → 위반(phantom = 선언만 있고 본문에 전혀 안 쓰임). **타 종류 ID**(예: test-design 본문 추적성 표의 FR-n·SP-n)는 다른 문서를 가리키는 참조라 이 대조에서 제외.
  - phantom 검사는 "본문에 ID가 나오는가"까지만 본다. 참조 위치(추적성·수용 기준 등)에만 등장하고 실제 정의 서술이 없는 경우는 형식이 아니라 내용 공백이라 ②가 판정한다(① 과잉 금지).
  - **id↔topic**: frontmatter `id`가 `<종류 접두>-<topic>` 규약과 일치해야 한다. 접두는 종류 고정 3종(`req-`/`spec-`/`td-`)을 **정확히 1회만** prefix-strip하고 **나머지 전체를 topic으로** 본다(다세그먼트 kebab 지원, 예 `req-user-auth`→`user-auth`; topic이 우연히 `req-`로 시작하는 `req-req-parser`→`req-parser`도 1회 strip으로 옳게 처리). 이 topic이 파일 stem과 문자열 완전일치해야 한다. 불일치 위반.
- **C3 참조 무결성** — `covers`·`rules`가 가리키는 대상이 실재(dangling 없음). frontmatter↔frontmatter 대조.
  - **spec.covers → 요구 items**: 대상 topic의 requirements 문서 `items`에 그 `FR-n`·`NFR-n`이 선언돼 있어야 한다.
  - **td.covers → 요구·사양 items**: `FR-n`·`NFR-n`은 requirements items, `SP-n`은 specification items에 선언돼 있어야 한다.
  - **교차 topic 접두**: `covers` 원소가 `topic:ID`(예 `auth:FR-1`) 형태면 그 topic 문서의 items에서 찾는다. 접두가 없으면 **참조하는 문서와 같은 topic**의 문서에서 찾는다.
  - **대상 부재 vs dangling**: 참조 대상 문서(topic+종류)가 아예 없으면 위반(대상 문서 부재), 문서는 있으나 그 `items`에 ID가 없으면 위반(dangling). 메시지로 구분한다.
  - **rules → rule 레지스트리**: `*.rules`의 각 원소가 실재 rule id여야 한다(§5).
  - `covers`에 미치환 `<...>`가 남아 있으면 항목으로 해소하지 않고 **C4가 잡는다**(참조 실패가 아니라 플레이스홀더 위반).
  - `related`는 검사 제외.
- **C4 플레이스홀더 없음** — 미치환 `<...>` 없음. **검사 범위 = frontmatter + 본문**. 코드 블록·인라인 코드 제외는 **본문에만** 적용하고, frontmatter의 `covers: [<...>]`·`id: req-<topic>` 같은 미치환도 잡는다.
  - 정규식은 산문의 부등호 오검을 피하도록 특이하게: `<`와 `>` 사이에 개행이 없고 공백으로 시작하지 않는 토큰(예: `<판정 기준.>`은 위반, `a < b`·`x<y`는 비위반)만 잡는다. 세부 정규식은 구현 시 red 테스트로 고정.
- **C5 금지어 없음**(결정A) — 닫힌 최소 목록만 검사, 코드 상수로 단일 관리:
  - 목록: `TBD`, `TODO`, `FIXME`, `미정`, `추후`, `나중에`.
  - ASCII 토큰(`TBD`·`TODO`·`FIXME`)은 대소문자 무시 + 단어 경계 매칭. 한글(`미정`·`추후`·`나중에`)은 정확 매칭.
  - 코드 블록·인라인 코드 제외(§3.3). 오검이 나오면 후속 조정.
- **C6 수용 기준 자리 채워짐** — `items`의 각 항목마다 수용 기준이 채워져 있어야 한다.
  - 수용 기준은 체크박스 줄 `- [ ] … <ID> … <내용>`으로 식별하고, 줄에서 ID 토큰을 뽑아 항목과 대응시킨다(볼드 여부 무관).
  - `items`의 어떤 항목에 대응 체크박스가 없거나, 대응 체크박스의 내용이 비었거나 플레이스홀더(`<...>`)·금지어면 위반.
  - **검증 가능한지·무의미한 filler인지는 판정하지 않는다** — ②의 몫.
- **범위 밖(안 한다)** — 커버리지 완결성(모든 요구가 사양·테스트로 커버되는지, 고아 항목 등)은 ②의 몫이라 검사하지 않는다.

## 5. rule id 레지스트리

- **검사 루트 하위 `rule/` 디렉터리의 `*.md`**(기본 루트면 `docs/sot/rule/*.md`) 각 파일 frontmatter `id`를 수집해 집합을 만든다. `rule/_TEMPLATE.md`·`rule/README.md`는 제외.
- `*.rules`의 각 원소를 이 집합과 대조(C3).

## 6. CLI 계약 (결정B)

- 호출: `python -m axdt.sot_lint [경로]`. 경로 인자 기본값 `docs/sot/`.
- 옵션: `--json`.
- **종료코드**: `errors` 있으면 **2**, 없고 `violations` 있으면 **1**, 둘 다 없으면 **0**.
- **텍스트 출력**: 위반마다 한 줄 `파일:라인 · 코드(C1~C6) · 메시지`(위치가 파일 전체/디렉터리 수준이면 라인 생략). 실행 오류는 `파일 · E_* · 메시지`.
- **`--json` 스키마**(고정):
  ```json
  {
    "schema_version": 1,
    "ok": false,
    "violations": [
      {"path": "docs/sot/requirements/auth.md", "line": 14, "code": "C2", "message": "..."}
    ],
    "errors": [],
    "summary": {"files": 3, "violations": 1, "errors": 0, "by_code": {"C2": 1}}
  }
  ```
  - `errors` = 검사 불능(§3.1: frontmatter 부재/malformed/중복 키 등). 실행 오류 코드는 `E_*`.
  - `ok` = `violations`와 `errors`가 **모두** 비었는가.
  - `line`은 위치가 특정 라인이 아니면 `null`(C1 종류 부재 등).

## 7. 결정성

- 같은 입력 = 같은 출력(정렬 포함).
- **정렬 키**: `violations`는 `(path, line, code, message)`, `errors`는 `(path, code, message)`를 유니코드 코드포인트로 정렬(locale 무관). `line`이 null이면 정렬상 가장 앞.
- set·dict에서 파생되는 모든 출력(파일 나열·rule id 집합·item 집합 순회)은 방출 전 정렬해 순서 비결정성을 제거.
- **인코딩·개행**: 입력은 UTF-8로 읽고, CRLF/LF를 정규화해 라인 번호를 센다(라인 번호는 1-기준).

## 8. 미해결·구현 시 확정

- C2의 세부 위반 코드 분리(종류 규약 위반 / 유일성 / 미선언 / phantom / id↔topic)를 하나로 묶을지 나눌지는 구현 시 결정. 메시지로 구분 가능하면 단일 코드로 둔다.
- C4 플레이스홀더 정규식의 정확한 형태는 구현 시 red 테스트(산문 부등호 비위반, `<판정 기준.>` 위반)로 고정.
- 코드 펜스/인라인 상태머신은 표준적인 라인 스캐너로 구현하되, 중첩·틸드 펜스(`~~~`)까지 다룰지는 테스트로 범위 확정.

## 9. 테스트·구현

- 테스트: pytest(`py -3`로 실행 — `python`은 깨진 WindowsApps stub).
- 구현은 Sonnet 서브에이전트에 위임(이 스펙 + rule ① + 템플릿 3종을 근거로).
- 구현 산출물: `WIP/axdt/sot_lint/`(패키지 `__init__.py`·`__main__.py`·검사 로직) + pytest.

## 참조

- 정본: `docs/sot/rule/sot-readiness.md` "① 형식".
- 파싱 대상 구조: `docs/sot/{requirements,specification,test-design}/_TEMPLATE.md`(frontmatter `items` 포함).
- 설계 배경: `WIP/drafts/b1-authoring-skill-draft.md` §5·§7·§8-2.
- 결정: `WIP/TODO.md` D20(sot-lint)·D21(선언명시)·D22(금지어·CLI·참조 확정).
