"""table.py — progress MD 테이블 파싱/직렬화 + report frontmatter 파싱 계약 검증.

table.py는 구조 파싱만 한다. 셀 값의 의미 검사(status 어휘·task id 형식 등)는
하지 않으므로 이 테스트도 그 경계를 명시적으로 확인한다(lint 몫과의 구분).
"""
import pytest

from axdt.progress import schema
from axdt.progress.table import (
    ProgressFormatError,
    Report,
    ReportFormatError,
    TaskRow,
    parse_progress,
    parse_report,
    render_progress,
)


# --- 라운드트립 ---


def test_roundtrip_multiple_rows():
    rows = [
        TaskRow("w1", "w1.t1-hub-init", "accepted", "L-alice", "2026-07-05"),
        TaskRow("w2", "w2.t1-auth-login", "blocked", "L-carol", "2026-07-05"),
    ]
    assert parse_progress(render_progress(rows)) == rows


def test_roundtrip_single_row():
    rows = [TaskRow("w1", "w1.t1-hub-init", "todo", "L-bob", "2026-07-06")]
    assert parse_progress(render_progress(rows)) == rows


def test_roundtrip_empty():
    assert parse_progress(render_progress([])) == []


def test_render_progress_empty_has_header_and_separator_only():
    lines = [line for line in render_progress([]).splitlines() if line.strip()]
    assert lines == [
        "| wave | task | status | leader | updated |",
        "|---|---|---|---|---|",
    ]


# --- 실제 파일 형태(프로즈 포함) ---


def test_parse_progress_with_surrounding_prose():
    text = """# Progress

이 문서는 진척 현황을 기록한다.

| wave | task | status | leader | updated |
|---|---|---|---|---|
| w1 | w1.t1-hub-init | accepted | L-alice | 2026-07-05 |
| w2 | w2.t1-auth-login | blocked | L-carol | 2026-07-05 |

이하 생략.
"""
    assert parse_progress(text) == [
        TaskRow("w1", "w1.t1-hub-init", "accepted", "L-alice", "2026-07-05"),
        TaskRow("w2", "w2.t1-auth-login", "blocked", "L-carol", "2026-07-05"),
    ]


def test_parse_progress_empty_form_only_header_and_separator():
    text = """# Progress

| wave | task | status | leader | updated |
|---|---|---|---|---|
"""
    assert parse_progress(text) == []


# --- 셀 공백 strip ---


def test_parse_progress_strips_cell_whitespace():
    text = """| wave | task | status | leader | updated |
|---|---|---|---|---|
|  w1  |  w1.t1-hub-init  |  accepted  |  L-alice  |  2026-07-05  |
"""
    assert parse_progress(text) == [
        TaskRow("w1", "w1.t1-hub-init", "accepted", "L-alice", "2026-07-05")
    ]


# --- 구조 오류: parse_progress ---


def test_parse_progress_zero_tables_raises():
    text = "# Progress\n\n표가 없는 문서.\n"
    with pytest.raises(ProgressFormatError):
        parse_progress(text)


def test_parse_progress_two_tables_raises():
    text = """| wave | task | status | leader | updated |
|---|---|---|---|---|
| w1 | w1.t1-hub-init | accepted | L-alice | 2026-07-05 |

| wave | task | status | leader | updated |
|---|---|---|---|---|
| w2 | w2.t1-auth-login | blocked | L-carol | 2026-07-05 |
"""
    with pytest.raises(ProgressFormatError):
        parse_progress(text)


def test_parse_progress_wrong_header_names_raises():
    text = """| wave | task | state | leader | updated |
|---|---|---|---|---|
| w1 | w1.t1-hub-init | accepted | L-alice | 2026-07-05 |
"""
    with pytest.raises(ProgressFormatError):
        parse_progress(text)


def test_parse_progress_wrong_header_order_raises():
    text = """| task | wave | status | leader | updated |
|---|---|---|---|---|
| w1.t1-hub-init | w1 | accepted | L-alice | 2026-07-05 |
"""
    with pytest.raises(ProgressFormatError):
        parse_progress(text)


def test_parse_progress_missing_separator_raises():
    text = """| wave | task | status | leader | updated |
| w1 | w1.t1-hub-init | accepted | L-alice | 2026-07-05 |
"""
    with pytest.raises(ProgressFormatError):
        parse_progress(text)


# --- parse_report ---


def test_parse_report_normal():
    text = """---
id: w1.t1-hub-init
status: done
---

본문 내용.
"""
    assert parse_report(text) == Report(id="w1.t1-hub-init", status="done")


def test_parse_report_missing_id_raises():
    text = """---
status: done
---
"""
    with pytest.raises(ReportFormatError):
        parse_report(text)


def test_parse_report_missing_status_raises():
    text = """---
id: w1.t1-hub-init
---
"""
    with pytest.raises(ReportFormatError):
        parse_report(text)


def test_parse_report_no_frontmatter_raises():
    text = "# report\n\nid: w1.t1-hub-init\nstatus: done\n"
    with pytest.raises(ReportFormatError):
        parse_report(text)


def test_parse_report_ignores_extra_keys_and_body():
    text = """---
id: w1.t1-hub-init
status: in-progress
owner: L-alice
tags: [a, b]
---

## 본문
자유 텍스트.
"""
    assert parse_report(text) == Report(id="w1.t1-hub-init", status="in-progress")


def test_parse_report_does_not_validate_status_vocabulary():
    # "accepted"는 REPORT_STATUSES에 없는 값이지만 table.py는 값 검사를
    # 하지 않으므로 예외 없이 그대로 담겨야 한다(lint 몫과의 경계 확인).
    assert "accepted" not in schema.REPORT_STATUSES
    text = """---
id: w1.t1-hub-init
status: accepted
---
"""
    assert parse_report(text) == Report(id="w1.t1-hub-init", status="accepted")
