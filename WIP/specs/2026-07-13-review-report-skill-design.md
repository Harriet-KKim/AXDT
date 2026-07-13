# 검토/보고용 HTML 스킬 (`review-report`) 설계

> 상태: **draft R2**. Codex(gpt-5.6-sol)·Fable 다중 리뷰(착수 불가 판정) 반영 개정. 사용자 검토 후 확정한다.
> 대응: 사용자 요청(검토/보고용 HTML을 체계적으로 쓰는 스킬), Backlog 373(용어집)·374(워크플로 도식) 연계.
> 성격: AXDT 산출물이 아니라 **개발 과정에서 쓰는 개인 도구**. 스킬 본체는 리포 밖(`~/.claude/skills/`), 프로젝트 데이터만 리포 안(`WIP/reviews/`).
> R2 개정 요지: 의견 왕복 JSON 단일화 · 앵커당 다중 의견 · 용어 풀이 실노출+단어경계 · HTMLParser 안전(파서 스택·fragment 제한) · context 신뢰 HTML+자체완결 검사 · Artifact 계약 실측(Task 0) · 메모리 삭제 지연.

---

## 1. 목표와 비목표

### 목표
- Spec·설계·결정사항을 **맥락이 충분히 담긴 HTML**로 보고하고, 사용자가 그 위에 **검토 의견을 주입**하며, 의견 수렴 후 재검토로 내용이 바뀌면 **같은 페이지(같은 URL)에 반영**하는 반복 루프를 스킬 하나로 고정한다.
- 어려운 용어는 **풀어서** 보이되(화면에 실제로 노출), 풀이의 단일 진실원은 스킬이 소유하지 않고 **프로젝트 용어집 문서를 참조**한다.
- 공통 반복 요소(껍데기·배경·용어 풀이)는 **공용 파일에서 조립**하고, 매 라운드 새로 쓰는 것은 본문뿐으로 한정한다.
- 페이지에 **세션 이름·주제 요약·라운드 수**를 필수로 싣고, 빠지거나 비면 빌드가 실패하게 한다.

### 비목표 (하지 않음)
- **페이지→에이전트 자동 왕복** — Artifact의 CSP가 외부 통신(`fetch`/XHR/WebSocket)을 막으므로 실시간 전송은 성립하지 않는다. 의견은 클립보드(기본)·브라우저 되읽기(보조)로 회수한다.
- **용어집 신규 저술** — Backlog 373의 몫. 이 스킬은 소비자다.
- **다중 리뷰어·권한 모델** — 리뷰어는 사용자 1명.
- **라운드 간 본문 diff 렌더** — Artifact 버전 이력이 대신한다.
- **일반 마크다운 렌더** — context는 신뢰 HTML(`context.html`)로 받는다. 표준 라이브러리로 마크다운 렌더러를 만들지 않는다(YAGNI).
- **용어집·배경 캐시** — 매 빌드 원본을 다시 읽는다(드리프트 방지, 파싱 비용 무시 가능).

---

## 2. 핵심 설계 결정

### 2.1 산출 경로 = Artifact, 라운드 = 같은 URL 덮어쓰기
로컬 HTML 파일이 아니라 **Artifact로 게시**한다(개인 규칙: HTML 산출물은 Artifact). Artifact는 같은 파일 경로(또는 `url`)로 재게시하면 **같은 URL에 덮어쓰고 버전 이력**을 남긴다. 이것이 "같은 페이지에 반영"의 메커니즘이다. 2라운드부터 `meta.json`의 `artifact_url`을 `url`로 넘겨 덮어쓰고, `label`에 `"Round N"`을 붙여 이력에 남긴다. **이 전제(favicon 필수·`<title>` 반영·같은 경로=같은 URL·`url` 업데이트·버전 열람)는 구현 전 Task 0에서 실제 도구로 실측해 계약을 고정한다(§10).**

### 2.2 공용은 파일로 분리, 조립기가 본문과 합성
Artifact는 자체 완결형이라 런타임에 외부 파일을 못 끌어온다. 따라서 "공용 참조"는 **게시 시점 인라인**이다. 껍데기(`shell.html`)와 조립기(`build.py`)를 스킬에 고정하고, 매 라운드 쓰는 것은 `body.html`뿐이다. 정확성이 중요한 코드(직렬화·파싱·치환)를 한 번 짜서 고정하면, 라운드마다 다시 쓰다 어긋나는 일이 없고 토큰도 준다.

