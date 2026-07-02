"""leader 모듈 — up/down 합성. 협력자(workspace/container/backend) monkeypatch."""
import pytest

from axdt.infra import leader, naming


@pytest.fixture
def i():
    return naming.parse("w3.t12-auth-login")


@pytest.fixture
def env(monkeypatch, tmp_path):
    class Rec:
        calls = None
        image = True
        start_fails = False
    rec = Rec()
    rec.calls = []

    monkeypatch.setattr(leader.container, "image_exists", lambda tag="dev": rec.image)
    monkeypatch.setattr(leader.container, "build_image",
                        lambda root, tag="dev": rec.calls.append("build"))
    monkeypatch.setattr(leader.workspace, "provision",
                        lambda root, ident, **k: rec.calls.append("provision"))
    monkeypatch.setattr(leader.workspace, "teardown",
                        lambda root, ident, **k: rec.calls.append(("teardown", k.get("force"))))

    class FakeBackend:
        def __init__(self, ident, root, **k):
            pass

        def start(self, command, cwd, env=None):
            if rec.start_fails:
                raise RuntimeError("start boom")
            rec.calls.append(("start", tuple(command)))

        def stop(self):
            rec.calls.append("stop")
    monkeypatch.setattr(leader, "TmuxDockerBackend", FakeBackend)
    return rec


def test_up_provisions_then_starts(i, tmp_path, env):
    leader.up(tmp_path, i)
    start_idx = next(n for n, c in enumerate(env.calls)
                     if isinstance(c, tuple) and c[0] == "start")
    assert env.calls.index("provision") < start_idx


def test_up_builds_image_when_missing(i, tmp_path, env):
    env.image = False
    leader.up(tmp_path, i)
    assert "build" in env.calls


def test_up_skips_build_when_image_exists(i, tmp_path, env):
    env.image = True
    leader.up(tmp_path, i)
    assert "build" not in env.calls


def test_up_uses_placeholder_command_by_default(i, tmp_path, env):
    leader.up(tmp_path, i)
    start = next(c for c in env.calls if isinstance(c, tuple) and c[0] == "start")
    assert start[1] == tuple(leader.PLACEHOLDER)


def test_up_compensates_teardown_on_start_failure(i, tmp_path, env):
    env.start_fails = True
    with pytest.raises(RuntimeError):
        leader.up(tmp_path, i)
    assert ("teardown", True) in env.calls


def test_down_stops_then_teardown(i, tmp_path, env):
    leader.down(tmp_path, i)
    assert env.calls.index("stop") < env.calls.index(("teardown", False))
