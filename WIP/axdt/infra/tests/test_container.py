"""container 모듈 — run_args는 순수(argv 빌더), 나머지는 proc 경유."""
from pathlib import Path, PurePosixPath

import pytest

from axdt.infra import container, naming, proc


@pytest.fixture
def i():
    return naming.parse("w3.t12-auth-login")


@pytest.fixture
def workdir():
    return Path("/home/u/workspaces/w3.t12-auth-login")


def test_image_ref():
    assert container.image_ref("dev") == "axdt/leader:dev"


def test_run_args_basic(i, workdir):
    argv = container.run_args(i, ["axdt-leader-placeholder"], workdir,
                              uid=1000, gid=1000, transport="daemon")
    assert argv[:4] == ["docker", "run", "--name", "axdt-w3.t12-auth-login"]
    joined = " ".join(argv)
    assert "/home/u/workspaces/w3.t12-auth-login:/work" in joined
    assert "-w /work" in joined
    assert "--user 1000:1000" in joined
    assert "HOME=/tmp/axdt-home" in joined
    assert argv[-1] == "axdt-leader-placeholder"


def test_run_args_daemon_adds_host_gateway(i, workdir):
    argv = container.run_args(i, ["x"], workdir, uid=1, gid=1,
                              transport="daemon")
    assert "--add-host=host.docker.internal:host-gateway" in argv


def test_run_args_rejects_non_daemon_transport(i, workdir):
    # file:// RW 허브 마운트는 pre-receive 게이트(ADR-0007)를 우회하므로 제거됐다(daemon 단일).
    with pytest.raises(ValueError):
        container.run_args(i, ["x"], workdir, uid=1, gid=1,
                            transport="file")


def test_run_args_env_pairs(i, workdir):
    argv = container.run_args(i, ["x"], workdir, uid=1, gid=1,
                              transport="daemon",
                              env={"FOO": "bar"})
    j = " ".join(argv)
    assert "-e FOO=bar" in j


def test_run_args_no_longer_accepts_port(i, workdir):
    # port는 argv에서 전혀 쓰이지 않던 죽은 파라미터였다(Nit #8). 컨테이너가 허브를
    # 찾는 실효 경로는 provision이 심은 origin 원격 URL뿐이라 시그니처에서 제거됐다.
    with pytest.raises(TypeError):
        container.run_args(i, ["x"], workdir, uid=1, gid=1,
                            transport="daemon", port=9418)


def test_build_argv_uses_dockerfile_and_context(i, tmp_path):
    argv = container.build_argv(tmp_path, tag="dev")
    j = " ".join(argv)
    assert argv[:2] == ["docker", "build"]
    assert "-t axdt/leader:dev" in j
    assert "leader.Dockerfile" in j


def test_exists_true_when_exact_name_found(i, fake_proc):
    fake_proc.handler = lambda argv, kw: proc.ProcResult(
        argv, 0, "axdt-w3.t12-auth-login\n", "")
    assert container.exists(i) is True


def test_exists_false_when_empty(i, fake_proc):
    fake_proc.handler = lambda argv, kw: proc.ProcResult(argv, 0, "", "")
    assert container.exists(i) is False


def test_exists_uses_anchored_exact_filter(i, fake_proc):
    container.exists(i)
    # substring 오매칭 방지: 앵커(^/name$) 또는 inspect 사용
    j = " ".join(fake_proc.last())
    assert "^/axdt-w3.t12-auth-login$" in j or "inspect" in j


def test_stop_and_rm_call_docker(i, fake_proc):
    container.stop(i)
    container.rm(i)
    assert fake_proc.find("docker", "stop", "axdt-w3.t12-auth-login")
    assert fake_proc.find("docker", "rm", "axdt-w3.t12-auth-login")


def test_image_exists_true_when_id_returned(fake_proc):
    fake_proc.handler = lambda argv, kw: proc.ProcResult(argv, 0, "abc123\n", "")
    assert container.image_exists("dev") is True


def test_image_exists_false_when_empty(fake_proc):
    fake_proc.handler = lambda argv, kw: proc.ProcResult(argv, 0, "", "")
    assert container.image_exists("dev") is False