### 2.3 용어집은 소유하지 않고 참조
스킬이 자기 용어집을 들면 손사본이 되어, Backlog 373이 완성되는 순간 두 벌로 갈라진다. 대신 `config.json`의 `glossary_sources`가 프로젝트 문서를 가리키고, 조립기가 빌드마다 파싱해 `{용어→풀이}` 맵을 만든다. 단일 진실원은 계속 `docs/sot/rule/` 쪽에 남는다. 지금은 `terminology.md` 하나로 시작하고, 373이 끝나면 배열에 경로 한 줄을 더한다.

파싱은 흔한 두 형태를 받는다: `- **용어** — 풀이`(정의 목록), `| 용어 | 풀이 |`(표). **소스 파일이 없으면 조용히 넘기지 않고 빌드 실패**(오탈자·경로 오류를 숨기지 않기 위해). 지표는 정직하게 정의한다: 조립기는 **미사용 용어집 항목 수**(용어집엔 있으나 본문에 안 쓰인 항목)만 참고 로그로 낸다. "본문에 등장하는데 풀이 없는 용어"는 감지할 입력이 없으므로(본문에서 용어를 표시하는 수단인 수동 `<b-term>`·용어집 등재어는 둘 다 이미 풀이가 있다) 이 지표를 만들지 않는다. Backlog 373 우선순위 근거는 저자가 수동 `<b-term>`으로 직접 단 용어 수(=용어집에 없어 손으로 푼 용어)로 대신 삼는다.

### 2.4 필수 메타데이터는 문서가 아니라 빌드가 강제
`session`·`topic`·`round`가 없거나 비면 조립기가 **exit 1로 멈춘다**. 나아가 타입·범위까지 검증한다: `round`는 정수 ≥ 1, `session`·`topic`은 비지 않은 문자열, `anchors`는 문자열 리스트, `round ≥ 2`면 `artifact_url` 필수, 본문 섹션 최소 1개. 세 값은 페이지 최상단 히어로에 항상 렌더된다.

### 2.5 의견 앵커 = 본문 문장이 아니라 섹션 안정 ID
검토 페이지는 본문이 라운드마다 고쳐지는 게 전제다. 문장에 하이라이트를 걸면 그 문장이 다음 라운드에 바뀌는 순간 앵커가 깨진다. 그래서 앵커는 **섹션에 부여한 안정 ID**다. 앵커는 **정규식 `[A-Za-z0-9_-]+`로 강제**(CSS 셀렉터·JS·라디오 name·localStorage 키에 안전하게 들어가도록)하고, 문서 내 **중복 앵커는 빌드 오류**다. 본문 최상위는 `<section data-anchor="SP-3" data-title="…">`의 반복이고, ID는 한 번 부여하면 라운드를 넘어 유지된다. `meta.json.anchors`와 본문을 대조해 소실 앵커(이전 의견 고아)를 경고한다.

### 2.6 의견에는 종류 태그, 앵커당 다중 의견
텍스트 뭉치로만 돌아오면 에이전트가 "반드시 고칠 것인지, 단순 질문인지"를 추측한다. **수정요청·질문·이견·승인** 네 종류로 태깅한다. 한 섹션에 성격이 다른 의견을 여럿 남길 수 있어야 하므로, 데이터 모델은 **앵커당 다중 의견**이다: `localStorage`·클립보드·`comments.json` 모두 **평면 `items` 배열**(각 항목이 `anchor`를 가짐)로 동형이다. UI의 "＋ 의견"은 항목을 **추가**(덮어쓰기 아님)하고 개별 삭제가 가능하다. 페이지 하단엔 어느 섹션에도 안 붙는 **총평(GENERAL)** 앵커를 둔다.

