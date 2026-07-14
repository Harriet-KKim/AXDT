"""C1~C6 검사 로직 — SoT 완료 판정 ① 형식(rule-sot-readiness) 그대로 구현.

C1~C6은 requirements·specification·test-design 3종 문서에만 적용한다(rule
적용범위: rule/은 대상이 아니다 — id 레지스트리 수집에만 쓰인다).

금지어 목록(C5)·플레이스홀더 정규식(C4)은 이 모듈이 코드 상수로 단일 관리하며,
C6(수용 기준 채워짐)도 같은 상수를 재사용한다(§2 명확화 ★).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from axdt.sot_lint.parser import CONTENT_KINDS, ParsedDocument

__all__ = [
    "Violation",
    "BANNED_WORDS",
    "find_banned_words",
    "run_checks",
]


@dataclass(frozen=True)
class Violation:
    """--json violations[]와 1:1 대응(path/line/code/message). line=None → 파일/디렉터리 수준."""

    path: str
    line: int | None
    code: str
    message: str


# --- 코드 상수 (단일 관리) ---

# C4: 플레이스홀더 문법은 `{{...}}`(이중 중괄호)만 잡는다(A2, rule-sot-readiness ① 개정).
# `<...>`를 쓰지 않는 이유: Markdown 자동링크(`<https://example.com>`)·제네릭 타입
# (`Map<K,V>`) 같은 정당한 본문과 구문이 겹쳐 오탐한다(위 두 예시는 실제로 이전 정규식이
# 잘못 위반으로 잡았다 — test_c4_does_not_match_markdown_autolink 등 참조).
# 내용은 1자 이상(빈 `{{}}`는 실제 템플릿 관례(`{{topic}}`)에 없어 대상 밖으로 둔다) +
# 개행 미포함(플레이스홀더는 한 줄 안에서 채우는 관례라 여러 줄에 걸친 `{{...}}`는
# 의도치 않은 중괄호 쌍일 가능성이 크다 — 코드펜스·인라인코드 제외는 기존과 동일).
PLACEHOLDER_RE = re.compile(r"\{\{[^{}\n]+\}\}")

_BANNED_ASCII: tuple[str, ...] = ("TBD", "TODO", "FIXME")
_BANNED_KOREAN: tuple[str, ...] = ("미정", "추후", "나중에")
BANNED_WORDS: tuple[str, ...] = _BANNED_ASCII + _BANNED_KOREAN

_BANNED_ASCII_RE = re.compile(r"\b(?:" + "|".join(_BANNED_ASCII) + r")\b", re.IGNORECASE)

# 항목 ID 토큰(본문 전체 종류 통합, 볼드 무관 — \b가 '**'를 자연히 경계로 인식).
_TOKEN_RE = re.compile(r"\b(?:FR|NFR|SP|TD)-\d+\b")
# `topic:ID` 접두 참조(§A-4) — covers처럼 다른 topic(또는 자기 topic)의 항목을 본문에서
# 가리킬 때 쓰는 표기. 접두가 붙은 토큰은 "그 문서의 자기 선언"이 아니라 참조이므로
# 본문 자기선언 대조(body_tokens)에서 제외해야 한다. 끝 위치(m.end())가 bare _TOKEN_RE
# 매치의 끝과 항상 같다는 점을 이용해, 그 끝 위치에서 bare 매치를 걸러낸다.
_PREFIXED_TOKEN_RE = re.compile(r"\b[\w-]+:(?:FR|NFR|SP|TD)-\d+\b")

# 종류별 items 규약(자기 종류 ID만 인정).
_OWN_ITEM_RE: dict[str, re.Pattern[str]] = {
    "requirements": re.compile(r"^(?:FR|NFR)-\d+$"),
    "specification": re.compile(r"^SP-\d+$"),
    "test-design": re.compile(r"^TD-\d+$"),
}
# 문서 id 접두(정확히 1회 strip 대상).
_ID_PREFIX: dict[str, str] = {
    "requirements": "req-",
    "specification": "spec-",
    "test-design": "td-",
}

# 체크박스 앵커: "- [ ]"/"- [x]"/"- [X]"로 시작하는 줄(★ 명확화, A1). 뒤 내용을 그룹1로
# 캡처. 체크 상태는 무관하다 — C6이 보는 건 "채워졌는가"이지 "체크됐는가"가 아니다.
_CHECKBOX_RE = re.compile(r"^\s*-\s+\[[ xX]\]\s*(.*)$")

# '## 수용 기준' 섹션 경계 판정용 — 레벨1(#)·레벨2(##) 제목만 섹션을 여닫는다(A1).
_HEADING_RE = re.compile(r"^(#{1,2})[ \t]+(.*?)[ \t]*$")
_ACCEPTANCE_HEADING_TITLE = "수용 기준"


def find_banned_words(text: str) -> list[str]:
    """text에서 금지어(닫힌 목록)를 전부 찾아 등장 위치 순으로 반환.

    ASCII(TBD/TODO/FIXME)는 대소문자 무시+단어 경계, 한글(미정/추후/나중에)은 정확 매칭.
    """
    found: list[tuple[int, str]] = []
    for m in _BANNED_ASCII_RE.finditer(text):
        found.append((m.start(), m.group(0)))
    for word in _BANNED_KOREAN:
        start = 0
        while True:
            idx = text.find(word, start)
            if idx == -1:
                break
            found.append((idx, word))
            start = idx + len(word)
    found.sort(key=lambda t: t[0])
    return [w for _, w in found]


def _coerce_list(value: object) -> list[str]:
    """frontmatter 스칼라/리스트 값을 문자열 리스트로 정규화(스칼라 1개 → 1원소 리스트)."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _comma_hint(raw: str) -> str:
    if "," in raw:
        return " — 콤마로 여러 값을 한 문자열에 넣은 것으로 보임(리스트로 표기할 것)"
    return ""


