"""Leader 합성 — up(workspace+컨테이너+tmux) / down(역순).

세션 안 실행 명령은 기본 placeholder(agent runner는 Phase 5 seam).
"""
from __future__ import annotations

from pathlib import Path

from . import config, container, naming, workspace
from .backend import TmuxDockerBackend

__all__ = ["PLACEHOLDER", "up", "down"]

PLACEHOLDER = ["axdt-leader-placeholder"]


def up(
    root: Path,
    i: naming.Identifier,
    *,
    base: str = "main",
    command: list[str] | None = None,
    tag: str = "dev",
    seed_from: Path | str | None = None,
) -> TmuxDockerBackend:
    """작업본 provision + 컨테이너/tmux 기동. start 실패 시 작업본까지 보상 정리."""
    command = list(command) if command else list(PLACEHOLDER)
    if not container.image_exists(tag):
        container.build_image(root, tag)
    workspace.provision(root, i, base=base, seed_from=seed_from)
    be = TmuxDockerBackend(i, root, tag=tag)
    try:
        be.start(command, config.workspace_path(root, i))
    except Exception:
        workspace.teardown(root, i, force=True)  # 원자성 근사
        raise
    return be


def down(root: Path, i: naming.Identifier, *, force: bool = False) -> None:
    TmuxDockerBackend(i, root).stop()
    workspace.teardown(root, i, force=force)
