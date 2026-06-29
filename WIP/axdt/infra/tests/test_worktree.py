"""worktree 모듈 — provision/teardown. proc은 목, 디렉터리는 실제."""
import pytest

from axdt.infra import config, hub, naming, proc, worktree


@pytest.fixture(autouse=True)
def no_daemon(monkeypatch):
    # 단위 테스트는 실제 git daemon을 띄우지 않는다(serve는 spawn).
    monkeypatch.setattr(hub, "serve", lambda *a, **k: None)


@pytest.fixture
def i():
    return naming.parse("w3.t12-auth-login")


@pytest.fixture
def seed(tmp_path):
    d = tmp_path / "canon"
    d.mkdir()
    return d


def test_provision_clones_and_sets_two_remotes(tmp_path, i, seed, fake_proc):
    worktree.provision(tmp_path, i, seed_from=seed, transport="daemon", port=9418)
    assert fake_proc.find("clone") is not None
    # host용 hub 원격 + 컨테이너용 origin 원격
    assert fake_proc.find("remote", "rename", "origin", "hub") is not None
    assert fake_proc.find("remote", "add", "origin") is not None
    assert fake_proc.find("checkout", "-b", "w3.t12-auth-login") is not None


def test_provision_returns_worktree_path(tmp_path, i, seed, fake_proc):
    p = worktree.provision(tmp_path, i, seed_from=seed)
    assert p == config.worktree_path(tmp_path, i)


def test_provision_fail_fast_when_exists(tmp_path, i, seed, fake_proc):
    config.worktree_path(tmp_path, i).mkdir(parents=True)
    with pytest.raises(FileExistsError):
        worktree.provision(tmp_path, i, seed_from=seed)
    assert fake_proc.find("clone") is None  # 클론 시도 안 함


def test_teardown_removes_dir_with_force(tmp_path, i, fake_proc):
    p = config.worktree_path(tmp_path, i)
    p.mkdir(parents=True)
    (p / "f.txt").write_text("x")
    worktree.teardown(tmp_path, i, force=True)
    assert not p.exists()


def test_teardown_noop_when_missing(tmp_path, i, fake_proc):
    worktree.teardown(tmp_path, i, force=True)  # no raise
    assert not config.worktree_path(tmp_path, i).exists()
