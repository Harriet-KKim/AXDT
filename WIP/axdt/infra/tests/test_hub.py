"""hub 모듈 — clone URL/daemon argv는 순수, init은 proc 경유."""
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from axdt.infra import config, hub, proc, tmux

_HAS_GIT = shutil.which("git") is not None


def test_clone_url_for_host_is_file_uri(tmp_path):
    assert hub.clone_url_for_host(tmp_path) == config.hub_repo(tmp_path).as_uri()


def test_clone_url_for_container_daemon(tmp_path):
    url = hub.clone_url_for_container(tmp_path, transport="daemon", port=9418)
    assert url == "git://host.docker.internal:9418/project.git"


def test_clone_url_for_container_rejects_non_daemon(tmp_path):
    # file:// RW 마운트는 pre-receive 게이트(ADR-0007)를 우회하므로 제거됐다(daemon 단일).
    with pytest.raises(ValueError):
        hub.clone_url_for_container(tmp_path, transport="file", port=9418)


def test_daemon_argv(tmp_path):
    argv = hub.daemon_argv(tmp_path, port=9418)
    j = " ".join(argv)
    assert "git" in argv and "daemon" in argv
    assert "--port=9418" in j
    assert "--enable=receive-pack" in j
    assert "--export-all" in j
    # git이 listener(git-daemon 자식) pid를 직접 쓰도록: 래퍼 Popen.pid는 listen하지
    # 않으므로(재리뷰 차단 결함), identity는 이 파일에 기록되는 pid로만 판정한다.
    assert f"--pid-file={config.daemon_pid(tmp_path)}" in argv


def test_init_requires_seed_or_empty(tmp_path, fake_proc):
    with pytest.raises(ValueError):
        hub.init(tmp_path)  # seed_from 없음 + empty=False
    assert fake_proc.calls == []  # proc 호출 전에 거부


def test_init_empty_only_inits_bare(tmp_path, fake_proc):
    hub.init(tmp_path, empty=True)
    assert fake_proc.find("init", "--bare") is not None
    assert fake_proc.find("clone", "--mirror") is None
    assert fake_proc.find("push", "--mirror") is None


def test_init_with_seed_clones_mirror(tmp_path, fake_proc):
    # seed는 clone --mirror로 모든 ref를 복제(비어있는 대상에만 생성).
    # push --mirror는 허브 pre-receive를 자기차단하므로 쓰지 않는다.
    seed = tmp_path / "canon"
    seed.mkdir()
    hub.init(tmp_path, seed_from=seed)
    assert fake_proc.find("clone", "--mirror") is not None
    assert fake_proc.find("init", "--bare") is None
    assert fake_proc.find("push", "--mirror") is None


def test_init_noop_when_hub_already_populated(tmp_path, fake_proc):
    # 권위 상태: 이미 내용 있으면 절대 덮어쓰지 않음
    repo = config.hub_repo(tmp_path)
    repo.mkdir(parents=True)
    (repo / "HEAD").write_text("ref: refs/heads/main\n")
    hub.init(tmp_path, empty=True)
    assert fake_proc.find("init", "--bare") is None
    assert fake_proc.find("clone", "--mirror") is None


# --- pre-receive allowlist 게이트(ADR-0007 (a)) ---

def test_install_gate_writes_executable_pre_receive_hook(tmp_path, fake_proc):
    repo = tmp_path / "hub.git"
    hub.install_gate(repo)
    hook = repo / "hooks" / "pre-receive"
    assert hook.exists()
    content = hook.read_text(encoding="utf-8")
    assert content.startswith("#!/bin/sh")
    # naming.py 식별자 정규식(refs/heads/ 접두, POSIX ERE 변환)이 훅에 그대로 박혀있어야 함.
    assert r"refs/heads/w[1-9][0-9]*\.t[1-9][0-9]*-[a-z0-9]+(-[a-z0-9]+)*$" in content
    assert "0000000000000000000000000000000000000000" in content  # zero-SHA 삭제 감지