# --- C1 존재 ---


def _check_c1(documents: dict[str, list[ParsedDocument]], root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for kind in CONTENT_KINDS:
        has_items = any(_coerce_list(doc.frontmatter.get("items")) for doc in documents[kind])
        if not has_items:
            violations.append(
                Violation(
                    path=(root / kind).as_posix(),
                    line=None,
                    code="C1",
                    message=f"{kind} 종류에 items를 선언한 문서가 없음(README·_TEMPLATE 제외)",
                )
            )
    return violations


# --- C2 항목 ID + 유일성 + 본문 일치 ---


def _check_c2(documents: dict[str, list[ParsedDocument]]) -> list[Violation]:
    violations: list[Violation] = []
    declarations: list[tuple[str, str, str]] = []  # (topic, item_id, path)

    for kind in CONTENT_KINDS:
        own_re = _OWN_ITEM_RE[kind]
        expected_prefix = _ID_PREFIX[kind]
        for doc in documents[kind]:
            items = _coerce_list(doc.frontmatter.get("items"))

            # id ↔ topic (접두 정확히 1회 strip, 나머지 전체가 topic)
            doc_id = doc.frontmatter.get("id")
            if not isinstance(doc_id, str) or not doc_id.startswith(expected_prefix):
                violations.append(
                    Violation(
                        doc.path,
                        None,
                        "C2",
                        f"frontmatter id가 '{expected_prefix}<topic>' 규약과 불일치: {doc_id!r}",
                    )
                )
            else:
                topic_from_id = doc_id[len(expected_prefix) :]
                if topic_from_id != doc.topic:
                    violations.append(
                        Violation(
                            doc.path,
                            None,
                            "C2",
                            f"id의 topic({topic_from_id!r})이 파일명({doc.topic!r})과 불일치",
                        )
                    )

            # 본문 토큰 집합(뷰A — 코드펜스만 제외, 인라인 포함 — 자기 종류 ID만).
            # `topic:ID` 접두가 붙은 토큰은 참조(다른 문서/항목을 가리킴)이지 이 문서의
            # 자기 선언이 아니므로 제외한다(§A-4) — 접두 없이 그 위치에서 끝나는 bare
            # 토큰만 자기 선언 후보로 센다(끝 오프셋으로 대조: 접두 매치와 bare 매치는
            # 항상 같은 위치에서 끝난다).
            body_tokens: dict[str, int] = {}
            for line_no, text in doc.body_view_a:
                prefixed_ends = {m.end() for m in _PREFIXED_TOKEN_RE.finditer(text)}
                for m in _TOKEN_RE.finditer(text):
                    if m.end() in prefixed_ends:
                        continue
                    tok = m.group(0)
                    if own_re.match(tok) and tok not in body_tokens:
                        body_tokens[tok] = line_no

            declared_valid: set[str] = set()
            for raw in items:
                if not own_re.match(raw):
                    # own_re에 안 맞는 항목은 애초에 이 kind의 유효한 선언이 아니므로
                    # declarations(전역 중복 대조용)에 넣지 않는다(§A-5) — 넣으면
                    # 다른 문서의 진짜 선언과 우연히 (topic, raw) 문자열이 같아지는
                    # 경우 거짓 "중복 선언"을 만든다. 형식 위반 자체는 그대로 보고한다.
                    violations.append(
                        Violation(
                            doc.path,
                            None,
                            "C2",
                            f"items 항목 ID 형식이 {kind} 규약과 불일치: {raw!r}{_comma_hint(raw)}",
                        )
                    )
                    continue
                declarations.append((doc.topic, raw, doc.path))
                declared_valid.add(raw)
                if raw not in body_tokens:
                    violations.append(
                        Violation(
                            doc.path,
                            None,
                            "C2",
                            f"items에 선언됐으나 본문에 등장하지 않음(phantom): {raw!r}",
                        )
                    )

            for tok, line_no in body_tokens.items():
                if tok not in declared_valid:
                    violations.append(
                        Violation(
                            doc.path,
                            line_no,
                            "C2",
                            f"본문에 등장하나 items에 선언되지 않음: {tok!r}",
                        )
                    )

    # SoT 전체 (topic, ID) 유일성 — 한 문서 내 items 중복도 topic이 같아 자연히 걸린다.
    by_key: dict[tuple[str, str], list[str]] = {}
    for topic, item_id, path in declarations:
        by_key.setdefault((topic, item_id), []).append(path)
    for (topic, item_id), paths in by_key.items():
        if len(paths) > 1:
            for p in sorted(set(paths)):
                others = sorted(set(paths) - {p})
                where = others if others else ["(같은 문서 내 중복 선언)"]
                violations.append(
                    Violation(
                        p,
                        None,
                        "C2",
                        f"(topic={topic!r}, id={item_id!r}) 중복 선언: 다른 선언 위치 {where}",
                    )
                )

    return violations


# --- C3 참조 무결성 ---


def _resolve_covers_target_kind(source_kind: str, id_part: str) -> str | None:
    if source_kind == "specification":
        return "requirements" if re.match(r"^(?:FR|NFR)-\d+$", id_part) else None
    if source_kind == "test-design":
        if re.match(r"^(?:FR|NFR)-\d+$", id_part):
            return "requirements"
        if re.match(r"^SP-\d+$", id_part):
            return "specification"
        return None
    return None


def _check_c3(
    documents: dict[str, list[ParsedDocument]],
    rule_statuses: dict[str, str | None],
    errored_topics: set[tuple[str, str]],
) -> list[Violation]:
    violations: list[Violation] = []
    by_topic: dict[tuple[str, str], ParsedDocument] = {}
    for kind in CONTENT_KINDS:
        for doc in documents[kind]:
            by_topic[(kind, doc.topic)] = doc

    for kind in CONTENT_KINDS:
        for doc in documents[kind]:
            if kind in ("specification", "test-design"):
                for raw in _coerce_list(doc.frontmatter.get("covers")):
                    if PLACEHOLDER_RE.search(raw):
                        continue  # 미치환 {{...}}는 C4가 잡는다
                    if ":" in raw:
                        topic, _, id_part = raw.partition(":")
                    else:
                        topic, id_part = doc.topic, raw

                    target_kind = _resolve_covers_target_kind(kind, id_part)
                    if target_kind is None:
                        violations.append(
                            Violation(
                                doc.path, None, "C3", f"covers 참조 형식을 알 수 없음: {raw!r}"
                            )
                        )
                        continue

                    target = by_topic.get((target_kind, topic))
                    if target is not None:
                        if id_part not in _coerce_list(target.frontmatter.get("items")):
                            violations.append(
                                Violation(
                                    doc.path,
                                    None,
                                    "C3",
                                    f"covers={raw!r}: 대상 문서({target_kind}/{topic})에 "
                                    f"항목 {id_part!r} 없음(dangling)",
                                )
                            )
                    elif (target_kind, topic) in errored_topics:
                        pass  # 대상 문서가 파싱 오류 — 이미 별도 E_*로 드러남(중복 보고 방지)
                    else:
                        violations.append(
                            Violation(
                                doc.path,
                                None,
                                "C3",
                                f"covers={raw!r}: 대상 문서 {target_kind}/{topic}.md 없음",
                            )
                        )

            for raw in _coerce_list(doc.frontmatter.get("rules")):
                if PLACEHOLDER_RE.search(raw):
                    continue
                if raw not in rule_statuses:
                    violations.append(
                        Violation(doc.path, None, "C3", f"rules={raw!r}: 실재하지 않는 rule id")
                    )
                    continue
                # active만 유효한 참조 대상(다중모델 리뷰 라운드5) — deprecated·superseded는
                # 실재해도 위반, status 누락/기형은 registry가 이미 None으로 fail-closed.
                status = rule_statuses[raw]
                if status != "active":
                    detail = f"status={status!r}" if status is not None else "status 누락/기형"
                    violations.append(
                        Violation(
                            doc.path,
                            None,
                            "C3",
                            f"rules={raw!r}: 참조 대상 rule이 active 상태가 아님({detail})",
                        )
                    )

    return violations


# --- C4 미치환 플레이스홀더 ---


def _check_c4(documents: dict[str, list[ParsedDocument]]) -> list[Violation]:
    violations: list[Violation] = []
    for kind in CONTENT_KINDS:
        for doc in documents[kind]:
            for line_no, text in doc.frontmatter_lines:
                for m in PLACEHOLDER_RE.finditer(text):
                    violations.append(
                        Violation(doc.path, line_no, "C4", f"미치환 플레이스홀더: {m.group(0)!r}")
                    )
            for line_no, text in doc.body_view_b:
                for m in PLACEHOLDER_RE.finditer(text):
                    violations.append(
                        Violation(doc.path, line_no, "C4", f"미치환 플레이스홀더: {m.group(0)!r}")
                    )
    return violations


# --- C5 금지어 ---


def _check_c5(documents: dict[str, list[ParsedDocument]]) -> list[Violation]:
    violations: list[Violation] = []
    for kind in CONTENT_KINDS:
        for doc in documents[kind]:
            # C4와 대칭: frontmatter(예: title)에 샌 금지어도 잡는다.
            # frontmatter엔 코드펜스가 없으므로 raw 줄을 그대로 스캔한다.
            for line_no, text in doc.frontmatter_lines:
                for word in find_banned_words(text):
                    violations.append(
                        Violation(doc.path, line_no, "C5", f"금지어 포함: {word!r}")
                    )
            for line_no, text in doc.body_view_b:
                for word in find_banned_words(text):
                    violations.append(
                        Violation(doc.path, line_no, "C5", f"금지어 포함: {word!r}")
                    )
    return violations


# --- C6 수용 기준 채워짐 ---


def _first_token(text: str) -> str | None:
    # `topic:ID` 접두 참조(§A-4)는 자기 항목이 아니라 다른 문서를 가리키는 참조이므로
    # 매핑 후보에서 제외하고, **접두 없는 bare ID 토큰의 첫 등장**을 매핑 키로 쓴다
    # (C2 body_tokens 자기선언 대조와 대칭 — 다중모델 리뷰 라운드11). 접두 매치와 bare
    # 매치는 끝 위치가 같으므로, prefixed 매치의 끝 위치에 드는 bare 매치를 건너뛴다.
    prefixed_ends = {m.end() for m in _PREFIXED_TOKEN_RE.finditer(text)}
    for m in _TOKEN_RE.finditer(text):
        if m.end() in prefixed_ends:
            continue
        return m.group(0)
    return None


def _strip_id_token(content: str, token: str) -> str:
    pattern = re.compile(r"\*{0,2}" + re.escape(token) + r"\*{0,2}")
    return pattern.sub("", content, count=1)


def _acceptance_section_range(doc: ParsedDocument) -> tuple[int, int] | None:
    """'## 수용 기준' 섹션의 (시작 줄, 끝 줄·미포함)을 반환. 섹션이 없으면 None(A1).

    헤딩 판정은 뷰A(코드펜스만 제외)로 한다 — 펜스 안의 가짜 '## 수용 기준'은 뷰A에서
    이미 빈 줄로 마스킹돼 있어 제목으로 잡히지 않는다(파서의 펜스 마스킹을 그대로
    재사용). 섹션 = 제목이 정확히 '수용 기준'인 레벨2(##) 제목부터, 그 다음에 나오는
    임의의 레벨1(#)/레벨2(##) 제목 직전까지(레벨3+ 하위 제목은 섹션에 포함).
    """
    start: int | None = None
    for line_no, text in doc.body_view_a:
        m = _HEADING_RE.match(text)
        if not m:
            continue
        if start is None:
            if len(m.group(1)) == 2 and m.group(2).strip() == _ACCEPTANCE_HEADING_TITLE:
                start = line_no + 1
            continue
        # 이미 섹션 안 — 다음에 나오는 어떤 레벨1/2 제목에서든 섹션이 끝난다.
        return (start, line_no)
    if start is None:
        return None
    return (start, 10**9)  # 문서 끝까지(더 나오는 레벨1/2 제목 없음)


def _check_c6(documents: dict[str, list[ParsedDocument]]) -> list[Violation]:
    violations: list[Violation] = []
    for kind in CONTENT_KINDS:
        for doc in documents[kind]:
            items = _coerce_list(doc.frontmatter.get("items"))
            if not items:
                continue

            section_range = _acceptance_section_range(doc)
            if section_range is None:
                violations.append(Violation(doc.path, None, "C6", "수용 기준 섹션 없음"))
                continue
            section_start, section_end = section_range

            # 존재·ID추출·비어있음 판정은 뷰A(인라인 코드 포함 — C2 phantom-오탐-방지와
            # 일관: 수용 기준을 인라인 코드로만 채워도 "비었다"고 오탐하지 않는다).
            # 플레이스홀더·금지어 판정은 뷰B(인라인·펜스 마스킹 — C4·C5와 일관).
            checkbox_for: dict[str, tuple[int, str, str]] = {}
            for (line_no, text_a), (_, text_b) in zip(doc.body_view_a, doc.body_view_b):
                if not (section_start <= line_no < section_end):
                    continue
                m = _CHECKBOX_RE.match(text_a)
                if not m:
                    continue
                token = _first_token(m.group(1))
                if token is None or token in checkbox_for:
                    continue
                content_a = m.group(1)
                m_b = _CHECKBOX_RE.match(text_b)
                content_b = m_b.group(1) if m_b else content_a
                checkbox_for[token] = (line_no, content_a, content_b)

            for item in items:
                found = checkbox_for.get(item)
                if found is None:
                    violations.append(
                        Violation(
                            doc.path,
                            None,
                            "C6",
                            f"항목 {item!r}에 대응하는 수용 기준 체크박스(- [ ]/[x]/[X]) 없음",
                        )
                    )
                    continue

                line_no, content_a, content_b = found
                remainder_b = _strip_id_token(content_b, item).strip()
                # 비어있음 = ID를 뺀 뒤 실제 내용(글자·숫자·한글)이 없음. 공백만 보던 기존
                # 판정은 백틱·콜론·대시 같은 부호만 남아도 '내용 있음'으로 통과시켰다(R3 리뷰).
                # 밑줄 제외 단어문자가 하나도 없으면 빈 것으로 본다(뷰A — 인라인 코드 포함).
                if re.search(r"[^\W_]", _strip_id_token(content_a, item)) is None:
                    violations.append(
                        Violation(
                            doc.path, line_no, "C6", f"항목 {item!r}의 수용 기준 내용이 비어 있음"
                        )
                    )
                elif PLACEHOLDER_RE.search(remainder_b):
                    violations.append(
                        Violation(
                            doc.path,
                            line_no,
                            "C6",
                            f"항목 {item!r}의 수용 기준이 미치환 플레이스홀더임",
                        )
                    )
                elif find_banned_words(remainder_b):
                    violations.append(
                        Violation(
                            doc.path, line_no, "C6", f"항목 {item!r}의 수용 기준에 금지어 포함"
                        )
                    )
    return violations


# --- rule 카탈로그 중복 id(§A-6) ---


def _check_duplicate_rule_ids(duplicate_rule_ids: dict[str, list[str]]) -> list[Violation]:
    """registry.find_duplicate_rule_ids의 결과를 위반으로 표면화.

    C3(참조 무결성)과 같은 코드를 쓴다 — 중복 id는 `rules: [id]` 참조가 어느 rule
    파일을 가리키는지 모호하게 만들어 참조 무결성을 해친다는 점에서 C3의 연장이다.
    각 중복 id마다, 그 id를 선언한 파일 수만큼 위반을 내(파일별로 자기 경로 기준
    "다른 선언 위치" 나열) 어느 파일을 고쳐도 문제가 드러나게 한다(C2 중복 선언과
    같은 리포팅 스타일).
    """
    violations: list[Violation] = []
    for rid, paths in duplicate_rule_ids.items():
        for p in sorted(paths):
            others = sorted(set(paths) - {p})
            violations.append(
                Violation(
                    p,
                    None,
                    "C3",
                    f"rule id 중복 선언: {rid!r}(다른 선언 위치 {others})",
                )
            )
    return violations


# --- 진입점 ---


def run_checks(
    documents: dict[str, list[ParsedDocument]],
    root: Path,
    rule_statuses: dict[str, str | None],
    errored_topics: set[tuple[str, str]],
    duplicate_rule_ids: dict[str, list[str]] | None = None,
) -> list[Violation]:
    violations: list[Violation] = []
    violations.extend(_check_c1(documents, root))
    violations.extend(_check_c2(documents))
    violations.extend(_check_c3(documents, rule_statuses, errored_topics))
    violations.extend(_check_c4(documents))
    violations.extend(_check_c5(documents))
    violations.extend(_check_c6(documents))
    violations.extend(_check_duplicate_rule_ids(duplicate_rule_ids or {}))
    return violations
