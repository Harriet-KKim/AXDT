"""경로·상수·환경설정.

런타임 산출물은 프로젝트 루트 아래 ``.axdt/`` 와 ``workspaces/`` 에 둔다(둘 다 gitignore).
상태 저장소는 없다(ADR-0002) — 존재 여부는 라이브 조회로 도출. 단 허브는 권위 상태.
"""
from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from pathlib import Path

from . import naming

__all__ = [
    "DEFAULT_HUB_PORT",
    "CONTAINER_HOME",
    "CONTAINER_WORKDIR",
    "Transport",
    "axdt_dir",
    "hub_dir",
    "hub_repo",
    "daemon_pid",
    "capture_dir",
    "capture_log",
    "workspaces_dir",
    "workspace_path",
    "progress_path",
    "report_dir",
    "transport",
    "hub_port",
    "derived_port",
    "project_root",
]

DEFAULT_HUB_PORT = 9418
# HOME은 작업트리(/work) 밖의 비-repo 경로 → 도구 설정·자격증명이 작업트리에 새지 않음.
CONTAINER_HOME = "/tmp/axdt-home"
CONTAINER_WORKDIR = "/work"

Transport = str  # "daemon" 단일 — file:// RW 마운트는 pre-receive 게이트(ADR-0007)를
# 우회하므로 제거됐다(ADR-0006 대안 C 기각).
_VALID_TRANSPORTS = ("daemon",)

# 등록 포트 대역(ephemeral 49152+ 회피)에서 결정적 파생.
_PORT_LO = 10000
_PORT_HI = 49151


# --- 경로 ---

def axdt_dir(root: Path) -> Path:
    return Path(root) / ".axdt"


def hub_dir(root: Path) -> Path:
    return axdt_dir(root) / "hub"


def hub_repo(root: Path) -> Path:
    return hub_dir(root) / "project.git"


def daemon_pid(root: Path) -> Path:
    return hub_dir(root) / "daemon.pid"


def capture_dir(root: Path) -> Path:
    return axdt_dir(root) / "capture"


def capture_log(root: Path, i: naming.Identifier) -> Path:
    return capture_dir(root) / f"{i.value}.log"


def workspaces_dir(root: Path) -> Path:
    return Path(root) / "workspaces"


def workspace_path(root: Path, i: naming.Identifier) -> Path:
    return workspaces_dir(root) / i.value


def progress_path(root: Path) -> Path:
    return Path(root) / "docs" / "interim" / "progress.md"


def report_dir(root: Path) -> Path:
    return Path(root) / "docs" / "interim" / "report"


# --- 환경 ---

def transport(env: Mapping[str, str] | None = None) -> Transport:
    env = os.environ if env is None else env
    t = env.get("AXDT_HUB_TRANSPORT", "daemon")
    if t not in _VALID_TRANSPORTS:
        raise ValueError(f"알 수 없는 AXDT_HUB_TRANSPORT={t!r} (daemon만 지원)")
    return t


def hub_port(root: Path, env: Mapping[str, str] | None = None) -> int:
    """선호 포트: AXDT_HUB_PORT 우선, 없으면 기본 9418. (점유 시 파생은 serve가 처리.)"""
    env = os.environ if env is None else env
    raw = env.get("AXDT_HUB_PORT")
    return int(raw) if raw else DEFAULT_HUB_PORT


def derived_port(root: Path) -> int:
    """프로젝트 루트 경로 해시로 등록 대역에서 결정적 파생(포트 점유 시 폴백용)."""
    digest = hashlib.sha256(str(root).encode("utf-8")).digest()
    span = _PORT_HI - _PORT_LO + 1
    return _PORT_LO + int.from_bytes(digest[:4], "big") % span


def project_root(env: Mapping[str, str] | None = None) -> Path:
    """프로젝트 루트 추정: AXDT_PROJECT_ROOT > git toplevel > cwd."""
    env = os.environ if env is None else env
    override = env.get("AXDT_PROJECT_ROOT")
    if override:
        return Path(override)
    try:
        from . import proc

        r = proc.run(["git", "rev-parse", "--show-toplevel"])
        return Path(r.stdout.strip())
    except Exception:
        return Path.cwd()