def test_install_gate_configures_deny_deletes_and_reflog(tmp_path, fake_proc):
    repo = tmp_path / "hub.git"
    hub.install_gate(repo)
    assert fake_proc.find("config", "receive.denyDeletes", "true") is not None
    assert fake_proc.find("config", "core.logAllRefUpdates", "true") is not None


def _git(*args: str, cwd) -> subprocess.CompletedProcess:
    # encoding 고정: 훅 메시지가 원격 push 클라이언트로 그대로 전달되는데, 로컬 콘솔
    # codepage(예: 한글 Windows cp949)에 의존하면 디코드가 깨질 수 있어 utf-8로 고정.
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


# --- serve() 포트 충돌 처리(재리뷰 결함 C6a, spec §6.1:206 정합) ---
# _port_open과 데몬 spawn은 monkeypatch로 격리(단위 테스트에서 실제 기동 금지).
# identity 판정은 daemon.pid 기반이다(포트 점유자의 repo HEAD 비교 금지 — 금지 ①).
# 단위 테스트는 hub._is_our_daemon 자체를 monkeypatch해 serve()의 분기(재사용/폴백/
# fail-closed)만 검증하고, 그 하위 판정 로직(_pid_alive/_read_cmdline/_cmdline_matches/
# _pid_listens_on_port)은 별도 테스트에서 각자 monkeypatch 조합으로 검증한다.


def test_serve_returns_preferred_when_free(tmp_path, fake_proc, monkeypatch):
    monkeypatch.setattr(hub, "_port_open", lambda port, host="127.0.0.1": False)
    spawned = []
    monkeypatch.setattr(hub, "_spawn_and_wait", lambda root, port: spawned.append(port) or port)

    result = hub.serve(tmp_path, transport="daemon", port=9418)

    assert result == 9418
    assert spawned == [9418]  # 비어있으면 선호 포트에서 기동


def _write_daemon_pid(tmp_path, pid: int) -> None:
    pidfile = config.daemon_pid(tmp_path)
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(pid))


def test_serve_reuses_preferred_when_daemon_pid_identity_confirms_ours(tmp_path, fake_proc, monkeypatch):
    monkeypatch.setattr(hub, "_port_open", lambda port, host="127.0.0.1": True)
    _write_daemon_pid(tmp_path, 4242)
    monkeypatch.setattr(
        hub, "_is_our_daemon",
        lambda root, pid, port, *, require_listen: pid == 4242 and port == 9418 and require_listen,
    )

    def _no_spawn(root, port):
        raise AssertionError("재사용 기대: 스폰이 호출되면 안 됨")
    monkeypatch.setattr(hub, "_spawn_and_wait", _no_spawn)

    result = hub.serve(tmp_path, transport="daemon", port=9418)

    assert result == 9418  # 재기동 없이 선호 포트 재사용


def test_serve_falls_back_to_derived_when_preferred_daemon_pid_missing(tmp_path, fake_proc, monkeypatch):
    """daemon.pid 자체가 없으면(파일 미기록) 무조건 외부로 취급 → 파생 폴백."""
    preferred = 9418
    derived = config.derived_port(tmp_path)
    open_ports = {preferred: True, derived: False}
    monkeypatch.setattr(hub, "_port_open", lambda port, host="127.0.0.1": open_ports.get(port, False))
    spawned = []
    monkeypatch.setattr(hub, "_spawn_and_wait", lambda root, port: spawned.append(port) or port)
    # daemon.pid 파일 없음(기록 자체가 없음).

    result = hub.serve(tmp_path, transport="daemon", port=preferred)

    assert result == derived
    assert spawned == [derived]  # 파생 포트가 비어있으니 거기서 기동


