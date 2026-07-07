"""TmuxDockerBackend — Phase 5 `SessionBackend` 계약의 실substrate 구현.

ABC는 본래 agent_runner(Phase 5)에 있으나 아직 main에 없으므로, 스펙 §2.4의
인라인 계약을 여기 단일 권위로 정의한다(통합 시 Maintainer가 대조).
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from pathlib import Path

from . import config, container, hub, naming, tmux

__all__ = [
    "SessionBackend", "TmuxDockerBackend",
    "BackendError", "NotStarted", "AlreadyStarted", "SessionDead",
]


class BackendError(RuntimeError):
    pass


class NotStarted(BackendError):
    pass


class AlreadyStarted(BackendError):
    pass


class SessionDead(BackendError):
    pass


class SessionBackend(ABC):
    """실행 substrate 추상(Phase 5 계약). start/send/read/alive/stop."""

    @abstractmethod
    def start(self, command: Sequence[str], cwd: Path,
              env: Mapping[str, str] | None = None) -> None: ...

    @abstractmethod
    def send_text(self, text: str) -> None: ...

    @abstractmethod
    def read_new_output(self) -> str: ...

    @abstractmethod
    def is_alive(self) -> bool: ...

    @abstractmethod
    def stop(self) -> None: ...


def _host_ids() -> tuple[int, int]:
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    return (getuid() if getuid else 0, getgid() if getgid else 0)


class TmuxDockerBackend(SessionBackend):
    """tmux 윈도우 안의 컨테이너로 Leader를 구동한다."""

    def __init__(self, i: naming.Identifier, root: Path, *,
                 transport: str | None = None, port: int | None = None,
                 uid: int | None = None, gid: int | None = None, tag: str = "dev"):
        self.i = i
        self.root = Path(root)
        self.transport = transport or config.transport()
        self.port = port or config.hub_port(self.root)
        duid, dgid = _host_ids()
        self.uid = duid if uid is None else uid
        self.gid = dgid if gid is None else gid
        self.tag = tag
        self._state = "NOT_STARTED"
        self._win: str | None = None
        self._offset = 0
        self._log = config.capture_log(self.root, i)

    # --- 내부 ---
    def _win_id(self) -> str | None:
        if self._win is not None:
            return self._win
        self._win = tmux.resolve_window(self.i)
        return self._win

    def _cleanup(self) -> None:
        win = self._win_id()
        if win is not None:
            tmux.kill_window(win)
        container.stop(self.i)
        container.rm(self.i)

    # --- SessionBackend 계약 ---
    def start(self, command: Sequence[str], cwd: Path,
              env: Mapping[str, str] | None = None) -> None:
        if self._state == "RUNNING":
            raise AlreadyStarted(f"이미 시작됨: {self.i.value}")
        cwd = Path(cwd)
        if not cwd.exists():
            raise FileNotFoundError(f"작업본 없음(provision 선행 필요): {cwd}")
        # 사전 fail-fast: 외부에 이미 동일 윈도우/컨테이너 존재
        if tmux.resolve_window(self.i) is not None or container.exists(self.i):
            raise AlreadyStarted(f"외부에 활성 자원 존재: {self.i.value}")
        hub.serve(self.root, transport=self.transport, port=self.port)
        tmux.ensure_session()
        try:
            argv = container.run_args(
                self.i, list(command), cwd,
                uid=self.uid, gid=self.gid,
                transport=self.transport, port=self.port,
                env=env, tag=self.tag,
            )
            self._win = tmux.new_window(naming.tmux_window(self.i), argv, cwd)
            tmux.start_capture(self._win, self._log)
            self._offset = 0
            self._state = "RUNNING"
        except Exception:
            self._cleanup()  # 부분 실패 보상 정리
            raise

    def send_text(self, text: str) -> None:
        if self._state == "NOT_STARTED":
            raise NotStarted(self.i.value)
        if not self.is_alive():
            raise SessionDead(self.i.value)
        tmux.send_text(self._win_id(), text)

    def read_new_output(self) -> str:
        text, self._offset = tmux.read_increment(self._log, self._offset)
        return text

    def is_alive(self) -> bool:
        return container.is_running(self.i) and self._win_id() is not None

    def status(self) -> str:
        if self._state == "NOT_STARTED" and self._win is None:
            return "NOT_STARTED"
        win = self._win_id() is not None
        run = container.is_running(self.i)
        if win and run:
            return "RUNNING"
        if win and not run:
            return "WINDOW_ONLY"
        if run and not win:
            return "CONTAINER_ONLY"
        return "STOPPED"

    def stop(self) -> None:
        win = self._win_id()
        if win is not None:
            tmux.kill_window(win)
        container.stop(self.i)
        container.rm(self.i)
        self._win = None
        self._state = "STOPPED"
