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