def test_serve_falls_back_to_derived_when_foreign_daemon_holds_port_despite_same_head(
    tmp_path, fake_proc, monkeypatch,
):
    """핵심 반례(spec §6.1:206 금지 ①): 외부 데몬이 우리와 **같은 HEAD**를 서빙 중이어도
    (=옛 HEAD-SHA 판정이면 오식별해 재사용했을 상황) daemon.pid identity가 불일치하면
    재사용을 금지하고 파생 포트로 폴백해야 한다. daemon.pid는 존재하되(다른 프로젝트
    daemon의 PID를 우연히 가리키는 stale 상태) cmdline base-path가 불일치하는 케이스로
    인코딩한다.
    """
    preferred = 9418
    derived = config.derived_port(tmp_path)
    open_ports = {preferred: True, derived: False}
    monkeypatch.setattr(hub, "_port_open", lambda port, host="127.0.0.1": open_ports.get(port, False))
    spawned = []
    monkeypatch.setattr(hub, "_spawn_and_wait", lambda root, port: spawned.append(port) or port)
    _write_daemon_pid(tmp_path, 9999)  # stale/외부 PID(같은 HEAD를 서빙해도 identity는 무관)
    monkeypatch.setattr(hub, "_is_our_daemon", lambda root, pid, port, *, require_listen: False)

    result = hub.serve(tmp_path, transport="daemon", port=preferred)

    assert result == derived
    assert spawned == [derived]


def test_serve_raises_when_both_ports_foreign(tmp_path, fake_proc, monkeypatch):
    preferred = 9418
    derived = config.derived_port(tmp_path)
    monkeypatch.setattr(hub, "_port_open", lambda port, host="127.0.0.1": True)  # 둘 다 열림
    _write_daemon_pid(tmp_path, 4242)
    monkeypatch.setattr(hub, "_is_our_daemon", lambda root, pid, port, *, require_listen: False)

    def _no_spawn(root, port):
        raise AssertionError("둘 다 외부 점유면 스폰 호출 없이 raise해야 함")
    monkeypatch.setattr(hub, "_spawn_and_wait", _no_spawn)

    with pytest.raises(RuntimeError):
        hub.serve(tmp_path, transport="daemon", port=preferred)


def test_serve_rejects_non_daemon_transport(tmp_path, fake_proc):
    with pytest.raises(ValueError):
        hub.serve(tmp_path, transport="file", port=9418)


# --- cmdline 매칭 규칙(spec §6.1:206 "cmdline 매칭 규칙") ---


def test_cmdline_matches_our_daemon_with_git_argv0(tmp_path):
    port = 9418
    cmdline = [
        "git", "daemon",
        f"--base-path={config.hub_dir(tmp_path)}",
        "--export-all", "--enable=receive-pack", f"--port={port}",
        str(config.hub_repo(tmp_path)),
    ]
    assert hub._cmdline_matches(cmdline, tmp_path, port)


def test_cmdline_matches_our_daemon_with_git_daemon_argv0(tmp_path):
    # git 버전에 따라 argv0가 별도 실행파일(git-daemon)로 관측될 수 있다 — argv0 정확
    # 일치에 의존하지 않고 "daemon" 원소 부재 + argv0가 git-daemon으로 끝남을 인정.
    port = 9418
    cmdline = [
        "/usr/lib/git-core/git-daemon",
        f"--base-path={config.hub_dir(tmp_path)}",
        f"--port={port}",
    ]
    assert hub._cmdline_matches(cmdline, tmp_path, port)


def test_cmdline_rejects_argv0_that_merely_ends_with_git_daemon(tmp_path):
    # 재리뷰 하드닝 D: endswith("git-daemon")은 "/tmp/notgit-daemon" 같은 위장 argv0도
    # 통과시킨다. Path(argv0).name 정확 일치로 이를 차단해야 한다("daemon" 토큰도 없음).
    port = 9418
    cmdline = ["/tmp/notgit-daemon", f"--base-path={config.hub_dir(tmp_path)}", f"--port={port}"]
    assert not hub._cmdline_matches(cmdline, tmp_path, port)


def test_cmdline_rejects_different_base_path(tmp_path):
    # 다른 프로젝트(워크트리)의 허브 daemon — base-path가 다르므로 우리 것이 아님.
    port = 9418
    other_root = tmp_path / "other-project"
    cmdline = ["git", "daemon", f"--base-path={config.hub_dir(other_root)}", f"--port={port}"]
    assert not hub._cmdline_matches(cmdline, tmp_path, port)


