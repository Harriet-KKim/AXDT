"""lint.py — progress.md ↔ report/*.md 정합성 검사 계약 검증.

§4.1(행 단위)·§4.2(참조 무결성)·§4.3(정합 매트릭스) 규칙을 각각 검증한다.
매트릭스 검증은 report 6종(5개 상태 + 파일 부재) x progress 8종 = 48셀 전부를
파라미터라이즈해 schema.pair_severity와 lint 결과가 정확히 일치함을 증명한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from axdt.progress import schema, table
from axdt.progress.lint import Finding, lint
from axdt.progress.table import TaskRow


def _write_progress(progress_path: Path, rows: list[TaskRow]) -> None:
    progress_path.write_text(table.render_progress(rows), encoding="utf-8")


def _write_report(report_dir: Path, filename_stem: str, id_value: str, status_value: str) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"{filename_stem}.md").write_text(
        f"---\nid: {id_value}\nstatus: {status_value}\n---\n\n본문.\n",
        encoding="utf-8",
    )


# --- §4.3 정합 매트릭스: report 6종 x progress 8종 = 48셀 전부 ---

_REPORT_KINDS = ["todo", "in-progress", "blocked", "done", "needs-spec", None]


@pytest.mark.parametrize("prog", sorted(schema.PROGRESS_STATUSES))
@pytest.mark.parametrize("rep", _REPORT_KINDS)
def test_matrix_cell_matches_schema_pair_severity(tmp_path, rep, prog):
    task = "w1.t1-matrix-cell"
    progress_path = tmp_path / "progress.md"
    _write_progress(progress_path, [TaskRow("w1", task, prog, "L-alice", "2026-07-05")])
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    if rep is not None:
        _write_report(report_dir, task, task, rep)

    findings = lint(progress_path, report_dir)
    pair_findings = [f for f in findings if f.code == "pair"]

    expected = schema.pair_severity(rep, prog)
    if expected is None:
        assert pair_findings == []
    else:
        assert len(pair_findings) == 1
        assert pair_findings[0].severity == expected
        assert pair_findings[0].task == task


# --- §4.1 행 단위 ---


def test_bad_status(tmp_path):
    progress_path = tmp_path / "progress.md"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t1-hub-init", "not-a-status", "L-alice", "2026-07-05")],
    )
    report_dir = tmp_path / "reports"
    findings = lint(progress_path, report_dir)
    bad_status = [f for f in findings if f.code == "bad-status"]
    assert len(bad_status) == 1
    assert bad_status[0].severity == "ERROR"
    assert bad_status[0].task == "w1.t1-hub-init"
    # bad-status 행은 pair 검사 생략(KeyError 회피)
    assert not any(f.code == "pair" for f in findings)


def test_bad_task_id(tmp_path):
    progress_path = tmp_path / "progress.md"
    _write_progress(
        progress_path,
        [TaskRow("w1", "not_a_valid_task_id", "todo", "L-alice", "2026-07-05")],
    )
    report_dir = tmp_path / "reports"
    findings = lint(progress_path, report_dir)
    bad_task_id = [f for f in findings if f.code == "bad-task-id"]
    assert len(bad_task_id) == 1
    assert bad_task_id[0].severity == "ERROR"
    assert bad_task_id[0].task == "not_a_valid_task_id"


def test_wave_mismatch(tmp_path):
    progress_path = tmp_path / "progress.md"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w2.t1-hub-init", "todo", "L-alice", "2026-07-05")],
    )
    report_dir = tmp_path / "reports"
    findings = lint(progress_path, report_dir)
    wave_mismatch = [f for f in findings if f.code == "wave-mismatch"]
    assert len(wave_mismatch) == 1
    assert wave_mismatch[0].severity == "ERROR"
    assert wave_mismatch[0].task == "w2.t1-hub-init"


def test_bad_updated(tmp_path):
    progress_path = tmp_path / "progress.md"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t1-hub-init", "todo", "L-alice", "07-05-2026")],
    )
    report_dir = tmp_path / "reports"
    findings = lint(progress_path, report_dir)
    bad_updated = [f for f in findings if f.code == "bad-updated"]
    assert len(bad_updated) == 1
    assert bad_updated[0].severity == "ERROR"
    assert bad_updated[0].task == "w1.t1-hub-init"


def test_dup_task(tmp_path):
    progress_path = tmp_path / "progress.md"
    _write_progress(
        progress_path,
        [
            TaskRow("w1", "w1.t1-hub-init", "todo", "L-alice", "2026-07-05"),
            TaskRow("w1", "w1.t1-hub-init", "in-progress", "L-bob", "2026-07-06"),
        ],
    )
    report_dir = tmp_path / "reports"
    findings = lint(progress_path, report_dir)
    dup_task = [f for f in findings if f.code == "dup-task"]
    assert len(dup_task) == 2
    assert all(f.severity == "ERROR" and f.task == "w1.t1-hub-init" for f in dup_task)


# --- 구조 (table.parse_progress 실패 시 행 검사 생략) ---


def test_structure_zero_tables(tmp_path):
    progress_path = tmp_path / "progress.md"
    progress_path.write_text("# Progress\n\n표가 없는 문서.\n", encoding="utf-8")
    report_dir = tmp_path / "reports"
    findings = lint(progress_path, report_dir)
    assert len(findings) == 1
    assert findings[0] == Finding("ERROR", "table-structure", None, findings[0].message)


def test_structure_two_tables(tmp_path):
    progress_path = tmp_path / "progress.md"
    progress_path.write_text(
        """| wave | task | status | leader | updated |
