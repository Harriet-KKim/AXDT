"""Leader별 격리 작업 디렉터리(worktrees/<id>) — bare 허브에서 clone.

호스트는 `hub`(file://) 원격으로 clone·fetch, 컨테이너 내부 push는 `origin`(git://).
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import config, hub, naming, proc

__all__ = ["provision", "teardown"]


def provision(
    root: Path,
    i: naming.Identifier,
    *,
    base: str = "main",
    force: bool = False,
    seed_from: Path | str | None = None,
    transport: str | None = None,
    port: int | None = None,
) -> Path:
    """작업본을 허브에서 clone하고 두 원격(hub/origin)·작업 브랜치를 구성한다.

    멱등 아님: 이미 있으면 force 없이 fail-fast. force면 teardown(비force) 후 재생성.
    """
    transport = transport or config.transport()
    port = port or config.hub_port(root)
    path = config.worktree_path(root, i)

    if path.exists():
        if not force:
            raise FileExistsError(f"작업본 이미 존재: {path} (force로만 재생성)")
        teardown(root, i, force=False)  # 데이터 보호는 유지

    # 허브 보장(권위 상태 — 이미 있으면 no-op).
    hub.init(root, seed_from=seed_from, empty=seed_from is None)
    hub.serve(root, transport=transport, port=port)

    host_url = hub.clone_url_for_host(root)
    container_url = hub.clone_url_for_container(root, transport=transport, port=port)

    path.parent.mkdir(parents=True, exist_ok=True)
    proc.run(["git", "clone", "--branch", base, host_url, str(path)], check=False)
    # 원격 분리: hub(호스트용) + origin(컨테이너 push용).
    proc.run(["git", "-C", str(path), "remote", "rename", "origin", "hub"], check=False)
    proc.run(["git", "-C", str(path), "remote", "add", "origin", container_url])
    proc.run(["git", "-C", str(path), "checkout", "-b", i.value])
    return path


def _has_unpushed(path: Path, i: naming.Identifier) -> bool:
    proc.run(["git", "-C", str(path), "fetch", "hub"], check=False)
    r = proc.run(
        ["git", "-C", str(path), "rev-list", "--count", f"hub/{i.value}..{i.value}"],
        check=False,
    )
    out = r.stdout.strip()
    return out not in ("", "0")


def teardown(root: Path, i: naming.Identifier, *, force: bool = False) -> None:
    path = config.worktree_path(root, i)
    if not path.exists():
        return
    if not force and _has_unpushed(path, i):
        raise RuntimeError(f"미push 커밋이 있습니다: {i.value} (force로 강제 삭제)")
    shutil.rmtree(path)
