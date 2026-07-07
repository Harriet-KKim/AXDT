"""config 모듈 — 경로·포트 파생·전송 선택의 순수 로직."""
from pathlib import Path

import pytest

from axdt.infra import config, naming


@pytest.fixture
def ident():
    return naming.parse("w3.t12-auth-login")


# --- 경로 ---

def test_axdt_and_hub_paths(tmp_path):
    assert config.axdt_dir(tmp_path) == tmp_path / ".axdt"
    assert config.hub_repo(tmp_path) == tmp_path / ".axdt" / "hub" / "project.git"
    assert config.daemon_pid(tmp_path) == tmp_path / ".axdt" / "hub" / "daemon.pid"


def test_workspace_path_uses_identifier(tmp_path, ident):
    assert config.workspace_path(tmp_path, ident) == (
        tmp_path / "workspaces" / "w3.t12-auth-login"
    )


def test_capture_log_path(tmp_path, ident):
    assert config.capture_log(tmp_path, ident) == (
        tmp_path / ".axdt" / "capture" / "w3.t12-auth-login.log"
    )


# --- 전송 선택 ---

def test_transport_defaults_to_daemon():
    assert config.transport({}) == "daemon"


def test_transport_reads_env_daemon():
    assert config.transport({"AXDT_HUB_TRANSPORT": "daemon"}) == "daemon"


def test_transport_rejects_file():
    # file:// RW 마운트는 pre-receive 게이트(ADR-0007)를 우회하므로 제거됐다(daemon 단일).
    with pytest.raises(ValueError):
        config.transport({"AXDT_HUB_TRANSPORT": "file"})


def test_transport_rejects_unknown():
    with pytest.raises(ValueError):
        config.transport({"AXDT_HUB_TRANSPORT": "ftp"})


# --- 포트 ---

def test_hub_port_defaults_to_9418(tmp_path):
    assert config.hub_port(tmp_path, env={}) == 9418


def test_hub_port_env_override(tmp_path):
    assert config.hub_port(tmp_path, env={"AXDT_HUB_PORT": "12345"}) == 12345


def test_derived_port_in_registered_band(tmp_path):
    p = config.derived_port(tmp_path)
    assert 10000 <= p <= 49151  # ephemeral(49152+) 회피


def test_derived_port_is_deterministic(tmp_path):
    assert config.derived_port(tmp_path) == config.derived_port(tmp_path)


def test_derived_port_differs_by_root():
    a = config.derived_port(Path("/projects/alpha"))
    b = config.derived_port(Path("/projects/beta"))
    assert a != b


def test_container_home_is_non_repo_path():
    # HOME은 작업트리(/work) 밖이어야 자격증명 유출이 없다.
    assert config.CONTAINER_HOME == "/tmp/axdt-home"
    assert "/work" != config.CONTAINER_HOME
