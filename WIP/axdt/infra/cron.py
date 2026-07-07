"""Watcher를 cron으로 주기 호출(ADR-0001). 마커 블록으로 멱등 교체.

엔트리는 cwd로 cd + flock로 overlap 방지 + (선택) env 주입.
"""
from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path

from . import config, proc

__all__ = ["MARKER_BEGIN", "MARKER_END", "build_crontab_text", "install", "uninstall"]

MARKER_BEGIN = "# >>> AXDT cron >>>"
MARKER_END = "# <<< AXDT cron <<<"

_DEFAULT_LOCK = "/tmp/axdt-watcher.lock"


def _strip_block(text: str) -> str:
    lines = text.splitlines()
    out, skip = [], False
    for line in lines:
        if line.strip() == MARKER_BEGIN:
            skip = True
            continue
        if line.strip() == MARKER_END:
            skip = False
            continue
        if not skip:
            out.append(line)
    return "\n".join(out).strip("\n")


def build_crontab_text(
    existing: str,
    *,
    interval_min: int,
    watcher_cmd: str,
    cwd: str,
    lockfile: str = _DEFAULT_LOCK,
    env: Mapping[str, str] | None = None,
) -> str:
    """기존 crontab 텍스트에서 AXDT 블록을 교체(없으면 추가)한 새 텍스트 반환."""
    base = _strip_block(existing)
    env_prefix = "".join(f"{k}={v} " for k, v in (env or {}).items())
    schedule = f"*/{interval_min} * * * *"
    entry = (
        f"{schedule} cd {cwd} && {env_prefix}"
        f"flock -n {lockfile} {watcher_cmd}"
    )
    block = f"{MARKER_BEGIN}\n{entry}\n{MARKER_END}"
    parts = [p for p in (base, block) if p]
    return "\n".join(parts) + "\n"


def _read_crontab() -> str:
    r = proc.run(["crontab", "-l"], check=False)
    return r.stdout if r.returncode == 0 else ""


def _write_crontab(text: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".axdtcron", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        proc.run(["crontab", path])
    finally:
        os.unlink(path)


def install(
    interval_min: int,
    watcher_cmd: str,
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    lockfile: str = _DEFAULT_LOCK,
) -> None:
    cwd = cwd or str(Path.cwd())
    new = build_crontab_text(
        _read_crontab(), interval_min=interval_min, watcher_cmd=watcher_cmd,
        cwd=cwd, lockfile=lockfile, env=env,
    )
    _write_crontab(new)


def uninstall() -> None:
    new = _strip_block(_read_crontab())
    _write_crontab(new + ("\n" if new else ""))
