"""subprocess 공통 래퍼.

모든 외부 명령(git/docker/tmux/crontab)을 이 한 곳으로 통과시켜
실행·캡처·에러 변환을 일원화한다. shell 없이 argv로만 실행한다.
"""
from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = ["ProcResult", "ProcError", "run"]


@dataclass(frozen=True)
class ProcResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


class ProcError(RuntimeError):
    """외부 명령이 0이 아닌 코드로 종료(또는 실행 실패)."""

    def __init__(self, argv: Sequence[str], returncode: int, stdout: str, stderr: str):
        self.argv = list(argv)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(
            f"명령 실패(exit {returncode}): {' '.join(map(str, argv))}\n{stderr.strip()}"
        )


def run(
    argv: Sequence[str | os.PathLike[str]],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    text: bool = True,
    timeout: float | None = None,
) -> ProcResult:
    """argv를 실행하고 :class:`ProcResult` 반환.

    - ``env`` 는 ``os.environ`` 위에 **덮어쓰는 overlay**(부분 지정 가능).
    - ``check=True`` 면 0이 아닌 종료코드에서 :class:`ProcError` 발생.
    - ``timeout`` (선택, 초): 지정하면 그 시간 내 종료하지 않을 때
      ``subprocess.TimeoutExpired``를 잡아 :class:`ProcError`(``returncode=-1``,
      ``stderr="timeout"``)로 변환한다. **timeout 초과는 ``check`` 와 무관하게 실패**로
      본다(정리 경로의 무기한 hang 방지). **기본값 ``None`` 이면 상한 없음 —
      기존 호출부는 이 인자를 생략하므로 동작이 완전히 불변이다**(하위호환 순수 추가).
    """
    argv_str = [str(a) for a in argv]
    full_env = {**os.environ, **env} if env is not None else None

    try:
        completed = subprocess.run(
            argv_str,
            cwd=Path(cwd) if cwd is not None else None,
            env=full_env,
            capture_output=True,
            text=text,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        out = e.stdout
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        raise ProcError(argv_str, -1, out or "", "timeout") from e
    result = ProcResult(
        argv=argv_str,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
    if check and result.returncode != 0:
        raise ProcError(argv_str, result.returncode, result.stdout, result.stderr)
    return result
