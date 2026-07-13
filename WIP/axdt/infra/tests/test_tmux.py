"""tmux 모듈 — read_increment는 실제 파일 IO, 나머지는 proc 경유."""
import os

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


def test_send_text_multiline_uses_unique_buffer(fake_proc):
    # 병렬 세션 교차 오염 방지: 고정 "axdt"가 아니라 고유 버퍼명을 쓰고,
    # load-buffer와 paste-buffer가 같은 버퍼명을 짝지어야 한다(R5 중대4).
    tmux.send_text("@7", "a\nb")
    load = fake_proc.find("load-buffer")
    paste = fake_proc.find("paste-buffer", "@7")
    assert load is not None and paste is not None
    load_buf = load[load.index("-b") + 1]
    paste_buf = paste[paste.index("-b") + 1]
    assert load_buf.startswith("axdt-") and load_buf != "axdt"
    assert load_buf == paste_buf


def test_send_text_multiline_deletes_buffer_on_paste_failure(fake_proc):
    # paste-buffer가 실패하면 -d가 고유 버퍼를 못 지운다 — finally에서 같은 버퍼명을
    # delete-buffer로 정리해야 한다(R6 경미3). 원예외는 그대로 전파.
    def h(argv, kw):
        if "paste-buffer" in " ".join(argv):
            raise RuntimeError("paste failed")
        return proc.ProcResult(argv, 0, "", "")

    fake_proc.handler = h
    with pytest.raises(RuntimeError):
        tmux.send_text("@7", "a\nb")
    load = fake_proc.find("load-buffer")
    delete = fake_proc.find("delete-buffer")
    assert load is not None and delete is not None
    load_buf = load[load.index("-b") + 1]
    del_buf = delete[delete.index("-b") + 1]
    assert del_buf == load_buf          # load와 같은 고유 버퍼를 정리


def test_send_text_multiline_deletes_buffer_on_success(fake_proc):
    # 성공 경로에서도 finally의 delete-buffer가 항상 돌아 고유 버퍼가 남지 않는다.
    tmux.send_text("@7", "a\nb")
    assert fake_proc.find("delete-buffer") is not None


# --- _load_buffer (실 임시파일 IO — 성공/실패 양쪽 unlink·utf-8 검증) ---

def test_load_buffer_writes_utf8_and_unlinks(fake_proc):
    captured: dict = {}

    def h(argv, kw):
        if "load-buffer" in " ".join(argv):
            path = argv[-1]
            captured["path"] = path
            captured["content"] = open(path, encoding="utf-8").read()
        return proc.ProcResult(argv, 0, "", "")

    fake_proc.handler = h
    tmux._load_buffer("한글 🚀 멀티\n라인", "axdt-test-buf")
    assert captured["content"] == "한글 🚀 멀티\n라인"     # utf-8로 정확히 기록
    assert not os.path.exists(captured["path"])            # 성공 시 임시파일 정리
    assert fake_proc.find("load-buffer", "axdt-test-buf") is not None  # 넘긴 버퍼명 사용


def test_load_buffer_warns_on_unlink_failure(fake_proc, monkeypatch, capsys):
    # os.unlink가 실패하면(파일 잠김 등) 조용히 삼키지 않고 stderr 경고를 낸다 —
    # 예외는 재발생시키지 않는다(기능 실패 아님, R8 경미4).
    def boom(_path):
        raise OSError("unlink denied")

    monkeypatch.setattr(tmux.os, "unlink", boom)
    tmux._load_buffer("x", "axdt-test-buf")   # 예외가 밖으로 새지 않아야 한다
    err = capsys.readouterr().err
    assert "prompt 임시 파일 정리 실패" in err


def test_load_buffer_unlinks_on_load_failure(fake_proc):
    captured: dict = {}

    def h(argv, kw):
        if "load-buffer" in " ".join(argv):
            captured["path"] = argv[-1]
            raise RuntimeError("load-buffer failed")
        return proc.ProcResult(argv, 0, "", "")

    fake_proc.handler = h
    with pytest.raises(RuntimeError):
        tmux._load_buffer("x", "axdt-test-buf")
    # load-buffer가 실패해도(예외) finally에서 임시파일이 정리돼야 한다.
    assert not os.path.exists(captured["path"])


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
