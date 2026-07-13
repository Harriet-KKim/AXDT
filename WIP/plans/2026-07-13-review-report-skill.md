# review-report 스킬 구현 계획 (R2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> 이 계획은 설계 R2(`WIP/specs/2026-07-13-review-report-skill-design.md`)를 태스크로 펼친 것이다. R1 계획을 폐기하고 전면 재작성했다.

**Goal:** 검토/보고용 HTML을 라운드 반복으로 게시·수렴하는 개인 스킬 `review-report`를 구현한다 — 조립기(`build.py`)가 본문·용어집·배경·의견 이력을 집 스타일 껍데기(`shell.html`)와 합쳐 자체완결 HTML을 낸다. 의견은 JSON 하나로 왕복하고, 앵커당 다중 의견을 지원하며, 마크업 처리는 문자열 조작이 아니라 HTMLParser 스택으로 한다.

**Architecture:** 공용(껍데기·조립기)은 스킬에 고정하고 매 라운드 바뀌는 것은 본문(`body.html`)뿐이다. 조립기는 `body.html`을 엄격한 fragment로 검증하고, 파서 스택으로 앵커 수집·이전 의견 카드 주입·섹션 번호매김을 수행한 뒤, 알려진 토큰만 1회 치환하는 방식으로 `shell.html`에 조각을 끼워 넣어 `out.html`을 만든다. 에이전트가 그것을 Artifact 툴로 같은 URL에 재게시한다. 의견은 `localStorage`(JS) ↔ 클립보드(JSON) ↔ `comments.json`(Python) 사이를 JSON 하나로 왕복한다. 용어 풀이의 진실원은 프로젝트 문서(`glossary_sources`)이고 조립기는 소비자다.

**Tech Stack:** Python 3 표준 라이브러리만(`html.parser`·`json`·`re`·`html`·`pathlib`·`sys`·`os`), 테스트는 `unittest`, 프론트는 순수 HTML/CSS/JS(웹폰트·CDN·외부 통신 없음).

## Global Constraints

- 스킬 파일은 **`C:/Users/Harriet/.claude/skills/review-report/`** 에 생성한다(개인 스킬, AXDT 리포 밖). 이 디렉터리를 **자체 git 저장소**로 초기화해(Task 1) 태스크별 커밋을 그곳에 남긴다. AXDT 리포에 커밋하는 것은 데이터 스캐폴딩(`WIP/reviews/`)과 `.gitignore` 갱신뿐(Task 11).
- Python 실행은 **`py -3`** 만 쓴다(`python`은 깨진 WindowsApps stub, exit 49).
- 런타임 의존은 **표준 라이브러리만**. 외부 패키지 금지(테스트 프레임워크 포함 — `unittest` 사용).
- `shell.html`은 **자체완결**: 외부 `fetch`/XHR/WebSocket·웹폰트·CDN·원격 이미지 금지(Artifact CSP 차단). 모든 CSS/JS 인라인.
- 문서·주석은 **한국어 평서·간결체**.
- 라이트/다크 **양방향** 지원: `prefers-color-scheme` 기본 + `:root[data-theme]` 오버라이드가 양쪽에서 이긴다.
- 테스트 실행 위치는 스킬 디렉터리, 명령은 **`py -3 -m unittest test_build -v`**.
- 입력 파일은 **`encoding="utf-8-sig"`**(BOM 허용), 출력 파일은 **`encoding="utf-8", newline=""`** 명시.
- Python 콘솔 출력(`print`/`stderr`)은 **ASCII 안전**: 경고는 `[!]`, 정보는 `[i]`. `⚠`·`ℹ` 등 cp949 밖 기호는 콘솔에 쓰지 않는다(HTML 파일 내용에는 제약 없음 — 파일 쓰기는 콘솔 코드페이지와 무관).
- 앵커·카드 주입·섹션 번호매김·용어 감싸기는 **정규식·문자열 `find` 대신 `HTMLParser` 스택**으로 구현한다(중첩·부분일치·주석 내 가짜 태그 오류 방지).
- `build.py`는 스킬 디렉터리에 있고 데이터는 프로젝트에 있으므로, 실행은 항상 **스킬 절대경로**로: `py -3 "C:/Users/Harriet/.claude/skills/review-report/build.py" <subcommand> <slug-dir> ...`.

---

## 파일 구조

