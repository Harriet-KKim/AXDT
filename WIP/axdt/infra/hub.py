"""로컬 bare repo 허브 — git 격리의 통합 지점(D3 .git 공유 문제 해결).

허브는 **권위 상태**(머지 전 Leader push 보유): 내용이 있으면 절대 덮어쓰지 않는다.
호스트는 file:// 로 clone(daemon 비의존), 컨테이너는 git 프로토콜로 push.
"""
from __future__ import annotations

import socket
import time
from pathlib import Path

from . import config, proc

__all__ = [
    "init", "daemon_argv", "serve", "stop_daemon",
    "clone_url_for_host", "clone_url_for_container",
]


def _is_populated(repo: Path) -> bool:
    return repo.exists() and any(repo.iterdir())


def init(root: Path, *, seed_from: Path | str | None = None, empty: bool = False) -> None:
    """bare 허브를 초기화한다. seed_from 필수(없으면 empty=True 명시 필요).

    seed_from이 있으면 ``git clone --mirror``로 모든 ref를 복제해 bare 허브를 만든다
    (로컬 경로·원격 URL 모두 지원). clone은 비어있는 대상에만 생성하며 receive-pack을
    거치지 않으므로, 보호 ref allowlist(`ADR-0007`)를 켠 허브도 자기차단 없이 seed된다.
    (`push --mirror`는 pre-receive를 발동해 seed 자체가 거부되므로 쓰지 않는다.)
    empty=True는 seed 없이 ``git init --bare``만 한다(도그푸딩/테스트용).
    이미 내용이 있으면 **no-op**(권위 상태 보호).
    """
    if seed_from is None and not empty:
        raise ValueError("hub.init: seed_from 필수 (또는 empty=True 명시)")
    repo = config.hub_repo(root)
    if _is_populated(repo):
        return
    if seed_from is not None:
        repo.parent.mkdir(parents=True, exist_ok=True)
        proc.run(["git", "clone", "--mirror", str(seed_from), str(repo)])
    else:
        repo.mkdir(parents=True, exist_ok=True)
        proc.run(["git", "init", "--bare", str(repo)])


def daemon_argv(root: Path, port: int) -> list[str]:
    return [
        "git", "daemon",
        f"--base-path={config.hub_dir(root)}",
        "--export-all",
        "--enable=receive-pack",
        f"--port={port}",
        str(config.hub_repo(root)),
    ]


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


def serve(root: Path, *, transport: str, port: int | None = None) -> int | None:
    """daemon 모드면 git daemon을 백그라운드 기동하고 readiness까지 대기.

    이미 떠 있으면 통과. file 모드는 no-op. 반환: 사용한 포트(daemon) 또는 None.
    """
    if transport != "daemon":
        return None
    import subprocess

    port = port or config.hub_port(root)
    if _port_open(port):
        return port
    pidfile = config.daemon_pid(root)
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(
        daemon_argv(root, port),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    pidfile.write_text(str(p.pid))
    for _ in range(50):  # 최대 ~5s readiness 대기
        if _port_open(port):
            return port
        time.sleep(0.1)
    raise RuntimeError(f"git daemon 기동 실패(port {port})")


def stop_daemon(root: Path) -> None:
    """활성 Leader 세션이 있으면 거부, 없을 때만 종료(push 단절 방지)."""
    from . import tmux

    if tmux._list_windows():  # 활성 윈도우 존재
        raise RuntimeError("활성 Leader 세션이 있어 daemon을 멈추지 않습니다")
    pidfile = config.daemon_pid(root)
    if not pidfile.exists():
        return
    pid = int(pidfile.read_text().strip())
    proc.run(["kill", str(pid)], check=False)
    pidfile.unlink(missing_ok=True)


def clone_url_for_host(root: Path) -> str:
    # 호스트 작업은 항상 file://(daemon 비의존, teardown 검사 안정).
    return config.hub_repo(root).as_uri()


def clone_url_for_container(root: Path, *, transport: str, port: int) -> str:
    if transport == "file":
        return "file:///hub"
    return f"git://host.docker.internal:{port}/project.git"
