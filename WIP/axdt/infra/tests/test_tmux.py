"""tmux 모듈 — read_increment는 실제 파일 IO, 나머지는 proc 경유."""
import pytest

from axdt.infra import naming, proc, tmux


@pytest.fixture
def i():
    return naming.parse("w3.t12-auth-login")


# --- read_increment (실 파일 IO, 목 없음) ---

def test_read_increment_from_zero(tmp_path):
    f = tmp_path / "c.log"
    f.write_bytes(b"hello")
    text, off = tmux.read_increment(f, 0)
    assert text == "hello"
    assert off == 5


def test_read_increment_only_new(tmp_path):
    f = tmp_path / "c.log"
    f.write_bytes(b"hello")
    _, off = tmux.read_increment(f, 0)
    f.write_bytes(b"hello world")
    text, off2 = tmux.read_increment(f, off)
    assert text == " world"
    assert off2 == 11


def test_read_increment_holds_partial_multibyte(tmp_path):
    f = tmp_path / "c.log"
    # "é" == b"\xc3\xa9"; 첫 바이트만 우선 도착
    f.write_bytes(b"x\xc3")
    text, off = tmux.read_increment(f, 0)
    assert text == "x"
    assert off == 1            # 0xc3은 보류
    f.write_bytes(b"x\xc3\xa9")
    text2, off2 = tmux.read_increment(f, off)
    assert text2 == "é"
    assert off2 == 3


def test_read_increment_missing_file(tmp_path):
    text, off = tmux.read_increment(tmp_path / "nope.log", 0)
    assert text == ""
    assert off == 0


# --- new_window / resolve_window ---

def test_new_window_returns_captured_id(i, fake_proc):
    fake_proc.handler = lambda argv, kw: proc.ProcResult(argv, 0, "@7\n", "")
    win_id = tmux.new_window("w3.t12-auth-login", ["docker", "run"], cwd="/x")
    assert win_id == "@7"
    j = " ".join(fake_proc.last())
    assert "new-window" in j and "-n w3.t12-auth-login" in j and "window_id" in j


def test_resolve_window_exact_match_not_prefix(i, fake_proc):
    fake_proc.handler = lambda argv, kw: proc.ProcResult(
        argv, 0,
        "@3 other\n@7 w3.t12-auth-login\n@9 w3.t12-auth-login-extra\n", "")
    assert tmux.resolve_window(i) == "@7"


def test_resolve_window_none_when_absent(i, fake_proc):
    fake_proc.handler = lambda argv, kw: proc.ProcResult(argv, 0, "@3 other\n", "")
    assert tmux.resolve_window(i) is None


# --- send_text 라우팅 ---

def test_send_text_plain_uses_send_keys_literal(fake_proc):
    tmux.send_text("@7", "hello")
    j = " ".join(fake_proc.last())
    assert "send-keys" in j and "-l" in j and "hello" in j


def test_send_text_plain_has_no_enter(fake_proc):
    tmux.send_text("@7", "hello")
    # literal만, Enter 키 토큰 없음
    assert "Enter" not in fake_proc.last()


def test_send_text_multiline_uses_paste_buffer(fake_proc):
    tmux.send_text("@7", "line1\nline2")
    assert fake_proc.find("load-buffer") is not None
    assert fake_proc.find("paste-buffer", "@7") is not None


# --- start_capture / kill ---

def test_start_capture_truncates_and_pipes(tmp_path, fake_proc):
    log = tmp_path / "c.log"
    log.write_text("stale")
    tmux.start_capture("@7", log)
    assert log.read_text() == ""               # truncated
    assert fake_proc.find("pipe-pane") is not None


def test_kill_window(fake_proc):
    tmux.kill_window("@7")
    assert fake_proc.find("kill-window", "@7") is not None


# --- ensure_session ---

def test_ensure_session_creates_when_missing(fake_proc):
    def h(argv, kw):
        rc = 1 if "has-session" in " ".join(argv) else 0
        return proc.ProcResult(argv, rc, "", "")
    fake_proc.handler = h
    tmux.ensure_session()
    assert fake_proc.find("new-session") is not None


def test_ensure_session_noop_when_exists(fake_proc):
    fake_proc.handler = lambda argv, kw: proc.ProcResult(argv, 0, "", "")
    tmux.ensure_session()
    assert fake_proc.find("new-session") is None