```
C:/Users/Harriet/.claude/skills/review-report/   (개인 스킬, 자체 git repo)
  SKILL.md                워크플로·트리거·본문 문법 (Task 10)
  build.py                조립기 진입점 + 순수 함수 (Task 1~9 누적)
  shell.html              집 스타일 껍데기 + 의견 UI + 클립보드 JSON (Task 8)
  test_build.py           unittest (Task 1~9 누적)
  ARTIFACT-CONTRACT.md    Artifact 재게시 거동 실측 기록 (Task 0)
  ARCHIVE-html-deliverable-house-style.md   메모리 백업 사본 (Task 11, 승인 후)

C:/Users/Harriet/Desktop/SST/AX Strategy/AXDT/   (worktree, AXDT 리포)
  .gitignore              `WIP/reviews/*/out.html` 무시 추가 (Task 11)
  WIP/reviews/
    config.json            glossary_sources·context_file (Task 11)
    context.html            배경 박스 원문, 신뢰 HTML (Task 11)
    .gitkeep                빈 reviews 유지 (Task 11)
```

`build.py` 한 파일에 순수 함수(파싱·검증·감싸기·렌더)와 진입점을 함께 둔다. 함수는 파일 IO 없이 문자열/딕셔너리만 다루는 것이 원칙이므로(예외: `load_glossary`·`build_page`·`ingest`는 명시적으로 IO를 한다) `from build import <fn>`로 단위 테스트된다. 진입점 `main()`은 `if __name__ == "__main__"` 가드 뒤에 둬 import가 안전하다.

---

## Task 0: Artifact 계약 실측

이 스킬 전체가 "같은 file_path로 재게시하면 같은 URL에 덮어쓰고 버전 이력이 남는다"는 Artifact 거동에 의존한다(설계 §2.1·§10). 코드를 한 줄도 쓰기 전에, 실제 Artifact 툴로 이 전제를 확인하고 계약을 문서에 고정한다. **이 태스크는 코드 태스크가 아니라 실행 에이전트가 도구로 직접 수행하는 검증 태스크다.**

**Files:**
- Create: `C:/Users/Harriet/.claude/skills/review-report/.probe/probe.html` (임시 실측용, Step 7에서 삭제)
- Create: `C:/Users/Harriet/.claude/skills/review-report/ARTIFACT-CONTRACT.md`

- [ ] **Step 1: 스킬 디렉터리 생성**

```bash
mkdir -p "C:/Users/Harriet/.claude/skills/review-report/.probe"
```

- [ ] **Step 2: 최소 페이지 작성**

Create `.probe/probe.html`:
```html
<title>Artifact 계약 실측</title>
<p>round=1</p>
```

- [ ] **Step 3: 1차 게시**

Artifact 툴 호출(정확한 파라미터로):
```
Artifact({
  file_path: "C:/Users/Harriet/.claude/skills/review-report/.probe/probe.html",
  favicon: "🧪",
  description: "review-report 스킬의 Artifact 재게시 계약 실측용 임시 페이지",
  label: "round-1"
})
```
반환된 URL을 그대로 기록해 둔다(Step 6에서 사용). 브라우저 탭 제목이 "Artifact 계약 실측"(즉 `<title>` 반영)인지, favicon 파라미터 없이 호출하면 거부되는지도 함께 확인한다(가능하면 favicon을 빼고 한 번 더 호출해 에러 메시지를 관찰).

- [ ] **Step 4: 내용 수정 후 같은 file_path로 재게시**

`.probe/probe.html`을 수정:
```html
<title>Artifact 계약 실측</title>
<p>round=2</p>
```

다시 게시(같은 `file_path`, 새 `label`):
```
Artifact({
  file_path: "C:/Users/Harriet/.claude/skills/review-report/.probe/probe.html",
  favicon: "🧪",
  description: "review-report 스킬의 Artifact 재게시 계약 실측용 임시 페이지",
  label: "round-2"
})
```

- [ ] **Step 5: URL 동일성·버전 이력 확인**

Step 3과 Step 4의 반환 URL이 **완전히 동일한지** 비교한다. 동일하지 않다면(별도 URL이 새로 발급됐다면) 설계 §2.1의 핵심 전제가 깨진 것이므로 즉시 중단하고 사용자에게 보고한다(뒤 태스크 전부가 이 전제 위에 있다).
URL이 동일하다면 그 URL을 열어(가능하면 claude-in-chrome으로) "round=2" 내용이 보이는지, 버전 이력에 "round-1"·"round-2" 라벨이 둘 다 남아 이전 버전 열람이 되는지 확인한다.

- [ ] **Step 6: 교차 대화 `url` 업데이트 경로 — 가능한 범위까지 확인**

`Artifact` 툴 스키마의 `url` 파라미터는 "이 대화가 게시하지 않은 아티팩트"를 갱신하는 경로다. 이번 대화에서 발행한 아티팩트이므로 이 경로는 이번 세션만으로는 완전히 검증할 수 없다 — `action: "list"`로 방금 게시한 아티팩트가 목록에 뜨는지, 그 목록의 URL이 Step 3의 URL과 일치하는지까지만 확인하고, "다른 대화에서 `url=` 로 갱신"은 **미검증(추후 실사용 중 첫 발생 시 확인)** 으로 ARTIFACT-CONTRACT.md에 명시한다.

- [ ] **Step 7: 실측 파일 정리**

```bash
rm -rf "C:/Users/Harriet/.claude/skills/review-report/.probe"
```

- [ ] **Step 8: 계약 기록**

Create `C:/Users/Harriet/.claude/skills/review-report/ARTIFACT-CONTRACT.md`:
```markdown
# Artifact 재게시 계약 실측 결과

review-report 스킬은 아래 전제 위에서 동작한다. 각 항목은 Task 0에서 실제 Artifact 툴로 확인했다.

## 확인된 사실
- 같은 `file_path`로 다시 `Artifact()`를 호출하면: (실측한 그대로 기록 — 예: "같은 URL로 재게시되고 버전 이력에 `label`이 남는다" 또는 실제 관찰과 다르면 그 내용)
- `favicon` 파라미터: (필수 여부, 누락 시 에러 메시지)
- `<title>` 태그: (브라우저 탭/게시물 제목에 반영되는지)
- 버전 이력: (이전 버전 열람 가능 여부, `label`이 어떻게 노출되는지)
- `action: "list"`로 방금 게시한 아티팩트 확인: (URL 일치 여부)

## 미검증
- 다른 대화에서 `url=` 파라미터로 이 대화가 게시한 아티팩트를 갱신하는 경로 — 실사용 중 라운드 2 게시 시점(SKILL.md 절차 §7)에 처음 실제로 쓰이므로, 그때 재확인하고 이 문서에 추가한다.

## 이 결과가 뒤 태스크에 미치는 영향
- Task 8(shell.html)의 `<title>{{TOPIC}}</title>` 배치는 위 "`<title>` 태그" 관찰 결과를 전제로 한다. 다르게 관찰됐다면 Task 8 착수 전 shell.html의 title 처리 방식을 이 문서의 관찰에 맞게 조정한다.
- Task 10(SKILL.md)의 라운드 절차(§7: "Round 1은 신규, Round 2+는 그 url로 재게시")는 위 "같은 file_path 재게시" 관찰을 그대로 절차화한 것이다.
```

이 파일의 본문(관찰된 사실)은 Step 3~6에서 실제로 관찰한 내용으로 **반드시 채운다** — 위 템플릿의 괄호 설명을 실제 관찰값으로 대체하는 것이 이 스텝의 산출물이다.

- [ ] **Step 9: 커밋 (스킬 repo)**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git init -q
git add ARTIFACT-CONTRACT.md
git commit -q -m "docs: Artifact 재게시 계약 실측 기록"
```

---

## Task 1: 스캐폴딩 + config/meta 로드·타입 검증

**Files:**
- Create: `C:/Users/Harriet/.claude/skills/review-report/build.py`
- Test: `C:/Users/Harriet/.claude/skills/review-report/test_build.py`

**Interfaces:**
- Produces:
  - `load_json(path: Path) -> dict` — JSON 파일을 `utf-8-sig`로 읽어 로드. 없으면 `FileNotFoundError`.
  - `REQUIRED_META = ("session", "topic", "round", "anchors")`
  - `validate_meta(meta: dict) -> None` — 타입·범위 검증 실패 시 `sys.exit(1)`(stderr에 사유 나열). `session`·`topic`은 비지 않은 문자열, `round`는 1 이상의 정수(`bool`은 정수로 치지 않음), `anchors`는 문자열 리스트, `round >= 2`면 `artifact_url` 필수.
  - `find_project_root(start: Path) -> Path` — `start`에서 위로 올라가며 `WIP/reviews/config.json`을 가진 디렉터리를 찾음, 없으면 `sys.exit(1)`.

- [ ] **Step 1: 스킬 저장소는 Task 0에서 이미 `git init` 됨 — 확인만**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report" && git status
```
Expected: `ARTIFACT-CONTRACT.md`는 커밋됨, 나머지는 없음(clean 또는 untracked 없음).

- [ ] **Step 2: 실패 테스트 작성**

Create `test_build.py`:
```python
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
import build


class LoadJsonTest(unittest.TestCase):
    def test_reads_utf8_bom(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            p.write_bytes(b"\xef\xbb\xbf" + json.dumps({"a": 1}).encode("utf-8"))
            self.assertEqual(build.load_json(p), {"a": 1})

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            build.load_json(Path("__nope__.json"))


class ValidateMetaTest(unittest.TestCase):
    def _exits_1(self, meta):
        with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            build.validate_meta(meta)
        self.assertEqual(cm.exception.code, 1)

    def test_missing_session_exits_1(self):
        self._exits_1({"topic": "t", "round": 1, "anchors": []})

    def test_session_not_str_exits_1(self):
        self._exits_1({"session": 3, "topic": "t", "round": 1, "anchors": []})

    def test_session_empty_exits_1(self):
        self._exits_1({"session": "  ", "topic": "t", "round": 1, "anchors": []})

    def test_missing_topic_exits_1(self):
        self._exits_1({"session": "s", "round": 1, "anchors": []})

    def test_round_not_int_exits_1(self):
        self._exits_1({"session": "s", "topic": "t", "round": "1", "anchors": []})

    def test_round_zero_exits_1(self):
        self._exits_1({"session": "s", "topic": "t", "round": 0, "anchors": []})

    def test_round_bool_exits_1(self):
        self._exits_1({"session": "s", "topic": "t", "round": True, "anchors": []})

    def test_anchors_not_list_exits_1(self):
        self._exits_1({"session": "s", "topic": "t", "round": 1, "anchors": "SP-3"})

    def test_anchors_element_not_str_exits_1(self):
        self._exits_1({"session": "s", "topic": "t", "round": 1, "anchors": [1, 2]})

    def test_round_ge2_without_artifact_url_exits_1(self):
        self._exits_1({"session": "s", "topic": "t", "round": 2, "anchors": []})

    def test_round1_complete_passes(self):
        build.validate_meta({"session": "s", "topic": "t", "round": 1, "anchors": []})

    def test_round2_with_artifact_url_passes(self):
        build.validate_meta({"session": "s", "topic": "t", "round": 2, "anchors": [],
                              "artifact_url": "https://claude.ai/public/artifacts/x"})


class FindProjectRootTest(unittest.TestCase):
    def test_finds_root_with_config(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "WIP" / "reviews").mkdir(parents=True)
            (root / "WIP" / "reviews" / "config.json").write_text("{}", encoding="utf-8")
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            self.assertEqual(build.find_project_root(nested), root)

    def test_not_found_exits_1(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
                build.find_project_root(Path(d))
            self.assertEqual(cm.exception.code, 1)


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

REQUIRED_META = ("session", "topic", "round", "anchors")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_meta(meta: dict) -> None:
    errors = []
    session = meta.get("session")
    if not isinstance(session, str) or not session.strip():
        errors.append("session은 비어 있지 않은 문자열이어야 함")
    topic = meta.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        errors.append("topic은 비어 있지 않은 문자열이어야 함")
    rnd = meta.get("round")
    round_ok = isinstance(rnd, int) and not isinstance(rnd, bool) and rnd >= 1
    if not round_ok:
        errors.append("round는 1 이상의 정수여야 함")
    anchors = meta.get("anchors")
    if not isinstance(anchors, list) or not all(isinstance(a, str) for a in anchors):
        errors.append("anchors는 문자열 리스트여야 함")
    if round_ok and rnd >= 2 and not meta.get("artifact_url"):
        errors.append("round >= 2면 artifact_url이 필수")
    if errors:
        sys.stderr.write("meta.json 검증 실패: " + "; ".join(errors) + "\n")
        sys.exit(1)


def find_project_root(start: Path) -> Path:
    for d in (start, *start.parents):
        if (d / "WIP" / "reviews" / "config.json").exists():
            return d
    sys.stderr.write("프로젝트 루트를 찾지 못함(WIP/reviews/config.json 없음)\n")
    sys.exit(1)


if __name__ == "__main__":
    pass
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (16 tests).

- [ ] **Step 6: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: config/meta 로드 + 타입·범위 검증"
```

---

## Task 2: 용어집 파싱·병합(소스 누락 실패·BOM)

**Files:**
- Modify: `build.py`
- Test: `test_build.py`

**Interfaces:**
- Consumes: 없음(문자열만) / `load_glossary`는 `Path` IO.
- Produces:
  - `parse_glossary(text: str) -> dict[str, str]` — `- **용어** — 풀이`(정의 목록, 구분자 `—`/`-`/`:` 허용)와 `| 용어 | 풀이 |`(표) 두 형식 모두 파싱. 표의 헤더행·구분행(`---`)은 제외.
  - `merge_glossaries(texts: list[str]) -> dict[str, str]` — 순서대로 병합, 같은 용어는 뒤 텍스트가 이김.
  - `class GlossaryError(Exception)` — 용어집 소스 파일을 찾을 수 없을 때.
  - `load_glossary(root: Path, sources: list[str]) -> dict[str, str]` — `root/<rel>` 각각을 `utf-8-sig`로 읽어 병합. **소스 하나라도 없으면 조용히 넘기지 않고 `GlossaryError`.**

- [ ] **Step 1: 실패 테스트 작성** (append to `test_build.py`, `unittest.main()` 앞에 삽입)

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
        self.assertNotIn("용어", g)
        self.assertNotIn("---", g)

    def test_merge_later_source_wins(self):
        a = "- **SoT** — 초기 풀이\n"
        b = "- **SoT** — 전문화된 풀이\n"
        self.assertEqual(build.merge_glossaries([a, b])["SoT"], "전문화된 풀이")

    def test_mixed_formats_in_one_source(self):
        text = "- **SoT** — 권위본\n\n| 용어 | 풀이 |\n|---|---|\n| gate | 관문 |\n"
        g = build.parse_glossary(text)
        self.assertEqual(g["SoT"], "권위본")
        self.assertEqual(g["gate"], "관문")


class LoadGlossaryTest(unittest.TestCase):
    def test_missing_source_raises(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(build.GlossaryError):
                build.load_glossary(root, ["docs/nope.md"])

    def test_reads_bom_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            p = root / "docs" / "g.md"
            p.write_bytes(b"\xef\xbb\xbf" + "- **SoT** — 권위본\n".encode("utf-8"))
            g = build.load_glossary(root, ["docs/g.md"])
            self.assertEqual(g["SoT"], "권위본")

    def test_merges_multiple_sources_in_order(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "a.md").write_text("- **X** — a\n", encoding="utf-8")
            (root / "docs" / "b.md").write_text("- **X** — b\n", encoding="utf-8")
            g = build.load_glossary(root, ["docs/a.md", "docs/b.md"])
            self.assertEqual(g["X"], "b")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.ParseGlossaryTest test_build.LoadGlossaryTest -v`
Expected: FAIL — `AttributeError: module 'build' has no attribute 'parse_glossary'`.

- [ ] **Step 3: 구현** (build.py 상단 import 블록을 아래로 교체, 이후 함수는 파일 끝에 append)

상단 import 교체:
```python
"""review-report 조립기 — 본문·용어집·배경·의견 이력을 집 스타일 껍데기와 합쳐 out.html을 만든다."""
import json
import re
import sys
from pathlib import Path
```

append:
```python
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
            if not term or set(term) <= set("-: "):
                continue
            if term in ("용어", "term", "Term"):
                continue
            out[term] = meaning
    return out


def merge_glossaries(texts: list) -> dict:
    merged = {}
    for t in texts:
        merged.update(parse_glossary(t))
    return merged


class GlossaryError(Exception):
    """용어집 소스 파일을 찾을 수 없을 때."""


def load_glossary(root: Path, sources: list) -> dict:
    texts = []
    missing = []
    for rel in sources:
        p = root / rel
        if not p.exists():
            missing.append(rel)
            continue
        texts.append(p.read_text(encoding="utf-8-sig"))
    if missing:
        raise GlossaryError("용어집 소스 파일을 찾을 수 없음: " + ", ".join(missing))
    return merge_glossaries(texts)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (23 tests).

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: 용어집 정의목록·표 파싱 + 병합 + 소스 누락 시 실패"
```

---

## Task 3: 용어 자동 감싸기(단어 경계·수동 b-term 소진·툴팁 속성)

R1은 정규식 없이 수동 파서였지만 결함이 둘 있었다: (A) `<b-term def="x">SoT</b-term> SoT`에서 뒤 SoT가 재감싸짐, (B) `SoT`가 `SoTware` 안에서 감싸짐. 이 태스크에서 둘 다 고친다: 수동 `<b-term>` 내부 텍스트를 읽어 등장 용어를 `wrapped`에 소진 등록하고, ASCII 전용 용어는 양옆 문자가 영숫자·`_`가 아닐 때만 매치되게 한다(단어 경계). CJK가 섞인 용어는 조사가 바로 붙으므로 경계를 적용하지 않는다.

**Files:**
- Modify: `build.py`
- Test: `test_build.py`

**Interfaces:**
- Consumes: `merge_glossaries`/`load_glossary` 결과 dict.
- Produces:
  - `class FragmentError(Exception)` — body.html의 fragment 마크업이 허용 규칙을 어겼을 때(이 태스크에서는 `<b-term>`에 `def` 속성이 없을 때 발생; Task 4에서 같은 예외를 fragment 구조 위반에도 재사용한다).
  - `_ascii_term(term: str) -> bool` — `all(ord(c) < 128 for c in term)`.
  - `_match_at(text: str, idx: int, term: str) -> bool` — `idx` 위치에서 `term`이 매치되는지, ASCII 용어는 단어 경계까지 확인.
  - `_render_bterm_open(attrs: dict) -> str` — `def` 필수(없으면 `FragmentError`), `tabindex="0"`·`title="{def}"`를 항상 채워 여는 태그 문자열 생성(자동·수동 공통 경로 — 둘 다 툴팁이 실제로 뜨게 하기 위함).
  - `wrap_terms(body_html: str, glossary: dict) -> tuple[str, int, list[str]]` — 본문 텍스트 노드에서 각 용어의 **첫 등장 한 번**을 감싼다. `pre·code·script·style·h1~h6·rr-prevcard`(Task 6에서 도입할 이전 의견 카드 래퍼 — 미리 suppress 목록에 넣어둠) 안에서는 감싸지 않는다. `<b-term>` 내부는 그대로 통과시키되 내부에 등장한 용어집 용어를 모두 `wrapped`에 등록(소진)한다. 반환: `(감싼 HTML, 자동 감싼 개수, 미사용 용어집 용어 목록)`.

- [ ] **Step 1: 실패 테스트 작성** (append to `test_build.py`)

```python
class WrapTermsTest(unittest.TestCase):
    def setUp(self):
        self.g = {"SoT": "권위본", "게이트": "사용자 승인 관문", "gate": "관문(영문)"}

    def test_wraps_first_occurrence_only(self):
        html, n, unused = build.wrap_terms("<p>SoT는 SoT다</p>", self.g)
        self.assertEqual(html.count("<b-term"), 1)
        self.assertIn("SoT</b-term>는 SoT다", html)

    def test_skips_code_and_headings(self):
        html, n, unused = build.wrap_terms(
            "<h2>SoT</h2><p><code>SoT</code> 게이트</p>", self.g)
        self.assertNotIn("<h2><b-term", html)
        self.assertNotIn("<code><b-term", html)
        self.assertIn("게이트</b-term>", html)

    def test_does_not_rewrap_existing_bterm(self):
        html, n, unused = build.wrap_terms(
            '<p><b-term def="x">SoT</b-term> SoT</p>', self.g)
        self.assertEqual(html.count("<b-term"), 1)
        self.assertEqual(n, 0)

    def test_reports_unused_glossary_terms(self):
        html, n, unused = build.wrap_terms("<p>게이트만 있음</p>", self.g)
        self.assertIn("SoT", unused)
        self.assertIn("gate", unused)
        self.assertNotIn("게이트", unused)

    def test_escapes_def_attribute(self):
        html, n, unused = build.wrap_terms("<p>X</p>", {"X": '따옴표"와 <꺾쇠>'})
        self.assertIn("&quot;", html)
        self.assertIn("&lt;", html)

    def test_ascii_word_boundary_skips_substring(self):
        html, n, unused = build.wrap_terms("<p>SoTware는 SoT의 일부다</p>", self.g)
        self.assertNotIn("SoTware</b-term>", html)
        self.assertNotIn('def="권위본">SoT</b-term>ware', html)
        self.assertIn("SoT</b-term>의 일부", html)

    def test_ascii_word_boundary_gate_vs_gateway(self):
        html, n, unused = build.wrap_terms("<p>gateway 뒤에 gate가 있다</p>", self.g)
        self.assertNotIn('def="관문(영문)">gate</b-term>way', html)
        self.assertIn("gate</b-term>가 있다", html)

    def test_cjk_term_no_boundary_check(self):
        html, n, unused = build.wrap_terms("<p>이 게이트는 게이트웨이가 아니다</p>", self.g)
        self.assertEqual(html.count("<b-term"), 1)
        self.assertIn("게이트</b-term>는", html)

    def test_manual_bterm_exhausts_term_prevents_later_autowrap(self):
        html, n, unused = build.wrap_terms(
            '<p><b-term def="수동 풀이">SoT</b-term> 뒤에 나온 SoT는 안 감싸진다</p>', self.g)
        self.assertEqual(html.count("<b-term"), 1)
        self.assertEqual(n, 0)
        self.assertNotIn("SoT", unused)

    def test_manual_bterm_gets_tabindex_and_title(self):
        html, n, unused = build.wrap_terms('<p><b-term def="수동 풀이">XYZ</b-term></p>', {})
        self.assertIn('tabindex="0"', html)
        self.assertIn('title="수동 풀이"', html)

    def test_auto_wrap_gets_tabindex_and_title(self):
        html, n, unused = build.wrap_terms("<p>SoT</p>", self.g)
        self.assertIn('tabindex="0"', html)
        self.assertIn('title="권위본"', html)

    def test_manual_bterm_without_def_raises(self):
        with self.assertRaises(build.FragmentError):
            build.wrap_terms("<p><b-term>SoT</b-term></p>", self.g)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.WrapTermsTest -v`
Expected: FAIL — `AttributeError: ... 'wrap_terms'`.

- [ ] **Step 3: 구현** (build.py 상단 import 블록 교체 + append)

상단 import 교체:
```python
"""review-report 조립기 — 본문·용어집·배경·의견 이력을 집 스타일 껍데기와 합쳐 out.html을 만든다."""
import html as _html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
```

append:
```python
# "rr-prevcard"는 Task 6에서 이전 의견 카드를 감싸는 래퍼 태그다. 카드 주입이 용어 감싸기보다
# 먼저 실행되므로(§6 파이프라인), 이 시점에 미리 suppress 대상에 넣어 카드 내용이 자동 감싸기·
# 소진 대상이 되지 않게 한다.
_SUPPRESS_TAGS = {"pre", "code", "script", "style",
                  "h1", "h2", "h3", "h4", "h5", "h6", "rr-prevcard"}


class FragmentError(Exception):
    """body.html의 fragment 마크업이 허용 규칙을 어겼을 때."""


def _ascii_term(term: str) -> bool:
    return all(ord(c) < 128 for c in term)


def _is_ascii_word(c: str) -> bool:
    # 단어 경계 판정은 ASCII 영숫자·_로 한정한다. str.isalnum()은 유니코드
    # 전체에 True라 한글 조사('SoT는'의 '는')를 경계로 안 봐 매치를 거부하는 버그가 있다.
    return c == "_" or (c.isascii() and c.isalnum())


def _match_at(text: str, idx: int, term: str) -> bool:
    if not text.startswith(term, idx):
        return False
    if _ascii_term(term):
        if idx > 0 and _is_ascii_word(text[idx - 1]):
            return False
        end = idx + len(term)
        if end < len(text) and _is_ascii_word(text[end]):
            return False
    return True


def _render_bterm_open(attrs: dict) -> str:
    deff = attrs.get("def")
    if not deff:
        raise FragmentError('<b-term>에는 def 속성이 필요합니다')
    esc_def = _html.escape(deff, quote=True)
    parts = ['def="%s"' % esc_def, 'tabindex="0"', 'title="%s"' % esc_def]
    for k, v in attrs.items():
        if k in ("def", "tabindex", "title"):
            continue
        parts.append('%s="%s"' % (k, _html.escape(v or "", quote=True)))
    return "<b-term %s>" % " ".join(parts)


class _TermWrapper(HTMLParser):
    def __init__(self, glossary):
        super().__init__(convert_charrefs=False)
        self.glossary = glossary
        self.out = []
        self.suppress = 0
        self.bterm_depth = 0
        self._bterm_buf = []
        self.wrapped = set()
        self.count = 0

    def handle_starttag(self, tag, attrs):
        if tag == "b-term":
            self.bterm_depth += 1
            self._bterm_buf = []
            self.out.append(_render_bterm_open(dict(attrs)))
            return
        if tag in _SUPPRESS_TAGS:
            self.suppress += 1
        self.out.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.out.append("</%s>" % tag)
        if tag == "b-term" and self.bterm_depth > 0:
            self.bterm_depth -= 1
            if self.bterm_depth == 0:
                self._exhaust("".join(self._bterm_buf))
                self._bterm_buf = []
        elif tag in _SUPPRESS_TAGS and self.suppress > 0:
            self.suppress -= 1

    def handle_data(self, data):
        if self.bterm_depth > 0:
            self._bterm_buf.append(data)
            self.out.append(data)
        elif self.suppress > 0:
            self.out.append(data)
        else:
            self.out.append(self._wrap(data))

    def handle_entityref(self, name):
        text = "&%s;" % name
        if self.bterm_depth > 0:
            self._bterm_buf.append(_html.unescape(text))
        self.out.append(text)

    def handle_charref(self, name):
        text = "&#%s;" % name
        if self.bterm_depth > 0:
            self._bterm_buf.append(_html.unescape(text))
        self.out.append(text)

    def handle_comment(self, data):
        self.out.append("<!--%s-->" % data)

    def _exhaust(self, text):
        for term in list(self.glossary):
            if term in self.wrapped:
                continue
            j = text.find(term)
            while j != -1:
                if _match_at(text, j, term):
                    self.wrapped.add(term)
                    break
                j = text.find(term, j + 1)

    def _wrap(self, text):
        result, i = [], 0
        while i < len(text):
            best = None
            for term in self.glossary:
                if term in self.wrapped:
                    continue
                j = text.find(term, i)
                found = None
                while j != -1:
                    if _match_at(text, j, term):
                        found = j
                        break
                    j = text.find(term, j + 1)
                if found is not None and (best is None or found < best[0]
                                          or (found == best[0] and len(term) > len(best[1]))):
                    best = (found, term)
            if best is None:
                result.append(text[i:])
                break
            idx, term = best
            result.append(text[i:idx])
            result.append(_render_bterm_open({"def": self.glossary[term]}))
            result.append(term)
            result.append("</b-term>")
            self.wrapped.add(term)
            self.count += 1
            i = idx + len(term)
        return "".join(result)


def wrap_terms(body_html: str, glossary: dict) -> tuple:
    w = _TermWrapper(glossary)
    w.feed(body_html)
    w.close()
    unused_glossary_terms = [t for t in glossary if t not in w.wrapped]
    return "".join(w.out), w.count, unused_glossary_terms
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (35 tests).

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: 용어 첫 등장 자동 감싸기(단어 경계·수동 b-term 소진·툴팁 속성)"
```

---

## Task 4: fragment 검증 + 앵커 수집(파서 스택)

R1은 `<section\b[^>]*\bdata-anchor="([^"]+)"` 정규식과 `find("</section>")`로 앵커·카드 위치를 찾았다 — 중첩 section·주석 속 가짜 태그·부분일치에 취약하다. 이 태스크는 `HTMLParser`의 section 깊이 스택으로 최상위 section만 인식하고, 위반을 한 곳(`FragmentError`)으로 모은다.

**Files:**
- Modify: `build.py`
- Test: `test_build.py`

**Interfaces:**
- Consumes: `FragmentError`(Task 3에서 정의, 여기서 재사용).
- Produces:
  - `_ANCHOR_RE = re.compile(r"^[A-Za-z0-9_-]+$")`
  - `validate_fragment(body_html: str) -> None` — 최상위에 `<section>` 이외 태그·텍스트(공백 제외) 있으면, `data-anchor`가 정규식 위반이거나 문서 내 중복이면, `data-title` 없으면, 어떤 태그든 `id` 속성이 있으면, DOCTYPE/PI가 있으면, 최상위 section이 하나도 없으면 — 모두 모아 `FragmentError`. 성공 시 아무것도 반환하지 않음(`None`).
  - `collect_anchors(body_html: str) -> list[str]` — 최상위 `<section>`의 `data-anchor` 값을 문서 순서로. (fragment가 이미 유효하다는 전제, 유효하지 않아도 최선의 결과를 낸다 — 에러 발생 여부와 무관하게 동작.)
  - `diff_anchors(declared: list[str], present: list[str]) -> list[str]` — `declared`(meta.json)에 있으나 `present`(본문)에 없는 앵커 = 고아 경고 대상.

- [ ] **Step 1: 실패 테스트 작성** (append to `test_build.py`)

```python
class ValidateFragmentTest(unittest.TestCase):
    def test_valid_passes(self):
        body = ('<section data-anchor="SP-3" data-title="a">x</section>'
                '<section data-anchor="D-2" data-title="b">y</section>')
        build.validate_fragment(body)

    def test_rejects_top_level_text(self):
        body = 'stray<section data-anchor="A" data-title="t">x</section>'
        with self.assertRaises(build.FragmentError):
            build.validate_fragment(body)

    def test_rejects_non_section_top_level_tag(self):
        with self.assertRaises(build.FragmentError):
            build.validate_fragment("<div>x</div>")

    def test_rejects_duplicate_anchor(self):
        body = ('<section data-anchor="A" data-title="t1">x</section>'
                '<section data-anchor="A" data-title="t2">y</section>')
        with self.assertRaises(build.FragmentError):
            build.validate_fragment(body)

    def test_rejects_bad_anchor_format(self):
        body = '<section data-anchor="sp 3!" data-title="t">x</section>'
        with self.assertRaises(build.FragmentError):
            build.validate_fragment(body)

    def test_requires_data_title(self):
        with self.assertRaises(build.FragmentError):
            build.validate_fragment('<section data-anchor="A">x</section>')

    def test_rejects_id_attribute(self):
        body = '<section data-anchor="A" data-title="t" id="sec-1">x</section>'
        with self.assertRaises(build.FragmentError):
            build.validate_fragment(body)

    def test_rejects_doctype(self):
        body = '<!DOCTYPE html><section data-anchor="A" data-title="t">x</section>'
        with self.assertRaises(build.FragmentError):
            build.validate_fragment(body)

    def test_rejects_empty_body(self):
        with self.assertRaises(build.FragmentError):
            build.validate_fragment("")

    def test_allows_nested_section(self):
        body = ('<section data-anchor="A" data-title="바깥">'
                '<section data-anchor="B" data-title="안">x</section></section>')
        build.validate_fragment(body)


class AnchorTest(unittest.TestCase):
    def test_collect_in_order(self):
        body = ('<section data-anchor="SP-3" data-title="a">x</section>'
                '<section data-anchor="D-2" data-title="b">y</section>')
        self.assertEqual(build.collect_anchors(body), ["SP-3", "D-2"])

    def test_collect_ignores_nested_section(self):
        body = ('<section data-anchor="A" data-title="바깥">'
                '<section data-anchor="B" data-title="안">x</section></section>')
        self.assertEqual(build.collect_anchors(body), ["A"])

    def test_diff_finds_missing(self):
        self.assertEqual(build.diff_anchors(["SP-3", "SP-5"], ["SP-3"]), ["SP-5"])

    def test_diff_empty_when_all_present(self):
        self.assertEqual(build.diff_anchors(["SP-3"], ["SP-3", "D-2"]), [])
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.ValidateFragmentTest test_build.AnchorTest -v`
Expected: FAIL — `AttributeError: ... 'validate_fragment'`.

- [ ] **Step 3: 구현** (append to `build.py`)

```python
_ANCHOR_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class _FragmentValidator(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.depth = 0
        self.anchors = []
        self._seen = set()
        self.errors = []

    def handle_decl(self, decl):
        self.errors.append("DOCTYPE/선언은 허용되지 않음: <!%s>" % decl)

    def handle_pi(self, data):
        self.errors.append("처리 명령(PI)은 허용되지 않음: <?%s>" % data)

    def unknown_decl(self, data):
        self.errors.append("알 수 없는 선언은 허용되지 않음: <![%s]>" % data)

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if self.depth == 0:
            if tag != "section":
                self.errors.append("최상위에는 <section>만 허용(발견: <%s>)" % tag)
            else:
                self._check_section(d)
        if "id" in d:
            self.errors.append('id 속성은 금지(조립기가 부여): <%s id="%s">' % (tag, d["id"]))
        if tag == "section":
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag == "section":
            self.depth -= 1

    def handle_endtag(self, tag):
        if tag == "section" and self.depth > 0:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth == 0 and data.strip():
            self.errors.append("최상위 section 밖의 텍스트는 허용되지 않음: %r" % data.strip()[:40])

    def _check_section(self, attrs):
        anchor = attrs.get("data-anchor")
        title = attrs.get("data-title")
        if not anchor or not _ANCHOR_RE.match(anchor):
            self.errors.append("data-anchor는 [A-Za-z0-9_-]+ 형식이어야 함(발견: %r)" % anchor)
        elif anchor in self._seen:
            self.errors.append("중복 앵커: %s" % anchor)
        else:
            self._seen.add(anchor)
            self.anchors.append(anchor)
        if not title:
            self.errors.append("data-title 필수(앵커: %s)" % anchor)


def validate_fragment(body_html: str) -> None:
    v = _FragmentValidator()
    v.feed(body_html)
    v.close()
    if v.depth != 0:
        v.errors.append("닫히지 않은 <section> 있음")
    if not v.anchors:
        v.errors.append("본문 섹션이 최소 1개 필요")
    if v.errors:
        raise FragmentError("; ".join(v.errors))


def collect_anchors(body_html: str) -> list:
    v = _FragmentValidator()
    v.feed(body_html)
    v.close()
    return v.anchors


def diff_anchors(declared: list, present: list) -> list:
    present_set = set(present)
    return [a for a in declared if a not in present_set]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (49 tests).

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: fragment 파서 스택 검증(최상위 section·앵커·id 금지) + 앵커 수집"
```

---

## Task 5: 섹션 번호·TOC(파서 스택)

**Files:**
- Modify: `build.py`
- Test: `test_build.py`

**Interfaces:**
- Consumes: 없음(fragment는 이미 Task 4에서 유효성이 보장된 상태로 들어온다는 전제).
- Produces:
  - `number_sections(body_html: str) -> tuple[str, str]` — 최상위 `<section>`에 문서 순서로 `id="sec-N"`을 부여하고, 각 섹션 서두에 `<h2 class="rr-ch"><span class="rr-num">N</span> {data-title}</h2>`를 삽입. 반환 `(번호 매긴 본문, TOC HTML)`. TOC는 `<nav class="rr-toc"><ol>...</ol></nav>`. 최상위 section만 대상(중첩은 번호·TOC 항목에서 제외, 내용은 그대로 보존).

- [ ] **Step 1: 실패 테스트 작성** (append to `test_build.py`)

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

    def test_ignores_nested_section_for_numbering(self):
        body = ('<section data-anchor="A" data-title="바깥">'
                '<section data-anchor="B" data-title="안">x</section></section>')
        numbered, toc = build.number_sections(body)
        self.assertEqual(toc.count("<li>"), 1)

    def test_preserves_body_content(self):
        body = '<section data-anchor="A" data-title="t"><p>본문 내용 확인</p></section>'
        numbered, toc = build.number_sections(body)
        self.assertIn("본문 내용 확인", numbered)

    def test_escapes_title_in_toc_and_heading(self):
        body = '<section data-anchor="A" data-title="a &amp; b">x</section>'
        numbered, toc = build.number_sections(body)
        self.assertIn("a &amp; b", toc)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.NumberSectionsTest -v`
Expected: FAIL — `AttributeError: ... 'number_sections'`.

- [ ] **Step 3: 구현** (append to `build.py`)

```python
class _SectionNumberer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self.depth = 0
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
Expected: PASS (53 tests).

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: 최상위 섹션 번호·TOC 생성(파서 스택)"
```

---

## Task 6: 이전 의견 카드 렌더 + 파서 스택 주입(GENERAL 포함)

R1은 `html_str.find("</section>", i)`로 카드를 끼워 넣었다 — 중첩 section이 있으면 잘못된 위치(안쪽 section의 닫힘)에 주입된다. 이 태스크는 section 깊이가 1로 돌아오는 정확한 닫힘 지점에만 주입한다(`_CardInjector`). 카드 렌더와 주입은 서로 강하게 결합돼 있어(주입이 렌더를 호출) 한 태스크로 묶는다.

**Files:**
- Modify: `build.py`
- Test: `test_build.py`

**Interfaces:**
- Produces:
  - `KINDS = ("수정요청", "질문", "이견", "승인")`, `RESOLUTIONS = ("반영", "일부 반영", "보류", "다르게 감")`
  - `render_comment_cards(comments: dict, anchor: str) -> str` — `comments["rounds"]`에서 해당 `anchor`에 달린 항목을(한 라운드에 여러 개일 수 있음) 라운드별 접힌 카드(`<details class="rr-prev">`)로 렌더. 없으면 빈 문자열. 있으면 전체를 `<rr-prevcard>...</rr-prevcard>`로 감싼다(Task 3의 감싸기 suppress 대상과 짝을 맞춤). `resolution`이 있으면 배지로 표시. 여러 줄 텍스트는 그대로 보존(렌더 쪽은 escape만, 줄바꿈 표시는 CSS `white-space:pre-wrap`이 Task 8에서 담당).
  - `inject_comment_cards(body_html: str, comments: dict) -> str` — 최상위 section이 깊이 1에서 닫히는 지점(자기 자신의 `</section>` 직전)에만 그 section의 `render_comment_cards` 결과를 삽입. 중첩 section의 닫힘은 무시.

- [ ] **Step 1: 실패 테스트 작성** (append to `test_build.py`)

```python
class RenderCommentCardsTest(unittest.TestCase):
    def test_renders_card_for_anchor(self):
        comments = {"rounds": [{"round": 1, "items": [
            {"anchor": "SP-3", "kind": "수정요청", "text": "3회는 많음",
             "resolution": "반영", "note": "2회로 축소"}]}]}
        html = build.render_comment_cards(comments, "SP-3")
        self.assertIn("3회는 많음", html)
        self.assertIn("반영", html)
        self.assertIn("2회로 축소", html)
        self.assertIn("<rr-prevcard>", html)

    def test_empty_when_no_match(self):
        comments = {"rounds": [{"round": 1, "items": [
            {"anchor": "D-2", "kind": "질문", "text": "x"}]}]}
        self.assertEqual(build.render_comment_cards(comments, "SP-3"), "")

    def test_multiple_items_same_anchor_same_round(self):
        comments = {"rounds": [{"round": 1, "items": [
            {"anchor": "SP-3", "kind": "수정요청", "text": "첫 의견"},
            {"anchor": "SP-3", "kind": "질문", "text": "둘째 의견"}]}]}
        html = build.render_comment_cards(comments, "SP-3")
        self.assertIn("첫 의견", html)
        self.assertIn("둘째 의견", html)
        self.assertIn("(2건)", html)

    def test_preserves_multiline_text_escaped(self):
        comments = {"rounds": [{"round": 1, "items": [
            {"anchor": "SP-3", "kind": "이견", "text": "1줄\n2줄 <script>"}]}]}
        html = build.render_comment_cards(comments, "SP-3")
        self.assertIn("1줄\n2줄", html)
        self.assertNotIn("<script>", html)


class CardInjectionTest(unittest.TestCase):
    def setUp(self):
        self.comments = {"rounds": [{"round": 1, "items": [
            {"anchor": "SP-3", "kind": "수정요청", "text": "고칠 것"}]}]}

    def test_injects_before_closing_tag_of_matching_section(self):
        body = ('<section data-anchor="SP-3" data-title="a">본문A</section>'
                '<section data-anchor="D-2" data-title="b">본문B</section>')
        out = build.inject_comment_cards(body, self.comments)
        first_end = out.find("</section>")
        self.assertLess(out.find("고칠 것"), first_end)
        self.assertNotIn("고칠 것", out[first_end + len("</section>"):])

    def test_nested_section_close_not_treated_as_injection_point(self):
        body = ('<section data-anchor="SP-3" data-title="바깥">'
                '<section data-anchor="INNER" data-title="안">내부</section>'
                '꼬리글</section>')
        out = build.inject_comment_cards(body, self.comments)
        self.assertEqual(out.count("<rr-prevcard>"), 1)
        outer_close = out.rfind("</section>")
        self.assertLess(out.find("<rr-prevcard>"), outer_close)
        self.assertGreater(out.find("<rr-prevcard>"), out.find("꼬리글"))

    def test_no_injection_when_no_comments(self):
        body = '<section data-anchor="Z" data-title="t">x</section>'
        out = build.inject_comment_cards(body, {"rounds": []})
        self.assertNotIn("rr-prevcard", out)

    def test_general_cards_render_independently(self):
        comments = {"rounds": [{"round": 1, "items": [
            {"anchor": "GENERAL", "kind": "승인", "text": "전반적으로 좋음"}]}]}
        html = build.render_comment_cards(comments, "GENERAL")
        self.assertIn("전반적으로 좋음", html)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.RenderCommentCardsTest test_build.CardInjectionTest -v`
Expected: FAIL.

- [ ] **Step 3: 구현** (append to `build.py`)

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
                badge = ('<div class="rr-res-row"><span class="rr-res" data-res="%s">%s</span> %s</div>'
                         % (_html.escape(it["resolution"]), _html.escape(it["resolution"]), note))
            rows.append(
                '<div class="rr-prev-item"><span class="rr-kind">%s</span>'
                '<p class="rr-prev-text">%s</p>%s</div>'
                % (_html.escape(it.get("kind", "")),
                   _html.escape(it.get("text", "")), badge))
        blocks.append(
            '<details class="rr-prev"><summary>Round %d 의견 (%d건)</summary>%s</details>'
            % (rnd.get("round", 0), len(items), "".join(rows)))
    if not blocks:
        return ""
    return "<rr-prevcard>%s</rr-prevcard>" % "".join(blocks)


class _CardInjector(HTMLParser):
    def __init__(self, comments):
        super().__init__(convert_charrefs=False)
        self.comments = comments
        self.out = []
        self.depth = 0
        self.current_anchor = None

    def handle_starttag(self, tag, attrs):
        if tag == "section":
            self.depth += 1
            if self.depth == 1:
                self.current_anchor = dict(attrs).get("data-anchor")
        self.out.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag == "section" and self.depth == 1:
            cards = render_comment_cards(self.comments, self.current_anchor)
            if cards:
                self.out.append(cards)
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


def inject_comment_cards(body_html: str, comments: dict) -> str:
    p = _CardInjector(comments)
    p.feed(body_html)
    p.close()
    return "".join(p.out)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (61 tests).

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: 이전 의견 카드 렌더 + 파서 스택 기반 정확한 위치 주입"
```

---

## Task 7: 의견 JSON 왕복(clipboard) + ingest + comments 검증

R1은 `###`·`[X]`·CRLF 텍스트 형식을 파이썬·JS 양쪽에 손으로 구현했고 왕복에서 손상됐다(실증됨). 이 태스크는 JSON 하나로 대체한다: JS는 `JSON.stringify`, 파이썬은 붙여넣은 텍스트에서 첫 `{`를 찾아 `json.JSONDecoder().raw_decode`로 그 블록만 엄격 파싱한다(앞의 사람용 한 줄은 무시).

**Files:**
- Modify: `build.py`
- Test: `test_build.py`

**Interfaces:**
- Consumes: `KINDS`·`RESOLUTIONS`(Task 6), `_ANCHOR_RE`(Task 4), `load_json`(Task 1).
- Produces:
  - `serialize_comments_json(slug: str, rnd: int, items: list) -> str` — `json.dumps({"slug": slug, "round": rnd, "items": items}, ensure_ascii=False)`.
  - `parse_clipboard(text: str) -> dict` — `text`에서 첫 `{`를 찾아 `json.JSONDecoder().raw_decode`로 그 지점부터 파싱. JSON 블록을 못 찾거나 파싱 실패 시 `sys.exit(1)`.
  - `validate_comments(comments: dict) -> None` — `rounds`가 리스트가 아니거나, 각 라운드의 `round`가 1부터 증가하는 정수가 아니거나(단조 위반), 항목의 `anchor`가 `_ANCHOR_RE` 위반이거나, `kind`가 `KINDS` 밖이거나, `resolution`이 있는데 `RESOLUTIONS` 밖이면 — 모아서 `sys.exit(1)`.
  - `merge_comments(comments: dict, rnd: int, items: list) -> dict` — 해당 `round` 항목이 있으면 `items`를 append, 없으면 새 라운드 엔트리 추가 후 `round` 기준 정렬.
  - `ingest(slug_dir: Path, clipboard_path: Path) -> dict` — `slug_dir/meta.json`을 읽어 클립보드 JSON의 `slug`(=`slug_dir.name`)·`round`(=`meta["round"]`)를 대조(불일치면 `sys.exit(1)`), `comments.json`에 원자적으로 병합(temp 파일 쓰기 후 `os.replace`) 후 검증·반환.

- [ ] **Step 1: 실패 테스트 작성** (append to `test_build.py`, 상단 import에 `import os`, `import tempfile` 이미 있으면 유지 — `os`만 추가)

상단 import 블록 교체(test_build.py):
```python
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
import build
```

append:
```python
class KindsResolutionsTest(unittest.TestCase):
    def test_kinds_and_resolutions_defined(self):
        self.assertEqual(build.KINDS, ("수정요청", "질문", "이견", "승인"))
        self.assertEqual(build.RESOLUTIONS, ("반영", "일부 반영", "보류", "다르게 감"))


class SerializeParseRoundtripTest(unittest.TestCase):
    def test_roundtrip_plain_json(self):
        items = [
            {"anchor": "SP-3", "kind": "수정요청", "text": "3회는 많음.\n2회로 줄이자."},
            {"anchor": "GENERAL", "kind": "승인", "text": "나머지 좋음 [X] 완료 ### 헤딩아님"},
        ]
        text = build.serialize_comments_json("sot-gate", 2, items)
        parsed = build.parse_clipboard(text)
        self.assertEqual(parsed["slug"], "sot-gate")
        self.assertEqual(parsed["round"], 2)
        self.assertEqual(parsed["items"], items)

    def test_roundtrip_with_human_prefix_line(self):
        items = [{"anchor": "SP-3", "kind": "질문", "text": "괄호 [테스트] 포함"}]
        json_block = build.serialize_comments_json("s", 1, items)
        pasted = "검토 의견 — 세션 / Round 1   (아래 JSON을 붙여넣어 주세요)\n" + json_block
        parsed = build.parse_clipboard(pasted)
        self.assertEqual(parsed["items"], items)

    def test_roundtrip_unicode_and_brackets(self):
        items = [{"anchor": "D-2", "kind": "이견", "text": "한글·유니코드 [대괄호] {중괄호} 보존"}]
        text = build.serialize_comments_json("s", 3, items)
        parsed = build.parse_clipboard(text)
        self.assertEqual(parsed["items"], items)

    def test_parse_clipboard_no_json_exits_1(self):
        with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            build.parse_clipboard("여기엔 JSON이 없습니다")
        self.assertEqual(cm.exception.code, 1)

    def test_parse_clipboard_malformed_json_exits_1(self):
        with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            build.parse_clipboard("전문 {broken json")
        self.assertEqual(cm.exception.code, 1)


class ValidateCommentsTest(unittest.TestCase):
    def test_valid_passes(self):
        comments = {"rounds": [
            {"round": 1, "items": [{"anchor": "SP-3", "kind": "수정요청", "text": "x",
                                     "resolution": "반영", "note": "y"}]},
            {"round": 2, "items": [{"anchor": "GENERAL", "kind": "승인", "text": "z"}]},
        ]}
        build.validate_comments(comments)

    def test_unknown_kind_exits_1(self):
        comments = {"rounds": [{"round": 1, "items": [
            {"anchor": "SP-3", "kind": "모름", "text": "x"}]}]}
        with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            build.validate_comments(comments)
        self.assertEqual(cm.exception.code, 1)

    def test_unknown_resolution_exits_1(self):
        comments = {"rounds": [{"round": 1, "items": [
            {"anchor": "SP-3", "kind": "수정요청", "text": "x", "resolution": "몰라요"}]}]}
        with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            build.validate_comments(comments)
        self.assertEqual(cm.exception.code, 1)

    def test_bad_anchor_format_exits_1(self):
        comments = {"rounds": [{"round": 1, "items": [
            {"anchor": "sp 3!", "kind": "질문", "text": "x"}]}]}
        with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            build.validate_comments(comments)
        self.assertEqual(cm.exception.code, 1)

    def test_non_monotonic_round_exits_1(self):
        comments = {"rounds": [{"round": 2, "items": []}, {"round": 1, "items": []}]}
        with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            build.validate_comments(comments)
        self.assertEqual(cm.exception.code, 1)


class IngestTest(unittest.TestCase):
    def _fixture(self, root, round_=2):
        slug_dir = Path(root) / "sot-gate"
        slug_dir.mkdir()
        (slug_dir / "meta.json").write_text(json.dumps(
            {"session": "s", "topic": "t", "round": round_, "anchors": [],
             "artifact_url": "https://x"}), encoding="utf-8")
        (slug_dir / "comments.json").write_text(json.dumps({"rounds": []}), encoding="utf-8")
        return slug_dir

    def test_ingest_merges_into_matching_round(self):
        with tempfile.TemporaryDirectory() as root:
            slug_dir = self._fixture(root, round_=2)
            items = [{"anchor": "SP-3", "kind": "수정요청", "text": "고쳐주세요"}]
            clip = Path(root) / "clip.json"
            clip.write_text(build.serialize_comments_json("sot-gate", 2, items), encoding="utf-8")
            comments = build.ingest(slug_dir, clip)
            self.assertEqual(comments["rounds"][0]["round"], 2)
            self.assertEqual(comments["rounds"][0]["items"], items)
            reloaded = build.load_json(slug_dir / "comments.json")
            self.assertEqual(reloaded, comments)

    def test_ingest_creates_round_entry_if_missing(self):
        with tempfile.TemporaryDirectory() as root:
            slug_dir = self._fixture(root, round_=1)
            items = [{"anchor": "GENERAL", "kind": "승인", "text": "좋음"}]
            clip = Path(root) / "clip.json"
            clip.write_text(build.serialize_comments_json("sot-gate", 1, items), encoding="utf-8")
            comments = build.ingest(slug_dir, clip)
            self.assertEqual(len(comments["rounds"]), 1)

    def test_ingest_slug_mismatch_exits_1(self):
        with tempfile.TemporaryDirectory() as root:
            slug_dir = self._fixture(root)
            clip = Path(root) / "clip.json"
            clip.write_text(build.serialize_comments_json("다른-slug", 2, []), encoding="utf-8")
            with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
                build.ingest(slug_dir, clip)
            self.assertEqual(cm.exception.code, 1)

    def test_ingest_round_mismatch_exits_1(self):
        with tempfile.TemporaryDirectory() as root:
            slug_dir = self._fixture(root, round_=2)
            clip = Path(root) / "clip.json"
            clip.write_text(build.serialize_comments_json("sot-gate", 1, []), encoding="utf-8")
            with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
                build.ingest(slug_dir, clip)
            self.assertEqual(cm.exception.code, 1)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.SerializeParseRoundtripTest test_build.ValidateCommentsTest test_build.IngestTest -v`
Expected: FAIL.

- [ ] **Step 3: 구현** (build.py 상단 import에 `os` 추가 + append)

상단 import 블록 교체:
```python
"""review-report 조립기 — 본문·용어집·배경·의견 이력을 집 스타일 껍데기와 합쳐 out.html을 만든다."""
import html as _html
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
```

append:
```python
def serialize_comments_json(slug: str, rnd: int, items: list) -> str:
    return json.dumps({"slug": slug, "round": rnd, "items": items}, ensure_ascii=False)


def parse_clipboard(text: str) -> dict:
    idx = text.find("{")
    if idx == -1:
        sys.stderr.write("붙여넣은 텍스트에서 JSON 블록을 찾지 못함\n")
        sys.exit(1)
    decoder = json.JSONDecoder()
    try:
        obj, _end = decoder.raw_decode(text[idx:])
    except json.JSONDecodeError as e:
        sys.stderr.write("JSON 파싱 실패: %s\n" % e)
        sys.exit(1)
    return obj


def validate_comments(comments: dict) -> None:
    errors = []
    rounds = comments.get("rounds")
    if not isinstance(rounds, list):
        sys.stderr.write("comments.json 검증 실패: rounds는 리스트여야 함\n")
        sys.exit(1)
    prev_round = 0
    for entry in rounds:
        rnd = entry.get("round")
        if not isinstance(rnd, int) or isinstance(rnd, bool) or rnd <= prev_round:
            errors.append("rounds는 1부터 증가하는 정수여야 함(발견: %r, 이전: %r)" % (rnd, prev_round))
        else:
            prev_round = rnd
        for it in entry.get("items", []):
            anchor = it.get("anchor")
            if not isinstance(anchor, str) or not _ANCHOR_RE.match(anchor):
                errors.append("잘못된 anchor: %r" % anchor)
            if it.get("kind") not in KINDS:
                errors.append("알 수 없는 kind: %r" % it.get("kind"))
            if "resolution" in it and it["resolution"] not in RESOLUTIONS:
                errors.append("알 수 없는 resolution: %r" % it.get("resolution"))
    if errors:
        sys.stderr.write("comments.json 검증 실패: " + "; ".join(errors) + "\n")
        sys.exit(1)


def merge_comments(comments: dict, rnd: int, items: list) -> dict:
    rounds = comments.setdefault("rounds", [])
    for entry in rounds:
        if entry.get("round") == rnd:
            entry.setdefault("items", []).extend(items)
            return comments
    rounds.append({"round": rnd, "items": list(items)})
    rounds.sort(key=lambda e: e.get("round", 0))
    return comments


def ingest(slug_dir: Path, clipboard_path: Path) -> dict:
    meta = load_json(slug_dir / "meta.json")
    text = clipboard_path.read_text(encoding="utf-8-sig")
    payload = parse_clipboard(text)
    if payload.get("slug") != slug_dir.name:
        sys.stderr.write("slug 불일치: clipboard=%r, 대상=%r\n"
                          % (payload.get("slug"), slug_dir.name))
        sys.exit(1)
    if payload.get("round") != meta.get("round"):
        sys.stderr.write("round 불일치: clipboard=%r, meta.json=%r\n"
                          % (payload.get("round"), meta.get("round")))
        sys.exit(1)
    cpath = slug_dir / "comments.json"
    comments = load_json(cpath) if cpath.exists() else {"rounds": []}
    comments = merge_comments(comments, payload["round"], payload.get("items", []))
    validate_comments(comments)
    tmp = cpath.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(comments, ensure_ascii=False, indent=2), encoding="utf-8", newline="")
    os.replace(tmp, cpath)
    return comments
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (76 tests).

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: 의견 JSON 왕복(clipboard) + ingest + comments 검증"
```

---

## Task 8: shell.html(집 스타일·다중 의견 UI·툴팁·JSON 복사·폴백)

**Files:**
- Create: `C:/Users/Harriet/.claude/skills/review-report/shell.html`
- Test: `test_build.py`

**Interfaces:**
- Consumes: `build.KINDS`(Task 6, JS 쪽 `KINDS` 배열과 값이 일치해야 함).
- Produces: 정적 자산. 알려진 토큰 11개: `{{SESSION}} {{TOPIC}} {{ROUND}} {{SLUG}} {{LEDE}} {{CONTEXT}} {{TOC}} {{BODY}} {{GLOSSARY_TABLE}} {{GENERAL_CARDS}} {{FOOTER}}`. Task 9의 `_KNOWN_TOKENS`가 이 11개와 정확히 일치해야 한다.

- [ ] **Step 1: shell.html 작성**

Create `shell.html`:
```html
<title>{{TOPIC}}</title>
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
    padding:10px 22px}
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

  b-term{border-bottom:1px dotted var(--accent);cursor:help;position:relative}
  b-term:focus{outline:2px solid var(--accent);outline-offset:2px}
  b-term:hover::after,b-term:focus::after{
    content:attr(def);position:absolute;left:0;bottom:125%;
    background:var(--ink);color:var(--card);padding:6px 10px;border-radius:6px;
    font-size:12.5px;white-space:pre-wrap;max-width:280px;width:max-content;
    box-shadow:var(--shadow);z-index:20;line-height:1.4}

  rr-prevcard{display:block}
  .rr-prev{margin:14px 0;border:1px dashed var(--line);border-radius:8px;padding:4px 12px;background:var(--bg)}
  .rr-prev summary{cursor:pointer;color:var(--muted);font-size:13.5px}
  .rr-prev-item{margin:8px 0}
  .rr-prev-text{white-space:pre-wrap;margin:4px 0}
  .rr-kind{font-size:12px;font-weight:600;color:var(--accent)}
  .rr-res-row{margin-top:4px}
  .rr-res{font-size:12px;font-weight:600;border-radius:5px;padding:1px 7px}
  .rr-res[data-res="반영"]{background:color-mix(in srgb,var(--good) 18%,transparent);color:var(--good)}
  .rr-res[data-res="일부 반영"]{background:color-mix(in srgb,var(--accent) 18%,transparent);color:var(--accent)}
  .rr-res[data-res="보류"]{background:color-mix(in srgb,var(--block) 18%,transparent);color:var(--block)}
  .rr-res[data-res="다르게 감"]{background:color-mix(in srgb,var(--bad) 18%,transparent);color:var(--bad)}

  .rr-cbox{margin-top:14px;padding-top:10px;border-top:1px dashed var(--line)}
  .rr-items{display:flex;flex-direction:column;gap:8px;margin-bottom:8px}
  .rr-item-row{border:1px solid var(--line);border-radius:8px;padding:8px 12px;background:var(--bg)}
  .rr-item-text{white-space:pre-wrap;margin:4px 0 6px}
  .rr-del{font:inherit;cursor:pointer;border:1px solid var(--line);background:var(--card);
    color:var(--bad);border-radius:6px;padding:2px 10px;font-size:12px}
  .rr-addbtn{font:inherit;cursor:pointer;border:1px solid var(--line);background:var(--bg);
    color:var(--muted);border-radius:6px;padding:3px 12px;font-size:12.5px}
  .rr-add-form{display:none;margin-top:10px;padding:12px;border:1px solid var(--accent);border-radius:8px}
  .rr-add-form.open{display:block}
  .rr-kind-radios{font-size:13px;display:flex;flex-wrap:wrap;gap:10px}
  .rr-add-form textarea{width:100%;min-height:70px;font:inherit;margin-top:8px;
    border:1px solid var(--line);border-radius:6px;padding:8px;background:var(--card);color:var(--ink)}
  .rr-form-actions{margin-top:8px;display:flex;gap:8px}
  .rr-form-actions button{font:inherit;cursor:pointer;border:1px solid var(--line);
    background:var(--card);color:var(--ink);border-radius:6px;padding:5px 14px}
  .rr-form-actions .rr-confirm{background:var(--accent);color:#fff;border-color:transparent}

  .rr-clipbox{margin:22px 0}
  .rr-clipbox label{display:block;font-size:12.5px;color:var(--muted);margin-bottom:6px}
  .rr-clipbox textarea{width:100%;min-height:90px;font-family:var(--mono);font-size:12.5px;
    border:1px solid var(--line);border-radius:8px;padding:10px;background:var(--card);color:var(--ink)}

  .rr-foot{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);
    color:var(--muted);font-size:13px}
  .rr-foot .rr-mono{font-size:12px}
  @media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>

<div id="rr-storage-warn" class="rr-warn" style="display:none">
  로컬 저장소(localStorage)를 사용할 수 없습니다. 의견이 저장되지 않으니 바로 아래 textarea에 직접 적어 복사해 주세요.
</div>

<div class="rr-bar">
  <button id="rr-theme" type="button">테마</button>
  <button class="primary" id="rr-copy" type="button">의견 복사</button>
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
    {{GENERAL_CARDS}}
  </section>

  <div class="rr-box">{{GLOSSARY_TABLE}}</div>

  <div class="rr-clipbox">
    <label for="rr-clip-fallback">클립보드 복사가 안 되면 아래에서 직접 선택해 복사하세요.</label>
    <textarea id="rr-clip-fallback" readonly onfocus="this.select()"></textarea>
  </div>

  <footer class="rr-foot">{{FOOTER}}</footer>
</div>

<script>
(function(){
  var SLUG="{{SLUG}}", ROUND="{{ROUND}}", SESSION="{{SESSION}}";
  var KEY="rr:"+SLUG+":r"+ROUND;
  var KINDS=["수정요청","질문","이견","승인"];
  var storageOk = true;

  function warnStorage(){
    storageOk = false;
    var w = document.getElementById("rr-storage-warn");
    if (w) w.style.display = "block";
  }
  function load(){
    if (!storageOk) return [];
    try {
      var raw = localStorage.getItem(KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) { warnStorage(); return []; }
  }
  function save(items){
    if (!storageOk) return;
    try { localStorage.setItem(KEY, JSON.stringify(items)); }
    catch (e) { warnStorage(); }
  }

  document.getElementById("rr-theme").onclick = function(){
    var r = document.documentElement, cur = r.getAttribute("data-theme");
    if (!cur) cur = matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light";
    r.setAttribute("data-theme", cur === "dark" ? "light" : "dark");
  };

  function esc(s){
    return String(s).replace(/[&<>]/g, function(c){
      return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c];
    });
  }

  function ensureCommentBox(sec){
    var anchor = sec.getAttribute("data-anchor");
    var box = sec.querySelector(":scope > .rr-cbox");
    if (box) return box;
    box = document.createElement("div");
    box.className = "rr-cbox";
    box.setAttribute("data-rr-anchor", anchor);
    box.innerHTML =
      '<div class="rr-items"></div>' +
      '<button type="button" class="rr-addbtn">＋ 의견</button>' +
      '<div class="rr-add-form">' +
      '<div class="rr-kind-radios">' +
      KINDS.map(function(k, i){
        return '<label><input type="radio" name="k-' + anchor + '" value="' + k +
               '"' + (i === 0 ? " checked" : "") + '> ' + k + '</label>';
      }).join(" ") +
      '</div>' +
      '<textarea placeholder="의견을 적으세요"></textarea>' +
      '<div class="rr-form-actions">' +
      '<button type="button" class="rr-confirm">추가</button>' +
      '<button type="button" class="rr-cancel">취소</button>' +
      '</div></div>';
    sec.appendChild(box);
    return box;
  }

  function renderAnchor(box){
    var anchor = box.getAttribute("data-rr-anchor");
    var items = load();
    var list = box.querySelector(".rr-items");
    list.innerHTML = "";
    items.forEach(function(it, idx){
      if (it.anchor !== anchor) return;
      var row = document.createElement("div");
      row.className = "rr-item-row";
      row.innerHTML = '<span class="rr-kind">' + esc(it.kind) + '</span>' +
        '<p class="rr-item-text"></p>' +
        '<button type="button" class="rr-del" data-idx="' + idx + '">삭제</button>';
      row.querySelector(".rr-item-text").textContent = it.text;
      list.appendChild(row);
    });
  }

  function updateFallback(){
    var items = load();
    var payload = {slug: SLUG, round: parseInt(ROUND, 10) || ROUND, items: items};
    var text = "검토 의견 — " + SESSION + " / Round " + ROUND +
      "   (아래 JSON을 붙여넣어 주세요)\n" + JSON.stringify(payload, null, 2);
    var ta = document.getElementById("rr-clip-fallback");
    if (ta) ta.value = text;
    return text;
  }

  function renderAll(){
    document.querySelectorAll(".rr-cbox").forEach(renderAnchor);
    updateFallback();
  }

  document.querySelectorAll("#rr-body section[data-anchor], #rr-general[data-anchor]")
    .forEach(function(sec){ ensureCommentBox(sec); });

  document.addEventListener("click", function(e){
    var t = e.target;
    if (t.classList.contains("rr-addbtn")){
      var form = t.parentNode.querySelector(".rr-add-form");
      form.classList.toggle("open");
    } else if (t.classList.contains("rr-cancel")){
      var box = t.closest(".rr-cbox");
      box.querySelector(".rr-add-form").classList.remove("open");
      box.querySelector("textarea").value = "";
    } else if (t.classList.contains("rr-confirm")){
      var box2 = t.closest(".rr-cbox");
      var anchor = box2.getAttribute("data-rr-anchor");
      var kindInput = box2.querySelector('input[type="radio"]:checked');
      var ta2 = box2.querySelector(".rr-add-form textarea");
      var text = ta2.value.trim();
      if (!text) return;
      var items = load();
      items.push({anchor: anchor, kind: kindInput ? kindInput.value : KINDS[0], text: text});
      save(items);
      ta2.value = "";
      box2.querySelector(".rr-add-form").classList.remove("open");
      renderAll();
    } else if (t.classList.contains("rr-del")){
      var idx = parseInt(t.getAttribute("data-idx"), 10);
      var items2 = load();
      items2.splice(idx, 1);
      save(items2);
      renderAll();
    }
  });

  document.getElementById("rr-copy").onclick = function(){
    var text = updateFallback();
    var btn = document.getElementById("rr-copy");
    if (navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(function(){
        btn.textContent = "복사됨";
        setTimeout(function(){ btn.textContent = "의견 복사"; }, 1500);
      }).catch(function(){
        btn.textContent = "복사 실패 — 아래에서 직접 복사";
        setTimeout(function(){ btn.textContent = "의견 복사"; }, 2000);
      });
    } else {
      btn.textContent = "아래에서 직접 복사";
      setTimeout(function(){ btn.textContent = "의견 복사"; }, 2000);
    }
  };

  renderAll();
})();
</script>
```

- [ ] **Step 2: shell.html 구조 확인 테스트 작성** (append to `test_build.py`)

```python
class ShellHtmlTest(unittest.TestCase):
    def setUp(self):
        self.shell = (Path(__file__).parent / "shell.html").read_text(encoding="utf-8")

    def test_all_known_tokens_present(self):
        for ph in ("{{SESSION}}", "{{TOPIC}}", "{{ROUND}}", "{{SLUG}}", "{{LEDE}}",
                   "{{CONTEXT}}", "{{TOC}}", "{{BODY}}", "{{GLOSSARY_TABLE}}",
                   "{{GENERAL_CARDS}}", "{{FOOTER}}"):
            self.assertIn(ph, self.shell)

    def test_light_dark_tokens_present(self):
        self.assertIn("prefers-color-scheme:dark", self.shell.replace(" ", ""))
        self.assertIn('data-theme="dark"', self.shell)
        self.assertIn('data-theme="light"', self.shell)

    def test_clipboard_fallback_textarea_present(self):
        self.assertIn('id="rr-clip-fallback"', self.shell)
        self.assertIn("readonly", self.shell)

    def test_storage_warning_element_present(self):
        self.assertIn('id="rr-storage-warn"', self.shell)

    def test_kinds_match_python_constants(self):
        for k in build.KINDS:
            self.assertIn(k, self.shell)

    def test_bterm_hover_focus_tooltip_css_present(self):
        self.assertIn("b-term:hover::after", self.shell.replace(" ", ""))
        self.assertIn("b-term:focus::after", self.shell.replace(" ", ""))

    def test_no_external_script_or_css_references(self):
        self.assertNotIn("http://", self.shell)
        self.assertNotIn("https://", self.shell)
        self.assertNotIn("cdn.", self.shell)
```

- [ ] **Step 3: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (83 tests).

- [ ] **Step 4: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add shell.html test_build.py
git commit -q -m "feat: shell.html 집 스타일 + 다중 의견 UI + 툴팁 + JSON 복사/폴백"
```

---

## Task 9: build 통합(토큰 1회 치환·외부 리소스 검사·용어표·푸터·ASCII 로그·CLI)

R1의 치환은 `.replace()`를 토큰마다 순차 호출했다 — 먼저 삽입된 조각(예: 본문) 안에 우연히 `"{{FOOTER}}"` 같은 문자열이 있으면 나중 치환이 그것까지 덮어써 버린다. `re.sub`에 콜백을 주면 **원본 텍스트 한 번의 스캔**으로 모든 치환이 끝나고, 콜백이 반환한 삽입 내용은 다시 스캔되지 않는다 — 이것이 "1회 치환"의 정확한 메커니즘이다.

**Files:**
- Modify: `build.py`
- Test: `test_build.py`

**Interfaces:**
- Consumes: Task 1~8의 모든 함수 + `shell.html`.
- Produces:
  - `_KNOWN_TOKENS`(11개, Task 8 shell.html과 정확히 일치), `class TemplateError(Exception)`, `render_shell(shell_html: str, values: dict) -> str`.
  - `class SelfContainmentError(Exception)`, `check_self_contained(html_str: str) -> None`.
  - `collect_bterms(html_str: str) -> dict[str, str]` — 최종 조립된 본문에서 자동·수동 `<b-term def="...">텍스트</b-term>`를 모두 수집(용어표는 여기서 나온다 — 용어집 dict의 부분집합이 아니라 실제 산출물에서 역수집).
  - `render_glossary_table(used: dict) -> str`, `render_footer(meta: dict) -> str`.
  - `build_page(slug_dir: Path) -> dict` — 전체 파이프라인 실행, `out.html` 기록, `{"sections","wrapped","unused_glossary_terms","orphans"}` 반환.
  - `main()` — CLI 진입점(`build`/`ingest` 하위명령), 요약 stdout 출력(ASCII 안전).

- [ ] **Step 1: 실패 테스트 작성** (append to `test_build.py`, 상단 import에 `redirect_stdout` 추가)

상단 import 블록 교체(test_build.py):
```python
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import build
```

append:
```python
class RenderShellTest(unittest.TestCase):
    def _values(self, **override):
        base = {"SESSION": "", "TOPIC": "", "ROUND": "", "SLUG": "", "LEDE": "",
                "CONTEXT": "", "TOC": "", "BODY": "", "GLOSSARY_TABLE": "",
                "GENERAL_CARDS": "", "FOOTER": ""}
        base.update(override)
        return base

    def test_known_tokens_replaced_once(self):
        template = "<p>{{BODY}}</p><footer>{{FOOTER}}</footer>"
        out = build.render_shell(template, self._values(BODY="본문", FOOTER="푸터"))
        self.assertEqual(out, "<p>본문</p><footer>푸터</footer>")

    def test_unrelated_double_brace_left_untouched(self):
        template = "{{BODY}}"
        out = build.render_shell(template, self._values(BODY="예시 문법은 {{예시}}처럼 씁니다"))
        self.assertIn("{{예시}}", out)

    def test_missing_known_token_value_raises(self):
        template = "{{BODY}}{{FOOTER}}"
        with self.assertRaises(build.TemplateError):
            build.render_shell(template, {"BODY": "x"})

    def test_leftover_known_token_after_reinjection_raises(self):
        template = "{{BODY}}{{FOOTER}}"
        with self.assertRaises(build.TemplateError):
            build.render_shell(template, self._values(BODY="{{FOOTER}}", FOOTER="x"))


class SelfContainedTest(unittest.TestCase):
    def test_flags_remote_src(self):
        with self.assertRaises(build.SelfContainmentError):
            build.check_self_contained('<img src="https://evil.example/x.png">')

    def test_flags_remote_href(self):
        with self.assertRaises(build.SelfContainmentError):
            build.check_self_contained('<link href="//cdn.example.com/a.css">')

    def test_flags_remote_css_url(self):
        with self.assertRaises(build.SelfContainmentError):
            build.check_self_contained('<style>body{background:url("https://x/y.png")}</style>')

    def test_allows_data_uri_relative_and_anchor(self):
        html = ('<img src="data:image/png;base64,AAA=">'
                '<a href="#sec-1">go</a>'
                '<a href="mailto:a@b.com">mail</a>')
        build.check_self_contained(html)


class CollectBTermsTest(unittest.TestCase):
    def test_collects_auto_and_manual(self):
        html = ('<p><b-term def="권위본" tabindex="0" title="권위본">SoT</b-term> 문서.'
                '<b-term def="수동 정의" tabindex="0" title="수동 정의">XYZ</b-term></p>')
        terms = build.collect_bterms(html)
        self.assertEqual(terms["SoT"], "권위본")
        self.assertEqual(terms["XYZ"], "수동 정의")


class RenderGlossaryTableTest(unittest.TestCase):
    def test_empty_message(self):
        self.assertIn("없습니다", build.render_glossary_table({}))

    def test_renders_rows(self):
        html = build.render_glossary_table({"SoT": "권위본"})
        self.assertIn("<table>", html)
        self.assertIn("SoT", html)
        self.assertIn("권위본", html)


class RenderFooterTest(unittest.TestCase):
    def test_minimal_footer(self):
        footer = build.render_footer({"session": "s"})
        self.assertIn("s", footer)
        self.assertNotIn("PR", footer)

    def test_full_footer(self):
        footer = build.render_footer({"session": "s", "target_files": ["a.md"],
                                       "pr": "#12", "created": "2026-07-13"})
        self.assertIn("a.md", footer)
        self.assertIn("#12", footer)
        self.assertIn("2026-07-13", footer)


class BuildPageIntegrationTest(unittest.TestCase):
    def _fixture(self, root):
        rev = Path(root) / "WIP" / "reviews"
        (rev / "sot-gate").mkdir(parents=True)
        (rev / "config.json").write_text(json.dumps({
            "glossary_sources": ["docs/g.md"], "context_file": "WIP/reviews/context.html"
        }), encoding="utf-8")
        (rev / "context.html").write_text(
            "<p>이 프로젝트는 문서 기반 워크플로다.</p>", encoding="utf-8")
        (Path(root) / "docs").mkdir()
        (Path(root) / "docs" / "g.md").write_text("- **SoT** — 권위본\n", encoding="utf-8")
        (rev / "sot-gate" / "meta.json").write_text(json.dumps({
            "session": "phase1 게이트", "topic": "재시도 정책", "round": 1,
            "anchors": ["SP-3", "SP-5"], "created": "2026-07-13"
        }, ensure_ascii=False), encoding="utf-8")
        (rev / "sot-gate" / "body.html").write_text(
            '<section data-anchor="SP-3" data-title="재시도">'
            'SoT 기반 재시도. <b-term def="수동 정의">XYZ</b-term> 개념도 나온다.'
            '</section>', encoding="utf-8")
        (rev / "sot-gate" / "comments.json").write_text(json.dumps({
            "rounds": [{"round": 1, "items": [
                {"anchor": "SP-3", "kind": "수정요청", "text": "3회는 많음",
                 "resolution": "반영", "note": "2회로 축소"}]}]
        }, ensure_ascii=False), encoding="utf-8")
        return rev / "sot-gate"

    def test_build_writes_out_and_summary(self):
        with tempfile.TemporaryDirectory() as root:
            slug_dir = self._fixture(root)
            summary = build.build_page(slug_dir)
            out = (slug_dir / "out.html").read_text(encoding="utf-8")
            self.assertIn("phase1 게이트", out)
            self.assertIn("재시도 정책", out)
            self.assertIn("<b-term", out)
            self.assertIn("XYZ", out)
            self.assertIn("3회는 많음", out)
            self.assertIn("반영", out)
            for token in build._KNOWN_TOKENS:
                self.assertNotIn("{{%s}}" % token, out)
            self.assertEqual(summary["sections"], 1)
            self.assertIn("SP-5", summary["orphans"])
            self.assertEqual(summary["wrapped"], 1)

    def test_missing_glossary_source_exits_1(self):
        with tempfile.TemporaryDirectory() as root:
            slug_dir = self._fixture(root)
            (Path(root) / "WIP" / "reviews" / "config.json").write_text(
                json.dumps({"glossary_sources": ["docs/nope.md"],
                            "context_file": "WIP/reviews/context.html"}), encoding="utf-8")
            with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
                build.build_page(slug_dir)
            self.assertEqual(cm.exception.code, 1)

    def test_fragment_violation_exits_1(self):
        with tempfile.TemporaryDirectory() as root:
            slug_dir = self._fixture(root)
            (slug_dir / "body.html").write_text("stray text no section", encoding="utf-8")
            with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
                build.build_page(slug_dir)
            self.assertEqual(cm.exception.code, 1)


class MainCliTest(unittest.TestCase):
    def test_build_subcommand_runs(self):
        fixture_maker = BuildPageIntegrationTest()
        with tempfile.TemporaryDirectory() as root:
            slug_dir = fixture_maker._fixture(root)
            old_argv = sys.argv
            sys.argv = ["build.py", "build", str(slug_dir)]
            try:
                with redirect_stdout(io.StringIO()) as out:
                    build.main()
            finally:
                sys.argv = old_argv
            self.assertIn("섹션", out.getvalue())

    def test_unknown_subcommand_exits_1(self):
        old_argv = sys.argv
        sys.argv = ["build.py", "nope"]
        try:
            with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
                build.main()
            self.assertEqual(cm.exception.code, 1)
        finally:
            sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `py -3 -m unittest test_build.RenderShellTest test_build.SelfContainedTest test_build.CollectBTermsTest test_build.BuildPageIntegrationTest -v`
Expected: FAIL — `AttributeError: ... 'render_shell'` 등.

- [ ] **Step 3: 구현** (append to `build.py`, 마지막의 `if __name__ == "__main__": pass`는 제거하고 아래 `main()` 정의 뒤의 가드로 교체)

먼저 파일 맨 끝의 `if __name__ == "__main__":\n    pass`를 삭제한다. 그 자리에 아래를 전부 append:

```python
_KNOWN_TOKENS = ("SESSION", "TOPIC", "ROUND", "SLUG", "LEDE", "CONTEXT", "TOC",
                  "BODY", "GLOSSARY_TABLE", "GENERAL_CARDS", "FOOTER")
_TOKEN_RE = re.compile(r"\{\{(\w+)\}\}")


class TemplateError(Exception):
    """shell.html 토큰 치환이 실패했을 때."""


def render_shell(shell_html: str, values: dict) -> str:
    def _sub(m):
        key = m.group(1)
        if key in _KNOWN_TOKENS:
            if key not in values:
                raise TemplateError("값이 채워지지 않은 알려진 토큰: {{%s}}" % key)
            return values[key]
        return m.group(0)

    out = _TOKEN_RE.sub(_sub, shell_html)
    leftover = [t for t in _KNOWN_TOKENS if ("{{%s}}" % t) in out]
    if leftover:
        raise TemplateError("미치환 토큰 남음: " + ", ".join(leftover))
    return out


_REMOTE_ATTR_RE = re.compile(r'\b(?:src|href)\s*=\s*"(?:https?:)?//[^"]*"', re.IGNORECASE)
_REMOTE_CSS_URL_RE = re.compile(r'url\(\s*[\'"]?(?:https?:)?//', re.IGNORECASE)


class SelfContainmentError(Exception):
    """out.html이 외부 리소스를 참조할 때."""


def check_self_contained(html_str: str) -> None:
    hits = [m.group(0) for m in _REMOTE_ATTR_RE.finditer(html_str)]
    hits += [m.group(0) for m in _REMOTE_CSS_URL_RE.finditer(html_str)]
    if hits:
        raise SelfContainmentError("외부 리소스 참조 발견(자체완결 위반): " + "; ".join(hits[:5]))


class _BTermCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.terms = {}
        self._depth = 0
        self._def = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "b-term":
            self._depth += 1
            self._def = dict(attrs).get("def", "")
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "b-term" and self._depth > 0:
            self._depth -= 1
            if self._depth == 0:
                text = "".join(self._buf).strip()
                if text:
                    self.terms[text] = self._def

    def handle_data(self, data):
        if self._depth > 0:
            self._buf.append(data)

    def handle_entityref(self, name):
        if self._depth > 0:
            self._buf.append(_html.unescape("&%s;" % name))

    def handle_charref(self, name):
        if self._depth > 0:
            self._buf.append(_html.unescape("&#%s;" % name))


def collect_bterms(html_str: str) -> dict:
    p = _BTermCollector()
    p.feed(html_str)
    p.close()
    return p.terms


def render_glossary_table(used: dict) -> str:
    if not used:
        return "<p>이 페이지에서 풀이한 용어가 없습니다.</p>"
    rows = "".join('<tr><td class="rr-mono">%s</td><td>%s</td></tr>'
                   % (_html.escape(t), _html.escape(d)) for t, d in used.items())
    return '<h3>용어</h3><table><tr><th>용어</th><th>풀이</th></tr>%s</table>' % rows


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

    body_raw = (slug_dir / "body.html").read_text(encoding="utf-8-sig")
    try:
        validate_fragment(body_raw)
    except FragmentError as e:
        sys.stderr.write("body.html 검증 실패: %s\n" % e)
        sys.exit(1)

    present = collect_anchors(body_raw)
    declared = meta.get("anchors", [])
    orphans = diff_anchors(declared, present)

    try:
        glossary = load_glossary(root, config.get("glossary_sources", []))
    except GlossaryError as e:
        sys.stderr.write("용어집 로드 실패: %s\n" % e)
        sys.exit(1)

    cpath = slug_dir / "comments.json"
    comments = load_json(cpath) if cpath.exists() else {"rounds": []}
    validate_comments(comments)

    body = inject_comment_cards(body_raw, comments)
    try:
        body, wrapped_n, unused_glossary_terms = wrap_terms(body, glossary)
    except FragmentError as e:
        sys.stderr.write("body.html 검증 실패: %s\n" % e)
        sys.exit(1)
    body, toc = number_sections(body)

    context_rel = config.get("context_file")
    context_html = ""
    if context_rel:
        context_path = root / context_rel
        if context_path.exists():
            context_html = context_path.read_text(encoding="utf-8-sig")

    general_cards = render_comment_cards(comments, "GENERAL")
    glossary_table = render_glossary_table(collect_bterms(body))

    shell_path = Path(__file__).parent / "shell.html"
    shell = shell_path.read_text(encoding="utf-8-sig")
    values = {
        "SESSION": _html.escape(meta["session"]),
        "TOPIC": _html.escape(meta["topic"]),
        "ROUND": str(meta["round"]),
        "SLUG": slug,
        "LEDE": _html.escape(meta.get("lede", meta["topic"])),
        "CONTEXT": context_html,
        "TOC": toc,
        "BODY": body,
        "GLOSSARY_TABLE": glossary_table,
        "GENERAL_CARDS": general_cards,
        "FOOTER": render_footer(meta),
    }
    try:
        out_html = render_shell(shell, values)
    except TemplateError as e:
        sys.stderr.write("shell.html 조립 실패: %s\n" % e)
        sys.exit(1)

    try:
        check_self_contained(out_html)
    except SelfContainmentError as e:
        sys.stderr.write("%s\n" % e)
        sys.exit(1)

    (slug_dir / "out.html").write_text(out_html, encoding="utf-8", newline="")

    return {"sections": len(present), "wrapped": wrapped_n,
            "unused_glossary_terms": unused_glossary_terms, "orphans": orphans}


def main():
    argv = sys.argv[1:]
    if len(argv) < 2 or argv[0] not in ("build", "ingest"):
        sys.stderr.write("사용법: py -3 build.py build <slug-dir>\n"
                          "       py -3 build.py ingest <slug-dir> <clipboard-file>\n")
        sys.exit(1)
    cmd = argv[0]
    if cmd == "build":
        if len(argv) != 2:
            sys.stderr.write("사용법: py -3 build.py build <slug-dir>\n")
            sys.exit(1)
        slug_dir = Path(argv[1]).resolve()
        summary = build_page(slug_dir)
        print("섹션 %d개 · 용어 %d개 감쌈 · 미사용 용어집 %d개"
              % (summary["sections"], summary["wrapped"],
                 len(summary["unused_glossary_terms"])))
        if summary["orphans"]:
            print("[!] 소실 앵커(이전 의견 고아): " + ", ".join(summary["orphans"]))
        if summary["unused_glossary_terms"]:
            print("[i] 미사용 용어집 항목: " + ", ".join(summary["unused_glossary_terms"]))
    else:
        if len(argv) != 3:
            sys.stderr.write("사용법: py -3 build.py ingest <slug-dir> <clipboard-file>\n")
            sys.exit(1)
        slug_dir = Path(argv[1]).resolve()
        clipboard_path = Path(argv[2]).resolve()
        comments = ingest(slug_dir, clipboard_path)
        total = sum(len(r.get("items", [])) for r in comments.get("rounds", []))
        print("[i] comments.json 갱신 — 누적 항목 %d개" % total)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (101 tests).

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add build.py test_build.py
git commit -q -m "feat: build_page 통합 파이프라인 + CLI(build/ingest) + 자체완결 검사"
```

---

## Task 10: SKILL.md 작성

**Files:**
- Create: `C:/Users/Harriet/.claude/skills/review-report/SKILL.md`

**Interfaces:** 없음(문서).

- [ ] **Step 1: SKILL.md 작성**

Create `SKILL.md`:
```markdown
---
name: review-report
description: 검토·보고용 해설 HTML을 만들 때 쓴다. Spec·설계·결정사항을 맥락과 용어 풀이가 담긴 자체완결 페이지로 게시하고, 사용자가 그 위에 검토 의견을 달면 회수해 같은 페이지(같은 URL)에 라운드를 올려 반영한다. "해설 HTML로 만들어줘"·"검토용으로 정리해줘"·"보고서 페이지로 만들어줘" 같은 단발 요청에도 이 집 스타일을 쓴다.
---

# review-report

검토/보고용 HTML을 라운드 반복으로 게시·수렴한다. 공용(껍데기·조립기)은 이 스킬에 고정되고, 매 라운드 쓰는 것은 본문(`body.html`)뿐이다. 의견은 `localStorage`(브라우저) ↔ 클립보드(JSON) ↔ `comments.json`(파이썬) 사이를 JSON 하나로 왕복한다.

## 언제 쓰나
- Spec·설계·결정사항을 사용자에게 HTML로 보고하고 검토 의견을 받아 여러 번 다듬을 때.
- "해설 HTML"·"검토용 정리"·"보고 페이지" 단발 요청. 이때도 이 스킬의 집 스타일(자립·해설형 + 라이트/다크 토큰 + 용어 툴팁)을 쓴다.

## 데이터 위치
- 프로젝트당 1회: `WIP/reviews/config.json`(용어집 경로·배경 경로)·`WIP/reviews/context.html`(배경 원문, 신뢰 HTML — 마크다운 렌더 안 함, 그대로 삽입됨). 없으면 먼저 만든다.
- 검토 세션당: `WIP/reviews/<slug>/`에 `meta.json`·`body.html`·`comments.json`. `<slug>`는 검토 주제 하나(= 아티팩트 URL 하나 = 라운드 시퀀스 하나)와 1:1이다. phase 접두 권장(`phase3-git-isolation`).

## 라운드 절차
1. **선행(최초 1회만)**: `WIP/reviews/config.json`·`context.html`이 없으면 만든다.
2. `<slug>/meta.json`(`session`·`topic`·`round`·`anchors` 필수, round=1로 시작)·`body.html` 작성. `comments.json`은 `{"rounds":[]}`로 시작.
3. 빌드:
   ```
   py -3 "C:/Users/Harriet/.claude/skills/review-report/build.py" build WIP/reviews/<slug>
   ```
   → `WIP/reviews/<slug>/out.html`. 출력의 `[!] 소실 앵커`·`[i] 미사용 용어집`을 확인한다.
4. 게시: Artifact 툴로 `out.html`을 게시한다. `<title>`은 shell이 이미 담고 있으므로 `description`·`favicon`만 채운다(favicon은 고정값 사용, 세션마다 새로 고르지 않는다 — 사용자가 탭을 아이콘으로 찾는다). Round 1은 신규 게시, 반환된 URL을 `meta.json.artifact_url`에 기록. Round 2+는 그 `url`로 재게시하고 `label:"Round N"`을 붙인다(재게시 거동은 `ARTIFACT-CONTRACT.md`에 실측 기록됨).
5. 회수: 사용자가 페이지 상단 "의견 복사"를 눌러 클립보드(또는 항상 보이는 폴백 textarea)에 담긴 JSON을 파일로 저장해 전달하면:
   ```
   py -3 "C:/Users/Harriet/.claude/skills/review-report/build.py" ingest WIP/reviews/<slug> <clipboard-file>
   ```
   claude-in-chrome이 살아 있으면 아티팩트 탭을 열어 `localStorage`의 `rr:<slug>:r<round>` 키를 JS로 직접 읽어 같은 형식으로 저장한 뒤 ingest해도 된다.
6. 반영: `comments.json`에 쌓인 항목마다 `resolution`(반영/일부 반영/보류/다르게 감)·`note`를 채운다. `body.html`을 갱신하고, `meta.json.round`를 +1 하고 `artifact_url`을 유지한다. 3으로 돌아간다.

## 본문 문법 (body.html)
- 최상위는 `<section data-anchor="SP-3" data-title="제목">`의 반복뿐이다. 다른 최상위 태그·텍스트는 빌드 오류다.
- `data-anchor`는 `[A-Za-z0-9_-]+`, 문서 내 유일, **라운드를 넘어 바꾸지 않는 안정 ID**. `data-title` 필수. `id` 속성은 쓰지 않는다(조립기가 부여).
- 장 번호·TOC는 조립기가 매긴다(본문에 번호를 직접 넣지 않는다).
- 용어 풀이: 용어집(`glossary_sources`)에 있는 용어는 본문 첫 등장을 조립기가 자동으로 감싼다. 없는 용어는 `<b-term def="풀이">용어</b-term>`로 직접 단다. 자동·수동 모두 hover/focus 툴팁으로 뜨고 하단 용어표에 실린다.
- 콜아웃: `<div class="rr-note">`·`<div class="rr-warn">`. 워크드 예제: `<div class="rr-panel">`.
- 외부 리소스(원격 `src`/`href`/CSS `url()`) 금지 — 조립기가 최종 산출물에서 검사해 위반 시 빌드를 실패시킨다.
- `meta.json.anchors`에 이번 라운드 앵커를 나열해 둔다. 본문에서 빠지면 "소실 앵커"로 경고된다(이전 의견이 고아가 됐다는 뜻).

## 의견 종류·처리 결과
- 의견 종류: 수정요청 · 질문 · 이견 · 승인.
- 처리 결과: 반영 · 일부 반영 · 보류 · 다르게 감.
- 한 섹션(총평 포함, 앵커 `GENERAL`)에 여러 의견을 남길 수 있다(추가식, 덮어쓰기 아님).

## 주의
- `out.html`은 생성물이라 커밋하지 않는다(`.gitignore`).
- Artifact는 외부 통신·웹폰트·CDN을 막으므로 `shell.html`은 항상 자체완결을 유지한다.
- 이 스킬은 HTML 산출물 집 스타일의 단일 소유자다. 스타일을 바꾸려면 `shell.html`을 고친다.
```

- [ ] **Step 2: SKILL.md 형식 확인**

Run: `py -3 -c "import pathlib,sys; t=pathlib.Path('SKILL.md').read_text(encoding='utf-8'); sys.exit(0 if t.startswith('---') and 'name: review-report' in t else 1)"`
Expected: exit 0.

- [ ] **Step 3: 전체 테스트 재실행(회귀 확인)**

Run: `py -3 -m unittest test_build -v`
Expected: PASS (101 tests).

- [ ] **Step 4: 커밋**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add SKILL.md
git commit -q -m "docs: SKILL.md 워크플로·본문 문법·의견 종류"
```

---

## Task 11: AXDT 데이터 스캐폴딩 + 스모크 + 2라운드 acceptance + 메모리 이전·삭제(승인 후)

R1의 스모크는 순서가 모순이었다(삭제 후에 게시/브라우저 확인을 하라고 적혀 있었다). 이 태스크는 순서를 고쳐 **삭제를 맨 마지막**에 둔다. 또한 `grep -c "b-term" out.html`은 CSS 선택자(`b-term:hover::after{...}`)만으로도 걸려 항상 참이 되는 거짓 통과였다 — `<b-term def=` 처럼 실제 여는 태그 패턴으로 바꾼다. 실제 `docs/sot/rule/terminology.md`는 `**용어** = 풀이` 형식(등호)을 쓰는데, Task 2의 파서는 설계 §2.3이 명시한 `—`/`-`/`:` 구분자만 지원한다 — 따라서 이 스모크에서 실제 프로젝트 용어집에 대한 자동 감싸기 개수는 **참고용**으로만 보고, 하드 어서션은 본문에 직접 단 수동 `<b-term>` 하나로 건다(용어집 형식이 나중에 맞춰지기 전까지는 자동 감싸기가 0건이어도 실패로 치지 않는다).

**Files (AXDT worktree):**
- Create: `WIP/reviews/config.json`
- Create: `WIP/reviews/context.html`
- Create: `WIP/reviews/.gitkeep`
- Modify: `.gitignore`
- Delete(승인 후): `C:/Users/Harriet/.claude/projects/C--Users-Harriet-Desktop-SST-AX-Strategy-AXDT/memory/html-deliverable-house-style.md`
- Modify(승인 후): `C:/Users/Harriet/.claude/projects/C--Users-Harriet-Desktop-SST-AX-Strategy-AXDT/memory/MEMORY.md`
- Create(승인 후): `C:/Users/Harriet/.claude/skills/review-report/ARCHIVE-html-deliverable-house-style.md`

작업 디렉터리: `C:/Users/Harriet/Desktop/SST/AX Strategy/AXDT/.claude/worktrees/review-report-skill`

- [ ] **Step 1: config.json·context.html 작성**

Create `WIP/reviews/config.json`:
```json
{
  "glossary_sources": ["docs/sot/rule/terminology.md"],
  "context_file": "WIP/reviews/context.html"
}
```

Create `WIP/reviews/context.html`(신뢰 HTML — 그대로 삽입되므로 완결된 태그만 쓴다):
```html
<p>AXDT는 AI 에이전트들이 역할을 나눠 문서(SoT) 기반으로 소프트웨어 개발을 자동 수행하는 워크플로 템플릿이다. 이 페이지는 그 설계·결정사항을 검토용으로 정리한 것으로, 대화 맥락 없이 페이지만으로 읽히도록 배경과 용어 풀이를 함께 싣는다.</p>
```

Create `WIP/reviews/.gitkeep`(빈 파일).

- [ ] **Step 2: .gitignore에 out.html 무시 추가**

`.gitignore` 끝에 추가:
```
# review-report 생성물 (재현 가능)
WIP/reviews/*/out.html
```

- [ ] **Step 3: 자동 스모크 — 실데이터로 빌드 1회**

```bash
cd "C:/Users/Harriet/Desktop/SST/AX Strategy/AXDT/.claude/worktrees/review-report-skill"
mkdir -p WIP/reviews/smoke
cat > WIP/reviews/smoke/meta.json <<'EOF'
{"session":"스모크","topic":"조립기 실데이터 검증","round":1,"anchors":["A-1"],"created":"2026-07-13"}
EOF
cat > WIP/reviews/smoke/body.html <<'EOF'
<section data-anchor="A-1" data-title="SoT 참조 확인">
<p>이 문단은 <b-term def="권위본, 변경은 게이트로만">SoT</b-term> 개념을 수동으로 단다.
용어집(docs/sot/rule/terminology.md)이 자동으로 감쌀 수도 있는 SoT라는 단어도 함께 둔다.</p>
</section>
EOF
echo '{"rounds":[]}' > WIP/reviews/smoke/comments.json
py -3 "C:/Users/Harriet/.claude/skills/review-report/build.py" build WIP/reviews/smoke
```
Expected 출력에 `섹션 1개`가 있어야 한다. `용어 N개 감쌈`의 N은 참고용(현재 `terminology.md`는 `=` 구분자를 쓰므로 Task 2 파서 기준 0일 수 있다 — 이는 실패가 아니다).

수동 `<b-term>`이 실제로 산출물에 열린 태그로 있는지, 세션명이 실렸는지 확인한다:
```bash
grep -c '<b-term def=' WIP/reviews/smoke/out.html
grep -c "스모크" WIP/reviews/smoke/out.html
```
Expected: 둘 다 1 이상(`<b-term def=`는 CSS 선택자 텍스트와 겹치지 않는 실제 여는 태그 패턴이라 거짓 통과가 없다).

**스모크 폴더는 아직 지우지 않는다 — Step 4의 2라운드 수동 acceptance에 그대로 쓴다.**

- [ ] **Step 4: 2라운드 수동 acceptance — Round 1 게시**

Artifact 툴로 `WIP/reviews/smoke/out.html`을 게시한다:
```
Artifact({
  file_path: "C:/Users/.../WIP/reviews/smoke/out.html",
  favicon: "🔎",
  description: "review-report 2라운드 acceptance 스모크",
  label: "Round 1"
})
```
반환된 URL을 기록하고 `WIP/reviews/smoke/meta.json`의 `artifact_url`에 채운다(아직 커밋하지 않음 — smoke는 최종적으로 삭제됨, 이 값은 이번 acceptance 확인에만 쓴다).

claude-in-chrome으로 그 URL을 연다. 페이지의 "SoT 참조 확인" 섹션에서 "＋ 의견"을 눌러 종류(예: 질문)를 고르고 텍스트를 입력해 "추가"를 누른다. 개발자 도구 없이 자바스크립트로 직접 확인한다(javascript_tool 또는 read_page 사용):
```javascript
localStorage.getItem("rr:smoke:r1")
```
Expected: 방금 추가한 항목이 담긴 JSON 배열 문자열(`anchor:"A-1"` 포함).

"의견 복사" 버튼을 눌러 하단의 항상 보이는 textarea(`#rr-clip-fallback`)에 같은 내용의 JSON이 채워지는지 확인한다. 라이트/다크 토글 버튼도 눌러 `data-theme` 속성이 바뀌는지 확인한다.

