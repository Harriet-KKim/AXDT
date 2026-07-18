"""server.py의 순수 렌더 함수 + 경로 탐색 방어 함수 단위 테스트.

HTTP 서버를 띄우지 않고 렌더/판정 함수만 직접 호출한다(HTTP 레벨 테스트는
test_server.py 몫).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from axdt.progress.table import Report, TaskRow
from axdt.web.server import render_error, render_overview, render_report, resolve_report_path


# --- render_overview ---


def test_render_overview_links_only_task_with_existing_report(tmp_path: Path):
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    (report_dir / "w1.t1-a.md").write_text(
        "---\nid: w1.t1-a\nstatus: done\n---\n\n본문.\n", encoding="utf-8"
    )

    rows = [
        TaskRow("w1", "w1.t1-a", "accepted", "L-alice", "2026-07-05"),
        TaskRow("w1", "w1.t1-b", "todo", "L-bob", "2026-07-05"),
    ]
    out = render_overview(rows, report_dir)

    assert '<a href="/report/w1.t1-a">w1.t1-a</a>' in out
    assert "w1.t1-b" in out
    assert '<a href="/report/w1.t1-b">' not in out


def test_render_overview_escapes_cell_values(tmp_path: Path):
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    rows = [TaskRow("w1", "w1.t1-a", "todo", "L-<script>alert(1)</script>", "2026-07-05")]
    out = render_overview(rows, report_dir)

    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_render_overview_empty_rows_renders_header_only():
    out = render_overview([], Path("does-not-matter"))
    assert "<table>" in out
    assert "<tr><td>" not in out


def test_render_overview_does_not_link_non_canonical_task(tmp_path: Path):
    # 비정규(대문자) 이름의 report 파일이 실제로 존재해도 링크를 걸지 않는다 —
    # 드릴다운 허용목록이 대문자를 막아 링크가 항상 404가 될 것이기 때문(깨진 링크 방지).
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    (report_dir / "W1.T1-A.md").write_text(
        "---\nid: W1.T1-A\nstatus: done\n---\n본문.\n", encoding="utf-8"
    )
    rows = [TaskRow("w1", "W1.T1-A", "todo", "L-a", "2026-07-05")]
    out = render_overview(rows, report_dir)
    assert "<a href=" not in out
    assert "W1.T1-A" in out  # 텍스트로는 표시


def test_render_overview_does_not_link_or_stat_traversal_task(tmp_path: Path):
    # '../secret' 같은 값은 링크하지 않는다(허용목록 밖) — is_file 호출 자체가
    # 단축평가로 생략돼 report_dir 밖 경로를 stat하지 않는다.
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    (tmp_path / "secret.md").write_text("SECRET", encoding="utf-8")
    rows = [TaskRow("w1", "../secret", "todo", "L-a", "2026-07-05")]
    out = render_overview(rows, report_dir)
    assert "<a href=" not in out


# --- render_report ---


def test_render_report_includes_status_badge_and_escapes_body():
    report = Report(id="w1.t1-a", status="in-progress")
    body = "본문 <danger> & 특수문자\n"
    out = render_report("w1.t1-a", report, body)

    assert "in-progress" in out
    assert "<danger>" not in out
    assert "&lt;danger&gt;" in out
    assert "&amp;" in out
    assert "<pre>" in out


def test_render_report_escapes_task_id_in_title_and_heading():
    report = Report(id="w1.t1-a", status="todo")
    out = render_report("w1.t1-<a>", report, "본문.")
    assert "<a>" not in out
    assert "&lt;a&gt;" in out


# --- render_error ---


def test_render_error_has_no_traceback_and_shows_message():
    out = render_error(500, "progress.md 형식 오류: 뭔가 잘못됨")
    assert "Traceback" not in out
    assert "형식 오류" in out
    assert "500" in out


def test_render_error_escapes_message():
    out = render_error(404, "<script>bad</script>")
    assert "<script>bad</script>" not in out


# --- resolve_report_path: 경로 탐색 방어 ---


def test_resolve_report_path_accepts_normal_task_id(tmp_path: Path):
    (tmp_path / "report").mkdir()
    resolved = resolve_report_path(tmp_path, "w1.t1-hub-init")
    assert resolved == (tmp_path / "report" / "w1.t1-hub-init.md").resolve()


def test_resolve_report_path_rejects_slash(tmp_path: Path):
    assert resolve_report_path(tmp_path, "a/b") is None


def test_resolve_report_path_rejects_backslash(tmp_path: Path):
    assert resolve_report_path(tmp_path, "a\\b") is None


def test_resolve_report_path_rejects_dotdot(tmp_path: Path):
    assert resolve_report_path(tmp_path, "..") is None
    assert resolve_report_path(tmp_path, "../secret") is None


def test_resolve_report_path_rejects_percent_encoded_traversal(tmp_path: Path):
    # unquote 후 "../../secret"이 되는 입력.
    assert resolve_report_path(tmp_path, "..%2f..%2fsecret") is None


def test_resolve_report_path_rejects_empty_and_null(tmp_path: Path):
    assert resolve_report_path(tmp_path, "") is None
    assert resolve_report_path(tmp_path, "a%00b") is None


@pytest.mark.parametrize("task_id", ["C:foo", "foo:stream", "W1.T1-A", "a:b", "café", "a b"])
def test_resolve_report_path_rejects_non_canonical_grammar(tmp_path: Path, task_id):
    # ':'(드라이브 상대경로·ADS)·대문자(대소문자 무관 FS 별칭)·비ASCII·공백은
    # 허용목록 [a-z0-9._-] 밖이라 거부한다.
    assert resolve_report_path(tmp_path, task_id) is None


def test_resolve_report_path_rejects_report_dir_symlink_escape(tmp_path: Path):
    # <root>/report 가 root 밖을 가리키는 심볼릭 링크면 거부한다(1차 방어).
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "w1.t1-a.md").write_text("secret", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    try:
        (root / "report").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("심볼릭 링크 생성 권한이 없는 환경")
    assert resolve_report_path(root, "w1.t1-a") is None