def test_cmdline_rejects_when_port_element_differs(tmp_path):
    # base-path·daemon 토큰은 일치해도 port가 다르면(문자열 substring이 아니라 원소
    # 단위 비교이므로) 불일치로 판정.
    cmdline = ["git", "daemon", f"--base-path={config.hub_dir(tmp_path)}", "--port=19418"]
    assert not hub._cmdline_matches(cmdline, tmp_path, 9418)


def test_cmdline_matches_ignores_port_when_none_given(tmp_path):
    # stop_daemon처럼 실행 중 포트를 모르는 호출자는 port=None으로 base-path만 확인.
    # (base-path 문자열은 플랫폼 경로 구분자에 의존하므로 config.hub_dir로 생성한다.)
    cmdline = ["git", "daemon", f"--base-path={config.hub_dir(tmp_path)}"]
    assert hub._cmdline_matches(cmdline, tmp_path, None)


def test_is_our_daemon_combines_alive_cmdline_and_listen(tmp_path, monkeypatch):
    port = 9418
    pid = 4242
    good_cmdline = ["git", "daemon", f"--base-path={config.hub_dir(tmp_path)}", f"--port={port}"]
    monkeypatch.setattr(hub, "_pid_alive", lambda p: p == pid)
    monkeypatch.setattr(hub, "_read_cmdline", lambda p: good_cmdline if p == pid else None)
    monkeypatch.setattr(hub, "_pid_listens_on_port", lambda p, prt: p == pid and prt == port)

    assert hub._is_our_daemon(tmp_path, pid, port, require_listen=True)
    assert not hub._is_our_daemon(tmp_path, pid + 1, port, require_listen=True)  # 죽은 PID


def test_is_our_daemon_false_when_not_listening_and_listen_required(tmp_path, monkeypatch):
    port = 9418
    pid = 4242
    good_cmdline = ["git", "daemon", f"--base-path={config.hub_dir(tmp_path)}", f"--port={port}"]
    monkeypatch.setattr(hub, "_pid_alive", lambda p: True)
    monkeypatch.setattr(hub, "_read_cmdline", lambda p: good_cmdline)
    monkeypatch.setattr(hub, "_pid_listens_on_port", lambda p, prt: False)  # cmdline은 맞지만 미청취

    assert not hub._is_our_daemon(tmp_path, pid, port, require_listen=True)
    assert hub._is_our_daemon(tmp_path, pid, port, require_listen=False)  # listen 불요구면 통과


# --- /proc/net/tcp 파서(_listening_inodes) 단위 테스트(재리뷰 커버리지 보강 H) ---
# /proc가 없는 Windows에서도 green이어야 하므로 pathlib.Path.read_text를 monkeypatch해
# 합성 텍스트로 파서만 독립 검증한다(실제 /proc 접근 없음).


def test_listening_inodes_collects_only_matching_port_and_listen_state(monkeypatch):
    port = 9418
    hex_port = format(port, "04X")
    header = "  sl  local_address rem_address   st ... inode\n"
    # 0A = LISTEN(수집 대상). 01 = ESTABLISHED(제외). 마지막 줄은 다른 포트(제외).
    tcp_text = (
        header
        + f"   0: 0100007F:{hex_port} 00000000:0000 0A 00000000:00000000 00:00000000 "
        "00000000     0        0 11111 1 0000000000000000 100 0 0 10 0\n"
        + f"   1: 0100007F:{hex_port} 0100007F:1234 01 00000000:00000000 00:00000000 "
        "00000000     0        0 22222 1 0000000000000000 100 0 0 10 0\n"
        + "   2: 0100007F:1F90 00000000:0000 0A 00000000:00000000 00:00000000 "
        "00000000     0        0 33333 1 0000000000000000 100 0 0 10 0\n"
    )

    def fake_read_text(self, *a, **kw):
        # as_posix(): WindowsPath가 "/proc/net/tcp"를 역슬래시로 정규화하므로 str(self)
        # 비교는 Windows에서 항상 불일치한다(이 테스트가 Windows green이어야 하는 이유).
        if self.as_posix() == "/proc/net/tcp":
            return tcp_text
        raise OSError("no tcp6 in this fixture")

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    assert hub._listening_inodes(port) == {"11111"}