|---|---|---|---|---|
| w1 | w1.t1-hub-init | accepted | L-alice | 2026-07-05 |

| wave | task | status | leader | updated |
|---|---|---|---|---|
| w2 | w2.t1-auth-login | blocked | L-carol | 2026-07-05 |
""",
        encoding="utf-8",
    )
    report_dir = tmp_path / "reports"
    findings = lint(progress_path, report_dir)
    assert len(findings) == 1
    assert findings[0].severity == "ERROR"
    assert findings[0].code == "table-structure"
    assert findings[0].task is None


def test_structure_header_mismatch(tmp_path):
    progress_path = tmp_path / "progress.md"
    progress_path.write_text(
        """| wave | task | state | leader | updated |
|---|---|---|---|---|
| w1 | w1.t1-hub-init | accepted | L-alice | 2026-07-05 |
""",
        encoding="utf-8",
    )
    report_dir = tmp_path / "reports"
    findings = lint(progress_path, report_dir)
    assert len(findings) == 1
    assert findings[0].severity == "ERROR"
    assert findings[0].code == "table-structure"


# --- §4.2 참조 무결성 ---


def test_report_id_mismatch(tmp_path):
    task = "w1.t1-hub-init"
    progress_path = tmp_path / "progress.md"
    _write_progress(progress_path, [TaskRow("w1", task, "todo", "L-alice", "2026-07-05")])
    report_dir = tmp_path / "reports"
    _write_report(report_dir, task, "w1.t2-other-task", "todo")

    findings = lint(progress_path, report_dir)
    mismatch = [f for f in findings if f.code == "report-id-mismatch"]
    assert len(mismatch) == 1
    assert mismatch[0].severity == "ERROR"
    assert mismatch[0].task == task
    # report가 깨졌으니 pair 검사는 생략
    assert not any(f.code == "pair" for f in findings)


def test_report_frontmatter_missing(tmp_path):
    task = "w1.t1-hub-init"
    progress_path = tmp_path / "progress.md"
    _write_progress(progress_path, [TaskRow("w1", task, "todo", "L-alice", "2026-07-05")])
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    (report_dir / f"{task}.md").write_text("# report\n\nfrontmatter 없음.\n", encoding="utf-8")

    findings = lint(progress_path, report_dir)
    frontmatter = [f for f in findings if f.code == "report-frontmatter"]
    assert len(frontmatter) == 1
    assert frontmatter[0].severity == "ERROR"
    assert frontmatter[0].task == task
    assert not any(f.code == "pair" for f in findings)


def test_report_status_not_controlled(tmp_path):
    task = "w1.t1-hub-init"
    progress_path = tmp_path / "progress.md"
    _write_progress(progress_path, [TaskRow("w1", task, "todo", "L-alice", "2026-07-05")])
    report_dir = tmp_path / "reports"
    # "accepted"는 progress 상태이지 REPORT_STATUSES에는 없음.
    _write_report(report_dir, task, task, "accepted")

    findings = lint(progress_path, report_dir)
    bad_report_status = [f for f in findings if f.code == "report-status"]
    assert len(bad_report_status) == 1
    assert bad_report_status[0].severity == "ERROR"
    assert bad_report_status[0].task == task
    assert not any(f.code == "pair" for f in findings)


def test_orphan_report_flagged(tmp_path):
    progress_path = tmp_path / "progress.md"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t1-hub-init", "todo", "L-alice", "2026-07-05")],
    )
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    _write_report(report_dir, "w1.t1-hub-init", "w1.t1-hub-init", "todo")
    # progress.md에 대응 행이 없는 orphan report.
    _write_report(report_dir, "w9.t9-orphan-task", "w9.t9-orphan-task", "todo")

    findings = lint(progress_path, report_dir)
    orphans = [f for f in findings if f.code == "orphan-report"]
    assert len(orphans) == 1
    assert orphans[0].severity == "WARN"
    assert orphans[0].task == "w9.t9-orphan-task"


def test_non_task_file_not_flagged_as_orphan(tmp_path):
    progress_path = tmp_path / "progress.md"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t1-hub-init", "todo", "L-alice", "2026-07-05")],
    )
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    _write_report(report_dir, "w1.t1-hub-init", "w1.t1-hub-init", "todo")
    (report_dir / "README.md").write_text("# README\n", encoding="utf-8")
    (report_dir / "_TEMPLATE.md").write_text("# template\n", encoding="utf-8")

    findings = lint(progress_path, report_dir)
    orphans = [f for f in findings if f.code == "orphan-report"]
    assert orphans == []


def test_report_absent_is_not_an_error(tmp_path):
    task = "w1.t1-hub-init"
    progress_path = tmp_path / "progress.md"
    _write_progress(progress_path, [TaskRow("w1", task, "todo", "L-alice", "2026-07-05")])
    report_dir = tmp_path / "reports"  # 생성하지 않음(디렉터리 자체가 없음)

    findings = lint(progress_path, report_dir)
    assert not any(
        f.code in ("report-id-mismatch", "report-frontmatter", "report-status")
        for f in findings
    )