### 2.7 의견 회수 = JSON 단일 계약 (클립보드 기본 + 브라우저 되읽기 보조)
의견 왕복은 **JSON 하나**로 한다. 텍스트 형식을 두 언어(파이썬·JS)에 손으로 구현하면 왕복이 깨지고(대괄호·`###`·CRLF·빈 줄 손상 — 실측으로 확인됨) 이중 구현이 된다. 그래서:
- JS는 `localStorage`의 의견을 **`JSON.stringify`로 직렬화**해 클립보드에 넣는다. 파이썬은 붙여넣은 텍스트에서 **JSON 블록만 `json.loads`로 엄격히 읽는다**. 형식·종류 목록·왕복 대칭이 JSON 하나로 고정된다.
- `localStorage` 키는 **라운드별 스코프** `rr:<slug>:r<round>`. 라운드로 키를 나누지 않으면 같은 URL 덮어쓰기에서 이전 라운드 초안이 되살아난다. 이전 라운드 키는 지우지 않고 남긴다(실수로 새 라운드를 열어도 초안 보존, 라운드로 갈려 안 섞임).
- 클립보드 쓰기(`navigator.clipboard.writeText`)가 iframe 권한으로 막힐 수 있으므로 **`.catch()` + 항상 보이는 readonly `<textarea>` 폴백**(선택→수동 복사)을 둔다. `localStorage` 접근 실패도 화면 경고로 표면화한다.
- 회수는 CLI 하위명령 **`ingest <slug-dir> <clipboard-file>`** 로 워크플로에 연결한다: 붙여넣은 JSON의 `slug`·`round`를 대상과 대조(불일치는 오류), `comments.json`의 해당 라운드에 원자적으로 병합. Chrome 확장이 살아 있으면 에이전트가 탭을 열어 `localStorage`를 직접 읽어 붙여넣기를 생략한다.

### 2.8 본문은 누적하지 않고 최신만, 이전 의견은 처리 결과 카드로
페이지 본문은 항상 **최신 안**만 담는다. 각 섹션(GENERAL 포함)에 그 섹션에 달렸던 이전 라운드 의견과 처리 결과가 접힌 카드로 붙는다: **반영 / 일부 반영 / 보류 / 다르게 감** + 한 줄 사유. 여러 줄 의견은 `white-space: pre-wrap`으로 줄바꿈을 보존한다. 이전 라운드의 페이지 전체 모습은 Artifact 버전 이력이 보존한다. 사용자는 한 화면에서 (a) 최신 안, (b) 지난 지적이 어떻게 됐는지를 함께 본다.

### 2.9 시각·구조는 확립된 집 스타일을 코드로 고정
`shell.html`은 사용자가 명시 승인한 **HTML 산출물 집 스타일**(메모리 `html-deliverable-house-style`)을 구현한다.

- **구조(자립·해설형)**: eyebrow 라벨 + 제목 + lede → 배경/읽는법 박스 → 목차(TOC) → 번호 매긴 장 → 하단 용어표 + 메타 푸터. 필수 메타(세션·주제·라운드)는 상단 히어로에, 출처 메타(대상 파일·PR·생성일)는 푸터에.
- **시각 시스템**: CSS 변수 토큰, 라이트·다크 양방향(`prefers-color-scheme` + `:root[data-theme]` 양쪽 우선). 절제 뉴트럴 + 강조1 + 보조1 + 의미색. 시스템 폰트만, 식별자·해시·`file:line`은 monospace. 카드·콜아웃·표 `overflow-x`·반응형·`prefers-reduced-motion`. AI 기본 룩 회피.
- **용어 풀이 실노출**: `<b-term>`은 점선 밑줄만이 아니라 **hover·focus로 뜨는 툴팁**으로 풀이를 보인다(`title` 속성 폴백 + `tabindex`로 키보드 접근). 자동·수동 용어 **모두 하단 용어표에 포함**한다.
- **적용 범위·트리거**: `SKILL.md` 트리거를 "해설·검토용 HTML 산출물 일반"으로 넓혀 단발 요청도 포섭한다. 집 스타일의 **단일 소유자가 스킬**이 된다(→ §9). 세부 판단은 `artifact-design` 스킬이 보강.

### 2.10 마크업 안전 — fragment 제한 + 파서 스택
조립기는 `body.html`을 관대하게 재작성하지 않고 **엄격한 fragment**로 제한한다.
- 허용: 최상위 `<section data-anchor data-title>` 반복. 각 앵커는 §2.5 정규식·유일. `data-title` 필수. 최상위 section 밖의 텍스트, 기존 `id` 속성, DOCTYPE/PI/CDATA는 **빌드 오류**로 거부한다(HTMLParser가 소실·정규화하는 것들).
- 앵커 수집·최상위 판정·이전 의견 카드 주입은 **HTMLParser의 section 깊이 스택**으로 한다(정규식·문자열 `find` 폐기 — 중첩·부분일치·주석 내 가짜 태그 오류 방지). 카드는 짝 맞는 종료 이벤트에 주입한다.
- `shell.html` 치환은 **알려진 토큰만 1회 스캔 치환**(`{{TOKEN}}` 정규식 콜백). 삽입된 본문 안의 `{{…}}`가 재치환되지 않는다. 미치환 검사는 알려진 토큰 목록에만 적용한다.

