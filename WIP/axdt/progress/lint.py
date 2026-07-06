"""progress.md ↔ report/*.md 정합성 검사 — §4 lint 규칙.

table.py(구조 파싱)와 schema.py(상태 어휘·정합 매트릭스)를 조합해 다음을
Finding 목록으로 보고한다. 순수 로직 + 파일 읽기만 하며 아무것도 고치지 않는다.

1) 구조: progress.md가 table.parse_progress로 파싱되지 않으면 그 자리에서
   ``table-structure`` ERROR 하나만 반환한다(구조가 깨지면 행을 못 보므로
   행 단위 검사는 생략한다).
2) 행 단위(§4.1): status 어휘, task id 형식, wave 접두 일치, updated 날짜
   형식, task id 중복.
3) 참조 무결성(§4.2): task의 canonical report 경로(``report_dir/{task}.md``)
   존재 시 파싱해 id·status를 검사하고, report_dir를 스캔해 progress에
   대응 행이 없는 task-형식 파일명을 orphan-report로 경고한다.
4) 정합 매트릭스(§4.3): report 상태(또는 파일 부재=None)와 progress 상태의
   조합을 schema.pair_severity로 판정한다. bad-status 행이거나 report가
   깨진 행은 판정에 필요한 값이 불명확하므로 pair 검사를 생략한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from axdt.infra import naming
from axdt.progress import schema, table

__all__ = ["Finding", "lint"]

_UPDATED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Finding:
    severity: str  # "ERROR" | "WARN"
    code: str
    task: str | None
    message: str


def lint(progress_path: Path, report_dir: Path) -> list[Finding]:
    text = progress_path.read_text(encoding="utf-8")
    try:
        rows = table.parse_progress(text)
    except table.ProgressFormatError as exc:
        return [Finding("ERROR", "table-structure", None, str(exc))]

    task_counts: dict[str, int] = {}
    for row in rows:
        task_counts[row.task] = task_counts.get(row.task, 0) + 1

    findings: list[Finding] = []
    for row in rows:
        findings.extend(_lint_row(row, task_counts, report_dir))

    findings.extend(_scan_orphan_reports(rows, report_dir))
    return findings


def _lint_row(
    row: table.TaskRow, task_counts: dict[str, int], report_dir: Path
) -> list[Finding]:
    findings: list[Finding] = []
    task = row.task

    status_ok = row.status in schema.PROGRESS_STATUSES
    if not status_ok:
        findings.append(
            Finding("ERROR", "bad-status", task, f"unknown progress status: {row.status!r}")
        )

    if not naming.is_valid(task):
        findings.append(Finding("ERROR", "bad-task-id", task, f"invalid task id: {task!r}"))
    else:
        expected_wave = f"w{naming.parse(task).wave}"
        if row.wave != expected_wave:
            findings.append(
                Finding(
                    "ERROR",
                    "wave-mismatch",
                    task,
                    f"wave column {row.wave!r} does not match task id wave prefix "
                    f"{expected_wave!r}",
                )
            )

    if not _UPDATED_RE.match(row.updated):
        findings.append(
            Finding("ERROR", "bad-updated", task, f"invalid updated date format: {row.updated!r}")
        )

    if task_counts.get(task, 0) > 1:
        findings.append(Finding("ERROR", "dup-task", task, f"duplicate task id: {task!r}"))

    rep_status, rep_usable, ref_findings = _check_report(task, report_dir)
    findings.extend(ref_findings)

    if status_ok and rep_usable:
        sev = schema.pair_severity(rep_status, row.status)
        if sev is not None:
            findings.append(
                Finding(
                    sev,
                    "pair",
                    task,
                    f"report={rep_status!r} progress={row.status!r}",
                )
            )

    return findings


def _check_report(task: str, report_dir: Path) -> tuple[str | None, bool, list[Finding]]:
    """canonical report 파일을 읽어 (report.status 또는 None, 사용가능여부, findings)."""
    findings: list[Finding] = []
    report_path = report_dir / f"{task}.md"
    if not report_path.is_file():
        return None, True, findings

    text = report_path.read_text(encoding="utf-8")
    try:
        report = table.parse_report(text)
    except table.ReportFormatError as exc:
        findings.append(Finding("ERROR", "report-frontmatter", task, str(exc)))
        return None, False, findings

    usable = True
    if report.id != task:
        findings.append(
            Finding(
                "ERROR",
                "report-id-mismatch",
                task,
                f"report id {report.id!r} != task {task!r}",
            )
        )
        usable = False
    if report.status not in schema.REPORT_STATUSES:
        findings.append(
            Finding("ERROR", "report-status", task, f"unknown report status: {report.status!r}")
        )
        usable = False

    if not usable:
        return None, False, findings
    return report.status, True, findings


def _scan_orphan_reports(rows: list[table.TaskRow], report_dir: Path) -> list[Finding]:
    if not report_dir.is_dir():
        return []

    task_set = {row.task for row in rows}
    findings: list[Finding] = []
    for path in sorted(report_dir.iterdir()):
        if not path.is_file() or path.suffix != ".md":
            continue
        stem = path.stem
        if not naming.is_valid(stem):
            continue
        if stem not in task_set:
            findings.append(
                Finding("WARN", "orphan-report", stem, f"orphan report file: {path.name}")
            )
    return findings
