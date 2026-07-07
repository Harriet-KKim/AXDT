"""backend 모듈 — TmuxDockerBackend(SessionBackend) 계약·상태/에러.

협력 모듈(tmux/container/hub)을 monkeypatch로 격리.
"""
import pytest

from axdt.infra import backend, naming
from axdt.infra.backend import AlreadyStarted, NotStarted, SessionDead, SessionBackend


@pytest.fixture
def i():
    return naming.parse("w3.t12-auth-login")


@pytest.fixture
def env(monkeypatch, tmp_path):
    """협력 모듈을 가짜로 교체하고 상태를 제어하는 레코더."""
    class Rec:
        calls = None
        alive = True
        win = "@7"
        external_exists = False
        resolve = None  # tmux.resolve_window 반환
    rec = Rec()
    rec.calls = []

    monkeypatch.setattr(backend.hub, "serve", lambda *a, **k: 9418)
    monkeypatch.setattr(backend.tmux, "ensure_session", lambda *a, **k: None)
    monkeypatch.setattr(backend.tmux, "start_capture", lambda *a, **k: rec.calls.append("capture"))
    monkeypatch.setattr(backend.tmux, "send_text", lambda w, t: rec.calls.append(("send", w, t)))
    monkeypatch.setattr(backend.tmux, "read_increment", lambda log, off: ("chunk", off + 5))
    monkeypatch.setattr(backend.tmux, "kill_window", lambda w: rec.calls.append(("kill", w)))
    monkeypatch.setattr(backend.tmux, "resolve_window", lambda ident, **k: rec.resolve)
    monkeypatch.setattr(backend.container, "run_args", lambda *a, **k: ["docker", "run"])
    monkeypatch.setattr(backend.container, "exists", lambda ident: rec.external_exists)
    monkeypatch.setattr(backend.container, "is_running", lambda ident: rec.alive)
    monkeypatch.setattr(backend.container, "stop", lambda ident: rec.calls.append("stop"))
    monkeypatch.setattr(backend.container, "rm", lambda ident: rec.calls.append("rm"))

    def fake_new_window(window, argv, cwd, **k):
        rec.calls.append("new_window")
        rec.resolve = rec.win  # 생성 후 lookup 가능
        return rec.win
    monkeypatch.setattr(backend.tmux, "new_window", fake_new_window)
    return rec


def _mk(i, tmp_path):
    return backend.TmuxDockerBackend(i, tmp_path, uid=1000, gid=1000)


def test_is_a_session_backend(i, tmp_path, env):
    assert isinstance(_mk(i, tmp_path), SessionBackend)


def test_start_runs_and_alive(i, tmp_path, env):
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    assert "new_window" in env.calls and "capture" in env.calls
    assert b.is_alive() is True


def test_start_twice_raises_already_started(i, tmp_path, env):
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    with pytest.raises(AlreadyStarted):
        b.start(["cmd"], tmp_path)


def test_start_fail_fast_when_external_exists(i, tmp_path, env):
    env.external_exists = True
    b = _mk(i, tmp_path)
    with pytest.raises(AlreadyStarted):
        b.start(["cmd"], tmp_path)


def test_start_missing_workdir_raises(i, tmp_path, env):
    b = _mk(i, tmp_path)
    with pytest.raises(FileNotFoundError):
        b.start(["cmd"], tmp_path / "nope")


def test_send_before_start_raises_not_started(i, tmp_path, env):
    b = _mk(i, tmp_path)
    with pytest.raises(NotStarted):
        b.send_text("hi")


def test_send_after_start_targets_window(i, tmp_path, env):
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    b.send_text("ping")
    assert ("send", "@7", "ping") in env.calls


def test_send_when_dead_raises_session_dead(i, tmp_path, env):
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    env.alive = False
    with pytest.raises(SessionDead):
        b.send_text("ping")


def test_read_new_output_drains(i, tmp_path, env):
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    assert b.read_new_output() == "chunk"


def test_stop_is_idempotent(i, tmp_path, env):
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    b.stop()
    b.stop()  # no raise
    assert "stop" in env.calls and "rm" in env.calls


def test_start_compensates_on_failure(i, tmp_path, env, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("capture failed")
    monkeypatch.setattr(backend.tmux, "start_capture", boom)
    b = _mk(i, tmp_path)
    with pytest.raises(RuntimeError):
        b.start(["cmd"], tmp_path)
    # 보상 정리: 컨테이너 rm 호출
    assert "rm" in env.calls


def test_status_reports_not_started(i, tmp_path, env):
    b = _mk(i, tmp_path)
    assert b.status() == "NOT_STARTED"