- [ ] **Step 5: 2라운드 수동 acceptance — Round 2로 전환·재게시**

```bash
cd "C:/Users/Harriet/Desktop/SST/AX Strategy/AXDT/.claude/worktrees/review-report-skill"
cat > WIP/reviews/smoke/meta.json <<'EOF'
{"session":"스모크","topic":"조립기 실데이터 검증","round":2,"anchors":["A-1"],
 "artifact_url":"<Step 4에서 기록한 URL>","created":"2026-07-13"}
EOF
py -3 "C:/Users/Harriet/.claude/skills/review-report/build.py" build WIP/reviews/smoke
```
다시 Artifact 툴로 게시하되 이번엔 Step 4와 **같은 `file_path`**(또는 확인됐다면 `url`)로, `label:"Round 2"`를 붙인다.

같은 URL을 새로고침해서 열고 자바스크립트로 확인한다:
```javascript
localStorage.getItem("rr:smoke:r1")   // Round 1 초안이 그대로 남아있어야 함(라운드별 키 격리)
localStorage.getItem("rr:smoke:r2")   // 새 라운드는 빈 배열이거나 null이어야 함(아직 아무것도 안 담음)
```
Expected: `r1` 키의 내용이 Step 4에서 추가한 항목을 그대로 보존(사라지지 않음), `r2` 키는 새로 시작(격리 확인). 가능하면 Artifact 버전 이력에서 "Round 1"·"Round 2" 둘 다 열람되는지도 확인한다.

