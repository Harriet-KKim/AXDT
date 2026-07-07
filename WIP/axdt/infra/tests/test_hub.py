"""hub 모듈 — clone URL/daemon argv는 순수, init은 proc 경유."""
import pytest

from axdt.infra import config, hub, proc


def test_clone_url_for_host_is_file_uri(tmp_path):
    assert hub.clone_url_for_host(tmp_path) == config.hub_repo(tmp_path).as_uri()


def test_clone_url_for_container_daemon(tmp_path):
    url = hub.clone_url_for_container(tmp_path, transport="daemon", port=9418)
    assert url == "git://host.docker.internal:9418/project.git"


def test_clone_url_for_container_file(tmp_path):
    url = hub.clone_url_for_container(tmp_path, transport="file", port=9418)
    assert url == "file:///hub"


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
