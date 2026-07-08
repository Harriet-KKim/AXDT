"""hub 모듈 — clone URL/daemon argv는 순수, init은 proc 경유."""
import shutil
import subprocess

import pytest

from axdt.infra import config, hub, proc

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


# --- serve() 포트 충돌 처리(재리뷰 결함 C6a) ---
# _port_open과 데몬 spawn은 monkeypatch로 격리(단위 테스트에서 실제 기동 금지).
# ls-remote identity 비교는 fake_proc.handler로 git://127.0.0.1:<port>/project.git
# (외부 daemon probe)와 file://...(우리 로컬 허브) 호출을 구분해 sha를 프로그램한다.


def _identity_handler(*, foreign_ports: tuple[int, ...] = (), our_sha: str = "cafefeed"):
    """ls-remote 호출을 가로채 identity를 프로그램하는 fake_proc.handler 팩토리.

    foreign_ports에 있는 포트로의 git:// probe는 우리 sha와 다른 값을 반환(불일치 =
    외부 데몬). 그 외 git:// probe와 file:// probe는 모두 our_sha를 반환(우리 허브).
    """
    def handler(argv, kw):
        joined = " ".join(argv)
        if "ls-remote" in joined:
            for p in foreign_ports:
                if f"127.0.0.1:{p}" in joined:
                    return proc.ProcResult(argv, 0, "deadbeef\tHEAD\n", "")
            return proc.ProcResult(argv, 0, f"{our_sha}\tHEAD\n", "")
        return proc.ProcResult(argv, 0, "", "")
    return handler


def test_serve_returns_preferred_when_free(tmp_path, fake_proc, monkeypatch):
    monkeypatch.setattr(hub, "_port_open", lambda port, host="127.0.0.1": False)
    spawned = []
    monkeypatch.setattr(hub, "_spawn_and_wait", lambda root, port: spawned.append(port) or port)

    result = hub.serve(tmp_path, transport="daemon", port=9418)

    assert result == 9418
    assert spawned == [9418]  # 비어있으면 선호 포트에서 기동


def test_serve_reuses_preferred_when_it_is_our_hub(tmp_path, fake_proc, monkeypatch):
    monkeypatch.setattr(hub, "_port_open", lambda port, host="127.0.0.1": True)

    def _no_spawn(root, port):
        raise AssertionError("재사용 기대: 스폰이 호출되면 안 됨")
    monkeypatch.setattr(hub, "_spawn_and_wait", _no_spawn)
    fake_proc.handler = _identity_handler()  # 모든 ls-remote가 our_sha 반환(우리 허브)

    result = hub.serve(tmp_path, transport="daemon", port=9418)

    assert result == 9418  # 재기동 없이 선호 포트 재사용


def test_serve_falls_back_to_derived_when_port_held_by_foreign_daemon(tmp_path, fake_proc, monkeypatch):
    preferred = 9418
    derived = config.derived_port(tmp_path)
    open_ports = {preferred: True, derived: False}
    monkeypatch.setattr(hub, "_port_open", lambda port, host="127.0.0.1": open_ports.get(port, False))
    spawned = []
    monkeypatch.setattr(hub, "_spawn_and_wait", lambda root, port: spawned.append(port) or port)
    fake_proc.handler = _identity_handler(foreign_ports=(preferred,))  # 선호 포트=외부 데몬

    result = hub.serve(tmp_path, transport="daemon", port=preferred)

    assert result == derived
    assert spawned == [derived]  # 파생 포트가 비어있으니 거기서 기동


def test_serve_raises_when_both_ports_foreign(tmp_path, fake_proc, monkeypatch):
    preferred = 9418
    derived = config.derived_port(tmp_path)
    monkeypatch.setattr(hub, "_port_open", lambda port, host="127.0.0.1": True)  # 둘 다 열림

    def _no_spawn(root, port):
        raise AssertionError("둘 다 외부 점유면 스폰 호출 없이 raise해야 함")
    monkeypatch.setattr(hub, "_spawn_and_wait", _no_spawn)
    fake_proc.handler = _identity_handler(foreign_ports=(preferred, derived))  # 둘 다 외부 데몬

    with pytest.raises(RuntimeError):
        hub.serve(tmp_path, transport="daemon", port=preferred)


def test_serve_rejects_non_daemon_transport(tmp_path, fake_proc):
    with pytest.raises(ValueError):
        hub.serve(tmp_path, transport="file", port=9418)


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
