"""tmux 오케스트레이션 — 세션/윈도우, send-keys 주입, pipe-pane 증분 캡처.

윈도우는 **생성 시 캡처한 고유 id(`@window-id`)로 타깃**한다(식별자의 점이
`-t name`을 오해석/prefix 매칭하는 문제 회피, §2.3/§6.4).
"""
from __future__ import annotations

import shlex
from collections.abc import Sequence
from pathlib import Path

from . import naming, proc

__all__ = [
    "SESSION", "ensure_session", "new_window", "resolve_window",
    "send_text", "start_capture", "read_increment", "kill_window",
]

SESSION = "axdt"


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
        _load_buffer(text)
        proc.run(["tmux", "paste-buffer", "-d", "-b", "axdt", "-t", win_id])
    else:
        proc.run(["tmux", "send-keys", "-t", win_id, "-l", "--", text])


def _load_buffer(text: str) -> None:
    # load-buffer는 stdin/파일을 받는다. proc 래퍼는 stdin을 안 다루므로
    # 임시 파일 경유(통합 시 실제 동작). 단위 테스트는 호출 사실만 확인.
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".axdtbuf", delete=False) as f:
        f.write(text)
        path = f.name
    proc.run(["tmux", "load-buffer", "-b", "axdt", path])


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


def kill_window(win_id: str) -> None:
    proc.run(["tmux", "kill-window", "-t", win_id], check=False)
