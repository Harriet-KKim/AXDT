"""progress 추적 스키마 — 상태값·전이·정합성 판정·wave 롤업의 단일 정의원.

순수 로직만 담는다(IO 없음). 다른 모든 progress 모듈은 이 모듈의 상수·함수를 그대로 참조한다.
"""
from __future__ import annotations

__all__ = [
    "REPORT_STATUSES",
    "PROGRESS_STATUSES",
    "WAVE_ROLLUP_STATUSES",
    "COLUMNS",
    "TERMINAL",
    "ALLOWED_TRANSITIONS",
    "pair_severity",
    "wave_rollup",
]

# --- 상태값 집합 ---

REPORT_STATUSES: frozenset[str] = frozenset(
    {"todo", "in-progress", "blocked", "done", "needs-spec"}
)
PROGRESS_STATUSES: frozenset[str] = frozenset(
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
WAVE_ROLLUP_STATUSES: frozenset[str] = frozenset(
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

# report 포인터 컬럼 없음(report.md는 그 자체가 문서이지 progress.md의 컬럼이 아님).
COLUMNS: tuple[str, ...] = ("wave", "task", "status", "leader", "updated")

TERMINAL: frozenset[str] = frozenset({"accepted", "superseded"})

# --- progress.status 전이 규칙 ---

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "todo": frozenset(
        {"in-progress", "blocked", "paused", "in-review", "accepted", "superseded"}
    ),
    "in-progress": frozenset(
        {"blocked", "paused", "in-review", "accepted", "rejected", "superseded"}
    ),
    "blocked": frozenset(
        {"in-progress", "paused", "in-review", "accepted", "superseded"}
    ),
    "paused": frozenset(
        {"todo", "in-progress", "blocked", "in-review", "accepted", "superseded"}
    ),
    "in-review": frozenset(
        {"accepted", "rejected", "in-progress", "blocked", "paused", "superseded"}
    ),
    "rejected": frozenset(
        {"in-progress", "blocked", "paused", "in-review", "accepted", "superseded"}
    ),
    "accepted": frozenset(),
    "superseded": frozenset(),
}

# --- report/progress 정합성 심각도 매트릭스 ---
# 행=report.status(None=파일 부재), 열=progress.status. "." -> None, "W" -> WARN, "E" -> ERROR.
_PAIR_SEVERITY: dict[str | None, dict[str, str | None]] = {
    "todo": {
        "todo": None,
        "in-progress": None,
        "blocked": None,
        "in-review": "WARN",
        "accepted": "ERROR",
        "rejected": "WARN",
        "paused": None,
        "superseded": None,
    },
    "in-progress": {
        "todo": None,
        "in-progress": None,
        "blocked": None,
        "in-review": "WARN",
        "accepted": "ERROR",
        "rejected": "WARN",
        "paused": "WARN",
        "superseded": None,
    },
    "blocked": {
        "todo": "WARN",
        "in-progress": "WARN",
        "blocked": None,
        "in-review": "WARN",
        "accepted": "ERROR",
        "rejected": "WARN",
        "paused": "WARN",
        "superseded": None,
    },
    "done": {
        "todo": "WARN",
        "in-progress": "WARN",
        "blocked": "WARN",
        "in-review": None,
        "accepted": None,
        "rejected": "WARN",
        "paused": "WARN",
        "superseded": None,
    },
    "needs-spec": {
        "todo": "WARN",
        "in-progress": "WARN",
        "blocked": None,
        "in-review": "WARN",
        "accepted": "ERROR",
        "rejected": "WARN",
        "paused": None,
        "superseded": None,
    },
    None: {
        "todo": None,
        "in-progress": "WARN",
        "blocked": None,
        "in-review": "WARN",
        "accepted": "ERROR",
        "rejected": "WARN",
        "paused": None,
        "superseded": None,
    },
}


def pair_severity(report: str | None, progress: str) -> str | None:
    """report.status(또는 None=파일 부재)와 progress.status의 정합 심각도.

    반환: "ERROR" | "WARN" | None. 알려지지 않은 report/progress 조합은 KeyError.
    """
    return _PAIR_SEVERITY[report][progress]


def wave_rollup(task_statuses: list[str]) -> str:
    """한 wave에 속한 task들의 progress.status 목록 → wave 롤업 상태.

    위에서부터 첫 매치하는 전량 함수:
    1. 목록이 비면 "empty"
    2. 하나라도 blocked면 "blocked"
    3. 하나라도 paused면 "paused"
    4. 전부 종료(TERMINAL의 부분집합)면 accepted가 하나라도 있으면 "done", 아니면 "superseded"
    5. {todo, superseded}의 부분집합이고 todo가 하나 이상이면 "todo"
    6. 활성(todo·in-progress·rejected)이 하나도 없고 in-review가 있으면 "in-review"
    7. 그 외(활성 잔존)는 "in-progress"
    """
    if not task_statuses:
        return "empty"

    statuses = set(task_statuses)

    if "blocked" in statuses:
        return "blocked"
    if "paused" in statuses:
        return "paused"
    if statuses <= TERMINAL:
        return "done" if "accepted" in statuses else "superseded"
    if statuses <= {"todo", "superseded"} and "todo" in statuses:
        return "todo"

    active = {"todo", "in-progress", "rejected"}
    if not (statuses & active) and "in-review" in statuses:
        return "in-review"

    return "in-progress"