---

## 3. 파일 배치

```
~/.claude/skills/review-report/     (개인 스킬 — 자체 git repo, worktree 복제 안 됨)
  SKILL.md            워크플로 · 라운드 절차 · 본문 문법 · 앵커/용어 규칙
  build.py            조립기 진입점 + 순수 함수 (py -3, 표준 라이브러리만)
  test_build.py       조립기 테스트 (unittest)
  shell.html          껍데기(집 스타일 §2.9): eyebrow+lede · 배경박스 · TOC · 토큰 라이트/다크 · 의견 UI · 용어표 · 메타 푸터 · 클립보드 JSON

<프로젝트>/WIP/reviews/           (프로젝트 데이터 — git 추적)
  config.json         glossary_sources · context_file
  context.html        배경 박스 원문 (신뢰 HTML, 1회 작성)
  <slug>/             검토 세션 하나 = 아티팩트 URL 하나 = 라운드 시퀀스 하나
    meta.json         session · topic · round · artifact_url · anchors[] · 출처 메타
    body.html         본문 (매 라운드 갱신하는 유일한 파일)
    comments.json     라운드별 의견 + 처리 결과 (진실원)
    out.html          생성물 (.gitignore)
```

### 배치 근거
- **개인 스킬**: AXDT는 worktree가 5개라 프로젝트 스킬은 그만큼 복제된다(`sot-readiness-review`가 그렇다). 개인 스킬은 복제 문제가 없고 다른 프로젝트에서도 쓴다. 자체 git repo로 이력·백업·복구를 확보한다.
- **`WIP/reviews/`**: `docs/interim/`은 AXDT가 만들어낼 제품의 산출물 스키마 자리다. `rule-terminology`가 "AXDT 자체 설계 문서는 `WIP/`에 둔다"고 명시하므로 검토 데이터도 `WIP/` 아래가 맞다.
- **평면 `<slug>`**: 폴더 단위는 phase가 아니라 검토 세션 하나(불변식: slug=URL=라운드 시퀀스). phase 접두로 정렬.
- **`comments.json` 단일 진실원**: 사람이 읽을 마크다운 사본을 두지 않는다(미러 드리프트 회피). 사람이 보는 뷰는 렌더된 페이지가 제공한다.
- **`out.html`만 무시**: `body.html` git 이력이 라운드별 본문 이력, `comments.json`이 감사 기록.

---

## 4. 데이터 계약

### 4.1 `config.json` (프로젝트당 1개)
```json
{
  "glossary_sources": ["docs/sot/rule/terminology.md"],
  "context_file": "WIP/reviews/context.html"
}
```
경로는 프로젝트 루트 기준. `glossary_sources`는 순서대로 병합, 겹치면 뒤 소스가 이긴다. **소스 파일이 없으면 빌드 실패.** 입력은 `utf-8-sig`로 읽어 BOM을 허용한다.

### 4.2 `meta.json` (검토 세션당 1개)
```json
{
  "session": "phase1 SoT 게이트 설계",
  "topic": "게이트 실패 시 재시도·재개 정책 확정",
  "round": 2,
  "artifact_url": "https://claude.ai/public/artifacts/…",
  "anchors": ["SP-3", "SP-5", "D-2"],
  "target_files": ["docs/sot/rule/sot-readiness.md"],
  "pr": "#12",
  "created": "2026-07-13"
}
```
검증은 §2.4. `target_files`·`pr`·`created`는 있으면 푸터에 렌더, 없으면 생략.

### 4.3 클립보드 형식 (JSON 단일 계약)
붙여넣기용 텍스트는 사람이 무엇인지 알아볼 한 줄 + **기계가 읽는 JSON 한 블록**이다.
```
검토 의견 — phase1 SoT 게이트 설계 / Round 2   (아래 JSON을 붙여넣어 주세요)
{"slug":"sot-gate","round":2,"items":[
  {"anchor":"SP-3","kind":"수정요청","text":"3회는 많음.\n2회로 줄이자."},
  {"anchor":"GENERAL","kind":"승인","text":"나머지 좋음"}
]}
```
파이썬은 첫 `{`부터 대응 닫힘까지를 `json.loads`(내부 개행·대괄호·유니코드 모두 JSON이 처리). JS는 `JSON.stringify(payload, null, 2)`로 같은 구조를 생성. 형식·왕복이 JSON 하나로 고정된다.

