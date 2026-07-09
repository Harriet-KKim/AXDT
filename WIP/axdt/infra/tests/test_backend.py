"""backend 모듈 — TmuxDockerBackend(SessionBackend) 계약·상태/에러.

협력 모듈(tmux/container/hub)을 monkeypatch로 격리.

SessionBackend 계약은 `axdt.agent_runner.backend`의 단일 ABC(정본)다. 이 모듈은
`axdt.infra.backend`가 그 정본을 재수출(re-export)하고 TmuxDockerBackend가
정본 계약(7 abstractmethod: start/send_text/read_new_output/is_alive/
exit_code/last_error/stop)을 온전히 구현하는지 검증한다.
"""
import pytest

from axdt.infra import backend, naming
from axdt.infra.backend import AlreadyStarted, NotStarted, SessionDead, SessionBackend
from axdt.agent_runner.backend import SessionBackend as CanonicalBackend
from axdt.agent_runner.runner import AgentRunner
from axdt.agent_runner.state import AgentState
from axdt.agent_runner.adapters.claude_code import ClaudeCodeAdapter


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
        exit_code = None  # container.exit_code 반환
    rec = Rec()
    rec.calls = []

    monkeypatch.setattr(backend.hub, "serve", lambda *a, **k: 9418)
    monkeypatch.setattr(backend.tmux, "ensure_session", lambda *a, **k: None)
    monkeypatch.setattr(backend.tmux, "start_capture", lambda *a, **k: rec.calls.append("capture"))
    monkeypatch.setattr(backend.tmux, "send_text", lambda w, t: rec.calls.append(("send", w, t)))
    monkeypatch.setattr(backend.tmux, "read_increment", lambda log, off: ("chunk", off + 5))
    monkeypatch.setattr(backend.tmux, "kill_window", lambda w: rec.calls.append(("kill", w)))
    monkeypatch.setattr(backend.tmux, "resolve_window", lambda ident, **k: rec.resolve)

    def fake_run_args(*a, **k):
        return ["docker", "run"]
    monkeypatch.setattr(backend.container, "run_args", fake_run_args)
    monkeypatch.setattr(backend.container, "exists", lambda ident: rec.external_exists)
    monkeypatch.setattr(backend.container, "is_running", lambda ident: rec.alive)
    monkeypatch.setattr(backend.container, "exit_code", lambda ident: rec.exit_code)
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


def test_reexports_canonical_session_backend():
    # 정본은 axdt.agent_runner.backend에 유일해야 한다(중복 인라인 ABC 금지).
    assert backend.SessionBackend is CanonicalBackend


def test_conforms_to_canonical_backend_contract(i, tmp_path, env):
    assert isinstance(_mk(i, tmp_path), CanonicalBackend)


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


def test_read_new_output_before_start_raises_not_started(i, tmp_path, env):
    # 스펙(2026-06-26 phase3 설계 85행): NOT_STARTED에서 read_new_output도
    # send_text와 동일하게 NotStarted를 던져야 한다(재리뷰 C6b).
    b = _mk(i, tmp_path)
    with pytest.raises(NotStarted):
        b.read_new_output()


def test_read_new_output_drains(i, tmp_path, env):
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    assert b.read_new_output() == "chunk"


def test_read_new_output_drains_after_death(i, tmp_path, env):
    # 스펙 86행: 죽은 뒤에도 남은 로그 증분을 반환해야 한다(드레인 허용).
    # is_alive()/status()로 막으면 안 된다 — NOT_STARTED 게이트만 적용.
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    env.alive = False
    assert b.is_alive() is False
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
    # 사후 진단 맥락 보존: 재raise 전에 last_error 기록
    assert b.last_error() == "capture failed"


def test_start_resets_last_error_on_later_success(i, tmp_path, env, monkeypatch):
    # 실패로 last_error가 남은 뒤, 결함을 제거하고 재시작에 성공하면 이전
    # 실패의 흔적(stale last_error)이 지워져야 한다.
    def boom(*a, **k):
        raise RuntimeError("capture failed")
    monkeypatch.setattr(backend.tmux, "start_capture", boom)
    b = _mk(i, tmp_path)
    with pytest.raises(RuntimeError):
        b.start(["cmd"], tmp_path)
    assert b.last_error() == "capture failed"

    # 결함 제거: start_capture가 정상 동작하도록 복구.
    # _cleanup의 kill_window로 외부 윈도우도 실제로 사라졌다고 가정하고
    # resolve_window 결과를 리셋한다(그래야 재-start의 사전 fail-fast를 통과).
    monkeypatch.setattr(backend.tmux, "start_capture",
                         lambda *a, **k: env.calls.append("capture"))
    env.resolve = None
    b.start(["cmd"], tmp_path)
    assert b.last_error() is None


def test_status_reports_not_started(i, tmp_path, env):
    b = _mk(i, tmp_path)
    assert b.status() == "NOT_STARTED"


def test_start_records_resolved_port_from_serve(i, tmp_path, env, monkeypatch):
    # hub.serve가 (포트 충돌 폴백 등으로) self.port와 다른 포트를 선택했을 때, start는
    # 그 반환값으로 self.port를 갱신해야 한다. 컨테이너로의 포트 전파는 run_args가
    # 아니라 provision이 심어둔 origin 원격 URL 경로이므로, 여기서는 self.port
    # 갱신만 검증한다.
    monkeypatch.setattr(backend.hub, "serve", lambda *a, **k: 23456)
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    assert b.port == 23456


# --- exit_code / last_error (F1: 정본 계약의 두 메서드) ---

def test_exit_code_none_while_alive(i, tmp_path, env):
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    assert b.is_alive() is True
    assert b.exit_code() is None


def test_exit_code_reports_clean_exit(i, tmp_path, env):
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    env.alive = False
    env.external_exists = True
    env.exit_code = 0
    assert b.exit_code() == 0
    assert b.last_error() is None


def test_exit_code_reports_crash(i, tmp_path, env):
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    env.alive = False
    env.external_exists = True
    env.exit_code = 3
    assert b.exit_code() == 3


def test_stop_defaults_exit_code_to_zero_when_unknown(i, tmp_path, env):
    # FakeBackend.stop()의 "exit_code 기본 0" 시맨틱과 일치해야 한다.
    b = _mk(i, tmp_path)
    b.start(["cmd"], tmp_path)
    env.alive = False
    env.external_exists = False  # 컨테이너 자체가 사라져 exit_code 포착 불가
    b.stop()
    assert b.exit_code() == 0


# --- 교차패키지 통합: AgentRunner(정본) + TmuxDockerBackend ---
# 회귀 목적: 구 infra 인라인 ABC는 exit_code/last_error가 없어 poll_state()가
# 세션 사망 시 AttributeError로 죽었다(재리뷰 결함 F1). 아래는 AttributeError
# 없이 ERROR/STOPPED로 정확히 분류됨을 고정한다.

def test_agent_runner_poll_state_reports_error_on_crash(i, tmp_path, env):
    b = _mk(i, tmp_path)
    runner = AgentRunner(ClaudeCodeAdapter(), b)
    runner.start_session(tmp_path)
    env.alive = False
    env.external_exists = True
    env.exit_code = 3
    assert runner.poll_state() is AgentState.ERROR


def test_agent_runner_poll_state_reports_stopped_on_clean_exit(i, tmp_path, env):
    b = _mk(i, tmp_path)
    runner = AgentRunner(ClaudeCodeAdapter(), b)
    runner.start_session(tmp_path)
    env.alive = False
    env.external_exists = True
    env.exit_code = 0
    assert runner.poll_state() is AgentState.STOPPED
