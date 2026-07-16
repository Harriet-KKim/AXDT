"""tmux 오케스트레이션 — 세션/윈도우, send-keys 주입, pipe-pane 증분 캡처.

윈도우는 **생성 시 캡처한 고유 id(`@window-id`)로 타깃**한다(식별자의 점이
`-t name`을 오해석/prefix 매칭하는 문제 회피, §2.3/§6.4).
"""
from __future__ import annotations

import os
import shlex
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path

from . import naming, proc

__all__ = [
    "SESSION", "ensure_session", "new_window", "resolve_window",
    "send_text", "start_capture", "read_increment", "kill_window",
]

SESSION = "axdt"


def _warn_quiet(msg: str, exc: BaseException | None = None) -> None:
    """정리 경고를 **무예외로** stderr에 낸다(R11 경미3 — 출력 안전화만, 시그니처·동작 불변).

    ``print``과 ``exc``의 ``repr`` 포맷팅을 각각 ``try/except Exception``으로 감싼다 —
    stderr 닫힘·비정상 ``__repr__``이 정리 경고 출력에서 탈출해 **원래 tmux 오류를 가리는**
    일을 막는다. ``BaseException``(KeyboardInterrupt 등)은 전파한다."""
    if exc is not None:
        try:
            msg = f"{msg}: {exc!r}"
        except Exception:  # noqa: BLE001 — __repr__ 실패도 흡수
            msg = f"{msg}: <repr-failed>"
    try:
        print(msg, file=sys.stderr)
    except Exception:  # noqa: BLE001 — stderr 닫힘 등 출력 실패도 흡수
        pass


def ensure_session(session: str = SESSION) -> None:
    r = proc.run(["tmux", "has-session", "-t", session], check=False)
    if r.returncode != 0:
        proc.run(["tmux", "new-session", "-d", "-s", session])


def new_window(window: str, argv: Sequence[str], cwd, *, session: str = SESSION) -> str:
    """윈도우를 만들고 생성된 `@window-id`를 반환. 중복이면 fail-fast."""
    if _find_window_by_name(window, session=session) is not None:
        raise FileExistsError(f"tmux 윈도우 이미 존재: {window}")
    shell_cmd = " ".join(shlex.quote(a) for a in argv)
    r = proc.run([
        "tmux", "new-window", "-t", session, "-n", window,
        "-c", str(cwd), "-P", "-F", "#{window_id}", shell_cmd,
    ])
    return r.stdout.strip()


def _list_windows(session: str = SESSION) -> list[tuple[str, str]]:
    r = proc.run(
        ["tmux", "list-windows", "-t", session, "-F", "#{window_id} #{window_name}"],
        check=False,
    )
    out: list[tuple[str, str]] = []
    for line in r.stdout.splitlines():
        wid, _, name = line.partition(" ")
        if wid:
            out.append((wid, name))
    return out


def _find_window_by_name(name: str, *, session: str = SESSION) -> str | None:
    # Python에서 정확 문자열 일치(점/prefix 안전).
    for wid, wname in _list_windows(session):
        if wname == name:
            return wid
    return None


def resolve_window(i: naming.Identifier, *, session: str = SESSION) -> str | None:
    return _find_window_by_name(naming.tmux_window(i), session=session)


def send_text(win_id: str, text: str) -> None:
    """텍스트를 그대로 주입(제출키 미부착). 개행/제어문자는 paste-buffer로."""
    if "\n" in text or "\r" in text or "\t" in text:
        # 고정 버퍼명("axdt")을 병렬 probe/세션이 공유하면 프롬프트가 서로 교차
        # 오염된다. 호출마다 고유 버퍼명을 만들어 load↔paste를 짝짓는다(R5 중대4).
        buf = f"axdt-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        _load_buffer(text, buf)
        try:
            proc.run(["tmux", "paste-buffer", "-d", "-b", buf, "-t", win_id])
        finally:
            # paste가 실패하면 -d가 버퍼를 못 지워 고유 버퍼가 쌓인다 — 명시적으로
            # 정리한다(이미 -d로 지워졌으면 무해, R6 경미3). tmux 부재 등으로 proc.run이
            # 던지면 원래 paste 실패를 가리므로 무예외로 감싼다(R11 경미3, 동작 불변).
            try:
                proc.run(["tmux", "delete-buffer", "-b", buf], check=False)
            except Exception:  # noqa: BLE001 — 정리 실패가 원래 오류를 안 가리게(BaseException은 전파)
                pass
    else:
        proc.run(["tmux", "send-keys", "-t", win_id, "-l", "--", text])


def _load_buffer(text: str, buf: str = "axdt") -> None:
    # load-buffer는 stdin/파일을 받는다. proc 래퍼는 stdin을 안 다루므로
    # 임시 파일 경유(통합 시 실제 동작). 단위 테스트는 호출 사실만 확인.
    #
    # 임시 경로를 먼저 확보하고 write+load를 try에, unlink를 finally에 둔다 —
    # write/close가 실패해도(예: LANG=C에서 UnicodeEncodeError) 파일이 새지 않게
    # 한다. encoding="utf-8"을 명시해 로케일 의존 인코딩 오류도 피한다. ``buf``는
    # 호출부가 넘기는 고유 버퍼명(R5 중대4).
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".axdtbuf")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        # load-buffer는 파일을 즉시 자기 버퍼로 읽어들이므로 이후 삭제는 안전.
        proc.run(["tmux", "load-buffer", "-b", buf, path])
    finally:
        try:
            os.unlink(path)
        except OSError as e:
            # 임시 파일 정리 실패는 기능 실패가 아니라(버퍼는 이미 tmux가 읽음) 예외를
            # 재발생시키지 않되, 파일 잔류를 사람이 알 수 있게 경고한다(R8 경미4). 경고 출력
            # 자체(print/repr)가 stderr 닫힘 등으로 탈출해 원래 오류를 가리지 않게 _warn_quiet
            # 무예외 헬퍼로 낸다(R11 경미3).
            _warn_quiet(f"[tmux] 경고: prompt 임시 파일 정리 실패 — {path} 남음", e)


def start_capture(win_id: str, logfile) -> None:
    log = Path(logfile)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_bytes(b"")  # truncate: 이전 run의 stale 출력 제거
    quoted = shlex.quote(str(log))
    proc.run(["tmux", "pipe-pane", "-o", "-t", win_id, f"cat >> {quoted}"])


def _decode_partial(b: bytes) -> tuple[str, int]:
    if not b:
        return "", 0
    for back in range(0, min(4, len(b) + 1)):
        end = len(b) - back
        try:
            return b[:end].decode("utf-8"), end
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace"), len(b)


def read_increment(logfile, offset: int) -> tuple[str, int]:
    p = Path(logfile)
    if not p.exists():
        return "", offset
    data = p.read_bytes()
    chunk = data[offset:]
    text, consumed = _decode_partial(chunk)
    return text, offset + consumed


def kill_window(win_id: str, *, timeout: float | None = None) -> None:
    """윈도우를 죽인다. ``timeout``(선택)을 주면 그 시간 내 tmux가 응답하지 않을 때
    ``proc.ProcError``(timeout)로 실패시켜 정리 경로가 무기한 hang하지 않게 한다
    (R8 중대1). 기본 ``None``이면 상한 없음(기존 동작 불변, 하위호환 순수 추가)."""
    proc.run(["tmux", "kill-window", "-t", win_id], check=False, timeout=timeout)