- [ ] **Step 6: acceptance 통과 후 스모크 삭제**

Step 4·5의 확인이 모두 통과했을 때만 실행한다:
```bash
rm -rf WIP/reviews/smoke
```

- [ ] **Step 7: 스캐폴딩 커밋 (AXDT 리포)**

```bash
cd "C:/Users/Harriet/Desktop/SST/AX Strategy/AXDT/.claude/worktrees/review-report-skill"
git add WIP/reviews/config.json WIP/reviews/context.html WIP/reviews/.gitkeep .gitignore
git commit -q -m "feat(reviews): review-report 데이터 스캐폴딩 + out.html 무시"
```

- [ ] **Step 8: 정지 — 사용자 승인 없이 다음 단계로 진행하지 않는다**

여기서 멈춘다. Step 9~11(메모리 삭제)은 **2라운드 acceptance(Step 4·5)가 실제로 통과했고, 사용자가 명시적으로 승인한 뒤에만** 진행한다. 설계 §9: "삭제는 2라운드 acceptance test 통과 + 사용자 승인 후에만 한다. 그 전에 삭제하면 검증 안 된 구현만 남기고 복구 경로를 잃을 위험이 있다." 사용자 승인을 이 태스크의 실행자(에이전트)가 스스로에게 내리는 것은 금지 — 실제 사용자 응답이 필요하다.

