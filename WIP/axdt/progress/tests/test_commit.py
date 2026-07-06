"""commit.py — 마일스톤 커밋 헬퍼 계약 검증.

마일스톤 커밋은 중간 전이를 건너뛴다. 그래서 여기서는 절대
schema.ALLOWED_TRANSITIONS로 끝점 쌍을 재검사하지 않는다(여러 칸 점프는
정상). 검사하는 건 몇 칸을 건너뛰어도 불변인 성질뿐(거부 4종): 종료 재개·
행 삭제·과claim·구조 오류.

git 인덱스/트리 블롭 의미(특히 과claim 판정)가 핵심이므로 가짜 proc가 아니라
실제 tmp git repo로 검증한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from axdt.infra import config, proc
from axdt.progress import table
from axdt.progress.commit import (
    CommitRejected,
    MilestonePlan,
    ProgressEvent,
    diff_progress,
    format_milestone_message,
    milestone_commit,
    plan_milestone,
)
from axdt.progress.table import TaskRow

# --- 테스트 헬퍼 ---


def _decode(output: str | bytes) -> str:
    # proc.ProcResult는 내부에서 ``completed.stdout or ""``로 빈 출력을 만들기 때문에,
    # text=False로 호출해도 빈 출력이면 bytes가 아니라 str ""로 온다. 둘 다 처리한다.
    return output if isinstance(output, str) else output.decode("utf-8", errors="replace")


@dataclass
class _GitResult:
    returncode: int
    stdout: str
    stderr: str


def _git(repo: Path, *args: str, check: bool = True) -> _GitResult:
    # text=False + 수동 UTF-8 디코드: 이 환경의 OS 로캘(cp949 등)로 subprocess의
    # 기본 text=True 디코드를 하면 git 블롭의 UTF-8 non-ASCII(∅, 한글)에서 깨진다.
    r = proc.run(["git", *args], cwd=repo, check=check, text=False)
    return _GitResult(
        returncode=r.returncode,
        stdout=_decode(r.stdout),
        stderr=_decode(r.stderr),
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t.com")
    _git(r, "config", "user.name", "t")
    return r


def _write_progress(repo: Path, rows: list[TaskRow]) -> None:
    path = config.progress_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(table.render_progress(rows), encoding="utf-8")


def _write_progress_text(repo: Path, text: str) -> None:
    path = config.progress_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_report(repo: Path, task: str, status: str, *, id: str | None = None) -> None:
    rid = task if id is None else id
    path = config.report_dir(repo) / f"{task}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nid: {rid}\nstatus: {status}\n---\n\n본문.\n", encoding="utf-8")


def _write_broken_report(repo: Path, task: str) -> None:
    path = config.report_dir(repo) / f"{task}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# frontmatter 없는 report\n", encoding="utf-8")


def _commit_all(repo: Path, message: str = "base") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _head_sha(repo: Path) -> str | None:
    r = _git(repo, "rev-parse", "HEAD", check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def _rev_count(repo: Path) -> int:
    r = _git(repo, "rev-list", "--count", "HEAD", check=False)
    return int(r.stdout.strip()) if r.returncode == 0 else 0


def _last_message(repo: Path) -> str:
    return _git(repo, "log", "-1", "--pretty=%B").stdout.rstrip("\n")


def _nothing_staged(repo: Path) -> bool:
    return _git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0


# =====================================================================
# diff_progress
# =====================================================================


def test_diff_new_rows_from_empty_base():
    new = [
        TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01"),
        TaskRow("w1", "w1.t2", "in-progress", "L-b", "2026-07-01"),
    ]
    events = diff_progress([], new)
    assert events == [
        ProgressEvent(task="w1.t1", before=None, after="todo", kind="new"),
        ProgressEvent(task="w1.t2", before=None, after="in-progress", kind="new"),
    ]


def test_diff_transition():
    base = [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")]
    new = [TaskRow("w1", "w1.t1", "in-review", "L-a", "2026-07-02")]
    events = diff_progress(base, new)
    assert events == [
        ProgressEvent(task="w1.t1", before="todo", after="in-review", kind="transition")
    ]


def test_diff_unchanged_status_no_event():
    base = [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")]
    new = [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-05")]  # updated만 바뀜
    assert diff_progress(base, new) == []


def test_diff_wave_complete_composite():
    base = [
        TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01"),
        TaskRow("w1", "w1.t2", "in-progress", "L-b", "2026-07-01"),
        TaskRow("w1", "w1.t3", "todo", "L-c", "2026-07-01"),
    ]
    new = [
        TaskRow("w1", "w1.t1", "accepted", "L-a", "2026-07-06"),
        TaskRow("w1", "w1.t2", "accepted", "L-b", "2026-07-06"),
        TaskRow("w1", "w1.t3", "todo", "L-c", "2026-07-01"),  # 미변경
    ]
    events = diff_progress(base, new)
    assert events == [
        ProgressEvent(task="w1.t1", before="todo", after="accepted", kind="transition"),
        ProgressEvent(task="w1.t2", before="in-progress", after="accepted", kind="transition"),
    ]


def test_diff_deletion_not_represented_as_event():
    # 행 삭제(base엔 있고 new엔 없음)는 diff_progress가 이벤트로 만들지 않는다.
    # (milestone_commit이 별도 집합 비교로 감지한다.)
    base = [
        TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01"),
        TaskRow("w1", "w1.t2", "todo", "L-b", "2026-07-01"),
    ]
    new = [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")]
    events = diff_progress(base, new)
    assert events == []
    assert all(e.task != "w1.t2" for e in events)


# =====================================================================
# format_milestone_message
# =====================================================================


def test_format_single_event_no_body():
    events = [ProgressEvent(task="w1.t1", before="todo", after="in-review", kind="transition")]
    msg = format_milestone_message(events)
    assert msg == "chore(progress): w1.t1 todo->in-review"


def test_format_single_new_event_renders_empty_set_symbol():
    events = [ProgressEvent(task="w1.t1", before=None, after="todo", kind="new")]
    msg = format_milestone_message(events)
    assert msg == "chore(progress): w1.t1 ∅->todo"


def test_format_batch_events_has_events_section():
    events = [
        ProgressEvent(task="w1.t1", before="todo", after="accepted", kind="transition"),
        ProgressEvent(task="w1.t2", before="in-progress", after="accepted", kind="transition"),
    ]
    msg = format_milestone_message(events)
    lines = msg.splitlines()
    assert lines[0] == "chore(progress): batch 2 events"
    assert "Events:" in lines
    assert "- w1.t1: todo -> accepted" in lines
    assert "- w1.t2: in-progress -> accepted" in lines


def test_format_rejected_requires_reason_raises_value_error():
    events = [ProgressEvent(task="w1.t1", before="todo", after="rejected", kind="transition")]
    with pytest.raises(ValueError):
        format_milestone_message(events)


def test_format_rejected_with_reason_included_in_body():
    events = [ProgressEvent(task="w1.t1", before="todo", after="rejected", kind="transition")]
    msg = format_milestone_message(events, rejection_reasons={"w1.t1": "스펙 미충족"})
    assert msg.splitlines()[0] == "chore(progress): w1.t1 todo->rejected"
    assert "Reason: w1.t1 스펙 미충족" in msg.splitlines()


def test_format_rejected_not_rejected_needs_no_reason():
    events = [ProgressEvent(task="w1.t1", before="todo", after="accepted", kind="transition")]
    # rejection_reasons 생략해도 예외 없음(accepted는 rejected가 아님).
    msg = format_milestone_message(events)
    assert "chore(progress): w1.t1 todo->accepted" == msg


def test_format_events_empty_gates_present_valid():
    msg = format_milestone_message([], gates=("wave1-complete",))
    assert msg.splitlines()[0] == "chore(progress): gate wave1-complete"
    assert "Gates:" in msg.splitlines()
    assert "- wave1-complete" in msg.splitlines()


def test_format_events_empty_multiple_gates():
    msg = format_milestone_message([], gates=("g1", "g2"))
    assert msg.splitlines()[0] == "chore(progress): 2 gates"
    assert "- g1" in msg.splitlines()
    assert "- g2" in msg.splitlines()


def test_format_events_empty_gates_empty_raises():
    with pytest.raises(ValueError):
        format_milestone_message([])


def test_format_gates_with_events_both_present():
    events = [ProgressEvent(task="w1.t1", before="todo", after="in-review", kind="transition")]
    msg = format_milestone_message(events, gates=("g1",))
    assert msg.splitlines()[0] == "chore(progress): w1.t1 todo->in-review"
    assert "Gates:" in msg.splitlines()
    assert "- g1" in msg.splitlines()


def test_format_mutable_default_does_not_leak_between_calls():
    # rejection_reasons=None 기본값 함정: 내부에서 {}로 새로 만들어야지 공유 dict면 안 됨.
    rejected_events = [ProgressEvent(task="w1.t1", before="todo", after="rejected", kind="transition")]
    with pytest.raises(ValueError):
        format_milestone_message(rejected_events)  # 사유 없음 -> 예외

    # 이전 호출의 예외/상태가 다음 호출에 전혀 영향 주지 않아야 함.
    other_events = [ProgressEvent(task="w1.t2", before="todo", after="accepted", kind="transition")]
    msg = format_milestone_message(other_events)
    assert msg == "chore(progress): w1.t2 todo->accepted"


# =====================================================================
# milestone_commit — 다중 칸 점프 성공 케이스
# =====================================================================


def test_milestone_commit_first_ever_commit_new_rows(repo: Path):
    # HEAD가 아예 없는 저장소(최초 커밋) -> base=[] 취급.
    assert _head_sha(repo) is None
    _write_progress(
        repo,
        [
            TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01"),
            TaskRow("w1", "w1.t2", "in-progress", "L-b", "2026-07-01"),
        ],
    )
    milestone_commit(repo)
    assert _rev_count(repo) == 1
    msg = _last_message(repo)
    assert "batch 2 events" in msg
    assert "- w1.t1: ∅ -> todo" in msg.splitlines()
    assert "- w1.t2: ∅ -> in-progress" in msg.splitlines()


def test_milestone_commit_multi_hop_todo_to_rejected_with_reason(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")])
    _commit_all(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "rejected", "L-a", "2026-07-02")])
    milestone_commit(repo, rejection_reasons={"w1.t1": "요구사항 불충족"})

    assert _rev_count(repo) == 2
    msg = _last_message(repo)
    assert msg.splitlines()[0] == "chore(progress): w1.t1 todo->rejected"
    assert "Reason: w1.t1 요구사항 불충족" in msg.splitlines()


def test_milestone_commit_empty_form_to_accepted_with_report_done(repo: Path):
    # 저장소 자체는 base 커밋이 있지만 progress.md는 빈 양식(최초 등록)이었다가
    # 이번 마일스톤에서 바로 accepted로 등록(report=done 갖춤).
    _write_progress(repo, [])
    _commit_all(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "accepted", "L-a", "2026-07-03")])
    _write_report(repo, "w1.t1", "done")
    milestone_commit(repo)

    assert _rev_count(repo) == 2
    msg = _last_message(repo)
    assert msg.splitlines()[0] == "chore(progress): w1.t1 ∅->accepted"


def test_milestone_commit_new_row_registered_directly_as_superseded(repo: Path):
    _write_progress(repo, [])
    _commit_all(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "superseded", "L-a", "2026-07-03")])
    milestone_commit(repo)

    assert _rev_count(repo) == 2
    msg = _last_message(repo)
    assert msg.splitlines()[0] == "chore(progress): w1.t1 ∅->superseded"


# =====================================================================
# milestone_commit — 거부 4종
# =====================================================================


def test_milestone_commit_rejects_terminal_resumed(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "accepted", "L-a", "2026-07-01")])
    _write_report(repo, "w1.t1", "done")
    _commit_all(repo)
    before_sha = _head_sha(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "in-progress", "L-a", "2026-07-02")])
    with pytest.raises(CommitRejected):
        milestone_commit(repo)

    assert _head_sha(repo) == before_sha  # 커밋 안 됨
    assert _nothing_staged(repo)  # 스테이징도 되돌려짐(혹은 애초에 안 됨)


def test_milestone_commit_rejects_row_deleted(repo: Path):
    _write_progress(
        repo,
        [
            TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01"),
            TaskRow("w1", "w1.t2", "todo", "L-b", "2026-07-01"),
        ],
    )
    _commit_all(repo)
    before_sha = _head_sha(repo)

    # w1.t2 행이 통째로 사라짐.
    _write_progress(repo, [TaskRow("w1", "w1.t1", "in-progress", "L-a", "2026-07-02")])
    with pytest.raises(CommitRejected):
        milestone_commit(repo)

    assert _head_sha(repo) == before_sha
    assert _nothing_staged(repo)


def test_milestone_commit_rejects_malformed_progress_structure(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")])
    _commit_all(repo)
    before_sha = _head_sha(repo)

    # 헤더 이름이 스키마와 어긋남 -> ProgressFormatError -> CommitRejected.
    _write_progress_text(
        repo,
        "| wave | task | state | leader | updated |\n"
        "|---|---|---|---|---|\n"
        "| w1 | w1.t1 | todo | L-a | 2026-07-01 |\n",
    )
    with pytest.raises(CommitRejected):
        milestone_commit(repo)

    assert _head_sha(repo) == before_sha
    assert _nothing_staged(repo)


# =====================================================================
# milestone_commit — 과claim
# =====================================================================


def test_milestone_commit_rejects_overclaim_report_missing(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")])
    _commit_all(repo)
    before_sha = _head_sha(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "accepted", "L-a", "2026-07-02")])
    # report 파일 자체가 없음.
    with pytest.raises(CommitRejected):
        milestone_commit(repo)

    assert _head_sha(repo) == before_sha
    assert _nothing_staged(repo)


def test_milestone_commit_rejects_overclaim_report_not_done(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")])
    _write_report(repo, "w1.t1", "in-progress")
    _commit_all(repo)
    before_sha = _head_sha(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "accepted", "L-a", "2026-07-02")])
    # report.md는 그대로(in-progress) -- accepted로 올리는 건 과claim.
    with pytest.raises(CommitRejected):
        milestone_commit(repo)

    assert _head_sha(repo) == before_sha
    assert _nothing_staged(repo)


def test_milestone_commit_accepts_when_report_done(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "in-review", "L-a", "2026-07-01")])
    _write_report(repo, "w1.t1", "in-progress")
    _commit_all(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "accepted", "L-a", "2026-07-02")])
    _write_report(repo, "w1.t1", "done")
    milestone_commit(repo)

    assert _rev_count(repo) == 2
    assert _last_message(repo).splitlines()[0] == "chore(progress): w1.t1 in-review->accepted"


def test_milestone_commit_prior_done_report_unchanged_accepted_passes(repo: Path):
    """앞 커밋에서 이미 done으로 커밋된 report를, 이번 커밋에서 report는 건드리지
    않고 progress만 accepted로 올리는 시나리오. 과claim 판정이 "이번 조작이 바꿨는가"가
    아니라 "커밋 트리(인덱스) 블롭이 done인가"임을 검증하는 핵심 케이스.
    """
    _write_progress(repo, [TaskRow("w1", "w1.t1", "in-review", "L-a", "2026-07-01")])
    _write_report(repo, "w1.t1", "done")  # report는 이미 이전 커밋에서 done.
    _commit_all(repo, "prior: report already done")

    # 이번 조작에서 report 파일은 전혀 건드리지 않음 -- progress.md만 바꾼다.
    _write_progress(repo, [TaskRow("w1", "w1.t1", "accepted", "L-a", "2026-07-03")])
    milestone_commit(repo)

    assert _rev_count(repo) == 2
    assert _last_message(repo).splitlines()[0] == "chore(progress): w1.t1 in-review->accepted"


def test_milestone_commit_in_review_does_not_require_report(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")])
    _commit_all(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "in-review", "L-a", "2026-07-02")])
    # report 없음 -- in-review는 차단 대상이 아님.
    milestone_commit(repo)

    assert _rev_count(repo) == 2
    assert _last_message(repo).splitlines()[0] == "chore(progress): w1.t1 todo->in-review"


# =====================================================================
# milestone_commit — 스코핑(이번에 안 바꾼 다른 task의 report 문제는 거부 안 함)
# =====================================================================


def test_milestone_commit_scoping_ignores_untouched_task_broken_report(repo: Path):
    _write_progress(
        repo,
        [
            TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01"),
            TaskRow("w1", "w1.t2", "todo", "L-b", "2026-07-01"),
        ],
    )
    _write_broken_report(repo, "w1.t2")  # w1.t2 report는 frontmatter조차 없음.
    _commit_all(repo)

    # w1.t2는 건드리지 않고, w1.t1만 in-progress로 전이(accepted 아님).
    _write_progress(
        repo,
        [
            TaskRow("w1", "w1.t1", "in-progress", "L-a", "2026-07-02"),
            TaskRow("w1", "w1.t2", "todo", "L-b", "2026-07-01"),
        ],
    )
    milestone_commit(repo)  # w1.t2의 깨진 report는 검사 대상이 아니므로 통과.

    assert _rev_count(repo) == 2
    assert _last_message(repo).splitlines()[0] == "chore(progress): w1.t1 todo->in-progress"


def test_milestone_commit_scoping_untouched_broken_report_does_not_block_others_accept(repo: Path):
    _write_progress(
        repo,
        [
            TaskRow("w1", "w1.t1", "in-review", "L-a", "2026-07-01"),
            TaskRow("w1", "w1.t2", "todo", "L-b", "2026-07-01"),
        ],
    )
    _write_report(repo, "w1.t1", "done")
    _write_broken_report(repo, "w1.t2")  # w1.t2는 여전히 안 건드림, 여전히 깨짐.
    _commit_all(repo)

    _write_progress(
        repo,
        [
            TaskRow("w1", "w1.t1", "accepted", "L-a", "2026-07-03"),
            TaskRow("w1", "w1.t2", "todo", "L-b", "2026-07-01"),
        ],
    )
    milestone_commit(repo)  # w1.t1만 accepted, w1.t2 report 문제는 무관.

    assert _rev_count(repo) == 2
    assert _last_message(repo).splitlines()[0] == "chore(progress): w1.t1 in-review->accepted"


# =====================================================================
# milestone_commit — 게이트(events=0)
# =====================================================================


def test_milestone_commit_gate_only_no_progress_change_allow_empty(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")])
    _commit_all(repo)
    before_sha = _head_sha(repo)

    # progress.md 완전히 무변경 -- 상태 무변경 게이트만 커밋.
    milestone_commit(repo, gates=("wave1-kickoff",))

    assert _head_sha(repo) != before_sha
    assert _rev_count(repo) == 2
    assert _last_message(repo).splitlines()[0] == "chore(progress): gate wave1-kickoff"


def test_milestone_commit_no_events_no_gates_raises_value_error(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")])
    _commit_all(repo)
    before_sha = _head_sha(repo)

    # progress.md 무변경, gates도 없음 -- 커밋할 것 없음.
    with pytest.raises(ValueError):
        milestone_commit(repo)

    assert _head_sha(repo) == before_sha


# =====================================================================
# milestone_commit — 가변 기본값 함정(연속 호출 간 상태 누수 없음)
# =====================================================================


def test_milestone_commit_default_rejection_reasons_does_not_leak_across_calls(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")])
    _commit_all(repo)

    # 1차 호출: rejection_reasons 생략 + rejected -> ValueError, 커밋 안 됨.
    _write_progress(repo, [TaskRow("w1", "w1.t1", "rejected", "L-a", "2026-07-02")])
    with pytest.raises(ValueError):
        milestone_commit(repo)
    assert _rev_count(repo) == 1

    # 2차 호출: 별도 task가 rejected인데 사유는 여전히 생략 -> 역시 ValueError여야 한다.
    # (1차 호출의 내부 기본값이 공유 dict라 뭔가 남아있었다면 여기서 잘못 통과해버릴 것.)
    _write_progress(
        repo,
        [
            TaskRow("w1", "w1.t1", "rejected", "L-a", "2026-07-02"),
            TaskRow("w1", "w1.t2", "rejected", "L-b", "2026-07-02"),
        ],
    )
    with pytest.raises(ValueError):
        milestone_commit(repo)
    assert _rev_count(repo) == 1

    # 3차 호출: 이번엔 사유를 제대로 주면 정상 커밋된다.
    milestone_commit(repo, rejection_reasons={"w1.t1": "사유1", "w1.t2": "사유2"})
    assert _rev_count(repo) == 2
    msg = _last_message(repo)
    assert "Reason: w1.t1 사유1" in msg.splitlines()
    assert "Reason: w1.t2 사유2" in msg.splitlines()


# =====================================================================
# plan_milestone — dry-run 미리보기(git add/commit 없이)
# =====================================================================


def test_plan_milestone_new_row_does_not_touch_git_state(repo: Path):
    assert _head_sha(repo) is None
    _write_progress(
        repo,
        [
            TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01"),
            TaskRow("w1", "w1.t2", "in-progress", "L-b", "2026-07-01"),
        ],
    )

    plan = plan_milestone(repo)

    assert isinstance(plan, MilestonePlan)
    assert plan.events == [
        ProgressEvent(task="w1.t1", before=None, after="todo", kind="new"),
        ProgressEvent(task="w1.t2", before=None, after="in-progress", kind="new"),
    ]
    assert "docs/interim/progress.md" in plan.staged
    assert "batch 2 events" in plan.message
    assert "- w1.t1: ∅ -> todo" in plan.message.splitlines()
    assert "- w1.t2: ∅ -> in-progress" in plan.message.splitlines()

    # git 인덱스/HEAD가 전혀 바뀌지 않아야 한다(진짜 최초 커밋조차 없음).
    assert _head_sha(repo) is None
    assert _nothing_staged(repo)


def test_plan_milestone_multi_hop_includes_existing_report_in_staged(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "in-review", "L-a", "2026-07-01")])
    _write_report(repo, "w1.t1", "done")
    _commit_all(repo)
    before_sha = _head_sha(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "accepted", "L-a", "2026-07-03")])
    # report는 이미 이전 커밋에서 done -- 이번엔 progress만 바꾼다.

    plan = plan_milestone(repo)

    assert plan.events == [
        ProgressEvent(task="w1.t1", before="in-review", after="accepted", kind="transition")
    ]
    assert "docs/interim/progress.md" in plan.staged
    assert "docs/interim/report/w1.t1.md" in plan.staged
    assert plan.message.splitlines()[0] == "chore(progress): w1.t1 in-review->accepted"

    # 미리보기만 했을 뿐 실제 커밋/스테이징은 없다.
    assert _head_sha(repo) == before_sha
    assert _nothing_staged(repo)


def test_plan_milestone_rejects_terminal_resumed_without_touching_git(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "accepted", "L-a", "2026-07-01")])
    _write_report(repo, "w1.t1", "done")
    _commit_all(repo)
    before_sha = _head_sha(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "in-progress", "L-a", "2026-07-02")])
    with pytest.raises(CommitRejected):
        plan_milestone(repo)

    assert _head_sha(repo) == before_sha
    assert _nothing_staged(repo)


def test_plan_milestone_rejects_row_deleted(repo: Path):
    _write_progress(
        repo,
        [
            TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01"),
            TaskRow("w1", "w1.t2", "todo", "L-b", "2026-07-01"),
        ],
    )
    _commit_all(repo)
    before_sha = _head_sha(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "in-progress", "L-a", "2026-07-02")])
    with pytest.raises(CommitRejected):
        plan_milestone(repo)

    assert _head_sha(repo) == before_sha
    assert _nothing_staged(repo)


def test_plan_milestone_rejects_malformed_progress_structure(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")])
    _commit_all(repo)

    _write_progress_text(
        repo,
        "| wave | task | state | leader | updated |\n"
        "|---|---|---|---|---|\n"
        "| w1 | w1.t1 | todo | L-a | 2026-07-01 |\n",
    )
    with pytest.raises(CommitRejected):
        plan_milestone(repo)


def test_plan_milestone_does_not_check_overclaim(repo: Path):
    # milestone_commit이라면 report 부재로 과claim 거부(CommitRejected)되지만,
    # plan_milestone은 스테이징 선행이 필요한 과claim 검사를 하지 않는다 --
    # 그건 실제 커밋 시점(milestone_commit)의 몫이다.
    _write_progress(repo, [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")])
    _commit_all(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "accepted", "L-a", "2026-07-02")])
    # report 파일 자체가 없음 -- milestone_commit이라면 CommitRejected.

    plan = plan_milestone(repo)  # 예외 없이 미리보기가 만들어진다.
    assert plan.events == [
        ProgressEvent(task="w1.t1", before="todo", after="accepted", kind="transition")
    ]
    assert plan.message.splitlines()[0] == "chore(progress): w1.t1 todo->accepted"

    # 실제 커밋은 여전히 과claim으로 거부된다(계약 불변).
    with pytest.raises(CommitRejected):
        milestone_commit(repo)


def test_plan_milestone_rejected_without_reason_raises_value_error(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")])
    _commit_all(repo)

    _write_progress(repo, [TaskRow("w1", "w1.t1", "rejected", "L-a", "2026-07-02")])
    with pytest.raises(ValueError):
        plan_milestone(repo)


def test_plan_milestone_gate_only_no_progress_change(repo: Path):
    _write_progress(repo, [TaskRow("w1", "w1.t1", "todo", "L-a", "2026-07-01")])
    _commit_all(repo)

    plan = plan_milestone(repo, gates=("wave1-kickoff",))
    assert plan.events == []
    assert plan.message.splitlines()[0] == "chore(progress): gate wave1-kickoff"
    assert _nothing_staged(repo)