def test_listening_inodes_empty_when_no_proc_net_tcp(monkeypatch):
    def fake_read_text(self, *a, **kw):
        raise OSError("no /proc on this platform")

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    assert hub._listening_inodes(9418) == set()


# --- _readiness() rc-gate 단위 테스트(재리뷰 커버리지 보강 H) ---
# child 즉사 경로(poll() non-None)는 이미 test_readiness_fails_when_child_already_exited가
# 커버한다. 여기서는 포트가 열린 뒤 ls-remote의 returncode 0/비영 분기만 검증한다.


def test_readiness_true_when_port_open_and_ls_remote_succeeds(tmp_path, monkeypatch, fake_proc):
    monkeypatch.setattr(hub, "_port_open", lambda port, host="127.0.0.1": True)
    fake_proc.handler = lambda argv, kw: proc.ProcResult(argv, 0, "", "")

    assert hub._readiness(tmp_path, 9418, _FakePopen(poll_result=None)) is True


def test_readiness_false_when_port_open_but_ls_remote_fails(tmp_path, monkeypatch, fake_proc):
    monkeypatch.setattr(hub, "_port_open", lambda port, host="127.0.0.1": True)
    fake_proc.handler = lambda argv, kw: proc.ProcResult(argv, 1, "", "boom")

    assert hub._readiness(tmp_path, 9418, _FakePopen(poll_result=None)) is False


# --- stop_daemon() identity 검증(spec §6.1:207) ---


def test_stop_daemon_kills_when_identity_confirms_ours(tmp_path, fake_proc, monkeypatch):
    monkeypatch.setattr(tmux, "_list_windows", lambda *a, **kw: [])
    _write_daemon_pid(tmp_path, 4242)
    monkeypatch.setattr(hub, "_is_our_daemon", lambda root, pid, port, *, require_listen: pid == 4242)

    hub.stop_daemon(tmp_path)

    assert fake_proc.find("kill", "4242") is not None
    assert not config.daemon_pid(tmp_path).exists()


def test_stop_daemon_does_not_kill_when_identity_mismatches(tmp_path, fake_proc, monkeypatch):
    # PID 재사용된 무고한 프로세스 종료 방지: identity 불일치면 kill 미호출, pidfile만 정리.
    monkeypatch.setattr(tmux, "_list_windows", lambda *a, **kw: [])
    _write_daemon_pid(tmp_path, 9999)
    monkeypatch.setattr(hub, "_is_our_daemon", lambda root, pid, port, *, require_listen: False)

    hub.stop_daemon(tmp_path)

    assert fake_proc.find("kill") is None
    assert not config.daemon_pid(tmp_path).exists()  # stale pidfile은 정리


def test_stop_daemon_preserves_pidfile_when_kill_fails_and_pid_still_alive(
    tmp_path, fake_proc, monkeypatch,
):
    # 재리뷰 하드닝 E: kill이 실패했고(returncode != 0) pid가 여전히 살아있으면
    # pidfile을 지우지 않는다(살아있는 우리 데몬을 추적 불가 상태로 만들지 않기 위함).
    monkeypatch.setattr(tmux, "_list_windows", lambda *a, **kw: [])
    _write_daemon_pid(tmp_path, 4242)
    monkeypatch.setattr(hub, "_is_our_daemon", lambda root, pid, port, *, require_listen: pid == 4242)
    monkeypatch.setattr(hub, "_pid_alive", lambda pid: True)  # kill 뒤에도 여전히 생존
    fake_proc.handler = lambda argv, kw: proc.ProcResult(argv, 1, "", "kill: permission denied")

    hub.stop_daemon(tmp_path)

    assert fake_proc.find("kill", "4242") is not None
    assert config.daemon_pid(tmp_path).exists()  # 실패했으므로 pidfile 보존


def test_stop_daemon_noop_when_no_pidfile(tmp_path, fake_proc, monkeypatch):
    monkeypatch.setattr(tmux, "_list_windows", lambda *a, **kw: [])
    hub.stop_daemon(tmp_path)
    assert fake_proc.calls == []


