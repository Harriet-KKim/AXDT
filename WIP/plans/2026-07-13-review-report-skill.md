# review-report 스킬 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 검토/보고용 HTML을 라운드 반복으로 게시·수렴하는 개인 스킬 `review-report`를 구현한다 — 조립기(`build.py`)가 본문·용어집·배경·의견 이력을 집 스타일 껍데기(`shell.html`)와 합쳐 자체완결 HTML을 낸다.

**Architecture:** 공용(껍데기·조립기)은 스킬에 고정하고 매 라운드 바뀌는 것은 본문(`body.html`)뿐. 조립기는 자리표시자 치환 방식으로 `shell.html`에 조각을 끼워 넣어 `out.html`을 만들고, 에이전트가 그것을 Artifact 툴로 같은 URL에 재게시한다. 용어 풀이의 진실원은 프로젝트 문서(`glossary_sources`)이고 조립기는 소비자다.

**Tech Stack:** Python 3 표준 라이브러리만(`html.parser`·`json`·`re`·`html`·`pathlib`·`sys`), 테스트는 `unittest`, 프론트는 순수 HTML/CSS/JS(웹폰트·CDN·외부 통신 없음).

## Global Constraints

- 스킬 파일은 **`C:/Users/Harriet/.claude/skills/review-report/`** 에 생성한다(개인 스킬, AXDT 리포 밖). 이 디렉터리를 **자체 git 저장소**로 초기화해(Task 1) 태스크별 커밋을 그곳에 남긴다. AXDT 리포에 커밋하는 것은 데이터 스캐폴딩(`WIP/reviews/`)과 `.gitignore` 갱신뿐(Task 9).
- Python 실행은 **`py -3`** 만 쓴다(`python`은 깨진 WindowsApps stub, exit 49).
- 런타임 의존은 **표준 라이브러리만**. 외부 패키지 금지(테스트 프레임워크 포함 — `unittest` 사용).
- `shell.html`은 **자체완결**: 외부 `fetch`/XHR/WebSocket·웹폰트·CDN·원격 이미지 금지(Artifact CSP 차단). 모든 CSS/JS 인라인.
- 문서·주석은 **한국어 평서·간결체**.
- 라이트/다크 **양방향** 지원: `prefers-color-scheme` 기본 + `:root[data-theme]` 오버라이드가 양쪽에서 이긴다.
- 테스트 실행 위치는 스킬 디렉터리, 명령은 **`py -3 -m unittest test_build -v`**.

---

## 파일 구조

