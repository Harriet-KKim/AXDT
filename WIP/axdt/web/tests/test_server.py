"""HTTP 레벨 통합 테스트 — http.server를 port 0(임의 포트)로 띄우고
urllib.request/raw socket으로 실제 요청을 보내 검증한다.

순수 렌더 로직 자체는 test_render.py가 이미 검증하므로, 여기서는 라우팅·
상태코드·read-only 불변식·경로 탐색 방어가 실제 HTTP 스택 위에서도 지켜지는지만
확인한다.
"""
from __future__ import annotations

import socket
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from axdt.web.server import make_server


# --- 서버 기동/종료 픽스처 ---


class _RunningServer:
    def __init__(self, root: Path):
        self.server = make_server(root, "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self._thread.join(timeout=5)
        self.server.server_close()

    def raw_get(self, raw_path: str) -> tuple[int, bytes]:
        """urllib을 거치지 않고 소켓으로 raw_path를 그대로 요청줄에 보낸다.

        urllib/http.client가 URL을 재해석해 '..' 세그먼트를 미리 접어버리는 걸
        피하고, 서버가 실제로 받는 바이트 그대로 경로 탐색 방어를 검증하기 위함.
        """
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as sock:
            request = f"GET {raw_path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n"
            sock.sendall(request.encode("utf-8"))
            chunks = []
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            data = b"".join(chunks)
        status_line = data.split(b"\r\n", 1)[0]
        status = int(status_line.split(b" ")[1])
        return status, data

    def raw_request(self, method: str, raw_path: str = "/") -> tuple[int, dict[str, str], bytes]:
        """임의 메서드를 요청줄에 그대로 보내 상태·헤더·본문을 돌려준다.

        urllib이 거부하거나 재해석하는 메서드(HEAD·OPTIONS·TRACE·임의 문자열)까지
        서버가 실제로 어떻게 응답하는지 검증하기 위함.
        """
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as sock:
            request = f"{method} {raw_path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n"
            sock.sendall(request.encode("utf-8"))
            chunks = []
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            data = b"".join(chunks)
        head, _, body = data.partition(b"\r\n\r\n")
        lines = head.split(b"\r\n")
        status = int(lines[0].split(b" ")[1])
        headers = {}
        for line in lines[1:]:
            key, _, value = line.partition(b":")
            headers[key.decode("latin-1").strip().lower()] = value.decode("latin-1").strip()
        return status, headers, body


@pytest.fixture
def running(tmp_path: Path):
    srv = _RunningServer(tmp_path)
    yield srv
    srv.close()


def _write_progress(root: Path, text: str) -> None:
    (root / "progress.md").write_text(text, encoding="utf-8")


def _write_report(root: Path, task: str, status: str, body: str = "본문.\n") -> None:
    report_dir = root / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"{task}.md").write_text(
        f"---\nid: {task}\nstatus: {status}\n---\n\n{body}", encoding="utf-8"
    )


_PROGRESS_HEADER = "| wave | task | status | leader | updated |\n|---|---|---|---|---|\n"


# --- 개요(GET /) ---


def test_overview_lists_rows_and_links_only_existing_report(running, tmp_path):
    _write_progress(
        tmp_path,
        _PROGRESS_HEADER
        + "| w1 | w1.t1-a | accepted | L-alice | 2026-07-05 |\n"
        + "| w1 | w1.t1-b | todo | L-bob | 2026-07-05 |\n",
    )
    _write_report(tmp_path, "w1.t1-a", "done")

    with urlopen(f"{running.base_url}/") as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8")

    assert '<a href="/report/w1.t1-a">w1.t1-a</a>' in body
    assert "w1.t1-b" in body
    assert '<a href="/report/w1.t1-b">' not in body


def test_overview_missing_progress_md_returns_error_page_not_traceback(running):
    with pytest.raises(HTTPError) as exc_info:
        urlopen(f"{running.base_url}/")
    err = exc_info.value
    assert err.code == 500
    body = err.read().decode("utf-8")
    assert "Traceback" not in body


def test_overview_malformed_progress_md_returns_error_page(running, tmp_path):
    _write_progress(tmp_path, "| wave | task | state | leader | updated |\n|---|---|---|---|---|\n")

    with pytest.raises(HTTPError) as exc_info:
        urlopen(f"{running.base_url}/")
    err = exc_info.value
    assert err.code == 500
    body = err.read().decode("utf-8")
    assert "Traceback" not in body


def test_overview_tolerates_bom_prefixed_progress(running, tmp_path):
    # 편집기가 붙인 선행 BOM이 있어도 개요가 정상 렌더돼야 한다(utf-8-sig 읽기).
    (tmp_path / "progress.md").write_text(
        "﻿" + _PROGRESS_HEADER + "| w1 | w1.t1-a | todo | L-a | 2026-07-05 |\n",
        encoding="utf-8",
    )
    with urlopen(f"{running.base_url}/") as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8")
    assert "w1.t1-a" in body