def test_stop_daemon_rejects_when_leader_session_active(tmp_path, fake_proc, monkeypatch):
    monkeypatch.setattr(tmux, "_list_windows", lambda *a, **kw: [("@1", "w1.t1-x")])
    _write_daemon_pid(tmp_path, 4242)
    with pytest.raises(RuntimeError):
        hub.stop_daemon(tmp_path)
    assert fake_proc.find("kill") is None


# --- readiness(spec §6.1:206 readiness) ---


class _FakePopen:
    """Popen 대체. ``_spawn_and_wait``의 정리(finally) 경로를 관측하도록 pid/terminate/
    wait도 제공한다(readiness 전용 테스트는 poll()만 사용)."""

    def __init__(self, poll_result, pid=555):
        self._poll_result = poll_result
        self.pid = pid
        self.terminate_called = False
        self.wait_called = False

    def poll(self):
        return self._poll_result

    def terminate(self):
        self.terminate_called = True

    def wait(self, timeout=None):
        self.wait_called = True
        return 0


def test_readiness_fails_when_child_already_exited(tmp_path):
    # bind 경합 등으로 자식이 즉사(poll()이 non-None)하면 포트/ls-remote 확인 없이 실패.
    assert hub._readiness(tmp_path, 9418, _FakePopen(poll_result=1)) is False


# --- _spawn_and_wait: --pid-file 채택 후 계약(재리뷰 차단 결함 A) ---
# git이 listener(git-daemon 자식) pid를 --pid-file에 직접 쓰므로, _spawn_and_wait는
# 더 이상 Popen.pid(래퍼)를 pidfile에 쓰지 않는다. readiness 성공 후 pidfile에서
# 읽은 listener pid를 _is_our_daemon(..., require_listen=True)로 재검증해야 반환한다.


def test_spawn_and_wait_raises_and_cleans_up_when_readiness_fails(tmp_path, monkeypatch, fake_proc):
    fake = _FakePopen(poll_result=None)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake)
    monkeypatch.setattr(hub, "_readiness", lambda root, port, popen: False)
    monkeypatch.setattr(hub, "_our_daemon_pid", lambda root: None)  # git이 아직 못 씀

    with pytest.raises(RuntimeError):
        hub._spawn_and_wait(tmp_path, 9418)

    assert fake.terminate_called  # 자식 정리
    assert fake.wait_called
    assert not config.daemon_pid(tmp_path).exists()  # 실패 시 pidfile 남기지 않음


def test_spawn_and_wait_raises_and_cleans_up_when_listener_revalidation_fails(
    tmp_path, monkeypatch, fake_proc,
):
    # readiness는 성공했지만 pidfile의 pid가 우리 daemon으로 재검증되지 않는 경우
    # (예: 그새 외부 프로세스가 포트를 물어 다른 pid가 listen) — 반환하지 않고 정리 후 raise.
    fake = _FakePopen(poll_result=None)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake)
    monkeypatch.setattr(hub, "_readiness", lambda root, port, popen: True)
    monkeypatch.setattr(hub, "_our_daemon_pid", lambda root: 777)
    monkeypatch.setattr(
        hub, "_is_our_daemon",
        lambda root, pid, port, *, require_listen: False,
    )

    with pytest.raises(RuntimeError):
        hub._spawn_and_wait(tmp_path, 9418)

    assert fake.terminate_called
    assert fake_proc.find("kill", "777") is not None  # listener도 종료 시도
    assert not config.daemon_pid(tmp_path).exists()


def test_spawn_and_wait_returns_port_after_readiness_and_listener_revalidation_succeed(
    tmp_path, monkeypatch, fake_proc,
):
    fake = _FakePopen(poll_result=None)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake)
    monkeypatch.setattr(hub, "_readiness", lambda root, port, popen: True)
    monkeypatch.setattr(hub, "_our_daemon_pid", lambda root: 777)  # git이 pidfile에 쓴 listener pid
    monkeypatch.setattr(
        hub, "_is_our_daemon",
        lambda root, pid, port, *, require_listen: pid == 777 and port == 9418 and require_listen,
    )

    result = hub._spawn_and_wait(tmp_path, 9418)

    assert result == 9418
    assert not fake.terminate_called  # 성공 경로: 자식을 죽이지 않음
    assert fake_proc.find("kill") is None  # 재검증 성공이므로 kill 호출 없음


