"""recover.py — progress.md + report/*.md → 구조화 상태(State) 복원 계약 검증.

reconstruct()는 progress.md를 권위 소스로 삼아 각 task의 상태를 복원하고,
report.md의 상태를 곁들여 여러 관점(수용 대기·재작업·블로커 등)으로 분류한다.
report.md가 깨져 있는 경우(파싱 실패·id 불일치·비통제 status) '부재'로 뭉개지
않고 report_invalid=True로 별도 표기해야 한다 — 그래야 done으로 오분류되어
pending_acceptance를 왜곡하는 일이 없다.
"""
from pathlib import Path

from axdt.progress import schema
from axdt.progress.recover import State, TaskState, format_summary, reconstruct
from axdt.progress.table import TaskRow, render_progress


def _write_progress(path: Path, rows: list[TaskRow]) -> None:
    path.write_text(render_progress(rows), encoding="utf-8")


def _write_report(
    report_dir: Path, filename_task: str, *, id_: str | None = None, status: str
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    rid = filename_task if id_ is None else id_
    text = f"---\nid: {rid}\nstatus: {status}\n---\n\n본문.\n"
    (report_dir / f"{filename_task}.md").write_text(text, encoding="utf-8")


def _write_broken_report(report_dir: Path, filename_task: str) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"{filename_task}.md").write_text(
        "# report\n\nfrontmatter 없음.\n", encoding="utf-8"
    )


def _find(items: list[TaskState], task: str) -> TaskState:
    matches = [item for item in items if item.task == task]
    assert len(matches) == 1, f"{task} expected exactly once in {items!r}"
    return matches[0]


def _tasks(items: list[TaskState]) -> set[str]:
    return {item.task for item in items}


# --- pending_acceptance ---


def test_pending_acceptance_includes_done_report_not_yet_accepted(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t1-a", "in-review", "L-alice", "2026-07-05")],
    )
    _write_report(report_dir, "w1.t1-a", status="done")

    state = reconstruct(progress_path, report_dir)

    assert "w1.t1-a" in _tasks(state.pending_acceptance)
    task_state = _find(state.pending_acceptance, "w1.t1-a")
    assert task_state.report == "done"
    assert task_state.progress == "in-review"
    assert task_state.report_invalid is False


def test_pending_acceptance_excludes_accepted_progress(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t2-b", "accepted", "L-alice", "2026-07-05")],
    )
    _write_report(report_dir, "w1.t2-b", status="done")

    state = reconstruct(progress_path, report_dir)

    assert "w1.t2-b" not in _tasks(state.pending_acceptance)


def test_pending_acceptance_excludes_superseded_progress(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t3-c", "superseded", "L-alice", "2026-07-05")],
    )
    _write_report(report_dir, "w1.t3-c", status="done")

    state = reconstruct(progress_path, report_dir)

    assert "w1.t3-c" not in _tasks(state.pending_acceptance)


# --- pending_blocker_acceptance ---


def test_pending_blocker_acceptance_report_blocked_progress_todo(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w2", "w2.t1-x", "todo", "L-bob", "2026-07-05")],
    )
    _write_report(report_dir, "w2.t1-x", status="blocked")

    state = reconstruct(progress_path, report_dir)

    assert "w2.t1-x" in _tasks(state.pending_blocker_acceptance)


def test_pending_blocker_acceptance_report_needs_spec_progress_in_review(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w2", "w2.t2-y", "in-review", "L-bob", "2026-07-05")],
    )
    _write_report(report_dir, "w2.t2-y", status="needs-spec")

    state = reconstruct(progress_path, report_dir)

    assert "w2.t2-y" in _tasks(state.pending_blocker_acceptance)


def test_pending_blocker_acceptance_excludes_progress_accepted(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w2", "w2.t3-z", "accepted", "L-bob", "2026-07-05")],
    )
    _write_report(report_dir, "w2.t3-z", status="blocked")

    state = reconstruct(progress_path, report_dir)

    assert "w2.t3-z" not in _tasks(state.pending_blocker_acceptance)


