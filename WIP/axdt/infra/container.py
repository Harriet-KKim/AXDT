"""Docker 컨테이너 생애주기. run_args는 순수(argv 빌더), 나머지는 proc 경유.

D3: worktree당 컨테이너 1개, **해당 작업본만 RW 마운트**.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from . import config, naming, proc

__all__ = [
    "IMAGE", "image_ref", "build_argv", "build_image",
    "run_args", "exists", "is_running", "stop", "rm",
]

IMAGE = "axdt/leader"


def image_ref(tag: str = "dev") -> str:
    return f"{IMAGE}:{tag}"


def _dockerfile(root: Path) -> Path:
    return Path(root) / "WIP" / "axdt" / "infra" / "docker" / "leader.Dockerfile"


def _build_context(root: Path) -> Path:
    return Path(root) / "WIP" / "axdt" / "infra" / "docker"


def build_argv(root: Path, tag: str = "dev") -> list[str]:
    return [
        "docker", "build",
        "-f", str(_dockerfile(root)),
        "-t", image_ref(tag),
        str(_build_context(root)),
    ]


def build_image(root: Path, tag: str = "dev") -> None:
    proc.run(build_argv(root, tag))


def run_args(
    i: naming.Identifier,
    command: Sequence[str],
    host_workdir: Path,
    *,
    uid: int,
    gid: int,
    transport: str = "daemon",
    port: int = config.DEFAULT_HUB_PORT,
    hub_repo: Path | None = None,
    env: Mapping[str, str] | None = None,
    tag: str = "dev",
) -> list[str]:
    """`docker run` argv를 생성한다(실행은 tmux 윈도우가 담당)."""
    argv: list[str] = [
        "docker", "run",
        "--name", naming.container(i),
        "-v", f"{Path(host_workdir).as_posix()}:{config.CONTAINER_WORKDIR}",
        "-w", config.CONTAINER_WORKDIR,
        "--user", f"{uid}:{gid}",
        "-e", f"HOME={config.CONTAINER_HOME}",
    ]
    if transport == "daemon":
        argv += ["--add-host=host.docker.internal:host-gateway"]
    elif transport == "file":
        if hub_repo is None:
            raise ValueError("file transport은 hub_repo 마운트가 필요합니다")
        argv += ["-v", f"{Path(hub_repo).as_posix()}:/hub"]
    for k, v in (env or {}).items():
        argv += ["-e", f"{k}={v}"]
    argv += ["-it", image_ref(tag)]
    argv += list(command)
    return argv


def _name_filter(i: naming.Identifier) -> str:
    # docker name 필터는 substring → 앵커로 정확 매칭(prefix 오매칭 차단).
    return f"name=^/{naming.container(i)}$"


def exists(i: naming.Identifier) -> bool:
    r = proc.run(
        ["docker", "ps", "-a", "--filter", _name_filter(i), "--format", "{{.Names}}"],
        check=False,
    )
    return naming.container(i) in r.stdout.split()


def is_running(i: naming.Identifier) -> bool:
    r = proc.run(
        ["docker", "ps", "--filter", _name_filter(i), "--format", "{{.Names}}"],
        check=False,
    )
    return naming.container(i) in r.stdout.split()


def stop(i: naming.Identifier) -> None:
    proc.run(["docker", "stop", naming.container(i)], check=False)


def rm(i: naming.Identifier) -> None:
    proc.run(["docker", "rm", "-f", naming.container(i)], check=False)