@pytest.mark.skipif(not _HAS_GIT, reason="git 미설치 환경")
def test_pre_receive_gate_enforces_ref_allowlist_with_real_git(tmp_path):
    """install_gate가 실제 pre-receive를 통해 작동하는지 실증(로컬 경로 push도 발동, ADR-0007)."""
    src = tmp_path / "src"
    src.mkdir()
    assert _git("init", "-q", "-b", "main", cwd=src).returncode == 0
    _git("config", "user.email", "axdt-test@example.com", cwd=src)
    _git("config", "user.name", "axdt-test", cwd=src)
    (src / "f.txt").write_text("hello\n")
    assert _git("add", "f.txt", cwd=src).returncode == 0
    r_commit = _git("commit", "-q", "-m", "init", cwd=src)
    assert r_commit.returncode == 0, r_commit.stderr
    assert _git("branch", "w1.t1-x", cwd=src).returncode == 0
    assert _git("tag", "v0.0.1", cwd=src).returncode == 0

    hub_repo = tmp_path / "hub.git"
    assert _git("init", "-q", "--bare", str(hub_repo), cwd=tmp_path).returncode == 0
    hub.install_gate(hub_repo)
    hub_url = hub_repo.as_uri()

    r_task = _git("push", hub_url, "w1.t1-x", cwd=src)
    assert r_task.returncode == 0, r_task.stderr

    r_main = _git("push", hub_url, "main", cwd=src)
    assert r_main.returncode != 0

    r_tag = _git("push", hub_url, "v0.0.1", cwd=src)
    assert r_tag.returncode != 0

    r_delete = _git("push", hub_url, ":w1.t1-x", cwd=src)
    assert r_delete.returncode != 0


# --- @integration: 실 프로세스로 daemon.pid identity 반례 실증(spec §6.1:206) ---
# 이 Windows 호스트에는 /proc가 없어 항상 skip(구조만 리뷰 대상). Linux/WSL2에서
# `py -3 -m pytest axdt -m integration` 으로 옵트인 실행.
_LINUX_PROC = sys.platform.startswith("linux") and Path("/proc").is_dir()
_SKIP_REASON = "daemon.pid identity 검증은 Linux/WSL2 /proc 전제(spec §1) — 이 호스트에선 skip"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _seed_repo(tmp_path) -> Path:
    src = tmp_path / "seed-src"
    src.mkdir()
    proc.run(["git", "init", "-q", "-b", "main", str(src)])
    # config는 서브커맨드 앞이 아니라 repo 설정으로 넣는다(-c는 commit 뒤에 오면
    # --reedit-message로 해석돼 커밋이 실패한다).
    proc.run(["git", "-C", str(src), "config", "user.email", "axdt-test@example.com"])
    proc.run(["git", "-C", str(src), "config", "user.name", "axdt-test"])
    (src / "f.txt").write_text("hello\n")
    proc.run(["git", "-C", str(src), "add", "f.txt"])
    proc.run(["git", "-C", str(src), "commit", "-q", "-m", "seed"])
    return src


def _wait_for_pidfile_pid(root: Path) -> int:
    """``--pid-file``에 git이 listener pid를 쓸 때까지 짧게 재시도(최대 ~1s)."""
    pidfile = config.daemon_pid(root)
    for _ in range(20):
        if pidfile.exists():
            try:
                return int(pidfile.read_text().strip())
            except ValueError:
                pass
        time.sleep(0.05)
    pytest.fail("git이 --pid-file을 기록하지 않음(listener pid 미기록)")


