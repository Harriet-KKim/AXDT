"""cli의 progress 도메인(§7) — lint/status/commit(dry-run 포함) 배선 통합 테스트.

lint/schema/table/recover/commit 자체의 로직은 각자의 단위 테스트가 이미
검증한다. 여기서는 axdt CLI가 그 공개 API를 올바른 인자로 호출하고, exit
code·stdout/stderr를 사양대로 매핑하는지만 확인한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from axdt import cli
from axdt.infra import config, proc
from axdt.progress import table
from axdt.progress.table import TaskRow

# --- 헬퍼 (test_commit.py와 동일한 패턴) ---


def _decode(output: str | bytes) -> str:
    return output if isinstance(output, str) else output.decode("utf-8", errors="replace")


@dataclass
class _GitResult:
    returncode: int
    stdout: str
    stderr: str


def _git(repo: Path, *args: str, check: bool = True) -> _GitResult:
    r = proc.run(["git", *args], cwd=repo, check=check, text=False)
    return _GitResult(returncode=r.returncode, stdout=_decode(r.stdout), stderr=_decode(r.stderr))


def _write_progress(root: Path, rows: list[TaskRow]) -> None:
    path = config.progress_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(table.render_progress(rows), encoding="utf-8")


def _write_report(root: Path, task: str, status: str) -> None:
    path = config.report_dir(root) / f"{task}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nid: {task}\nstatus: {status}\n---\n\n본문.\n", encoding="utf-8")


@pytest.fixture
def root(monkeypatch, tmp_path):
    # config.project_root()가 AXDT_PROJECT_ROOT env를 읽는 경로 그대로 사용
    # (test_cli.py처럼 config.project_root를 통째로 monkeypatch하지 않는다).
    monkeypatch.setenv("AXDT_PROJECT_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def git_root(monkeypatch, tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t.com")
    _git(r, "config", "user.name", "t")
    monkeypatch.setenv("AXDT_PROJECT_ROOT", str(r))
    return r


# =====================================================================
# build_parser — progress 도메인 파싱
# =====================================================================


def test_build_parser_progress_lint_status_commit_parse():
    parser = cli.build_parser()
    for argv in (["progress", "lint"], ["progress", "status"], ["progress", "commit"]):
        args = parser.parse_args(argv)
        assert args.domain == "progress"
        assert callable(args.func)


def test_build_parser_progress_commit_dry_run_and_reason_gate_flags():
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "progress",
            "commit",
            "--dry-run",
            "--reason",
            "w1.t1-a=사유",
            "--gate",
            "g1",
        ]
    )
    assert args.dry_run is True
    assert args.reason == ["w1.t1-a=사유"]
    assert args.gate == ["g1"]


# =====================================================================
# progress lint
# =====================================================================


def test_progress_lint_clean_exits_zero(root):
    _write_progress(root, [TaskRow("w1", "w1.t1-a", "todo", "L-a", "2026-07-01")])
    assert cli.main(["progress", "lint"]) == 0


def test_progress_lint_error_exits_nonzero_and_reports_code(root, capsys):
    # 스키마에 없는 status -> bad-status ERROR.
    _write_progress(root, [TaskRow("w1", "w1.t1-a", "bogus-status", "L-a", "2026-07-01")])
    assert cli.main(["progress", "lint"]) == 1
    out = capsys.readouterr().out
    assert "ERROR" in out
    assert "bad-status" in out


def test_progress_lint_warn_only_still_exits_zero(root, capsys):
    # report=todo, progress=in-review -> WARN(치명적이지 않음). ERROR가 없으면 0.
    _write_progress(root, [TaskRow("w1", "w1.t1-a", "in-review", "L-a", "2026-07-01")])
    _write_report(root, "w1.t1-a", "todo")
    assert cli.main(["progress", "lint"]) == 0
    out = capsys.readouterr().out
    assert "WARN" in out


# =====================================================================
# progress status
# =====================================================================


def test_progress_status_exits_zero_and_prints_task_id(root, capsys):
    # paused -> blocked_or_paused 섹션에 task id와 함께 렌더링됨.
    _write_progress(root, [TaskRow("w1", "w1.t1-a", "paused", "L-a", "2026-07-01")])
    assert cli.main(["progress", "status"]) == 0
    out = capsys.readouterr().out
    assert "w1.t1-a" in out


def test_progress_status_malformed_progress_fails_gracefully(root, capsys):
    # 헤더 이름이 스키마와 어긋남 -> table.ProgressFormatError -> traceback 없이 1 반환.
    path = config.progress_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "| wave | task | state | leader | updated |\n"
        "|---|---|---|---|---|\n"
        "| w1 | w1.t1-a | todo | L-a | 2026-07-01 |\n",
        encoding="utf-8",
    )
    assert cli.main(["progress", "status"]) == 1
    err = capsys.readouterr().err
    assert "오류" in err


# =====================================================================
# progress commit --dry-run
# =====================================================================


def test_progress_commit_dry_run_exits_zero_prints_message_and_does_not_commit(
    git_root, capsys
):
    _write_progress(git_root, [TaskRow("w1", "w1.t1-a", "todo", "L-a", "2026-07-01")])
    _git(git_root, "add", "-A")
    _git(git_root, "commit", "-q", "-m", "base")
    before_log = _git(git_root, "log", "--oneline").stdout

    _write_progress(git_root, [TaskRow("w1", "w1.t1-a", "in-review", "L-a", "2026-07-02")])

    assert cli.main(["progress", "commit", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "chore(progress): w1.t1-a todo->in-review" in out

    # dry-run -- 커밋도, 스테이징도 안 됨.
    after_log = _git(git_root, "log", "--oneline").stdout
    assert after_log == before_log
    assert _git(git_root, "diff", "--cached", "--quiet", check=False).returncode == 0


def test_progress_commit_dry_run_with_reason_and_gate(git_root, capsys):
    _write_progress(git_root, [TaskRow("w1", "w1.t1-a", "todo", "L-a", "2026-07-01")])
    _git(git_root, "add", "-A")
    _git(git_root, "commit", "-q", "-m", "base")

    _write_progress(git_root, [TaskRow("w1", "w1.t1-a", "rejected", "L-a", "2026-07-02")])

    rc = cli.main(
        [
            "progress",
            "commit",
            "--dry-run",
            "--reason",
            "w1.t1-a=스펙 미충족",
            "--gate",
            "wave1-kickoff",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Reason: w1.t1-a 스펙 미충족" in out
    assert "- wave1-kickoff" in out


def test_progress_commit_dry_run_rejects_terminal_resumed(git_root, capsys):
    _write_progress(git_root, [TaskRow("w1", "w1.t1-a", "accepted", "L-a", "2026-07-01")])
    _write_report(git_root, "w1.t1-a", "done")
    _git(git_root, "add", "-A")
    _git(git_root, "commit", "-q", "-m", "base")

    _write_progress(git_root, [TaskRow("w1", "w1.t1-a", "in-progress", "L-a", "2026-07-02")])

    assert cli.main(["progress", "commit", "--dry-run"]) == 1
    err = capsys.readouterr().err
    assert "거부:" in err


def test_progress_commit_actual_dispatches_milestone_commit(git_root, capsys):
    _write_progress(git_root, [TaskRow("w1", "w1.t1-a", "todo", "L-a", "2026-07-01")])
    _git(git_root, "add", "-A")
    _git(git_root, "commit", "-q", "-m", "base")

    _write_progress(git_root, [TaskRow("w1", "w1.t1-a", "in-progress", "L-a", "2026-07-02")])

    assert cli.main(["progress", "commit"]) == 0
    log = _git(git_root, "log", "-1", "--pretty=%B")
    assert "w1.t1-a todo->in-progress" in log.stdout


def test_progress_commit_empty_reason_for_rejected_task_fails(git_root, capsys):
    # --reason t= 형태(빈 사유)는 rejected task 사유로 인정되지 않는다(공백/빈 문자열).
    _write_progress(git_root, [TaskRow("w1", "w1.t1-a", "todo", "L-a", "2026-07-01")])
    _git(git_root, "add", "-A")
    _git(git_root, "commit", "-q", "-m", "base")

    _write_progress(git_root, [TaskRow("w1", "w1.t1-a", "rejected", "L-a", "2026-07-02")])

    rc = cli.main(["progress", "commit", "--reason", "w1.t1-a="])
    assert rc == 1
    err = capsys.readouterr().err
    assert "오류" in err