def test_error_page_does_not_leak_absolute_path(running, tmp_path):
    # progress.md 부재 → 500. 오류 페이지에 서버 절대경로가 노출되면 안 된다.
    with pytest.raises(HTTPError) as exc_info:
        urlopen(f"{running.base_url}/")
    body = exc_info.value.read().decode("utf-8")
    assert str(tmp_path) not in body
    assert "Traceback" not in body


# --- 드릴다운(GET /report/<id>) ---


def test_report_drilldown_returns_badge_and_escaped_body(running, tmp_path):
    _write_progress(tmp_path, _PROGRESS_HEADER)
    _write_report(tmp_path, "w1.t1-a", "blocked", body="블로커: <secret> & 계속\n")

    with urlopen(f"{running.base_url}/report/w1.t1-a") as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8")

    assert "blocked" in body
    assert "<secret>" not in body
    assert "&lt;secret&gt;" in body


def test_report_missing_returns_404(running, tmp_path):
    _write_progress(tmp_path, _PROGRESS_HEADER)

    with pytest.raises(HTTPError) as exc_info:
        urlopen(f"{running.base_url}/report/no-such-task")
    assert exc_info.value.code == 404


# --- 경로 탐색 방어 ---


def test_path_traversal_percent_encoded_dotdot_rejected(running, tmp_path):
    # report 디렉터리 바로 밖에 secret 파일을 둔다 -- 절대 응답에 포함돼선 안 됨.
    secret = tmp_path / "secret.md"
    secret.write_text("SECRET-CONTENT", encoding="utf-8")
    _write_progress(tmp_path, _PROGRESS_HEADER)

    status, data = running.raw_get("/report/..%2f..%2fsecret")
    assert status == 404
    assert b"SECRET-CONTENT" not in data


def test_path_traversal_literal_dotdot_rejected(running, tmp_path):
    _write_progress(tmp_path, _PROGRESS_HEADER)
    status, data = running.raw_get("/report/../foo")
    assert status == 404


@pytest.mark.parametrize("task_id", ["a/b", "a%2fb", "a\\b", ".."])
def test_report_task_id_with_forbidden_chars_rejected(running, tmp_path, task_id):
    _write_progress(tmp_path, _PROGRESS_HEADER)
    status, _data = running.raw_get(f"/report/{task_id}")
    assert status == 404


@pytest.mark.parametrize("task_id", ["C:foo", "foo:stream", "W1.T1-A"])
def test_report_non_canonical_task_id_rejected(running, tmp_path, task_id):
    # ':'(드라이브 상대경로·NTFS ADS)·대문자(대소문자 무관 FS 별칭)는 허용목록 밖 → 404.
    _write_progress(tmp_path, _PROGRESS_HEADER)
    status, _data = running.raw_get(f"/report/{task_id}")
    assert status == 404


# --- read-only 불변식 ---


def test_post_returns_405(running, tmp_path):
    _write_progress(tmp_path, _PROGRESS_HEADER)
    req = Request(f"{running.base_url}/", method="POST")
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)
    assert exc_info.value.code == 405


def test_put_returns_405(running, tmp_path):
    _write_progress(tmp_path, _PROGRESS_HEADER)
    req = Request(f"{running.base_url}/report/w1.t1-a", method="PUT")
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)
    assert exc_info.value.code == 405


def test_unknown_path_returns_404(running, tmp_path):
    _write_progress(tmp_path, _PROGRESS_HEADER)
    with pytest.raises(HTTPError) as exc_info:
        urlopen(f"{running.base_url}/nope")
    assert exc_info.value.code == 404


def test_post_does_not_create_any_file(running, tmp_path):
    req = Request(f"{running.base_url}/report/new-task", method="POST", data=b"hello")
    with pytest.raises(HTTPError):
        urlopen(req)
    assert not (tmp_path / "report").exists()


@pytest.mark.parametrize(
    "method", ["POST", "PUT", "DELETE", "PATCH", "OPTIONS", "TRACE", "PROPFIND", "FOO"]
)
def test_non_get_methods_return_405_with_allow_header(running, tmp_path, method):
    # 쓰기 4종뿐 아니라 HEAD 외 표준·비표준 메서드까지 전부 405(+Allow: GET),
    # stdlib 기본값 501로 새지 않아야 한다.
    _write_progress(tmp_path, _PROGRESS_HEADER)
    status, headers, _body = running.raw_request(method, "/")
    assert status == 405
    assert headers.get("allow") == "GET"


def test_head_returns_405_without_body(running, tmp_path):
    # HEAD도 405로 거부하되, HEAD 응답에는 본문을 싣지 않는다.
    _write_progress(tmp_path, _PROGRESS_HEADER)
    status, headers, body = running.raw_request("HEAD", "/")
    assert status == 405
    assert headers.get("allow") == "GET"
    assert body == b""