@pytest.mark.integration
@pytest.mark.skipif(not _LINUX_PROC, reason=_SKIP_REASON)
def test_serve_reuses_real_daemon_via_pid_identity(tmp_path):
    """실 git daemon을 하나 띄우면 git이 ``--pid-file``에 listener(git-daemon 자식) pid를
    직접 쓴다(래퍼 Popen.pid가 아니라). serve()가 재기동 없이 그 포트를 재사용하는지
    확인한다. 동시에 _read_cmdline·_pid_listens_on_port가 그 listener pid를 대상으로
    참을 반환하는지(=매칭 규칙이 실물과 맞는지) 검증한다.
    """
    root = tmp_path / "proj"
    seed = _seed_repo(tmp_path)
    hub.init(root, seed_from=seed)

    port = _free_port()
    real_daemon = subprocess.Popen(
        hub.daemon_argv(root, port),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            if hub._port_open(port):
                break
            time.sleep(0.1)
        else:
            pytest.fail("실 git daemon 기동 실패(포트 미개방)")

        # git이 --pid-file에 쓴 listener pid를 읽는다(수동으로 래퍼 pid를 적지 않음 —
        # real_daemon.pid는 래퍼라 listen하지 않는다).
        listener_pid = _wait_for_pidfile_pid(root)
        assert listener_pid != real_daemon.pid, "listener pid는 래퍼(git) pid와 달라야 함"

        # 매칭 규칙이 실물 listener 프로세스와 맞는지 직접 확인(cmdline 실제 형태 검증).
        cmdline = hub._read_cmdline(listener_pid)
        assert cmdline is not None, "실 프로세스 cmdline 조회 실패"
        assert hub._cmdline_matches(cmdline, root, port), f"cmdline 불일치: {cmdline}"
        assert hub._pid_listens_on_port(listener_pid, port)

        result = hub.serve(root, transport="daemon", port=port)

        assert result == port  # 재기동 없이 재사용
        # pidfile의 pid가 안 바뀌었으면(=새 spawn 없었음) 재사용이 확인된 것.
        assert int(config.daemon_pid(root).read_text().strip()) == listener_pid
    finally:
        # terminate(SIGTERM) + wait: git의 clean_on_exit가 자식(listener)까지 정리한다.
        # SIGKILL은 래퍼만 죽이고 자식을 orphan으로 남길 수 있어 쓰지 않는다.
        real_daemon.terminate()
        real_daemon.wait(timeout=5)


@pytest.mark.integration
@pytest.mark.skipif(not _LINUX_PROC, reason=_SKIP_REASON)
def test_serve_falls_back_when_real_foreign_daemon_shares_our_head(tmp_path):
    """핵심 반례(실프로세스): 외부(다른 base-path) git daemon이 우리와 **같은 HEAD**로
    선호 포트를 점유해도(=옛 HEAD-SHA 판정이면 오식별했을 상황) daemon.pid identity가
    없으므로 serve()는 재사용하지 않고 파생 포트로 폴백해야 한다.
    """
    seed = _seed_repo(tmp_path)
    root = tmp_path / "proj"
    hub.init(root, seed_from=seed)
    foreign_root = tmp_path / "foreign-proj"
    hub.init(foreign_root, seed_from=seed)  # 동일 seed → HEAD sha가 우리 허브와 같음

    preferred = _free_port()
    foreign_daemon = subprocess.Popen(
        hub.daemon_argv(foreign_root, preferred),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            if hub._port_open(preferred):
                break
            time.sleep(0.1)
        else:
            pytest.fail("외부 git daemon 기동 실패(포트 미개방)")

        # root의 daemon.pid는 기록하지 않는다(외부 데몬이므로 우리 pidfile이 없는 것이 정상).
        derived = config.derived_port(root)

        result = hub.serve(root, transport="daemon", port=preferred)

        assert result == derived  # 같은 HEAD라도 재사용 금지 → 파생 폴백
        derived_pid = int(config.daemon_pid(root).read_text().strip())
        assert derived_pid != foreign_daemon.pid
    finally:
        foreign_daemon.terminate()
        foreign_daemon.wait(timeout=5)
        # serve()가 파생 포트에 내부 spawn한 우리 데몬(핸들 없음)도 정리한다(누수 금지):
        # root pidfile의 listener pid를 kill(래퍼는 git의 clean_on_exit로 뒤따라 종료).
        our_pid = hub._our_daemon_pid(root)
        if our_pid is not None:
            proc.run(["kill", str(our_pid)], check=False)
