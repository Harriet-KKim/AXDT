"""progress.md + report/*.md → 구조화 상태(State) 복원.

progress.md는 권위 파일이다. 각 task의 canonical report(``report_dir /
f"{task}.md"``)를 곁들여 여러 관점(수용 대기·재작업·블로커 등)으로 분류한다.

report.md가 존재하지만 깨져 있는 경우(파싱 실패·id 불일치·비통제 status)는
'부재(None)'로 뭉개지 않고 ``report_invalid=True``로 별도 표기한다. 그렇게
하지 않으면 예컨대 report=="done"으로 오분류되어 아직 검토도 못 받은 task가
pending_acceptance(수용 대기)에서 누락되는 등 상태가 왜곡된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from axdt.progress import schema, table

__all__ = ["TaskState", "State", "reconstruct", "format_summary"]

_BLOCKER_REPORT_STATUSES = frozenset({"blocked", "needs-spec"})
_BLOCKER_PROGRESS_STATUSES = frozenset({"todo", "in-progress", "in-review", "rejected"})
_BLOCKED_OR_PAUSED_PROGRESS = frozenset({"blocked", "paused"})
_ATTENTION_SEVERITIES = frozenset({"WARN", "ERROR"})


@dataclass
class TaskState:
    task: str
    progress: str  # progress.status (권위)
    report: str | None  # report.status. 부재 또는 깨졌으면 None
    updated: str
    report_invalid: bool = False  # canonical report가 있으나 파싱실패/id불일치/비통제status


@dataclass
class State:
    tasks: list[TaskState] = field(default_factory=list)
    pending_acceptance: list[TaskState] = field(default_factory=list)
    pending_blocker_acceptance: list[TaskState] = field(default_factory=list)
    in_rework: list[TaskState] = field(default_factory=list)
    blocked_or_paused: list[TaskState] = field(default_factory=list)
    needs_attention: list[TaskState] = field(default_factory=list)
    wave_rollup: dict[str, str] = field(default_factory=dict)


def _read_canonical_report(report_dir: Path, task: str) -> tuple[str | None, bool]:
    """canonical report 파일을 읽어 (report_status, report_invalid)를 반환.

    - 파일 부재: (None, False)
    - 파싱 실패 / id 불일치 / status가 REPORT_STATUSES 밖: (None, True)
    - 정상: (status, False)
    """
    report_path = report_dir / f"{task}.md"
    if not report_path.exists():
        return None, False

    text = report_path.read_text(encoding="utf-8")
    try:
        report = table.parse_report(text)
    except table.ReportFormatError:
        return None, True

    if report.id != task:
        return None, True
    if report.status not in schema.REPORT_STATUSES:
        return None, True

    return report.status, False


def reconstruct(progress_path: Path, report_dir: Path) -> State:
    rows = table.parse_progress(progress_path.read_text(encoding="utf-8"))

    tasks: list[TaskState] = []
    pending_acceptance: list[TaskState] = []
    pending_blocker_acceptance: list[TaskState] = []
    in_rework: list[TaskState] = []
    blocked_or_paused: list[TaskState] = []
    needs_attention: list[TaskState] = []
    waves: dict[str, list[str]] = {}

    for row in rows:
        report_status, report_invalid = _read_canonical_report(report_dir, row.task)
        task_state = TaskState(
            task=row.task,
            progress=row.status,
            report=report_status,
            updated=row.updated,
            report_invalid=report_invalid,
        )
        tasks.append(task_state)
        waves.setdefault(row.wave, []).append(row.status)

        if task_state.report == "done" and task_state.progress not in schema.TERMINAL:
            pending_acceptance.append(task_state)

        if (
            task_state.report in _BLOCKER_REPORT_STATUSES
            and task_state.progress in _BLOCKER_PROGRESS_STATUSES
        ):
            pending_blocker_acceptance.append(task_state)

        if task_state.progress == "rejected":
            in_rework.append(task_state)

        if task_state.progress in _BLOCKED_OR_PAUSED_PROGRESS:
            blocked_or_paused.append(task_state)

        # progress.status가 통제 어휘(schema.PROGRESS_STATUSES) 밖이면
        # schema.pair_severity가 KeyError를 던지므로, 그 경우엔 pair_severity를
        # 호출하지 않고 곧바로 needs_attention에 넣는다(비통제 status 자체가
        # 주의 필요 사유다).
        attention = task_state.report_invalid
        if task_state.progress not in schema.PROGRESS_STATUSES:
            attention = True
        elif schema.pair_severity(task_state.report, task_state.progress) in _ATTENTION_SEVERITIES:
            attention = True
        if attention:
            needs_attention.append(task_state)

    wave_rollup = {
        wave: schema.wave_rollup(statuses) for wave, statuses in waves.items()
    }

    return State(
        tasks=tasks,
        pending_acceptance=pending_acceptance,
        pending_blocker_acceptance=pending_blocker_acceptance,
        in_rework=in_rework,
        blocked_or_paused=blocked_or_paused,
        needs_attention=needs_attention,
        wave_rollup=wave_rollup,
    )


def _render_section(title: str, items: list[TaskState]) -> list[str]:
    lines = [f"## {title}"]
    if not items:
        lines.append("없음")
    else:
        for item in items:
            flag = " (report_invalid)" if item.report_invalid else ""
            lines.append(f"- {item.task}: progress={item.progress}, report={item.report}{flag}")
    return lines


def format_summary(state: State) -> str:
    """Maintainer/web용 텍스트 요약. 각 집합을 섹션으로 나열한다."""
    lines: list[str] = []

    lines.extend(_render_section("수용 대기 (pending acceptance)", state.pending_acceptance))
    lines.extend(
        _render_section(
            "블로커/사양 수용 대기 (pending blocker acceptance)",
            state.pending_blocker_acceptance,
        )
    )
    lines.extend(_render_section("재작업 (in rework)", state.in_rework))
    lines.extend(_render_section("블로커/보류 (blocked or paused)", state.blocked_or_paused))
    lines.extend(_render_section("주의 필요 (needs attention)", state.needs_attention))

    lines.append("## wave 롤업")
    if not state.wave_rollup:
        lines.append("없음")
    else:
        for wave in sorted(state.wave_rollup):
            lines.append(f"- {wave}: {state.wave_rollup[wave]}")

    return "\n".join(lines) + "\n"
