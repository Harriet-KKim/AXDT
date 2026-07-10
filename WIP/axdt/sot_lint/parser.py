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

# 여는 펜스: 줄 시작(최대 3칸 들여쓰기) + 백틱 또는 물결 3개 이상.
# 틸드(~~~) 펜스도 백틱과 동등하게 지원(미해결 §8 결정 — 구현 시 확정, 보고 참조).
_FENCE_RE = re.compile(r"^([ ]{0,3})(`{3,}|~{3,})")
# 인라인 코드: 같은 개수의 백틱으로 감싼 구간(백리퍼런스로 개수 일치 강제).
_INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")


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
        text = raw.decode("utf-8")
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

    중첩 펜스는 다루지 않는다(단일 레벨 상태머신). 여는 펜스와 같은 문자·같거나
    더 긴 길이의 구분선을 닫는 펜스로 인정한다(CommonMark 근사).
    """
    out: list[str] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for line in lines:
        m = _FENCE_RE.match(line)
        if not in_fence:
            if m:
                in_fence = True
                fence_char = m.group(2)[0]
                fence_len = len(m.group(2))
                out.append("")
            else:
                out.append(line)
        else:
            if m and m.group(2)[0] == fence_char and len(m.group(2)) >= fence_len:
                in_fence = False
                out.append("")
            else:
                out.append("")
    return out


def _mask_inline_code(line: str) -> str:
    """인라인 코드(백틱 구간)를 같은 길이의 공백으로 마스킹(줄 길이·줄 번호 불변)."""
    return _INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line)
