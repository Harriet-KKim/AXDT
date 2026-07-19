"""읽기 전용 interim 뷰어 — 요청 핸들러 + 순수 렌더 함수 + 서버 구동.

progress.md·report/<task>.md 파싱은 axdt.progress.table을 그대로 재사용한다
(단일 진실원 — 여기서 MD 테이블·frontmatter를 다시 파싱하지 않는다). 이 모듈이
새로 하는 일은 HTML 렌더링과 HTTP 라우팅뿐이다.

라우트(전부 GET, 읽기 전용):
  GET /              — progress.md 개요 테이블
  GET /report/<id>   — report/<id>.md 드릴다운(상태 배지 + 본문)
GET만 콘텐츠를 제공하고, 그 밖의 모든 메서드(HEAD·OPTIONS·쓰기 등)는 405(Allow: GET).
알 수 없는 경로·존재하지 않는 report는 404.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from axdt.progress.table import (
    ProgressFormatError,
    Report,
    ReportFormatError,
    TaskRow,
    parse_progress,
    parse_report,
    report_body,
)

__all__ = [
    "render_overview",
    "render_report",
    "render_error",
    "resolve_report_path",
    "make_server",
    "build_parser",
    "main",
]

_DEFAULT_ROOT = "docs/interim"
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000

_STYLE = """
body { font-family: sans-serif; margin: 2rem; color: #1a1a1a; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }
th { background: #f0f0f0; }
.badge { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 0.8rem;
         background: #e0e0e0; font-size: 0.9rem; margin: 0.5rem 0; }
pre { white-space: pre-wrap; background: #f7f7f7; border: 1px solid #ddd;
      padding: 1rem; border-radius: 0.3rem; }
"""


def _page(title: str, body_html: str) -> str:
    return (
        "<!doctype html>\n<html><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body>{body_html}</body></html>\n"
    )


# --- task_id 허용 판정(단일 진실원: 개요 링크와 드릴다운이 같은 판정을 쓴다) ---


_TASK_ID_RE = re.compile(r"[a-z0-9._-]+")


def _is_admissible_task_id(task_id: str) -> bool:
    """드릴다운(resolve_report_path)이 받아들일 task_id인지 — 안전 문자 집합
    ``[a-z0-9._-]`` 이고 '..'를 포함하지 않는가. 개요 링크도 이 판정으로 걸어야
    링크가 걸린 task는 클릭 시 반드시 열린다(둘의 판정이 어긋나지 않게)."""
    return bool(task_id) and ".." not in task_id and _TASK_ID_RE.fullmatch(task_id) is not None


# --- 순수 렌더 함수 ---


def render_error(status: int, message: str) -> str:
    """스택트레이스 없는, 사람이 읽을 오류 페이지."""
    body = f"<h1>오류 {status}</h1><p>{html.escape(message)}</p>"
    return _page(f"오류 {status}", body)


def render_overview(rows: list[TaskRow], report_dir: Path) -> str:
    """progress 행 목록 → 개요 HTML 테이블.

    task 셀은 task가 드릴다운 허용 문법이고 canonical 경로 report_dir/<task>.md가
    실제로 존재할 때만 /report/<task> 링크로 건다(아니면 링크 없는 텍스트) —
    링크 판정과 드릴다운 판정을 같은 헬퍼로 통일해 깨진 링크를 만들지 않는다.
    """
    header_cells = "".join(
        f"<th>{html.escape(col)}</th>" for col in ("wave", "task", "status", "leader", "updated")
    )
    body_rows = "".join(_overview_row(row, report_dir) for row in rows)
    table_html = f"<table><tr>{header_cells}</tr>{body_rows}</table>"
    return _page("AXDT progress 개요", f"<h1>progress 개요</h1>{table_html}")


def _overview_row(row: TaskRow, report_dir: Path) -> str:
    report_path = report_dir / f"{row.task}.md"
    if _is_admissible_task_id(row.task) and report_path.is_file():
        # task_cell은 이미 완성된 HTML(escape된 텍스트를 담은 <a> 태그)이므로
        # 아래에서 다른 셀들처럼 다시 html.escape하면 태그 자체가 깨진다.
        task_cell = (
            f'<a href="/report/{quote(row.task, safe="")}">{html.escape(row.task)}</a>'
        )
    else:
        task_cell = html.escape(row.task)
    plain_cells = (
        f"<td>{html.escape(row.wave)}</td>"
        f"<td>{task_cell}</td>"
        f"<td>{html.escape(row.status)}</td>"
        f"<td>{html.escape(row.leader)}</td>"
        f"<td>{html.escape(row.updated)}</td>"
    )
    return f"<tr>{plain_cells}</tr>"


def render_report(task_id: str, report: Report, body: str) -> str:
    """report 드릴다운 HTML — status 배지 + 본문(escape 후 <pre>)."""
    badge = f'<span class="badge">{html.escape(report.status)}</span>'
    body_html = f"<pre>{html.escape(body)}</pre>"
    content = f"<h1>report: {html.escape(task_id)}</h1>{badge}{body_html}"
    return _page(f"report: {task_id}", content)


# --- 경로 탐색 방어 ---


def resolve_report_path(root: Path, raw_task_id: str) -> Path | None:
    """<root>/report/<task_id>.md의 안전한 절대경로를 해석.

    task_id는 안전 문자 집합 ``[a-z0-9._-]`` 만 허용한다(정규 task-id는 이 안에
    들며, 뷰어라 엄격한 D14 문법까지 강제하진 않는다 — 이름이 약간 어긋난 report도
    표시). 이 허용목록 하나가 '/'·'\\'·':'(Windows 드라이브 상대경로·NTFS ADS)·
    널문자·대문자(대소문자 무관 파일시스템의 별칭 혼동)를 한꺼번에 막는다. '..'는
    점이 허용목록에 있으므로 따로 거부한다(헬퍼 `_is_admissible_task_id`가 개요
    링크 판정과 이 검사를 단일 진실원으로 공유한다). <root>/report/가 심볼릭 링크로
    root 밖을 가리키면 거부하고(1차), 해석한 실제 경로가 <root>/report/ 밖이면
    역시 None(2차 방어).
    """
    try:
        task_id = unquote(raw_task_id, errors="strict")
    except UnicodeDecodeError:
        return None

    if not _is_admissible_task_id(task_id):
        return None

    root_resolved = Path(root).resolve()
    report_dir = (root_resolved / "report").resolve()
    try:
        report_dir.relative_to(root_resolved)
    except ValueError:
        return None

    candidate = (report_dir / f"{task_id}.md").resolve()
    try:
        candidate.relative_to(report_dir)
    except ValueError:
        return None
    return candidate


# --- HTTP 서버 ---


class _InterimHTTPServer(ThreadingHTTPServer):
    """root(interim 디렉터리)를 핸들러에 전달하기 위한 서버 서브클래스."""

    def __init__(self, server_address: tuple[str, int], handler_class, root: Path) -> None:
        self.root = Path(root)
        super().__init__(server_address, handler_class)


class _Handler(BaseHTTPRequestHandler):
    server: _InterimHTTPServer  # type: ignore[assignment]

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # 로컬 개발용 read-only 뷰어라 접속 로그는 콘솔에 남기지 않는다
        # (Windows 콘솔 인코딩 문제도 회피).
        pass

    # --- 읽기 전용 불변식: GET만 콘텐츠 제공, 그 밖의 모든 메서드는 405 ---

    _ALLOW = "GET"

    def _reject_non_get(self, *, with_body: bool) -> None:
        """비-GET 요청을 405로 거부한다. Allow 헤더를 붙이고(RFC 9110 §15.5.6),
        HEAD 응답에는 본문을 싣지 않는다."""
        page = render_error(405, "읽기 전용 서버입니다. GET만 허용합니다.")
        encoded = page.encode("utf-8")
        self.send_response(405)
        self.send_header("Allow", self._ALLOW)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        if with_body:
            self.wfile.write(encoded)

    def do_HEAD(self) -> None:  # noqa: N802
        self._reject_non_get(with_body=False)

    def __getattr__(self, name: str):
        # do_GET·do_HEAD는 정의돼 있어 여기 오지 않는다. 그 밖의 do_<METHOD>
        # (POST·PUT·DELETE·PATCH·OPTIONS·TRACE·CONNECT·임의 메서드)를 전부 405로
        # 거부해, 핸들러가 없을 때 stdlib이 내는 기본값 501로 새지 않게 한다.
        if name.startswith("do_"):
            return lambda: self._reject_non_get(with_body=True)
        raise AttributeError(name)

    # --- GET 라우팅 ---

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        root = self.server.root
        if path == "/":
            self._handle_overview(root)
        elif path.startswith("/report/"):
            self._handle_report(root, path[len("/report/") :])
        else:
            self._send_html(404, render_error(404, "알 수 없는 경로입니다."))

    def _handle_overview(self, root: Path) -> None:
        progress_path = root / "progress.md"
        try:
            # utf-8-sig: 편집기가 붙인 선행 BOM을 허용(report 파서의 관용과 정책 일치).
            text = progress_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            # 절대경로는 오류 페이지에 노출하지 않는다(비루프백 바인드 시 정보 유출 방지).
            self._send_html(500, render_error(500, "progress.md를 읽을 수 없습니다."))
            return
        try:
            rows = parse_progress(text)
        except ProgressFormatError as exc:
            self._send_html(500, render_error(500, f"progress.md 형식 오류: {exc}"))
            return
        self._send_html(200, render_overview(rows, root / "report"))

    def _handle_report(self, root: Path, raw_task_id: str) -> None:
        report_path = resolve_report_path(root, raw_task_id)
        if report_path is None or not report_path.is_file():
            self._send_html(404, render_error(404, "report를 찾을 수 없습니다."))
            return

        # raw_task_id는 위에서 이미 검증됐으므로 표시용으로 그대로 unquote해 쓴다.
        task_id = unquote(raw_task_id, errors="strict")
        try:
            text = report_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            # 절대경로는 오류 페이지에 노출하지 않는다.
            self._send_html(500, render_error(500, "report 파일을 읽을 수 없습니다."))
            return
        try:
            report = parse_report(text)
        except ReportFormatError as exc:
            self._send_html(500, render_error(500, f"report 형식 오류: {exc}"))
            return
        self._send_html(200, render_report(task_id, report, report_body(text)))

    def _send_html(self, status: int, body_html: str) -> None:
        encoded = body_html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def make_server(root: Path, host: str = _DEFAULT_HOST, port: int = _DEFAULT_PORT) -> _InterimHTTPServer:
    """root(interim 디렉터리)를 서빙하는 서버 인스턴스 생성(아직 accept 루프 시작 전)."""
    return _InterimHTTPServer((host, port), _Handler, Path(root))


# --- CLI ---


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m axdt.web", description="interim progress/report 읽기 전용 브리핑 서버"
    )
    p.add_argument("--root", default=_DEFAULT_ROOT, help=f"interim 디렉터리 경로(기본 {_DEFAULT_ROOT})")
    p.add_argument("--host", default=_DEFAULT_HOST, help=f"바인드 호스트(기본 {_DEFAULT_HOST})")
    p.add_argument("--port", type=int, default=_DEFAULT_PORT, help=f"바인드 포트(기본 {_DEFAULT_PORT})")
    return p


def main(argv: list[str] | None = None) -> int:
    # Windows cp949 콘솔 등에서 한글 출력이 UnicodeEncodeError로 죽는 걸 막는다
    # (axdt.sot_lint.cli.main과 동일 패턴).
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = build_parser().parse_args(argv)
    root = Path(args.root)
    server = make_server(root, args.host, args.port)
    print(f"AXDT web briefing: http://{args.host}:{args.port}/  (root={root})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
