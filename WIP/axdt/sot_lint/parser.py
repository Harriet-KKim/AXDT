"""SoT 문서 파싱 — frontmatter(YAML) + 본문의 코드펜스/인라인 상태머신.

파일 탐색(discover)부터 frontmatter 파싱(중복 키 거부 커스텀 YAML 로더)까지 담당하고,
본문의 두 텍스트 뷰(view A=코드펜스만 제외, view B=코드펜스+인라인 제외)를 만든다.
- 뷰A: C2(본문 ID 토큰 매칭)가 쓴다 — 인라인 코드로만 등장한 항목도 "본문에 등장"으로
  인정해 phantom 오탐을 막는다(통합 마스킹 금지 — 뷰를 나누는 이유).
- 뷰B: C4(플레이스홀더)·C5(금지어)가 쓴다.
줄 번호는 항상 원문(1-기준) 그대로 유지한다 — 마스킹은 내용만 지우고 줄을 없애지 않는다.

frontmatter 부재·YAML malformed·중복 키는 위반이 아니라 실행 오류(ParseError, E_*)로
취급한다(rule ① §3.1, sot-lint 스펙 §3.1).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError

__all__ = [
    "KINDS",
    "CONTENT_KINDS",
    "ParseError",
    "ParsedDocument",
    "DuplicateKeyError",
    "discover",
    "load_document",
    "load_all",
]

# rule은 C1~C6 검사 대상이 아니다(rule-sot-readiness 적용범위: req·spec·test-design만).
# id 레지스트리(§5) 수집을 위해서만 로드한다.
KINDS: tuple[str, ...] = ("requirements", "specification", "test-design", "rule")
CONTENT_KINDS: tuple[str, ...] = ("requirements", "specification", "test-design")

# 여는 펜스: 줄 시작(최대 3칸 들여쓰기) + 백틱 또는 물결 3개 이상 + 임의의 trailing
# 텍스트(정보 문자열, 예: ```python) 허용. 틸드(~~~) 펜스도 백틱과 동등하게 지원
# (미해결 §8 결정 — 구현 시 확정, 보고 참조).
_FENCE_OPEN_RE = re.compile(r"^([ ]{0,3})(`{3,}|~{3,})")
# 닫는 펜스(§A-3): CommonMark상 정보 문자열을 허용하지 않는다 — 같은 종류·같은/더 긴
# 길이의 구분선 뒤에 **공백만** 허용(그 외 trailing 텍스트가 있으면 닫는 펜스가 아니다).
_FENCE_CLOSE_RE = re.compile(r"^([ ]{0,3})(`{3,}|~{3,})[ \t]*$")
# 인라인 코드 백틱런(여는/닫는 후보) 토큰화용 — 개수 판정은 _mask_inline_code가 CommonMark
# 규칙(여는 런과 정확히 같은 '길이'의 런으로만 닫힘, 부분열은 불허)대로 직접 수행한다(§A-2).
_BACKTICK_RUN_RE = re.compile(r"`+")


# --- YAML: SafeLoader 상속 + 중복 키 거부 ---


class DuplicateKeyError(ConstructorError):
    """frontmatter YAML 매핑에 같은 키가 두 번 이상 나타남.

    yaml.safe_load는 중복 키를 조용히 마지막 값으로 덮어써서 위반을 숨긴다.
    이 로더는 SafeLoader의 construct_mapping을 그대로 재현하되 중복만 거부한다.
    """


class _StrictSafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            raise ConstructorError(
                None, None, f"expected a mapping node, but found {node.id}", node.start_mark
            )
        self.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError as exc:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found unhashable key",
                    key_node.start_mark,
                ) from exc
            if key in mapping:
                raise DuplicateKeyError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key: {key!r}",
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


# --- 데이터 모델 ---


@dataclass(frozen=True)
class ParseError:
    """검사 불능(실행 오류, 종료코드 2). --json errors[]와 1:1 대응(path/code/message)."""

    path: str
    code: str  # E_*
    message: str


@dataclass
class ParsedDocument:
    path: str
    kind: str
    topic: str
    frontmatter: dict[str, Any]
    # (원문 파일 줄 번호, raw text) — frontmatter 블록 내부(--- 두 줄 제외). C4 frontmatter 스캔용.
    frontmatter_lines: list[tuple[int, str]]
    body_view_a: list[tuple[int, str]]  # 코드펜스만 제외 (C2)
    body_view_b: list[tuple[int, str]]  # 코드펜스+인라인 제외 (C4·C5)


# --- 탐색 ---


def _is_excluded(name: str) -> bool:
    return name == "README.md" or name.endswith("_TEMPLATE.md")


def discover(root: Path) -> dict[str, list[Path]]:
    """root 하위 각 종류 디렉터리 직속 *.md를 이름순 정렬해 모은다(README·_TEMPLATE 제외)."""
    result: dict[str, list[Path]] = {}
    for kind in KINDS:
        d = root / kind
        files: list[Path] = []
        if d.is_dir():
            for p in sorted(d.glob("*.md"), key=lambda x: x.name):
                if _is_excluded(p.name):
                    continue
                files.append(p)
        result[kind] = files
    return result


# --- frontmatter + 본문 로드 ---


def load_document(path: Path, kind: str) -> ParsedDocument | ParseError:
    display = path.as_posix()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return ParseError(display, "E_READ", f"파일을 읽을 수 없음: {exc}")

    try:
        # utf-8-sig: BOM(``)이 있으면 제거하고 없으면 평범한 UTF-8과 동일하게 동작한다
        # (§A-1). BOM을 그대로 두면 첫 줄이 "---"가 아니라 "﻿---"가 돼
        # frontmatter 존재 검사(lines[0].rstrip() != "---")가 항상 실패, BOM 붙은
        # 정상 파일이 E_FRONTMATTER_MISSING으로 오판된다.
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return ParseError(display, "E_ENCODING", f"UTF-8 디코드 실패: {exc}")

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    if not lines or lines[0].rstrip() != "---":
        return ParseError(display, "E_FRONTMATTER_MISSING", "frontmatter(--- 블록) 없음")

    close_idx = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            close_idx = i
            break
    if close_idx is None:
        return ParseError(display, "E_FRONTMATTER_MISSING", "frontmatter 종료(---) 없음")

    fm_lines_raw = lines[1:close_idx]
    frontmatter_lines = [(i + 2, fm_lines_raw[i]) for i in range(len(fm_lines_raw))]
    fm_text = "\n".join(fm_lines_raw)

    try:
        frontmatter = yaml.load(fm_text, Loader=_StrictSafeLoader)
    except DuplicateKeyError as exc:
        return ParseError(display, "E_YAML_DUPLICATE_KEY", f"frontmatter 중복 키: {exc}")
    except yaml.YAMLError as exc:
        return ParseError(display, "E_YAML_MALFORMED", f"frontmatter YAML 파싱 실패: {exc}")

    if frontmatter is None:
        frontmatter = {}
    if not isinstance(frontmatter, dict):
        return ParseError(display, "E_YAML_MALFORMED", "frontmatter가 YAML 매핑(dict)이 아님")

    body_lines_raw = lines[close_idx + 1 :]
    body_start = close_idx + 2  # 1-기준 파일 줄 번호(닫는 --- 다음 줄)
    body_numbered = [(body_start + i, body_lines_raw[i]) for i in range(len(body_lines_raw))]

    view_a_texts = _mask_fences([t for _, t in body_numbered])
    view_a = [(body_numbered[i][0], view_a_texts[i]) for i in range(len(body_numbered))]

    view_b_texts = [_mask_inline_code(t) for t in view_a_texts]
    view_b = [(body_numbered[i][0], view_b_texts[i]) for i in range(len(body_numbered))]

    return ParsedDocument(
        path=display,
        kind=kind,
        topic=path.stem,
        frontmatter=frontmatter,
        frontmatter_lines=frontmatter_lines,
        body_view_a=view_a,
        body_view_b=view_b,
    )


def load_all(
    root: Path,
) -> tuple[dict[str, list[ParsedDocument]], list[ParseError], set[tuple[str, str]]]:
    """root 하위 4종 디렉터리를 탐색해 전부 로드.

    반환: (종류별 성공 문서 목록, 오류 목록, 파싱 실패한 (kind, topic) 집합).
    마지막 값은 C3가 "대상 문서 부재"와 "대상 문서는 있으나 파싱 오류"를 구분하는 데 쓴다.
    """
    discovered = discover(root)
    documents: dict[str, list[ParsedDocument]] = {kind: [] for kind in KINDS}
    errors: list[ParseError] = []
    errored_topics: set[tuple[str, str]] = set()
    for kind, paths in discovered.items():
        for p in paths:
            result = load_document(p, kind)
            if isinstance(result, ParseError):
                errors.append(result)
                errored_topics.add((kind, p.stem))
            else:
                documents[kind].append(result)
    return documents, errors, errored_topics


# --- 코드펜스·인라인 코드 마스킹 ---


def _mask_fences(lines: list[str]) -> list[str]:
    """``` 또는 ~~~ (3개 이상) 펜스 블록 내부(+구분선 자체)를 빈 줄로 마스킹.

    중첩 펜스는 다루지 않는다(단일 레벨 상태머신). 여는 펜스는 trailing 정보
    문자열을 허용하지만, 닫는 펜스는 같은 문자·같거나 더 긴 길이의 구분선 뒤에
    공백만 허용한다(§A-3, CommonMark). trailing에 다른 문자가 있으면 그 줄은
    "닫는 펜스가 아닌, 여전히 코드 블록 내부의 한 줄"로 취급돼 블록이 계속 열려
    있는다(마스킹 탈출 방지).
    """
    out: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line in lines:
        if not in_fence:
            m = _FENCE_OPEN_RE.match(line)
            # CommonMark: 백틱 펜스의 여는 줄 info string엔 백틱이 올 수 없다(인라인 코드
            # 스팬과 모호). trailing에 백틱이 있으면 유효한 여는 펜스가 아니므로 일반 줄로
            # 둔다 — 아니면 `​```lang`x` 뒤 내용이 코드로 마스킹돼 C4/C5(미치환·금지어)를
            # 숨기는 우회가 생긴다(§A-3, 다중모델 리뷰 라운드9). 틸드(~~~)는 info에 백틱 허용.
            if m and not (m.group(2)[0] == "`" and "`" in line[m.end():]):
                in_fence = True
                fence_char = m.group(2)[0]
                fence_len = len(m.group(2))
                out.append("")
            else:
                out.append(line)
        else:
            m = _FENCE_CLOSE_RE.match(line)
            if m and m.group(2)[0] == fence_char and len(m.group(2)) >= fence_len:
                in_fence = False
                out.append("")
            else:
                out.append("")
    return out


def _mask_inline_code(line: str) -> str:
    """인라인 코드(백틱 구간)를 같은 길이의 공백으로 마스킹(줄 길이·줄 번호 불변).

    CommonMark 코드 스팬 규칙대로 직접 스캔한다(§A-2): 여는 백틱런과 정확히 같은
    '길이'의 백틱런만 닫는 런으로 인정한다. 기존 `(`+)(.+?)\\1`(backreference) 방식은
    더 긴 런의 앞부분 부분열까지 같은 글자수라는 이유로 닫는 런으로 오인해(예: 길이
    2 여는 런을 길이 3인 런의 처음 2글자로 닫아버림) 그 사이 텍스트를 코드로
    잘못 감추거나(정상 텍스트·금지어 은닉), 반대로 남는 텍스트가 갈 곳을 잃어
    금지어가 새게 만들었다 — 백틱런을 토큰화해 맞는 길이의 "다음 런"만 짝짓는다.
    """
    runs = list(_BACKTICK_RUN_RE.finditer(line))
    if len(runs) < 2:
        return line

    mask_spans: list[tuple[int, int]] = []
    i = 0
    while i < len(runs):
        opener = runs[i]
        closer_idx = None
        for j in range(i + 1, len(runs)):
            if len(runs[j].group(0)) == len(opener.group(0)):
                closer_idx = j
                break
        if closer_idx is None:
            i += 1
            continue
        mask_spans.append((opener.start(), runs[closer_idx].end()))
        # 닫는 런 바로 다음 런부터 새 여는 후보로 계속 스캔(non-overlapping).
        i = closer_idx + 1

    if not mask_spans:
        return line

    out_chars = list(line)
    for start, end in mask_spans:
        for k in range(start, end):
            out_chars[k] = " "
    return "".join(out_chars)
