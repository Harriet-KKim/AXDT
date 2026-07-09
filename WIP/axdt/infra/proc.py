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


# timeout 초과 시 사용하는 비영 sentinel returncode(check=False일 때).
# bash의 timeout(1) 명령과 동일한 관례(124)를 따른다.
_TIMEOUT_RETURNCODE = 124


def _decode_partial(data: bytes | str | None) -> str:
    """TimeoutExpired가 들고 있는 부분 출력을 str로 정규화(None/bytes/str 모두 처리)."""
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode(errors="replace")
    return data


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
    - ``timeout`` 초과 시(``subprocess.TimeoutExpired``): ``check=True`` 면
      :class:`ProcError`(returncode=``_TIMEOUT_RETURNCODE``)로 변환해 raise, ``check=False``
      면 비영 sentinel returncode와 부분 출력(있으면)을 담은 :class:`ProcResult`를 반환한다
      (호출자가 "미응답"을 non-zero로 감지할 수 있도록 — readiness 프로브의 전제).
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
    except subprocess.TimeoutExpired as exc:
        stdout = _decode_partial(exc.stdout)
        stderr = _decode_partial(exc.stderr)
        if check:
            raise ProcError(argv_str, _TIMEOUT_RETURNCODE, stdout, stderr) from exc
        return ProcResult(
            argv=argv_str, returncode=_TIMEOUT_RETURNCODE, stdout=stdout, stderr=stderr
        )

    result = ProcResult(
        argv=argv_str,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
    if check and result.returncode != 0:
        raise ProcError(argv_str, result.returncode, result.stdout, result.stderr)
    return result