- [ ] **Step 9: (승인 후) 메모리 내용을 스킬 repo에 백업**

`C:/Users/Harriet/.claude/projects/C--Users-Harriet-Desktop-SST-AX-Strategy-AXDT/memory/html-deliverable-house-style.md`의 전체 내용을 읽어, 그대로 아래 경로에 옮겨 적는다(내용은 원본을 Read해서 그대로 사본을 만든다 — 이 계획 문서에는 원본 내용을 미리 적어두지 않는다, 실행 시점 원본이 진실원이다):

Create `C:/Users/Harriet/.claude/skills/review-report/ARCHIVE-html-deliverable-house-style.md`:
```markdown
# 백업: html-deliverable-house-style (구 메모리)

> 이 파일은 `~/.claude/projects/.../memory/html-deliverable-house-style.md`의 2라운드 acceptance 통과 시점 사본이다.
> 집 스타일의 진실원은 이제 이 스킬의 `shell.html`이다. 이 파일은 이력 보존용이며 코드에서 참조하지 않는다.

(원본 메모리 파일의 전체 내용을 여기에 그대로 붙여넣는다)
```

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git add ARCHIVE-html-deliverable-house-style.md
git commit -q -m "docs: 구 house-style 메모리 백업(스킬이 진실원으로 이전)"
```

- [ ] **Step 10: (승인 후) 원본 메모리 삭제 + 색인 정리**

```bash
rm "C:/Users/Harriet/.claude/projects/C--Users-Harriet-Desktop-SST-AX-Strategy-AXDT/memory/html-deliverable-house-style.md"
```

`MEMORY.md`에서 `html-deliverable-house-style` 색인 줄을 제거한다(있다면). `use-artifact-tool-for-html-deliverables.md` 메모리 본문 끝에 한 줄 추가:
```
집 스타일 표준 구현체는 `~/.claude/skills/review-report/shell.html`(review-report 스킬)이다. 새 HTML 산출물은 이 스킬을 우선 검토한다.
```

- [ ] **Step 11: 스킬 repo 최종 태그**

```bash
cd "C:/Users/Harriet/.claude/skills/review-report"
git tag v1.0
git log --oneline
```
Expected: Task 0~10의 커밋이 순서대로 보인다.

---

## Self-Review

### 스펙 R2 커버리지 대조

| 설계 절 | 요구 | 반영 태스크 |
|---|---|---|
| §2.1 | Artifact 같은 URL 재게시가 "같은 페이지 반영"의 메커니즘 | Task 0(실측·계약 고정), Task 10(절차화) |
| §2.2 | 공용은 파일 분리, 조립기가 본문과 합성 | Task 8(shell.html)·Task 9(build_page) |
| §2.3 | 용어집 참조(소유 안 함), 2형식 파싱, 소스 누락 시 실패, 미사용 용어집 지표 | Task 2(`parse_glossary`/`load_glossary`), Task 9(`unused_glossary_terms` 출력) |
| §2.4 | 필수 메타 exit 1, 타입·범위(round≥1 정수·session/topic 비지않은 문자열·anchors 리스트·round≥2 시 artifact_url) | Task 1(`validate_meta`) |
| §2.5 | 앵커 = 섹션 안정 ID, 정규식 강제, 중복 금지, 소실 앵커 경고 | Task 4(`validate_fragment`/`collect_anchors`/`diff_anchors`) |
| §2.6 | 의견 종류 4개, 앵커당 다중 의견, GENERAL 총평 | Task 6(`KINDS`), Task 8(다중 아이템 UI + GENERAL 섹션) |
| §2.7 | 의견 왕복 JSON 단일화, localStorage 라운드별 키, 클립보드 폴백, ingest 하위명령 | Task 7(`serialize_comments_json`/`parse_clipboard`/`ingest`), Task 8(JS 쪽 JSON 직렬화·폴백 textarea) |
| §2.8 | 본문은 최신만, 이전 의견은 처리 결과 카드, 여러 줄 pre-wrap | Task 6(`render_comment_cards`/`inject_comment_cards`), Task 8 CSS(`white-space:pre-wrap`) |
| §2.9 | 집 스타일 구조·시각 시스템·용어 풀이 실노출·트리거 확장 | Task 8(shell.html 전체), Task 10(SKILL.md 트리거) |
| §2.10 | fragment 제한 + 파서 스택(앵커·카드·번호매김), 토큰 1회 치환 | Task 4·5·6(각 파서 스택), Task 9(`render_shell`) |
| §3 | 파일 배치(개인 스킬 vs `WIP/reviews/`) | Global Constraints + Task 0·1(스킬 repo), Task 11(데이터 스캐폴딩) |
| §4.1 config.json | glossary_sources·context_file, 경로 프로젝트 루트 기준 | Task 11 Step 1 |
| §4.2 meta.json | 필드·검증 | Task 1 |
| §4.3 클립보드 형식 | 사람 한 줄 + JSON 블록, 첫 `{`부터 `raw_decode` | Task 7(`parse_clipboard`) |
| §4.4 comments.json | 평면 items, resolution/note, kind/resolution/anchor/round 검증 | Task 7(`validate_comments`) |
| §5 본문 문법 | section 반복·b-term·콜아웃·외부리소스 금지 | Task 10(SKILL.md), Task 4(fragment 규칙), Task 9(`check_self_contained`) |
| §6 조립기 절차 9단계 | 순서대로 | Task 9(`build_page`) — validate_meta → validate_fragment → glossary → comments 검증 → 카드 주입 → 용어 감싸기 → 번호매김 → context/용어표/푸터 → render_shell → 자체완결 검사 → 저장 → 요약 |
| §6 ingest | slug/round 대조, 병합 | Task 7(`ingest`) |
| §7 라운드 절차 | 6단계 | Task 10(SKILL.md) |
| §8 테스트 항목 | 메타/용어집/감싸기/fragment/앵커·카드/클립보드/ingest/치환/자체완결/집 스타일 | Task 1~9 각 테스트 클래스(총 101개) |
| §9 메모리 이전·삭제(지연) | acceptance 통과 + 승인 후만 | Task 11 Step 8(명시적 정지 체크포인트)~10 |
| §10 Artifact 계약 실측 | 구현 전 1회 실측 | Task 0 |

### R1 대비 실증된 blocking 4개 수정 위치

1. **용어 감싸기 결함(수동 b-term 소진 미비·단어 경계 없음)** → Task 3: `_TermWrapper`가 `<b-term>` 내부 텍스트를 버퍼링해 종료 시 `_exhaust()`로 소진 등록하고, `_match_at()`이 ASCII 용어에만 단어 경계를 적용(CJK는 미적용). 테스트 `test_manual_bterm_exhausts_term_prevents_later_autowrap`·`test_ascii_word_boundary_skips_substring`·`test_ascii_word_boundary_gate_vs_gateway`.
2. **의견 왕복 텍스트 형식 손상** → Task 7: `serialize_comments_json`/`parse_clipboard`가 JSON 하나로 왕복(`json.JSONDecoder().raw_decode`로 붙여넣은 텍스트에서 JSON 블록만 추출). 테스트 `SerializeParseRoundtripTest`(개행·대괄호·`###`·유니코드 보존 확인).
3. **마크업 안전(정규식 앵커수집·문자열 find 카드주입)** → Task 4(`_FragmentValidator`)·Task 5(`_SectionNumberer`)·Task 6(`_CardInjector`) 모두 `HTMLParser` 깊이 스택으로 재작성. 테스트 `test_nested_section_close_not_treated_as_injection_point`가 R1이라면 깨졌을 케이스를 정확히 검증.
4. **"풀이 없는 용어" 오명명** → Task 3·9: 반환값·로그 문구를 `unused_glossary_terms`(미사용 용어집 항목)로 정정. Task 9 `main()`의 출력 문구가 이 이름을 그대로 씀.

### Placeholder 스캔
전 태스크의 코드 스텝에 `TODO`·"이하 동일"·"Task N 참고" 같은 자리표시자 없음 — 각 스텝이 실제로 붙여넣을 완전한 코드다. `{{...}}` 표기는 shell.html의 치환 토큰(의도된 것) 뿐이다.

### 타입 일관성 확인
- `wrap_terms(body_html, glossary) -> (str, int, list[str])` — Task 3 정의, Task 9 `build_page`에서 `body, wrapped_n, unused_glossary_terms = wrap_terms(...)`로 그대로 소비.
- `validate_fragment(body_html) -> None`(raise on error) vs `collect_anchors(body_html) -> list` — Task 4에서 분리 정의, Task 9에서 각각 독립 호출(전자는 try/except, 후자는 직접).
- `render_comment_cards(comments, anchor) -> str` — Task 6 정의, Task 6 자체 `_CardInjector`와 Task 9 `build_page`(GENERAL 전용 호출)에서 동일 시그니처로 소비.
- `serialize_comments_json(slug, rnd, items) -> str` / `parse_clipboard(text) -> dict{"slug","round","items"}` — Task 7 정의, Task 7 `ingest`와 테스트 전반에서 키 이름(`slug`/`round`/`items`, 항목의 `anchor`/`kind`/`text`) 일관.
- `_KNOWN_TOKENS`(Task 9, 11개) = shell.html의 토큰 11개(Task 8) — Task 8 Step 2 `test_all_known_tokens_present`와 Task 9 `render_shell`이 같은 집합을 전제.
- `KINDS`(Task 6, 4개 한글 문자열) — Task 7 `validate_comments`, Task 8 shell.html JS의 `KINDS` 배열, Task 8 테스트 `test_kinds_match_python_constants`가 모두 같은 값을 참조.
- `FragmentError` — Task 3에서 정의(용어 태그 결함용), Task 4에서 같은 클래스를 fragment 구조 위반에도 재사용(별도 예외 클래스를 새로 만들지 않음) — Task 9 `build_page`가 두 발생 지점을 모두 `except FragmentError`로 잡음.

