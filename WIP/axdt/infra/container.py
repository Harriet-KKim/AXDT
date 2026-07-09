"""Docker 컨테이너 생애주기. run_args는 순수(argv 빌더), 나머지는 proc 경유.

D3: workspace당 컨테이너 1개, **해당 작업본만 RW 마운트**.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from . import config, naming, proc

__all__ = [
    "IMAGE", "image_ref", "build_argv", "build_image", "image_exists",
    "run_args", "exists", "is_running", "exit_code", "stop", "rm",
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


def image_exists(tag: str = "dev") -> bool:
    r = proc.run(["docker", "images", "-q", image_ref(tag)], check=False)
    return bool(r.stdout.strip())


def run_args(
    i: naming.Identifier,
    command: Sequence[str],
    host_workdir: Path,
    *,
    uid: int,
    gid: int,
    transport: str = "daemon",
    env: Mapping[str, str] | None = None,
    tag: str = "dev",
) -> list[str]:
    """`docker run` argv를 생성한다(실행은 tmux 윈도우가 담당).

    transport는 daemon 단일이다. file:// RW 허브 마운트(예전 폴백)는 컨테이너가
    hooks/config/refs를 직접 조작해 pre-receive 게이트(ADR-0007)를 우회할 수 있어
    제거됐다(ADR-0006 대안 C 기각).

    컨테이너가 허브를 찾는 경로는 provision이 심어둔 workspace origin 원격
    URL(호스트 게이트웨이 경유)뿐이다. 포트는 그 URL에 이미 담겨 있으므로
    argv에는 필요 없다.
    """
    if transport != "daemon":
        raise ValueError(f"알 수 없는 transport={transport!r} (daemon만 지원)")
    argv: list[str] = [
        "docker", "run",
        "--name", naming.container(i),
        "-v", f"{Path(host_workdir).as_posix()}:{config.CONTAINER_WORKDIR}",
        "-w", config.CONTAINER_WORKDIR,
        "--user", f"{uid}:{gid}",
        "-e", f"HOME={config.CONTAINER_HOME}",
        "--add-host=host.docker.internal:host-gateway",
    ]
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


def exit_code(i: naming.Identifier) -> int | None:
    r = proc.run(
        ["docker", "inspect", "-f", "{{.State.ExitCode}}", naming.container(i)],
        check=False,
    )
    out = r.stdout.strip()
    if not out:
        return None
    try:
        return int(out)
    except ValueError:
        return None


def stop(i: naming.Identifier) -> None:
    proc.run(["docker", "stop", naming.container(i)], check=False)


def rm(i: naming.Identifier) -> None:
    proc.run(["docker", "rm", "-f", naming.container(i)], check=False)
