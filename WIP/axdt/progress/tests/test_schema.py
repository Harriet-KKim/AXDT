"""schema 모듈 — 상태 상수·전이 규칙·pair_severity·wave_rollup 계약 검증."""
import pytest

from axdt.progress import schema

# --- 상수 ---


def test_report_statuses():
    assert schema.REPORT_STATUSES == frozenset(
        {"todo", "in-progress", "blocked", "done", "needs-spec"}
    )


def test_progress_statuses():
    assert schema.PROGRESS_STATUSES == frozenset(
        {
            "todo",
            "in-progress",
            "blocked",
            "in-review",
            "accepted",
            "rejected",
            "paused",
            "superseded",
        }
    )


def test_wave_rollup_statuses():
    assert schema.WAVE_ROLLUP_STATUSES == frozenset(
        {
            "empty",
            "todo",
            "in-progress",
            "in-review",
            "blocked",
            "paused",
            "done",
            "superseded",
        }
    )


def test_columns_exact_order_and_count():
    assert schema.COLUMNS == ("wave", "task", "status", "leader", "updated")
    assert len(schema.COLUMNS) == 5


def test_terminal():
    assert schema.TERMINAL == frozenset({"accepted", "superseded"})


def test_allowed_transitions_terminal_states_empty():
    assert schema.ALLOWED_TRANSITIONS["accepted"] == frozenset()
    assert schema.ALLOWED_TRANSITIONS["superseded"] == frozenset()


def test_allowed_transitions_todo():
    assert schema.ALLOWED_TRANSITIONS["todo"] == frozenset(
        {"in-progress", "blocked", "paused", "in-review", "accepted", "superseded"}
    )


def test_allowed_transitions_in_progress():
    assert schema.ALLOWED_TRANSITIONS["in-progress"] == frozenset(
        {"blocked", "paused", "in-review", "accepted", "rejected", "superseded"}
    )


def test_allowed_transitions_blocked():
    assert schema.ALLOWED_TRANSITIONS["blocked"] == frozenset(
        {"in-progress", "paused", "in-review", "accepted", "superseded"}
    )


def test_allowed_transitions_paused():
    assert schema.ALLOWED_TRANSITIONS["paused"] == frozenset(
        {"todo", "in-progress", "blocked", "in-review", "accepted", "superseded"}
    )


def test_allowed_transitions_in_review():
    assert schema.ALLOWED_TRANSITIONS["in-review"] == frozenset(
        {"accepted", "rejected", "in-progress", "blocked", "paused", "superseded"}
    )


def test_allowed_transitions_rejected():
    assert schema.ALLOWED_TRANSITIONS["rejected"] == frozenset(
        {"in-progress", "blocked", "paused", "in-review", "accepted", "superseded"}
    )


# --- pair_severity: 6 report(None 포함) x 8 progress = 48 셀 전부 ---

# report \ progress 컬럼 순서: todo, in-progress, blocked, in-review, accepted, rejected, paused, superseded
_PAIR_SEVERITY_MATRIX = [
    # (report, progress, expected)
    ("todo", "todo", None),
    ("todo", "in-progress", None),
    ("todo", "blocked", None),
    ("todo", "in-review", "WARN"),
    ("todo", "accepted", "ERROR"),
    ("todo", "rejected", "WARN"),
    ("todo", "paused", None),
    ("todo", "superseded", None),
    ("in-progress", "todo", None),
    ("in-progress", "in-progress", None),
    ("in-progress", "blocked", None),
    ("in-progress", "in-review", "WARN"),
    ("in-progress", "accepted", "ERROR"),
    ("in-progress", "rejected", "WARN"),
    ("in-progress", "paused", "WARN"),
    ("in-progress", "superseded", None),
    ("blocked", "todo", "WARN"),
    ("blocked", "in-progress", "WARN"),
    ("blocked", "blocked", None),
    ("blocked", "in-review", "WARN"),
    ("blocked", "accepted", "ERROR"),
    ("blocked", "rejected", "WARN"),
    ("blocked", "paused", "WARN"),
    ("blocked", "superseded", None),
    ("done", "todo", "WARN"),
    ("done", "in-progress", "WARN"),
    ("done", "blocked", "WARN"),
    ("done", "in-review", None),
    ("done", "accepted", None),
    ("done", "rejected", "WARN"),
    ("done", "paused", "WARN"),
    ("done", "superseded", None),
    ("needs-spec", "todo", "WARN"),
    ("needs-spec", "in-progress", "WARN"),
    ("needs-spec", "blocked", None),
    ("needs-spec", "in-review", "WARN"),
    ("needs-spec", "accepted", "ERROR"),
    ("needs-spec", "rejected", "WARN"),
    ("needs-spec", "paused", None),
    ("needs-spec", "superseded", None),
    (None, "todo", None),
    (None, "in-progress", "WARN"),
    (None, "blocked", None),
    (None, "in-review", "WARN"),
    (None, "accepted", "ERROR"),
    (None, "rejected", "WARN"),
    (None, "paused", None),
    (None, "superseded", None),
]


def test_pair_severity_matrix_has_48_cells():
    assert len(_PAIR_SEVERITY_MATRIX) == 48


@pytest.mark.parametrize("report,progress,expected", _PAIR_SEVERITY_MATRIX)
def test_pair_severity(report, progress, expected):
    assert schema.pair_severity(report, progress) == expected


# --- wave_rollup ---


def test_wave_rollup_empty():
    assert schema.wave_rollup([]) == "empty"


def test_wave_rollup_all_superseded():
    assert schema.wave_rollup(["superseded", "superseded"]) == "superseded"


def test_wave_rollup_all_accepted():
    assert schema.wave_rollup(["accepted", "accepted"]) == "done"


def test_wave_rollup_accepted_and_superseded():
    assert schema.wave_rollup(["accepted", "superseded"]) == "done"


def test_wave_rollup_todo_and_superseded():
    assert schema.wave_rollup(["todo", "superseded"]) == "todo"


def test_wave_rollup_todo_and_accepted():
    # accepted는 {todo, superseded}의 부분집합이 아니므로 규칙 5 미해당 → 규칙 7(활성 잔존)
    assert schema.wave_rollup(["todo", "accepted"]) == "in-progress"


def test_wave_rollup_blocked_and_accepted():
    assert schema.wave_rollup(["blocked", "accepted"]) == "blocked"


def test_wave_rollup_paused_and_accepted():
    assert schema.wave_rollup(["paused", "accepted"]) == "paused"


def test_wave_rollup_in_review_and_accepted():
    assert schema.wave_rollup(["in-review", "accepted"]) == "in-review"


def test_wave_rollup_rejected_and_accepted():
    assert schema.wave_rollup(["rejected", "accepted"]) == "in-progress"


def test_wave_rollup_todo_and_in_progress():
    assert schema.wave_rollup(["todo", "in-progress"]) == "in-progress"


def test_wave_rollup_single_todo():
    assert schema.wave_rollup(["todo"]) == "todo"


def test_wave_rollup_single_in_review():
    assert schema.wave_rollup(["in-review"]) == "in-review"


def test_wave_rollup_blocked_beats_paused():
    assert schema.wave_rollup(["blocked", "paused"]) == "blocked"


def test_wave_rollup_paused_beats_terminal_mix():
    assert schema.wave_rollup(["paused", "superseded", "accepted"]) == "paused"
