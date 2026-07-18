"""progress.md 테이블 ↔ 객체 파싱/직렬화 + report.md frontmatter 파싱.

구조 파싱만 담당한다. 셀 값의 의미 검사(status 어휘·task id 형식·wave 접두
일치·중복·날짜 형식 등)는 하지 않는다 — 그것은 lint 모듈의 몫이다. 컬럼
이름·순서는 schema.COLUMNS를 단일 정의원으로 참조한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from axdt.progress import schema

__all__ = [
    "TaskRow",
    "Report",
    "ProgressFormatError",
    "ReportFormatError",
    "parse_progress",
    "render_progress",
    "parse_report",
]


class ProgressFormatError(ValueError):
    """parse_progress: MD 테이블 구조 위반(0개/2개 이상, 헤더 불일치, 구분행 없음 등)."""


class ReportFormatError(ValueError):
    """parse_report: frontmatter 부재 또는 id/status 키 누락."""


@dataclass
class TaskRow:
    wave: str
    task: str
    status: str
    leader: str
    updated: str


@dataclass
class Report:
    id: str
    status: str


_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")


def _is_row_line(line: str) -> bool:
    return line.strip().startswith("|")


def _split_row(line: str) -> list[str]:
    stripped = line.strip()
    inner = stripped[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def _is_separator_row(line: str) -> bool:
    cells = _split_row(line)
    return bool(cells) and all(_SEPARATOR_CELL_RE.match(cell) for cell in cells)


def _find_table_blocks(lines: list[str]) -> list[list[str]]:
    """연속된 '|'-시작 행들을 블록으로 묶는다(프로즈·빈 줄이 블록을 끊는다)."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _is_row_line(line):
            current.append(line)
        else:
            if current:
                blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def parse_progress(text: str) -> list[TaskRow]:
    lines = text.splitlines()
    blocks = _find_table_blocks(lines)
    # 유효한 테이블 = 2줄 이상이고 2번째 줄이 구분행인 블록. 구분행이 없는
    # '|'-블록은 유효 테이블로 세지 않는다 → 0개로 취급되어 아래에서 에러.
    valid_blocks = [
        block for block in blocks if len(block) >= 2 and _is_separator_row(block[1])
    ]
    if len(valid_blocks) != 1:
        raise ProgressFormatError(
            f"progress.md must contain exactly 1 table, found {len(valid_blocks)}"
        )

    block = valid_blocks[0]
    header = tuple(_split_row(block[0]))
    if header != schema.COLUMNS:
        raise ProgressFormatError(
            f"table header {header!r} does not match schema.COLUMNS {schema.COLUMNS!r}"
        )

    rows: list[TaskRow] = []
    for row_line in block[2:]:
        cells = _split_row(row_line)
        if len(cells) != len(schema.COLUMNS):
            raise ProgressFormatError(
                f"row has {len(cells)} cells, expected {len(schema.COLUMNS)}: {row_line!r}"
            )
        rows.append(TaskRow(*cells))
    return rows


def render_progress(rows: list[TaskRow]) -> str:
    lines = [
        "| " + " | ".join(schema.COLUMNS) + " |",
        "|" + "|".join(["---"] * len(schema.COLUMNS)) + "|",
    ]
    for row in rows:
        cells = (row.wave, row.task, row.status, row.leader, row.updated)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


# 선행 BOM(﻿)은 옵션, 줄바꿈은 \r\n(CRLF)·\n(LF) 둘 다 허용한다 -- git으로 커밋된
# report 블롭이 CRLF로 저장돼 있어도 과claim 판정에서 오거부되지 않도록. 내부 라인
# 파싱은 splitlines()라 \r\n을 이미 안전하게 처리한다(추가 조치 불필요).
_FRONTMATTER_RE = re.compile(r"^﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", re.DOTALL)


def parse_report(text: str) -> Report:
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise ReportFormatError("report frontmatter (leading '---' block) not found")

    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        values[key.strip()] = value.strip()

    missing = [key for key in ("id", "status") if key not in values]
    if missing:
        raise ReportFormatError(f"report frontmatter missing key(s): {missing!r}")

    return Report(id=values["id"], status=values["status"])


def report_body(text: str) -> str:
    """report 원문에서 frontmatter 블록 이후의 본문을 반환한다.

    frontmatter(선행 '---' 블록)가 없으면 ReportFormatError. parse_report와
    **같은** frontmatter 경계 판정(`_FRONTMATTER_RE`)을 쓰므로, status 파싱과
    본문 슬라이스의 경계가 어긋나지 않는다(단일 진실원 — 소비자가 경계 판정을
    재구현하지 않도록 공개 헬퍼로 노출).
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise ReportFormatError("report frontmatter (leading '---' block) not found")
    return text[match.end() :]
