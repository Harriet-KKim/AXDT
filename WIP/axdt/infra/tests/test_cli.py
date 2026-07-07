"""cli 모듈 — argparse 디스패치. 협력자 monkeypatch로 라우팅·exit code 검증."""
import pytest

from axdt import cli


@pytest.fixture
def root(monkeypatch, tmp_path):
    from axdt.infra import config
    monkeypatch.setattr(config, "project_root", lambda *a, **k: tmp_path)
    return tmp_path


def test_verify_naming_valid_exits_zero(root, capsys):
    assert cli.main(["verify-naming", "w3.t12-auth-login"]) == 0


def test_verify_naming_invalid_exits_nonzero(root):
    assert cli.main(["verify-naming", "w03.t1-x"]) != 0


def test_leader_up_dispatches(root, monkeypatch):
    called = {}
    monkeypatch.setattr(cli.leader, "up",
                        lambda r, i, **k: called.update(i=i.value))
    assert cli.main(["leader", "up", "w3.t12-auth-login"]) == 0
    assert called["i"] == "w3.t12-auth-login"


def test_leader_down_dispatches(root, monkeypatch):
    called = {}
    monkeypatch.setattr(cli.leader, "down",
                        lambda r, i, **k: called.update(i=i.value, force=k.get("force")))
    assert cli.main(["leader", "down", "w3.t12-auth-login", "--force"]) == 0
    assert called["force"] is True


def test_workspace_create_dispatches(root, monkeypatch):
    called = {}
    monkeypatch.setattr(cli.workspace, "provision",
                        lambda r, i, **k: called.update(i=i.value))
    assert cli.main(["workspace", "create", "w3.t12-auth-login"]) == 0
    assert called["i"] == "w3.t12-auth-login"


def test_invalid_identifier_arg_exits_nonzero(root):
    # 잘못된 식별자는 디스패치 전에 검증 실패
    assert cli.main(["leader", "up", "BAD"]) != 0


def test_no_command_exits_nonzero(root):
    assert cli.main([]) != 0