### 4.4 `comments.json` (진실원, 클립보드와 동형)
```json
{
  "rounds": [
    {
      "round": 1,
      "items": [
        { "anchor": "SP-3", "kind": "수정요청", "text": "…",
          "resolution": "반영", "note": "2회로 축소, ADR-0012 갱신" }
      ]
    }
  ]
}
```
`items`는 클립보드 payload와 같은 평면 배열. `resolution`·`note`는 에이전트가 다음 라운드에서 채운다. 빌드는 과거 항목의 `kind ∈ KINDS`·`resolution ∈ RESOLUTIONS`(있으면)·`anchor` 형식·`round` 단조를 검증하고 위반 시 실패한다.

---

## 5. 본문 작성 문법 (`body.html`)

```html
<section data-anchor="SP-3" data-title="게이트 실패 시 재시도 정책">
  <p>재시도는 최대 <b-term def="지정한 횟수만큼만 반복">3회</b-term>까지 하고…</p>
</section>
```
- 최상위는 `<section>` 반복. 각 `data-anchor`(§2.5 정규식·유일)·`data-title` 필수. `id` 속성 금지(조립기가 부여). 장 번호·TOC는 조립기가 매긴다.
- 용어 풀이: 용어집에 있으면 첫 등장을 조립기가 자동으로 감싼다(단어 경계 준수 — §6). 없으면 `<b-term def="풀이">용어</b-term>`로 직접 단다. 둘 다 툴팁으로 노출되고 용어표에 실린다.
- 감싸기 제외: 코드 블록·제목·기존 `<b-term>`·이전 의견 카드.
- 콜아웃 `<div class="rr-note">`·`<div class="rr-warn">`, 워크드 예제 `<div class="rr-panel">`.
- 외부 리소스(원격 `src`/`href`/CSS `url()`·`<script>`) 금지 — 조립기가 최종 산출물에서 검사해 위반 시 실패(자체완결 보장).

---

## 6. 조립기 계약 (`build.py`)

`py -3 "<skill>/build.py" build WIP/reviews/<slug>` 의 절차:

1. 프로젝트 루트 탐색 → `config.json`·`<slug>/meta.json` 로드(`utf-8-sig`). 메타 검증(§2.4) 실패 시 exit 1.
2. `glossary_sources` 파싱(정의목록·표). 소스 누락 시 실패. `{용어→풀이}` 맵.
3. `body.html`을 fragment 파서로 검증(§2.10): 최상위 section·앵커 정규식·유일성·`data-title`·`id`금지·금지 노드. 위반 시 exit 1. 앵커를 스택으로 수집해 `meta.anchors`와 대조(소실 경고).
4. 이전 의견 카드를 파서 스택으로 **정확한 section 종료에 주입**(GENERAL 포함). 카드는 감싸기 제외로 표시.
5. **본문(카드 제외)에 용어 첫 등장 감싸기** — ASCII 용어는 단어 경계(양옆 영숫자·`_`면 스킵), CJK 용어는 경계 없이. 수동 `<b-term>` 내부 용어는 소진 등록(재감쌈 방지). 카드보다 본문을 먼저 처리해 첫 등장이 본문에서 소비되게 한다.
6. 최상위 section 순서로 장 번호·TOC 생성(파서 스택).
7. `context.html`(신뢰) → 배경 박스, 용어 맵(사용분) → 용어표, `meta` 출처 메타 → 푸터.
8. `shell.html`을 **알려진 토큰 1회 치환**(§2.10)으로 조립 → `out.html`(utf-8, 명시 newline). 최종 산출물 외부 리소스 검사(위반 시 실패).
9. 요약 출력(ASCII 안전 로그): `섹션 N · 용어 M개 감쌈 · 미사용 용어집 K개 · 소실 앵커 목록`.

`ingest` 하위명령: `py -3 "<skill>/build.py" ingest WIP/reviews/<slug> <clipboard.json>` — JSON 로드, `slug`·`round` 대조(불일치 오류), `comments.json` 해당 라운드에 병합.