# --- in_rework ---


def test_in_rework_for_rejected_progress(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t4-d", "rejected", "L-alice", "2026-07-05")],
    )
    # report 파일 없음(권위 아님, 부재)

    state = reconstruct(progress_path, report_dir)

    assert "w1.t4-d" in _tasks(state.in_rework)
    task_state = _find(state.in_rework, "w1.t4-d")
    assert task_state.report is None
    assert task_state.report_invalid is False


# --- blocked_or_paused ---


def test_blocked_or_paused(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [
            TaskRow("w1", "w1.t5-e", "blocked", "L-alice", "2026-07-05"),
            TaskRow("w1", "w1.t6-f", "paused", "L-alice", "2026-07-05"),
        ],
    )
    _write_report(report_dir, "w1.t6-f", status="todo")

    state = reconstruct(progress_path, report_dir)

    assert _tasks(state.blocked_or_paused) == {"w1.t5-e", "w1.t6-f"}
    # report=None+progress=blocked, report=todo+progress=paused 둘 다
    # pair_severity가 None이라 needs_attention에는 들어가지 않는다.
    assert "w1.t5-e" not in _tasks(state.needs_attention)
    assert "w1.t6-f" not in _tasks(state.needs_attention)


# --- 깨진 report: 파싱 실패 ---


def test_broken_report_parse_failure_marks_invalid_not_absent(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t7-g", "in-review", "L-alice", "2026-07-05")],
    )
    _write_broken_report(report_dir, "w1.t7-g")

    state = reconstruct(progress_path, report_dir)

    task_state = _find(state.tasks, "w1.t7-g")
    assert task_state.report is None
    assert task_state.report_invalid is True
    assert "w1.t7-g" in _tasks(state.needs_attention)
    # done으로 오분류되어 pending_acceptance를 왜곡하면 안 된다.
    assert "w1.t7-g" not in _tasks(state.pending_acceptance)


# --- 깨진 report: id 불일치 ---


def test_broken_report_id_mismatch_marks_invalid(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t8-h", "todo", "L-alice", "2026-07-05")],
    )
    _write_report(report_dir, "w1.t8-h", id_="w1.t-wrong-id", status="done")

    state = reconstruct(progress_path, report_dir)

    task_state = _find(state.tasks, "w1.t8-h")
    assert task_state.report is None
    assert task_state.report_invalid is True
    assert "w1.t8-h" in _tasks(state.needs_attention)
    assert "w1.t8-h" not in _tasks(state.pending_acceptance)


# --- 깨진 report: 비통제 status ---


def test_broken_report_uncontrolled_status_marks_invalid(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t9-i", "todo", "L-alice", "2026-07-05")],
    )
    # "accepted"는 REPORT_STATUSES에 없는 값(schema.REPORT_STATUSES 참조).
    assert "accepted" not in schema.REPORT_STATUSES
    _write_report(report_dir, "w1.t9-i", status="accepted")

    state = reconstruct(progress_path, report_dir)

    task_state = _find(state.tasks, "w1.t9-i")
    assert task_state.report is None
    assert task_state.report_invalid is True
    assert "w1.t9-i" in _tasks(state.needs_attention)


# --- report 부재(정상 케이스, invalid 아님) ---


def test_missing_report_file_sets_report_none_not_invalid(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t10-j", "todo", "L-alice", "2026-07-05")],
    )
    report_dir.mkdir(parents=True, exist_ok=True)  # 디렉터리는 있지만 파일 없음

    state = reconstruct(progress_path, report_dir)

    task_state = _find(state.tasks, "w1.t10-j")
    assert task_state.report is None
    assert task_state.report_invalid is False


# --- needs_attention: pair_severity 매트릭스와 일치 ---