```
C:/Users/Harriet/.claude/skills/review-report/   (개인 스킬, 자체 git repo)
  SKILL.md          워크플로·트리거·본문 문법 (Task 8)
  build.py          조립기 진입점 + 순수 함수 (Task 1~7)
  shell.html        집 스타일 껍데기 + 의견 UI + 클립보드 직렬화 JS (Task 6)
  test_build.py     unittest (Task 1~7 누적)

C:/Users/Harriet/Desktop/SST/AX Strategy/AXDT/   (worktree, AXDT 리포)
  .gitignore        `WIP/reviews/*/out.html` 무시 추가 (Task 9)
  WIP/reviews/
    config.json     glossary_sources·context_file (Task 9)
    context.md      배경 박스 원문 (Task 9)
    .gitkeep        빈 reviews 유지
```

`build.py` 한 파일에 순수 함수(파싱·감싸기·렌더)와 진입점을 함께 둔다. 함수는 파일 IO 없이 문자열만 다루므로 `from build import <fn>`로 단위 테스트된다. 진입점은 `if __name__ == "__main__"` 가드 뒤에 둬 import가 안전하다.

---

## Task 1: 스캐폴딩 + config/meta 로드·검증

**Files:**
- Create: `C:/Users/Harriet/.claude/skills/review-report/build.py`
- Test: `C:/Users/Harriet/.claude/skills/review-report/test_build.py`

**Interfaces:**
- Produces:
  - `REQUIRED_META = ("session", "topic", "round")`
  - `load_json(path: Path) -> dict` — JSON 파일 로드, 없으면 `FileNotFoundError`
  - `validate_meta(meta: dict) -> None` — 필수 키 누락 시 `sys.exit(1)` (stderr에 누락 키)
  - `find_project_root(start: Path) -> Path` — `start`에서 위로 올라가며 `WIP/reviews/config.json`을 가진 디렉터리를 찾음, 없으면 `sys.exit(1)`

- [ ] **Step 1: 스킬 디렉터리와 자체 git 저장소 생성**

Run:
```bash
mkdir -p "C:/Users/Harriet/.claude/skills/review-report"
cd "C:/Users/Harriet/.claude/skills/review-report"
git init -q
```
Expected: `.git/` 생성.

- [ ] **Step 2: 실패 테스트 작성**

Create `test_build.py`:
```python
import io
import json
import unittest
from contextlib import redirect_stderr
from pathlib import Path
import build


class ValidateMetaTest(unittest.TestCase):
    def test_missing_session_exits_1(self):
        with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            build.validate_meta({"topic": "t", "round": 1})
        self.assertEqual(cm.exception.code, 1)

    def test_missing_topic_exits_1(self):
        with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            build.validate_meta({"session": "s", "round": 1})
        self.assertEqual(cm.exception.code, 1)

    def test_missing_round_exits_1(self):
        with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            build.validate_meta({"session": "s", "topic": "t"})
        self.assertEqual(cm.exception.code, 1)

    def test_complete_meta_passes(self):
        build.validate_meta({"session": "s", "topic": "t", "round": 1})  # no raise


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `py -3 -m unittest test_build -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build'`.

- [ ] **Step 4: 최소 구현**

Create `build.py`:
```python
"""review-report 조립기 — 본문·용어집·배경·의견 이력을 집 스타일 껍데기와 합쳐 out.html을 만든다."""
import json
import sys
from pathlib import Path

REQUIRED_META = ("session", "topic", "round")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_meta(meta: dict) -> None:
    missing = [k for k in REQUIRED_META if k not in meta or meta[k] in ("", None)]
    if missing:
        sys.stderr.write("meta.json 필수 필드 누락: " + ", ".join(missing) + "\n")
        sys.exit(1)


def find_project_root(start: Path) -> Path:
    for d in (start, *start.parents):
        if (d / "WIP" / "reviews" / "config.json").exists():
            return d
    sys.stderr.write("프로젝트 루트를 찾지 못함(WIP/reviews/config.json 없음)\n")
    sys.exit(1)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (4 tests).

- [ ] **Step 6: 커밋 (스킬 repo)**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: config/meta 로드·필수 필드 검증"
```

---

## Task 2: 용어집 파싱·병합

**Files:**
- Modify: `build.py`
- Test: `test_build.py`

**Interfaces:**
- Consumes: 없음(문자열만).
- Produces:
  - `parse_glossary(text: str) -> dict[str, str]` — 마크다운 텍스트에서 `- **용어** — 풀이`(정의 목록)와 `| 용어 | 풀이 |`(표) 두 형식을 모두 파싱. 표의 헤더행·구분행(`---`)은 제외.
  - `merge_glossaries(texts: list[str]) -> dict[str, str]` — 순서대로 병합, 같은 용어는 뒤 텍스트가 이김.

- [ ] **Step 1: 실패 테스트 작성** (append to `test_build.py`)

```python
class ParseGlossaryTest(unittest.TestCase):
    def test_definition_list(self):
        text = "- **SoT** — 권위본, 변경은 게이트로만\n- **Interim** — 작업 중 산출물\n"
        g = build.parse_glossary(text)
        self.assertEqual(g["SoT"], "권위본, 변경은 게이트로만")
        self.assertEqual(g["Interim"], "작업 중 산출물")

    def test_table(self):
        text = (
            "| 용어 | 풀이 |\n"
            "|---|---|\n"
            "| verdict | 검토 판정값 |\n"
            "| blocking | 착수 전 반드시 닫아야 하는 지적 |\n"
        )
        g = build.parse_glossary(text)
        self.assertEqual(g["verdict"], "검토 판정값")
        self.assertEqual(g["blocking"], "착수 전 반드시 닫아야 하는 지적")
        self.assertNotIn("용어", g)  # 헤더행 제외
        self.assertNotIn("---", g)   # 구분행 제외

    def test_merge_later_source_wins(self):
        a = "- **SoT** — 초기 풀이\n"
        b = "- **SoT** — 전문화된 풀이\n"
        self.assertEqual(build.merge_glossaries([a, b])["SoT"], "전문화된 풀이")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.ParseGlossaryTest -v`
Expected: FAIL — `AttributeError: module 'build' has no attribute 'parse_glossary'`.

- [ ] **Step 3: 구현** (append to `build.py`)

```python
import re

_DEF_LINE = re.compile(r"^\s*[-*]\s+\*\*(?P<term>[^*]+)\*\*\s*[—\-:]\s*(?P<def>.+?)\s*$")
_TABLE_ROW = re.compile(r"^\s*\|(?P<cells>.+)\|\s*$")


def parse_glossary(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        m = _DEF_LINE.match(line)
        if m:
            out[m.group("term").strip()] = m.group("def").strip()
            continue
        m = _TABLE_ROW.match(line)
        if m:
            cells = [c.strip() for c in m.group("cells").split("|")]
            if len(cells) < 2:
                continue
            term, meaning = cells[0], cells[1]
            if not term or set(term) <= set("-: "):   # 구분행
                continue
            if term in ("용어", "term", "Term"):        # 헤더행
                continue
            out[term] = meaning
    return out


def merge_glossaries(texts: list) -> dict:
    merged = {}
    for t in texts:
        merged.update(parse_glossary(t))
    return merged
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (7 tests).

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: 용어집 정의목록·표 파싱 + 뒤 소스 우선 병합"
```

---

## Task 3: 용어 자동 감싸기

**Files:**
- Modify: `build.py`
- Test: `test_build.py`

**Interfaces:**
- Consumes: `merge_glossaries` 결과 dict.
- Produces:
  - `wrap_terms(body_html: str, glossary: dict) -> tuple[str, int, list[str]]` — 본문 텍스트 노드에서 각 용어의 **첫 등장 한 번**을 `<b-term def="...">용어</b-term>`로 감싼다. `pre·code·script·style·h1~h6·b-term` 안에서는 감싸지 않는다. 반환: `(감싼 HTML, 감싼 개수, 본문에 안 나타난 용어 목록)`. `def` 속성은 HTML escape.

- [ ] **Step 1: 실패 테스트 작성** (append)

```python
class WrapTermsTest(unittest.TestCase):
    def setUp(self):
        self.g = {"SoT": "권위본", "게이트": "사용자 승인 관문"}

    def test_wraps_first_occurrence_only(self):
        html, n, missing = build.wrap_terms("<p>SoT는 SoT다</p>", self.g)
        self.assertEqual(html.count("<b-term"), 1)
        self.assertIn('<b-term def="권위본">SoT</b-term>는 SoT다', html)

    def test_skips_code_and_headings(self):
        html, n, missing = build.wrap_terms(
            "<h2>SoT</h2><p><code>SoT</code> 게이트</p>", self.g)
        self.assertNotIn("<b-term def=\"권위본\">SoT", html)  # h2·code 속 SoT 미감쌈
        self.assertIn('<b-term def="사용자 승인 관문">게이트</b-term>', html)

    def test_does_not_rewrap_existing_bterm(self):
        html, n, missing = build.wrap_terms(
            '<p><b-term def="x">SoT</b-term> SoT</p>', self.g)
        self.assertEqual(html.count("<b-term"), 1)  # 기존 것 유지, 첫 등장 소진

    def test_reports_missing(self):
        html, n, missing = build.wrap_terms("<p>게이트만 있음</p>", self.g)
        self.assertIn("SoT", missing)
        self.assertNotIn("게이트", missing)

    def test_escapes_def_attribute(self):
        html, n, missing = build.wrap_terms("<p>X</p>", {"X": '따옴표"와 <꺾쇠>'})
        self.assertIn("&quot;", html)
        self.assertIn("&lt;", html)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.WrapTermsTest -v`
Expected: FAIL — `AttributeError: ... 'wrap_terms'`.

- [ ] **Step 3: 구현** (append to `build.py`)

```python
import html as _html
from html.parser import HTMLParser

_SUPPRESS_TAGS = {"pre", "code", "script", "style",
                  "h1", "h2", "h3", "h4", "h5", "h6", "b-term"}


class _TermWrapper(HTMLParser):
    def __init__(self, glossary):
        super().__init__(convert_charrefs=False)
        self.glossary = glossary
        self.out = []
        self.suppress = 0
        self.wrapped = set()
        self.count = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SUPPRESS_TAGS:
            self.suppress += 1
        self.out.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.out.append("</%s>" % tag)
        if tag in _SUPPRESS_TAGS and self.suppress > 0:
            self.suppress -= 1

    def handle_data(self, data):
        self.out.append(data if self.suppress > 0 else self._wrap(data))

    def handle_entityref(self, name):
        self.out.append("&%s;" % name)

    def handle_charref(self, name):
        self.out.append("&#%s;" % name)

    def handle_comment(self, data):
        self.out.append("<!--%s-->" % data)

    def _wrap(self, text):
        result, i = [], 0
        while i < len(text):
            best = None
            for term in self.glossary:
                if term in self.wrapped:
                    continue
                idx = text.find(term, i)
                if idx != -1 and (best is None or idx < best[0]
                                  or (idx == best[0] and len(term) > len(best[1]))):
                    best = (idx, term)
            if best is None:
                result.append(text[i:])
                break
            idx, term = best
            result.append(text[i:idx])
            deff = _html.escape(self.glossary[term], quote=True)
            result.append('<b-term def="%s">%s</b-term>' % (deff, term))
            self.wrapped.add(term)
            self.count += 1
            i = idx + len(term)
        return "".join(result)


def wrap_terms(body_html: str, glossary: dict) -> tuple:
    w = _TermWrapper(glossary)
    w.feed(body_html)
    w.close()
    missing = [t for t in glossary if t not in w.wrapped]
    return "".join(w.out), w.count, missing
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (12 tests).

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: 용어 첫 등장 자동 감싸기(코드·제목·기존 b-term 제외)"
```

---

## Task 4: 앵커 수집·대조

**Files:**
- Modify: `build.py`
- Test: `test_build.py`

**Interfaces:**
- Produces:
  - `collect_anchors(body_html: str) -> list[str]` — 최상위 `<section>`의 `data-anchor` 값을 문서 순서로.
  - `diff_anchors(declared: list[str], present: list[str]) -> list[str]` — `declared`(meta.json)에 있으나 `present`(본문)에 없는 앵커 = 고아 경고 대상.

- [ ] **Step 1: 실패 테스트 작성** (append)

```python
class AnchorTest(unittest.TestCase):
    def test_collect_in_order(self):
        body = ('<section data-anchor="SP-3" data-title="a">x</section>'
                '<section data-anchor="D-2" data-title="b">y</section>')
        self.assertEqual(build.collect_anchors(body), ["SP-3", "D-2"])

    def test_diff_finds_missing(self):
        self.assertEqual(build.diff_anchors(["SP-3", "SP-5"], ["SP-3"]), ["SP-5"])

    def test_diff_empty_when_all_present(self):
        self.assertEqual(build.diff_anchors(["SP-3"], ["SP-3", "D-2"]), [])
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.AnchorTest -v`
Expected: FAIL.

- [ ] **Step 3: 구현** (append)

```python
_ANCHOR = re.compile(r'<section\b[^>]*\bdata-anchor="([^"]+)"', re.IGNORECASE)


def collect_anchors(body_html: str) -> list:
    return _ANCHOR.findall(body_html)


def diff_anchors(declared: list, present: list) -> list:
    present_set = set(present)
    return [a for a in declared if a not in present_set]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (15 tests).

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: 섹션 앵커 수집 + meta 대조 고아 탐지"
```

---

## Task 5: 섹션 번호·TOC

**Files:**
- Modify: `build.py`
- Test: `test_build.py`

**Interfaces:**
- Produces:
  - `number_sections(body_html: str) -> tuple[str, str]` — 최상위 `<section>`에 문서 순서로 `id="sec-N"`을 부여하고, 각 섹션 서두에 `<h2 class="rr-ch"><span class="rr-num">N</span> {data-title}</h2>`를 삽입. 반환 `(번호 매긴 본문, TOC HTML)`. TOC는 `<nav class="rr-toc"><ol><li><a href="#sec-N">N. 제목</a></li>...</ol></nav>`. 최상위 section만 대상(중첩 무시).

- [ ] **Step 1: 실패 테스트 작성** (append)

```python
class NumberSectionsTest(unittest.TestCase):
    def test_numbers_and_toc(self):
        body = ('<section data-anchor="SP-3" data-title="재시도 정책">본문1</section>'
                '<section data-anchor="D-2" data-title="재개 신호">본문2</section>')
        numbered, toc = build.number_sections(body)
        self.assertIn('id="sec-1"', numbered)
        self.assertIn('id="sec-2"', numbered)
        self.assertIn("재시도 정책", numbered)
        self.assertIn('<a href="#sec-1">1. 재시도 정책</a>', toc)
        self.assertIn('<a href="#sec-2">2. 재개 신호</a>', toc)

    def test_ignores_nested_section(self):
        body = ('<section data-anchor="A" data-title="바깥">'
                '<section data-anchor="B" data-title="안">x</section></section>')
        numbered, toc = build.number_sections(body)
        self.assertEqual(toc.count("<li>"), 1)  # 최상위만
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.NumberSectionsTest -v`
Expected: FAIL.

- [ ] **Step 3: 구현** (append)

```python
class _SectionNumberer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self.depth = 0          # section 중첩 깊이
        self.n = 0
        self.toc = []

    def handle_starttag(self, tag, attrs):
        if tag == "section":
            self.depth += 1
            if self.depth == 1:
                self.n += 1
                d = dict(attrs)
                title = d.get("data-title", "")
                self.out.append('<section id="sec-%d"%s>' % (
                    self.n, self._attrs_str(attrs)))
                self.out.append(
                    '<h2 class="rr-ch"><span class="rr-num">%d</span> %s</h2>'
                    % (self.n, _html.escape(title)))
                self.toc.append(
                    '<li><a href="#sec-%d">%d. %s</a></li>'
                    % (self.n, self.n, _html.escape(title)))
                return
        self.out.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.out.append("</%s>" % tag)
        if tag == "section" and self.depth > 0:
            self.depth -= 1

    def handle_data(self, data):
        self.out.append(data)

    def handle_entityref(self, name):
        self.out.append("&%s;" % name)

    def handle_charref(self, name):
        self.out.append("&#%s;" % name)

    def handle_comment(self, data):
        self.out.append("<!--%s-->" % data)

    @staticmethod
    def _attrs_str(attrs):
        return "".join(' %s="%s"' % (k, _html.escape(v or "", quote=True))
                       for k, v in attrs)


def number_sections(body_html: str) -> tuple:
    p = _SectionNumberer()
    p.feed(body_html)
    p.close()
    toc = '<nav class="rr-toc"><ol>%s</ol></nav>' % "".join(p.toc)
    return "".join(p.out), toc
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (17 tests).

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: 최상위 섹션 번호·TOC 생성"
```

---

## Task 6: 의견 카드 렌더 + 클립보드 직렬화/역직렬화 + shell.html

**Files:**
- Modify: `build.py`
- Create: `C:/Users/Harriet/.claude/skills/review-report/shell.html`
- Test: `test_build.py`

**Interfaces:**
- Produces (build.py):
  - `KINDS = ("수정요청", "질문", "이견", "승인")`, `RESOLUTIONS = ("반영", "일부 반영", "보류", "다르게 감")`
  - `render_comment_cards(comments: dict, anchor: str) -> str` — `comments["rounds"]`에서 해당 `anchor`에 달린 항목을 라운드별 접힌 카드(`<details class="rr-prev">`)로. 없으면 빈 문자열. `resolution`이 있으면 배지로 표시.
  - `serialize_comments(session: str, slug: str, rnd: int, items: list[dict]) -> str` — §4.3 클립보드 형식 문자열 생성.
  - `parse_clipboard(text: str) -> dict` — 클립보드 형식을 `{"slug","round","items":[{anchor,kind,text}]}`로 역파싱(왕복 대칭).
- shell.html은 아래 자리표시자를 가진다: `{{SESSION}} {{TOPIC}} {{ROUND}} {{SLUG}} {{LEDE}} {{CONTEXT}} {{TOC}} {{BODY}} {{GLOSSARY_TABLE}} {{FOOTER}}`.

- [ ] **Step 1: 실패 테스트 작성** (append)

```python
class CommentCardTest(unittest.TestCase):
    def test_renders_card_for_anchor(self):
        comments = {"rounds": [{"round": 1, "items": [
            {"anchor": "SP-3", "kind": "수정요청", "text": "3회는 많음",
             "resolution": "반영", "note": "2회로 축소"}]}]}
        html = build.render_comment_cards(comments, "SP-3")
        self.assertIn("3회는 많음", html)
        self.assertIn("반영", html)
        self.assertIn("2회로 축소", html)

    def test_empty_when_no_match(self):
        comments = {"rounds": [{"round": 1, "items": [
            {"anchor": "D-2", "kind": "질문", "text": "x"}]}]}
        self.assertEqual(build.render_comment_cards(comments, "SP-3"), "")


class ClipboardRoundtripTest(unittest.TestCase):
    def test_roundtrip(self):
        items = [
            {"anchor": "SP-3", "kind": "수정요청", "text": "2회로 줄이자"},
            {"anchor": "GENERAL", "kind": "승인", "text": "나머지 좋음"},
        ]
        text = build.serialize_comments("phase1 게이트", "sot-gate", 2, items)
        self.assertIn("slug=sot-gate round=2", text)
        parsed = build.parse_clipboard(text)
        self.assertEqual(parsed["slug"], "sot-gate")
        self.assertEqual(parsed["round"], 2)
        self.assertEqual(parsed["items"], items)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.CommentCardTest test_build.ClipboardRoundtripTest -v`
Expected: FAIL.

- [ ] **Step 3: build.py 구현** (append)

```python
KINDS = ("수정요청", "질문", "이견", "승인")
RESOLUTIONS = ("반영", "일부 반영", "보류", "다르게 감")


def render_comment_cards(comments: dict, anchor: str) -> str:
    blocks = []
    for rnd in comments.get("rounds", []):
        items = [it for it in rnd.get("items", []) if it.get("anchor") == anchor]
        if not items:
            continue
        rows = []
        for it in items:
            badge = ""
            if it.get("resolution"):
                note = _html.escape(it.get("note", ""))
                badge = ('<span class="rr-res" data-res="%s">%s</span> %s'
                         % (_html.escape(it["resolution"]),
                            _html.escape(it["resolution"]), note))
            rows.append(
                '<div class="rr-prev-item"><span class="rr-kind">%s</span>'
                '<p>%s</p>%s</div>'
                % (_html.escape(it.get("kind", "")),
                   _html.escape(it.get("text", "")), badge))
        blocks.append(
            '<details class="rr-prev"><summary>Round %d 의견</summary>%s</details>'
            % (rnd.get("round", 0), "".join(rows)))
    return "".join(blocks)


def serialize_comments(session: str, slug: str, rnd: int, items: list) -> str:
    lines = ["### 검토 의견 — %s / Round %d" % (session, rnd),
             "<!--rr:meta slug=%s round=%d-->" % (slug, rnd), ""]
    for it in items:
        lines.append("[%s] %s" % (it["anchor"], it["kind"]))
        lines.append(it["text"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


_META_RE = re.compile(r"<!--rr:meta slug=(?P<slug>\S+) round=(?P<round>\d+)-->")
_ITEM_RE = re.compile(r"^\[(?P<anchor>[^\]]+)\]\s+(?P<kind>\S+)\s*$")


def parse_clipboard(text: str) -> dict:
    m = _META_RE.search(text)
    slug = m.group("slug") if m else None
    rnd = int(m.group("round")) if m else None
    items, cur = [], None
    for line in text.splitlines():
        im = _ITEM_RE.match(line)
        if im:
            if cur:
                cur["text"] = cur["text"].strip()
                items.append(cur)
            cur = {"anchor": im.group("anchor"), "kind": im.group("kind"), "text": ""}
        elif cur is not None and not line.startswith("<!--") and not line.startswith("###"):
            cur["text"] += (line + "\n")
    if cur:
        cur["text"] = cur["text"].strip()
        items.append(cur)
    return {"slug": slug, "round": rnd, "items": items}
```

- [ ] **Step 4: shell.html 작성**

Create `shell.html` (완전한 자체완결 페이지 — 아래 전체를 그대로):
```html
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root{
    --bg:#f6f7f9; --card:#fff; --ink:#1c2530; --muted:#5c6672; --line:#e4e8ee;
    --accent:#2f6fb0; --accent2:#0f8f8f;
    --bad:#c0392b; --good:#1a8f4c; --block:#c47d00;
    --code:#eef1f6; --shadow:0 1px 3px rgba(20,30,50,.06);
    --radius:12px;
    --mono:ui-monospace,SFMono-Regular,"Cascadia Code",Consolas,monospace;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif;
  }
  @media (prefers-color-scheme:dark){
    :root{--bg:#141821;--card:#1c222d;--ink:#e6eaf0;--muted:#9aa4b2;--line:#2b3340;
      --accent:#6fb0e6;--accent2:#3fc4c4;--bad:#e8746a;--good:#4fc27f;--block:#e0a53f;
      --code:#232a36;--shadow:0 1px 3px rgba(0,0,0,.4);}
  }
  :root[data-theme="light"]{--bg:#f6f7f9;--card:#fff;--ink:#1c2530;--muted:#5c6672;
    --line:#e4e8ee;--accent:#2f6fb0;--accent2:#0f8f8f;--bad:#c0392b;--good:#1a8f4c;
    --block:#c47d00;--code:#eef1f6;--shadow:0 1px 3px rgba(20,30,50,.06);}
  :root[data-theme="dark"]{--bg:#141821;--card:#1c222d;--ink:#e6eaf0;--muted:#9aa4b2;
    --line:#2b3340;--accent:#6fb0e6;--accent2:#3fc4c4;--bad:#e8746a;--good:#4fc27f;
    --block:#e0a53f;--code:#232a36;--shadow:0 1px 3px rgba(0,0,0,.4);}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
    line-height:1.7;font-size:15.5px}
  .rr-wrap{max-width:900px;margin:0 auto;padding:0 22px 96px}
  .rr-bar{position:sticky;top:0;z-index:10;display:flex;gap:10px;align-items:center;
    justify-content:flex-end;background:var(--bg);border-bottom:1px solid var(--line);
    padding:10px 22px;margin:0 -22px 0}
  .rr-bar button{font:inherit;cursor:pointer;border:1px solid var(--line);
    background:var(--card);color:var(--ink);border-radius:8px;padding:6px 12px}
  .rr-bar button.primary{background:var(--accent);color:#fff;border-color:transparent}
  .rr-hero{margin-top:26px;padding:26px 28px;border-radius:var(--radius);
    background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;box-shadow:var(--shadow)}
  .rr-eyebrow{font-size:12px;letter-spacing:.08em;text-transform:uppercase;opacity:.85}
  .rr-hero h1{margin:6px 0 10px;font-size:26px;letter-spacing:-.3px}
  .rr-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
  .rr-chip{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.28);
    border-radius:999px;padding:3px 12px;font-size:12.5px}
  .rr-lede{margin:20px 2px;color:var(--muted)}
  .rr-box{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent2);
    border-radius:var(--radius);padding:16px 20px;margin:18px 0;box-shadow:var(--shadow)}
  .rr-toc{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
    padding:14px 20px;margin:18px 0;box-shadow:var(--shadow)}
  .rr-toc ol{margin:6px 0;padding-left:22px} .rr-toc a{color:var(--accent);text-decoration:none}
  section{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
    padding:8px 24px 20px;margin:16px 0;box-shadow:var(--shadow)}
  .rr-ch{display:flex;align-items:baseline;gap:12px;font-size:19px;
    border-bottom:1px solid var(--line);padding-bottom:10px}
  .rr-num{font-family:var(--mono);color:var(--accent);font-size:15px}
  code,.rr-mono{font-family:var(--mono);background:var(--code);border-radius:5px;padding:.1em .35em;font-size:.9em}
  pre{background:var(--code);border-radius:8px;padding:14px 16px;overflow-x:auto}
  pre code{background:none;padding:0}
  table{border-collapse:collapse;width:100%;display:block;overflow-x:auto}
  th,td{border:1px solid var(--line);padding:7px 11px;text-align:left}
  .rr-note,.rr-warn{border-radius:8px;padding:12px 16px;margin:14px 0;border:1px solid}
  .rr-note{background:color-mix(in srgb,var(--accent) 8%,transparent);border-color:var(--accent)}
  .rr-warn{background:color-mix(in srgb,var(--block) 12%,transparent);border-color:var(--block)}
  .rr-panel{border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:14px 0;background:var(--bg)}
  b-term{border-bottom:1px dotted var(--accent);cursor:help}
  b-term::after{content:attr(def);display:none}
  .rr-prev{margin:14px 0;border:1px dashed var(--line);border-radius:8px;padding:4px 12px;background:var(--bg)}
  .rr-prev summary{cursor:pointer;color:var(--muted);font-size:13.5px}
  .rr-prev-item{margin:8px 0} .rr-kind{font-size:12px;font-weight:600;color:var(--accent)}
  .rr-res{font-size:12px;font-weight:600;border-radius:5px;padding:1px 7px}
  .rr-res[data-res="반영"]{background:color-mix(in srgb,var(--good) 18%,transparent);color:var(--good)}
  .rr-res[data-res="일부 반영"]{background:color-mix(in srgb,var(--accent) 18%,transparent);color:var(--accent)}
  .rr-res[data-res="보류"]{background:color-mix(in srgb,var(--block) 18%,transparent);color:var(--block)}
  .rr-res[data-res="다르게 감"]{background:color-mix(in srgb,var(--bad) 18%,transparent);color:var(--bad)}
  .rr-cbtn{font:inherit;cursor:pointer;border:1px solid var(--line);background:var(--bg);
    color:var(--muted);border-radius:6px;padding:2px 10px;font-size:12.5px;float:right}
  .rr-form{margin:12px 0;padding:12px;border:1px solid var(--accent);border-radius:8px;display:none}
  .rr-form.open{display:block}
  .rr-form label{font-size:13px;margin-right:12px} .rr-form textarea{width:100%;min-height:60px;
    font:inherit;margin-top:8px;border:1px solid var(--line);border-radius:6px;padding:8px;
    background:var(--card);color:var(--ink)}
  .rr-foot{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);
    color:var(--muted);font-size:13px}
  .rr-foot .rr-mono{font-size:12px}
  @media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>

<div class="rr-bar">
  <button id="rr-theme">테마</button>
  <button class="primary" id="rr-copy">의견 복사</button>
</div>

<div class="rr-wrap">
  <header class="rr-hero">
    <div class="rr-eyebrow">검토 · 보고</div>
    <h1>{{TOPIC}}</h1>
    <div class="rr-chips">
      <span class="rr-chip">세션: {{SESSION}}</span>
      <span class="rr-chip">Round {{ROUND}}</span>
    </div>
  </header>

  <p class="rr-lede">{{LEDE}}</p>
  <div class="rr-box">{{CONTEXT}}</div>
  {{TOC}}

  <main id="rr-body">{{BODY}}</main>

  <section id="rr-general" data-anchor="GENERAL">
    <h2 class="rr-ch"><span class="rr-num">✱</span> 총평</h2>
    <button class="rr-cbtn" data-anchor="GENERAL">＋ 의견</button>
    <div class="rr-form" data-anchor="GENERAL"></div>
  </section>

  <div class="rr-box">{{GLOSSARY_TABLE}}</div>
  <footer class="rr-foot">{{FOOTER}}</footer>
</div>

<script>
(function(){
  var SLUG="{{SLUG}}", ROUND="{{ROUND}}", SESSION="{{SESSION}}";
  var KEY="rr:"+SLUG+":r"+ROUND;
  var KINDS=["수정요청","질문","이견","승인"];

  function load(){try{return JSON.parse(localStorage.getItem(KEY))||{}}catch(e){return {}}}
  function save(d){localStorage.setItem(KEY,JSON.stringify(d))}

  // 테마 토글: 현재 계산색 반대로 data-theme 고정
  document.getElementById("rr-theme").onclick=function(){
    var r=document.documentElement, cur=r.getAttribute("data-theme");
    if(!cur){cur=matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light";}
    r.setAttribute("data-theme",cur==="dark"?"light":"dark");
  };

  // 각 섹션에 의견 버튼·폼 주입
  function anchorOf(sec){return sec.getAttribute("data-anchor");}
  function buildForm(form,anchor,data){
    var v=data[anchor]||{kind:"수정요청",text:""};
    var radios=KINDS.map(function(k){
      return '<label><input type="radio" name="k-'+anchor+'" value="'+k+'"'+
             (k===v.kind?" checked":"")+'> '+k+'</label>';}).join(" ");
    form.innerHTML=radios+'<textarea placeholder="의견을 적으세요">'+
      (v.text||"").replace(/</g,"&lt;")+'</textarea>';
    var ta=form.querySelector("textarea");
    function persist(){
      var kind=form.querySelector('input[name="k-'+anchor+'"]:checked').value;
      var d=load(); 
      if(ta.value.trim()){d[anchor]={kind:kind,text:ta.value};}else{delete d[anchor];}
      save(d);
    }
    ta.addEventListener("input",persist);
    form.querySelectorAll("input").forEach(function(i){i.addEventListener("change",persist);});
  }
  var data=load();
  document.querySelectorAll("section[data-anchor]").forEach(function(sec){
    var anchor=anchorOf(sec);
    if(!sec.querySelector(".rr-cbtn")){
      var h=sec.querySelector(".rr-ch")||sec.firstChild;
      var btn=document.createElement("button");
      btn.className="rr-cbtn"; btn.textContent="＋ 의견"; btn.setAttribute("data-anchor",anchor);
      var form=document.createElement("div"); form.className="rr-form"; form.setAttribute("data-anchor",anchor);
      sec.insertBefore(btn,sec.children[1]||null); sec.insertBefore(form,btn.nextSibling);
    }
  });
  document.querySelectorAll(".rr-cbtn").forEach(function(btn){
    var anchor=btn.getAttribute("data-anchor");
    var form=btn.parentNode.querySelector('.rr-form[data-anchor="'+anchor+'"]');
    if(form && !form.dataset.built){buildForm(form,anchor,data); form.dataset.built="1";}
    btn.onclick=function(){form.classList.toggle("open");};
  });

  // 클립보드 직렬화 (build.py serialize_comments와 동일 형식)
  document.getElementById("rr-copy").onclick=function(){
    var d=load(), lines=["### 검토 의견 — "+SESSION+" / Round "+ROUND,
      "<!--rr:meta slug="+SLUG+" round="+ROUND+"-->",""];
    Object.keys(d).forEach(function(anchor){
      lines.push("["+anchor+"] "+d[anchor].kind); lines.push(d[anchor].text); lines.push("");
    });
    var text=lines.join("\n").replace(/\n+$/,"")+"\n";
    navigator.clipboard.writeText(text).then(function(){
      var b=document.getElementById("rr-copy"); b.textContent="복사됨 ✓";
      setTimeout(function(){b.textContent="의견 복사";},1500);
    });
  };
})();
</script>
```

- [ ] **Step 5: shell.html 자리표시자 존재 확인 테스트** (append to test_build.py)

```python
class ShellPlaceholderTest(unittest.TestCase):
    def test_all_placeholders_present(self):
        shell = (Path(__file__).parent / "shell.html").read_text(encoding="utf-8")
        for ph in ("{{SESSION}}", "{{TOPIC}}", "{{ROUND}}", "{{SLUG}}", "{{LEDE}}",
                   "{{CONTEXT}}", "{{TOC}}", "{{BODY}}", "{{GLOSSARY_TABLE}}", "{{FOOTER}}"):
            self.assertIn(ph, shell)
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (22 tests).

- [ ] **Step 7: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py shell.html
git commit -q -m "feat: 의견 카드·클립보드 왕복 직렬화 + 집 스타일 shell.html"
```

---

## Task 7: 조립 통합 (build 진입점)

**Files:**
- Modify: `build.py`
- Test: `test_build.py`

**Interfaces:**
- Consumes: Task 1~6의 모든 함수 + `shell.html`.
- Produces:
  - `render_glossary_table(used: dict) -> str` — 본문에 실제 감싼 용어만 `<table>`로.
  - `render_footer(meta: dict) -> str` — `target_files·pr·created` 있으면 표시, 없으면 생략.
  - `build_page(slug_dir: Path) -> dict` — 전체 파이프라인 실행, `out.html` 기록, `{"sections","wrapped","missing","orphans"}` 요약 반환.
  - `main()` — CLI 진입점, 요약 stdout 출력.

- [ ] **Step 1: 실패 테스트 작성** (append)

```python
import tempfile, os


class BuildPageTest(unittest.TestCase):
    def _fixture(self, root):
        rev = Path(root) / "WIP" / "reviews"
        (rev / "sot-gate").mkdir(parents=True)
        (rev / "config.json").write_text(json.dumps({
            "glossary_sources": ["docs/g.md"], "context_file": "WIP/reviews/context.md"
        }), encoding="utf-8")
        (rev / "context.md").write_text("이 프로젝트는 문서 기반 개발 워크플로다.", encoding="utf-8")
        (Path(root) / "docs").mkdir()
        (Path(root) / "docs" / "g.md").write_text("- **SoT** — 권위본\n", encoding="utf-8")
        (rev / "sot-gate" / "meta.json").write_text(json.dumps({
            "session": "phase1 게이트", "topic": "재시도 정책", "round": 1,
            "anchors": ["SP-3", "SP-5"], "created": "2026-07-13"
        }, ensure_ascii=False), encoding="utf-8")
        (rev / "sot-gate" / "body.html").write_text(
            '<section data-anchor="SP-3" data-title="재시도">SoT 기반 재시도</section>',
            encoding="utf-8")
        (rev / "sot-gate" / "comments.json").write_text(
            json.dumps({"rounds": []}), encoding="utf-8")
        return rev / "sot-gate"

    def test_build_writes_out_and_summary(self):
        with tempfile.TemporaryDirectory() as root:
            slug_dir = self._fixture(root)
            summary = build.build_page(slug_dir)
            out = (slug_dir / "out.html").read_text(encoding="utf-8")
            self.assertIn("phase1 게이트", out)      # 세션 히어로
            self.assertIn("재시도 정책", out)          # 주제
            self.assertIn("<b-term", out)             # 용어 감쌈
            self.assertNotIn("{{", out)               # 자리표시자 모두 치환
            self.assertEqual(summary["sections"], 1)
            self.assertIn("SP-5", summary["orphans"])  # body에 없는 앵커
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.BuildPageTest -v`
Expected: FAIL — `'build_page'` 없음.

- [ ] **Step 3: 구현** (append)

```python
def render_glossary_table(used: dict) -> str:
    if not used:
        return "<p>이 페이지에서 풀이한 용어가 없습니다.</p>"
    rows = "".join("<tr><td class=\"rr-mono\">%s</td><td>%s</td></tr>"
                   % (_html.escape(t), _html.escape(d)) for t, d in used.items())
    return "<h3>용어</h3><table><tr><th>용어</th><th>풀이</th></tr>%s</table>" % rows


def render_footer(meta: dict) -> str:
    parts = ["세션: %s" % _html.escape(meta.get("session", ""))]
    if meta.get("target_files"):
        parts.append("대상: " + ", ".join(
            '<span class="rr-mono">%s</span>' % _html.escape(f) for f in meta["target_files"]))
    if meta.get("pr"):
        parts.append("PR " + _html.escape(str(meta["pr"])))
    if meta.get("created"):
        parts.append("생성 " + _html.escape(str(meta["created"])))
    return " · ".join(parts)


def build_page(slug_dir: Path) -> dict:
    slug = slug_dir.name
    root = find_project_root(slug_dir)
    config = load_json(root / "WIP" / "reviews" / "config.json")
    meta = load_json(slug_dir / "meta.json")
    validate_meta(meta)

    body_raw = (slug_dir / "body.html").read_text(encoding="utf-8")
    cpath = slug_dir / "comments.json"
    comments = load_json(cpath) if cpath.exists() else {"rounds": []}

    # 용어집
    texts = []
    for rel in config.get("glossary_sources", []):
        p = root / rel
        if p.exists():
            texts.append(p.read_text(encoding="utf-8"))
    glossary = merge_glossaries(texts)

    # 앵커 대조
    declared = meta.get("anchors", [])
    present = collect_anchors(body_raw)
    orphans = diff_anchors(declared, present)

    # 각 섹션에 이전 라운드 카드 주입(닫는 태그 앞)
    def inject_cards(html_str):
        for anchor in present:
            cards = render_comment_cards(comments, anchor)
            if not cards:
                continue
            needle = 'data-anchor="%s"' % anchor
            i = html_str.find(needle)
            if i == -1:
                continue
            end = html_str.find("</section>", i)
            if end != -1:
                html_str = html_str[:end] + cards + html_str[end:]
        return html_str

    body = inject_cards(body_raw)
    body, wrapped_n, missing = wrap_terms(body, glossary)
    body, toc = number_sections(body)

    used = {t: glossary[t] for t in glossary if t not in missing}
    context_path = root / config.get("context_file", "")
    context_html = (context_path.read_text(encoding="utf-8")
                    if context_path.exists() else "")

    shell = (Path(__file__).parent / "shell.html").read_text(encoding="utf-8")
    repl = {
        "{{SESSION}}": _html.escape(meta["session"]),
        "{{TOPIC}}": _html.escape(meta["topic"]),
        "{{ROUND}}": str(meta["round"]),
        "{{SLUG}}": slug,
        "{{LEDE}}": _html.escape(meta.get("lede", meta["topic"])),
        "{{CONTEXT}}": context_html,
        "{{TOC}}": toc,
        "{{BODY}}": body,
        "{{GLOSSARY_TABLE}}": render_glossary_table(used),
        "{{FOOTER}}": render_footer(meta),
    }
    for k, v in repl.items():
        shell = shell.replace(k, v)
    (slug_dir / "out.html").write_text(shell, encoding="utf-8")

    return {"sections": len(present), "wrapped": wrapped_n,
            "missing": missing, "orphans": orphans}


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("사용법: py -3 build.py WIP/reviews/<slug>\n")
        sys.exit(1)
    slug_dir = Path(sys.argv[1]).resolve()
    s = build_page(slug_dir)
    print("섹션 %d · 용어 %d개 감쌈 · 풀이 없는 용어 %d개"
          % (s["sections"], s["wrapped"], len(s["missing"])))
    if s["orphans"]:
        print("⚠ 소실 앵커(이전 의견 고아): " + ", ".join(s["orphans"]))
    if s["missing"]:
        print("ℹ 본문에 안 나타난 용어: " + ", ".join(s["missing"]))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (23 tests).

- [ ] **Step 5: 스모크 — 실제 CLI 1회 실행**

fixture로 임시 슬러그를 만들 필요 없이, Task 9에서 만들 실데이터로 검증하므로 여기서는 단위 테스트로 충분. 커밋만.

- [ ] **Step 6: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: build_page 통합 파이프라인 + CLI 진입점"
```

---

## Task 8: SKILL.md 작성

**Files:**
- Create: `C:/Users/Harriet/.claude/skills/review-report/SKILL.md`

**Interfaces:** 없음(문서).

- [ ] **Step 1: SKILL.md 작성**

Create `SKILL.md`:
```markdown
---
name: review-report
description: 검토·보고용 해설 HTML을 만들 때 쓴다. Spec·설계·결정사항을 맥락과 용어 풀이가 담긴 자체완결 페이지로 게시하고, 사용자가 그 위에 검토 의견을 달면 회수해 같은 페이지(같은 URL)에 라운드를 올려 반영한다. "해설 HTML로 만들어줘"·"검토용으로 정리해줘"류 단발 요청에도 이 집 스타일을 쓴다.
---

# review-report

검토/보고용 HTML을 라운드 반복으로 게시·수렴한다. 공용(껍데기·조립기)은 이 스킬에 고정되고, 매 라운드 쓰는 것은 본문(`body.html`)뿐이다.

## 언제 쓰나
- Spec·설계·결정사항을 사용자에게 HTML로 보고하고 검토 의견을 받아 여러 번 다듬을 때.
- "해설 HTML"·"검토용 정리" 단발 요청. 이때도 이 스킬의 집 스타일(자립·해설형 + 라이트/다크 토큰)을 쓴다.

## 데이터 위치
- 프로젝트당: `WIP/reviews/config.json`(용어집·배경 경로)·`WIP/reviews/context.md`(배경 원문). 없으면 먼저 만든다.
- 검토 세션당: `WIP/reviews/<slug>/`에 `meta.json`·`body.html`·`comments.json`. `<slug>`는 검토 주제 하나(= 아티팩트 URL 하나 = 라운드 시퀀스 하나). phase 접두 권장(`phase3-git-isolation`).

## 라운드 절차
1. `<slug>/meta.json`(session·topic·round 필수)·`body.html` 작성. `comments.json`은 `{"rounds":[]}`로 시작.
2. 빌드: `py -3 build.py WIP/reviews/<slug>` → `out.html`. 경고(소실 앵커·풀이 없는 용어) 확인.
3. 게시: Artifact 툴로 `out.html` 게시. Round 1은 신규, 반환된 URL을 `meta.json.artifact_url`에 기록. Round 2+는 그 `url`로 재게시 + `label:"Round N"`.
4. 회수: 사용자가 상단 "의견 복사"로 복사→붙여넣기. 또는 claude-in-chrome이 살아 있으면 아티팩트 탭을 열어 `localStorage`의 `rr:<slug>:r<round>` 키를 직접 읽는다.
5. 반영: 회수 의견을 `comments.json`의 해당 라운드에 적재하고 각 항목의 `resolution`(반영/일부 반영/보류/다르게 감)·`note`를 채운다. `body.html` 갱신, `meta.json.round`+1. 2로 돌아간다.

## 본문 문법 (body.html)
- 최상위는 `<section data-anchor="SP-3" data-title="제목">`의 반복. `data-anchor`는 라운드를 넘어 **바꾸지 않는 안정 ID**. 장 번호·TOC는 조립기가 매긴다(본문에 번호 넣지 말 것).
- 용어 풀이: 용어집에 있으면 조립기가 첫 등장을 자동으로 감싼다. 없으면 `<b-term def="풀이">용어</b-term>`로 직접 단다.
- 콜아웃 `<div class="rr-note">`·`<div class="rr-warn">`, 워크드 예제 `<div class="rr-panel">`.
- `meta.json.anchors`에 섹션 앵커를 나열해 둔다(조립기가 대조; 빠지면 이전 의견이 고아가 됨).

## 주의
- `out.html`은 생성물이라 커밋하지 않는다(`.gitignore`).
- Artifact는 외부 통신·웹폰트·CDN을 막으므로 `shell.html`은 자체완결을 유지한다.
- 이 스킬은 HTML 산출물 집 스타일의 단일 소유자다. 스타일을 바꾸려면 `shell.html`을 고친다.
```

- [ ] **Step 2: SKILL.md 형식 확인**

Run: `py -3 -c "import pathlib,sys; t=pathlib.Path('SKILL.md').read_text(encoding='utf-8'); sys.exit(0 if t.startswith('---') and 'name: review-report' in t else 1)"`
Expected: exit 0.

- [ ] **Step 3: 전체 테스트 재실행 (회귀 확인)**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (23 tests).

- [ ] **Step 4: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add SKILL.md
git commit -q -m "docs: SKILL.md 워크플로·트리거·본문 문법"
```

---

## Task 9: AXDT 데이터 스캐폴딩 + 실사용 스모크 + 메모리 이전·삭제

**Files (AXDT worktree):**
- Create: `WIP/reviews/config.json`
- Create: `WIP/reviews/context.md`
- Create: `WIP/reviews/.gitkeep`
- Modify: `.gitignore`
- Delete: `C:/Users/Harriet/.claude/projects/.../memory/html-deliverable-house-style.md`
- Modify: `C:/Users/Harriet/.claude/projects/.../memory/MEMORY.md`

작업 디렉터리: `C:/Users/Harriet/Desktop/SST/AX Strategy/AXDT/.claude/worktrees/review-report-skill`

- [ ] **Step 1: config.json·context.md 작성**

Create `WIP/reviews/config.json`:
```json
{
  "glossary_sources": ["docs/sot/rule/terminology.md"],
  "context_file": "WIP/reviews/context.md"
}
```

Create `WIP/reviews/context.md`:
```markdown
AXDT는 AI 에이전트들이 역할을 나눠 문서(SoT) 기반으로 소프트웨어 개발을 자동 수행하는 워크플로 템플릿이다. 이 페이지는 그 설계·결정사항을 검토용으로 정리한 것으로, 대화 맥락 없이 페이지만으로 읽히도록 배경과 용어 풀이를 함께 싣는다.
```

Create `WIP/reviews/.gitkeep` (빈 파일).

- [ ] **Step 2: .gitignore에 out.html 무시 추가**

`.gitignore` 끝에 추가:
```
# review-report 생성물 (재현 가능)
WIP/reviews/*/out.html
```

- [ ] **Step 3: 실사용 스모크 — 진짜 페이지 1개 빌드**

임시 검토 세션으로 조립기가 실데이터에서 도는지 확인:
```bash
cd "C:/Users/Harriet/Desktop/SST/AX Strategy/AXDT/.claude/worktrees/review-report-skill"
mkdir -p WIP/reviews/smoke
cat > WIP/reviews/smoke/meta.json <<'EOF'
{"session":"스모크","topic":"조립기 실데이터 검증","round":1,"anchors":["A-1"],"created":"2026-07-13"}
EOF
cat > WIP/reviews/smoke/body.html <<'EOF'
<section data-anchor="A-1" data-title="SoT 참조 확인"><p>이 문단의 SoT 용어가 자동으로 감싸져야 한다.</p></section>
EOF
echo '{"rounds":[]}' > WIP/reviews/smoke/comments.json
py -3 "C:/Users/Harriet/.claude/skills/review-report/build.py" WIP/reviews/smoke
```
Expected 출력에 `섹션 1 · 용어 N개 감쌈`. `WIP/reviews/smoke/out.html`에 `<b-term`과 `스모크`(세션명)가 있는지 확인:
```bash
grep -c "b-term" WIP/reviews/smoke/out.html
grep -c "스모크" WIP/reviews/smoke/out.html
```
Expected: 둘 다 1 이상. 확인 후 스모크 삭제:
```bash
rm -rf WIP/reviews/smoke
```

- [ ] **Step 4: 브라우저 수동 검증 (의견 왕복)**

스모크 `out.html`을 임시로 남겨 Artifact로 게시하고, 페이지에서 총평에 "＋ 의견" → 종류 선택 → 텍스트 입력 → "의견 복사"를 눌러 클립보드에 §4.3 형식이 담기는지, 라이트/다크 토글이 되는지 눈으로 확인한다. 확인 후 `parse_clipboard`가 그 텍스트를 되읽는지 대화에서 점검. (자동 테스트는 Task 6에서 이미 왕복 검증됨 — 이 단계는 실브라우저 거동 확인.)

- [ ] **Step 5: 스캐폴딩 커밋 (AXDT 리포)**

```bash
cd "C:/Users/Harriet/Desktop/SST/AX Strategy/AXDT/.claude/worktrees/review-report-skill"
git add WIP/reviews/config.json WIP/reviews/context.md WIP/reviews/.gitkeep .gitignore
git commit -q -m "feat(reviews): review-report 데이터 스캐폴딩 + out.html 무시"
```

- [ ] **Step 6: 메모리 이전·삭제 (스킬 구현 완료 → 진실원 이전 완료)**

집 스타일이 이제 `shell.html`+`SKILL.md`로 코드화됐다. 진실원 이전이 끝났으므로 옛 출처를 제거한다(설계 §9).

```bash
rm "C:/Users/Harriet/.claude/projects/C--Users-Harriet-Desktop-SST-AX-Strategy-AXDT/memory/html-deliverable-house-style.md"
```

그리고 `MEMORY.md`에서 해당 색인 줄(`- [Use Artifact tool ...]` 근처의 house-style 줄이 있으면)을 제거한다. 현재 인덱스에 house-style 줄이 없다면(방금 세션에 추가된 것이면) 확인만 하고 넘어간다. `use-artifact-tool-for-html-deliverables` 메모리 본문에 "집 스타일 표준 구현체는 `~/.claude/skills/review-report/shell.html`" 포인터 한 줄을 추가한다.

- [ ] **Step 7: 스킬 repo 최종 태그**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git tag v1.0
git log --oneline
```
Expected: Task1~8 커밋이 순서대로.