의존성은 표준 라이브러리만. 게시는 조립기가 하지 않고 에이전트가 `out.html`을 Artifact 툴로 올린다. 실행은 스킬 디렉터리의 **절대 경로**로 부른다(build.py는 스킬에 있고 데이터는 프로젝트에 있으므로).

---

## 7. 라운드 절차 (SKILL.md가 규정)

1. **선행(최초 1회)**: `config.json`·`context.html` 없으면 만든다. Artifact 계약이 미확인이면 Task 0 실측(§10)을 먼저.
2. **새 검토**: `<slug>/meta.json`(round=1)·`body.html` 작성. `comments.json`=`{"rounds":[]}`.
3. **빌드**: `py -3 "<skill>/build.py" build WIP/reviews/<slug>` → `out.html`. 경고 확인.
4. **게시**: Artifact 툴로 `out.html` 게시 — **고정 `favicon`·`description`, `<title>`은 shell이 보유**. Round 1은 신규, 반환 URL을 `artifact_url`에 기록. Round 2+는 그 `url`로 재게시 + `label:"Round N"`.
5. **회수**: 사용자가 "의견 복사"→붙여넣기 → `ingest`. 또는 확장으로 `localStorage` 되읽기.
6. **반영**: `comments.json`의 각 항목 `resolution`·`note` 결정, `body.html` 갱신, `round`+1. 3으로.

---

## 8. 테스트 (`test_build.py`)

- 메타 검증: 필수 누락·타입 오류(round 비정수/음수, session 비문자열)·round≥2 URL 누락·섹션 0개 → exit 1.
- 용어집: 두 형식 파싱, 뒤 소스 우선, 소스 누락 실패, BOM 허용, 표 escape.
- 용어 감싸기: 첫 등장만, 코드/제목/기존 b-term/카드 제외, **수동 b-term 뒤 동일 용어 미재감쌈**, **단어 경계(SoT/SoTware, gate/gateway)**, 최장 우선.
- fragment 검증: 중첩/기존 id/DOCTYPE/앵커 정규식 위반·중복 앵커 → 오류.
- 앵커 수집·카드 주입: 파서 스택 정확성(중첩 section에도 올바른 종료에 주입), GENERAL 카드 렌더.
- 클립보드: `json.loads` 왕복 대칭(내부 개행·대괄호·`###`·유니코드), slug/round 불일치 오류.
- `ingest`: comments.json 병합, 중복 방지.
- 치환: 알려진 토큰만 1회 치환(본문 내 `{{…}}` 불변), 미치환 검사.
- 자체완결: 최종 산출물 외부 리소스 검사.
- 집 스타일: TOC·장 번호, 용어표(자동+수동), 푸터(필드 유무), 라이트/다크 토큰, b-term 툴팁 규칙 존재.

---

## 9. 열린 질문 / 후속

- Backlog 373(용어집) 완성 시 `glossary_sources`에 경로 추가 — 스킬 변경 없이 설정만.
- Backlog 374(워크플로 도식)를 배경 박스/별도 섹션으로 끌어올지는 도식이 나온 뒤.
- **메모리 `html-deliverable-house-style` 이전·삭제 (지연)**: 스킬이 집 스타일 단일 소유자가 되지만, 삭제는 **2라운드 acceptance test 통과 + 사용자 승인 후**에만 한다. 그 전에 삭제하면 검증 안 된 구현만 남기고 복구 경로를 잃을 위험이 있다(Codex 지적). 삭제 전 메모리 내용을 스킬 repo에 백업 커밋하고, `MEMORY.md` 색인 줄도 함께 정리한다.

---

## 10. Artifact 계약 실측 (Task 0 — 구현 전)

스킬 전체가 Artifact 재게시 거동에 의존하므로, 구현 착수 전 실제 도구로 1회 확인해 계약을 문서에 고정한다:
1. 최소 페이지를 게시 → 공개 URL·favicon 필수 여부·`<title>` 반영 확인.
2. **같은 file_path로 재게시** → URL 동일성·버전 이력(`label`) 확인.
3. 이전 버전 열람 가능 확인.
4. (해당 시) 다른 대화의 아티팩트를 `url`로 업데이트하는 경로 확인.

결과(정확한 파라미터·반환 URL 형식·favicon/title 규칙)를 이 절에 기록한 뒤 §2.1·§7을 확정한다.