def test_needs_attention_report_none_progress_in_review_is_warn(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t11-k", "in-review", "L-alice", "2026-07-05")],
    )
    report_dir.mkdir(parents=True, exist_ok=True)

    state = reconstruct(progress_path, report_dir)

    assert schema.pair_severity(None, "in-review") == "WARN"
    assert "w1.t11-k" in _tasks(state.needs_attention)


def test_needs_attention_report_blocked_progress_accepted_is_error(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t12-l", "accepted", "L-alice", "2026-07-05")],
    )
    _write_report(report_dir, "w1.t12-l", status="blocked")

    state = reconstruct(progress_path, report_dir)

    assert schema.pair_severity("blocked", "accepted") == "ERROR"
    assert "w1.t12-l" in _tasks(state.needs_attention)


def test_needs_attention_excludes_clean_pairs(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [TaskRow("w1", "w1.t13-m", "todo", "L-alice", "2026-07-05")],
    )
    _write_report(report_dir, "w1.t13-m", status="todo")

    state = reconstruct(progress_path, report_dir)

    assert schema.pair_severity("todo", "todo") is None
    assert "w1.t13-m" not in _tasks(state.needs_attention)


# --- wave_rollup ---


def test_wave_rollup_matches_schema_per_wave(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [
            TaskRow("w1", "w1.t1-a", "accepted", "L-alice", "2026-07-05"),
            TaskRow("w1", "w1.t2-b", "todo", "L-alice", "2026-07-05"),
            TaskRow("w2", "w2.t1-c", "blocked", "L-carol", "2026-07-05"),
            TaskRow("w2", "w2.t2-d", "in-progress", "L-carol", "2026-07-05"),
            TaskRow("w3", "w3.t1-e", "accepted", "L-dan", "2026-07-05"),
            TaskRow("w3", "w3.t2-f", "superseded", "L-dan", "2026-07-05"),
        ],
    )

    state = reconstruct(progress_path, report_dir)

    assert state.wave_rollup == {
        "w1": schema.wave_rollup(["accepted", "todo"]),
        "w2": schema.wave_rollup(["blocked", "in-progress"]),
        "w3": schema.wave_rollup(["accepted", "superseded"]),
    }
    assert state.wave_rollup["w1"] == "in-progress"
    assert state.wave_rollup["w2"] == "blocked"
    assert state.wave_rollup["w3"] == "done"


# --- format_summary ---


def test_format_summary_includes_each_section_task_id(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(
        progress_path,
        [
            TaskRow("w1", "w1.t1-pending", "in-review", "L-alice", "2026-07-05"),
            TaskRow("w1", "w1.t2-blocker", "todo", "L-alice", "2026-07-05"),
            TaskRow("w1", "w1.t3-rework", "rejected", "L-alice", "2026-07-05"),
            TaskRow("w1", "w1.t4-paused", "paused", "L-alice", "2026-07-05"),
            TaskRow("w1", "w1.t5-attn", "in-review", "L-alice", "2026-07-05"),
        ],
    )
    _write_report(report_dir, "w1.t1-pending", status="done")
    _write_report(report_dir, "w1.t2-blocker", status="blocked")
    # w1.t3-rework, w1.t4-paused: report 없음
    # w1.t5-attn: report 없음 -> pair_severity(None, "in-review") == WARN

    state = reconstruct(progress_path, report_dir)
    summary = format_summary(state)

    assert "w1.t1-pending" in summary
    assert "w1.t2-blocker" in summary
    assert "w1.t3-rework" in summary
    assert "w1.t4-paused" in summary
    assert "w1.t5-attn" in summary


def test_format_summary_empty_state_has_no_crash(tmp_path):
    progress_path = tmp_path / "progress.md"
    report_dir = tmp_path / "report"
    _write_progress(progress_path, [])

    state = reconstruct(progress_path, report_dir)
    summary = format_summary(state)

    assert isinstance(summary, str)
    assert state.tasks == []