---

## Self-Review 결과

**Spec coverage:**
- §2.1 Artifact 같은 URL 재게시 → Task 8 절차 3.
- §2.2 공용 분리·조립 → Task 6·7.
- §2.3 용어집 참조·2형식 파싱·풀이 없는 용어 카운트 → Task 2·7.
- §2.4 필수 메타 exit 1 → Task 1.
- §2.5 섹션 안정 앵커·대조 → Task 4·7.
- §2.6 의견 종류 태그·GENERAL → Task 6 shell.
- §2.7 localStorage 라운드 스코프 키·클립보드 → Task 6 shell + serialize.
- §2.8 최신 본문 + 이전 처리 카드 → Task 6·7 `render_comment_cards`·`inject_cards`.
- §2.9 집 스타일(구조·토큰 라이트/다크·트리거 확장) → Task 6 shell·Task 8 SKILL.
- §4.1~4.4 데이터 계약 → Task 1·6·7.
- §5 본문 문법 → Task 8 SKILL.
- §6 조립기 절차 8단계 → Task 7 `build_page`.
- §8 테스트 항목 → Task 1~7 각 테스트.
- §9 메모리 이전·삭제 → Task 9 Step 6.

**Placeholder scan:** 코드 스텝은 모두 실제 코드 포함. 자리표시자 `{{...}}`는 shell 치환 토큰(의도).

**Type consistency:** `wrap_terms`는 `(str,int,list)` 반환 — Task 3 정의와 Task 7 소비 일치. `serialize_comments`/`parse_clipboard` 왕복 키(`slug·round·items[anchor,kind,text]`) 일치. `render_comment_cards(comments, anchor)` 시그니처 Task 6 정의 = Task 7 호출 일치.
