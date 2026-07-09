"""로컬 bare repo 허브 — git 격리의 통합 지점(D3 .git 공유 문제 해결).

허브는 **권위 상태**(머지 전 Leader push 보유): 내용이 있으면 절대 덮어쓰지 않는다.
호스트는 file:// 로 clone(daemon 비의존), 컨테이너는 git 프로토콜로 push.

허브는 **수신 ref allowlist**(`ADR-0007` (a), 신원-무관) pre-receive 게이트를 강제한다
(`install_gate`) — task 브랜치 형식(`refs/heads/w<n>.t<n>-<slug>`)만 push를 허용하고
그 외 ref(`main`/`sot/*`/tags 등)와 삭제는 거부한다. 콘텐츠·경로 게이트(`ADR-0007` (b),
보호 경로 diff 검사)는 그 표를 읽어 검사하는 CODE가 미구현이라 Phase 3 후속 CODE다
(규칙 `rule-protected-paths`는 SoT에 실재 — 의존은 충족, 남은 건 검사 코드).
"""
from __future__ import annotations

import os
import socket
import sys
import time
from pathlib import Path

from . import config, proc

__all__ = [
    "init", "daemon_argv", "serve", "stop_daemon", "install_gate",
    "clone_url_for_host", "clone_url_for_container",
]

# ADR-0007 (a): task 브랜치 형식만 허용(naming.py의 식별자 정규식 + refs/heads/ 접두).
# POSIX ERE(grep -E)라 \d 대신 [0-9], 명명 그룹 없음.
_ALLOWED_REF_RE = r"^refs/heads/w[1-9][0-9]*\.t[1-9][0-9]*-[a-z0-9]+(-[a-z0-9]+)*$"
_ZERO_SHA = "0" * 40

_PRE_RECEIVE_HOOK = f"""#!/bin/sh
# AXDT hub pre-receive - ADR-0007 (a): default-deny allowlist for incoming refs
# (identity-agnostic). Only task branches (refs/heads/w<n>.t<n>-<slug>) are allowed;
# everything else (main/sot/*/tags/etc.) and ref deletion (new=zero-SHA) is rejected.
# Content/path gate ((b): protected-path diff) is out of scope here (Phase 3 follow-up CODE).
# Messages below are ASCII-only: they cross the git wire back to the pushing client's
# terminal, whose locale/codepage AXDT does not control (e.g. cp949 on Korean Windows).
while read old new ref
do
    if [ "$new" = "{_ZERO_SHA}" ]; then
        echo "AXDT hub: ref deletion rejected ($ref)" >&2
        exit 1
    fi
    if ! printf '%s' "$ref" | grep -Eq '{_ALLOWED_REF_RE}'; then
        echo "AXDT hub: ref rejected - not in task-branch allowlist ($ref)" >&2
        exit 1
    fi
done
exit 0
"""


def install_gate(repo: Path) -> None:
    """허브에 pre-receive allowlist 게이트를 (재)설치한다(`ADR-0007` (a)).

    - ``hooks/pre-receive``: 수신 ref가 ``refs/heads/w<n>.t<n>-<slug>`` 형식일 때만
      허용(default-deny). 그 외 모든 ref(``main``·``sot/*``·태그·``refs/remotes/*`` 등)와
      삭제(수신 new-SHA가 40개 0)는 거부해 exit 1(pre-receive 비영 시 git이 어떤 ref도
      갱신하지 않는다).
    - ``receive.denyDeletes=true``·``core.logAllRefUpdates=true`` 도 함께 설정한다
      (방어 심화; reflog로 bare 허브에서도 변경 이력 보존).
    - 멱등: 기존 훅 위에 덮어써 재설치해도 안전(재기동·기존 허브 대비).
    - 범위 제한: 콘텐츠·경로 게이트(``ADR-0007`` (b), 보호 경로 diff 검사)는 그 표를
      읽어 검사하는 CODE가 미구현이라 Phase 3 후속 CODE(규칙은 SoT에 실재).
    """
    repo = Path(repo)
    hooks_dir = repo / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-receive"
    hook_path.write_text(_PRE_RECEIVE_HOOK, encoding="utf-8", newline="\n")
    os.chmod(hook_path, 0o755)
    proc.run(["git", "-C", str(repo), "config", "receive.denyDeletes", "true"])
    proc.run(["git", "-C", str(repo), "config", "core.logAllRefUpdates", "true"])


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
    install_gate(repo)


def daemon_argv(root: Path, port: int) -> list[str]:
    # --pid-file: git daemon(부모 래퍼가 아니라 실제 listener인 git-daemon 자식)이
    # 이 파일에 **자신의(listener) pid**를 직접 쓴다(§6.1:206 identity의 전제). 래퍼
    # Popen.pid는 listen하지 않으므로 우리가 pid를 지어내 쓰지 않고 git이 쓰게 한다.
    return [
        "git", "daemon",
        f"--pid-file={config.daemon_pid(root)}",
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


# --- daemon.pid 기반 identity(§6.1:206 (a)(b)(c)) ---
# 포트 점유자의 repo HEAD 비교는 금지(금지 ①, 다른 워크트리는 HEAD가 동일해 오식별).
# 정체불명 외부 포트에 wire 프로브(ls-remote 등)도 금지(금지 ②). 판정은 오직
# daemon.pid에 적힌 PID의 생존·cmdline·listen 상태로만 한다. /proc 접근은 호출
# 시점에만 일어나며(Linux/WSL2 전제, §1) 아래 헬퍼들은 각각 monkeypatch 가능하도록
# 모듈 함수로 분리한다.


def _pid_alive(pid: int) -> bool:
    """pid 생존 확인(POSIX kill(pid, 0) 시맨틱).

    Windows에서는 ``os.kill(pid, 0)``이 생존 확인이 아니라 대상 프로세스를 실제로
    종료시킨다(CPython 문서). identity 메커니즘 자체가 ``/proc`` 전제(Linux/WSL2
    전용, §1)라 비-Linux에선 애초에 재사용 판정이 불가능하므로, 파괴적 호출을 하지
    않고 바로 False를 반환한다.
    """
    if not sys.platform.startswith("linux"):
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_cmdline(pid: int) -> list[str] | None:
    """pid의 실행 argv. ``/proc/<pid>/cmdline``(NUL 구분) 우선, 실패 시 ``ps`` 폴백.

    ``ps -p <pid> -o args=`` 폴백은 출력이 단일 문자열이라 공백으로 split한다
    (base-path에 공백이 있으면 부정확하나 Linux 대상 경로엔 통상 공백이 없다).
    둘 다 실패하면 None.
    """
    raw: bytes | None
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        raw = None
    if raw is not None:
        parts = raw.split(b"\0")
        if parts and parts[-1] == b"":
            parts = parts[:-1]
        if parts:
            return [p.decode("utf-8", errors="replace") for p in parts]
    try:
        r = proc.run(["ps", "-p", str(pid), "-o", "args="], check=False)
    except OSError:
        return None
    if r.returncode != 0:
        return None
    line = r.stdout.strip()
    return line.split() if line else None


def _listening_inodes(port: int) -> set[str]:
    """``/proc/net/tcp``·``tcp6``에서 port를 LISTEN 중인 소켓의 inode 집합."""
    inodes: set[str] = set()
    hex_port = format(port, "04X")
    for name in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(name).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) < 10:
                continue
            local_address, state, inode = fields[1], fields[3], fields[9]
            local_port = local_address.rpartition(":")[2]
            if local_port.upper() == hex_port and state == "0A":  # 0A = LISTEN
                inodes.add(inode)
    return inodes


def _pid_listens_on_port(pid: int, port: int) -> bool:
    """pid가 port를 LISTEN 중인지 ``/proc/net/tcp[6]`` + ``/proc/<pid>/fd`` symlink로 확인."""
    inodes = _listening_inodes(port)
    if not inodes:
        return False
    try:
        fds = list(Path(f"/proc/{pid}/fd").iterdir())
    except OSError:
        return False
    for fd in fds:
        try:
            target = os.readlink(fd)
        except OSError:
            continue
        if target.startswith("socket:[") and target[len("socket:["):-1] in inodes:
            return True
    return False


def _cmdline_matches(cmdline: list[str], root: Path, port: int | None) -> bool:
    """cmdline이 ``daemon_argv(root, port)`` 기대 argv와 판별 원소 단위로 일치하는지.

    argv0(``git`` 대 ``git-daemon``)는 git 버전에 따라 다르므로 정확 일치에 의존하지
    않는다. base-path(identity의 핵심)·``daemon`` 토큰·(port가 주어지면) port, 이
    판별 원소들이 각각 **원소로**(joined 문자열 substring이 아니라) 존재해야 한다.
    port=None이면 base-path·daemon 토큰만 확인한다(``stop_daemon``처럼 호출 시점에
    실행 중인 포트를 모르는 경우용).
    """
    base_path_arg = f"--base-path={config.hub_dir(root)}"
    if base_path_arg not in cmdline:
        return False
    argv0 = cmdline[0] if cmdline else ""
    # 파일명 정확 일치(Path(...).name)로: "/tmp/notgit-daemon" 같은 위장 argv0가
    # endswith("git-daemon") 부분일치로 오통과하는 것을 막는다.
    if "daemon" not in cmdline and Path(argv0).name != "git-daemon":
        return False
    if port is not None and f"--port={port}" not in cmdline:
        return False
    return True


def _is_our_daemon(root: Path, pid: int, port: int | None, *, require_listen: bool) -> bool:
    """pid가 root의 우리 daemon인지 판정(§6.1:206 (a)(b)(c) / §6.1:207).

    (a) pid 생존 (b) cmdline이 우리 daemon argv와 판별 원소 단위 일치 — 이 둘은 항상.
    (c) require_listen=True면 추가로 그 pid가 port를 listen 중인지까지 확인(port 필수).
    serve()의 재사용 판정은 require_listen=True, stop_daemon()의 kill 전 검증은
    require_listen=False(포트를 모르는 시점이라 port=None으로 호출).
    """
    if not _pid_alive(pid):
        return False
    cmdline = _read_cmdline(pid)
    if cmdline is None:
        return False
    if not _cmdline_matches(cmdline, root, port):
        return False
    if require_listen:
        if port is None:
            raise ValueError("require_listen=True 이면 port가 필요합니다")
        if not _pid_listens_on_port(pid, port):
            return False
    return True


def _our_daemon_pid(root: Path) -> int | None:
    """``daemon.pid`` 파일에서 PID를 읽는다. 없거나 파싱 불가하면 None(stale/미기록).

    ``exists()``와 ``read_text()`` 사이 파일이 삭제되는 경합(``FileNotFoundError``
    등 ``OSError``)도 흡수한다. 파싱된 pid가 0 이하이면 오염된 pidfile로 간주해
    None을 반환한다(``os.kill(0, 0)``/``os.kill(-1, 0)`` 같은 위험한 호출로 이어지는
    경로를 원천 차단).
    """
    pidfile = config.daemon_pid(root)
    if not pidfile.exists():
        return None
    try:
        pid = int(pidfile.read_text().strip())
    except (OSError, ValueError):
        return None
    if pid <= 0:
        return None
    return pid


def _readiness(root: Path, port: int, popen) -> bool:
    """방금 띄운 daemon의 기동 완료를 확인(§6.1:206 readiness).

    (a) Popen 자식 생존(``poll() is None`` — bind 경합으로 즉사했으면 실패) +
    (b) 포트 connect 성공 + (c) **우리가 방금 띄운** 데몬 대상 ``git ls-remote``가
    timeout 10s 안에 returncode 0(응답성·repo 도달 확인 — HEAD 값 비교 아님, 빈
    허브도 통과). 정체불명 외부 포트에는 이 프로브를 보내지 않는다(금지 ②) — 방금
    이 프로세스가 spawn한 popen 대상에서만 호출된다.
    """
    for _ in range(50):  # 최대 ~5s 대기
        if popen.poll() is not None:
            return False
        if _port_open(port):
            r = proc.run(
                ["git", "ls-remote", f"git://127.0.0.1:{port}/project.git", "HEAD"],
                check=False, timeout=10,
            )
            return r.returncode == 0
        time.sleep(0.1)
    return False


def _spawn_and_wait(root: Path, port: int) -> int:
    """git daemon을 spawn하고 readiness + listener pid 재검증까지 마친 뒤 port를 반환.

    ``daemon_argv``의 ``--pid-file``로 git이 **listener(git-daemon 자식) pid**를
    직접 쓴다 — 래퍼 ``Popen.pid``는 listen하지 않으므로 우리가 pid를 지어내 pidfile에
    쓰지 않는다(A). readiness 성공 후에도 그 pidfile의 pid를 ``_is_our_daemon(...,
    require_listen=True)``로 재검증한다(TOCTOU 차단 — 외부 데몬이 그새 포트를 물었으면
    우리 자식은 bind 실패로 즉사하거나, 기록된 pid가 그 포트를 listen하지 않아 여기서
    걸린다). 실패 경로는 전부 자식 종료 + pidfile 정리 후 재raise한다.
    """
    import subprocess

    pidfile = config.daemon_pid(root)
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.unlink(missing_ok=True)  # stale 제거: git이 이번 실행의 pid를 새로 쓰게 함
    p = subprocess.Popen(
        daemon_argv(root, port),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not _readiness(root, port, p):
            raise RuntimeError(f"git daemon 기동 실패(port {port})")
        listener_pid: int | None = None
        for _ in range(20):  # git이 --pid-file을 쓰는 극소 창 대비 최대 ~1s 재시도
            listener_pid = _our_daemon_pid(root)
            if listener_pid is not None:
                break
            time.sleep(0.05)
        if listener_pid is None or not _is_our_daemon(root, listener_pid, port, require_listen=True):
            raise RuntimeError(f"git daemon listener 재검증 실패(port {port})")
        return port
    except BaseException:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        lp = _our_daemon_pid(root)
        if lp is not None:
            proc.run(["kill", str(lp)], check=False)
        pidfile.unlink(missing_ok=True)
        raise


def _reuse_if_ours(root: Path, port: int) -> bool:
    """port에서 서빙 중인 프로세스가 ``daemon.pid`` 기준 우리 daemon인지(재사용 판정)."""
    pid = _our_daemon_pid(root)
    return pid is not None and _is_our_daemon(root, pid, port, require_listen=True)


def serve(root: Path, *, transport: str, port: int | None = None) -> int:
    """git daemon을 백그라운드 기동하고 readiness까지 대기(transport는 daemon 단일).

    선호 포트(``port`` 또는 ``config.hub_port``)가 닫혀 있으면 거기서 기동한다.
    열려 있으면 재사용 여부를 ``daemon.pid`` 기반 identity로 판정한다(``_reuse_if_ours``:
    기록 PID 생존 + cmdline 판별 원소 일치 + 그 PID가 포트 listen, 셋 다 만족해야
    재사용 — 포트 점유자의 repo HEAD 비교는 하지 않는다, 다른 워크트리는 HEAD가
    같아 오식별하기 때문). 판정 실패(``daemon.pid`` 없음·stale·불일치)면 열린 포트를
    외부로 취급해, 프로젝트 경로 해시로 결정적으로 파생한 포트(``config.derived_port``)로
    폴백한다 — 파생 포트도 열려 있고 우리 것이 아니면 RuntimeError(fail-closed).

    기동 전 pre-receive 게이트를 멱등 재설치한다(기존 허브·재기동 대비 — install_gate는
    덮어써도 안전). 반환: 실제로 선택된 포트(항상 int).
    """
    if transport != "daemon":
        raise ValueError(f"알 수 없는 transport={transport!r} (daemon만 지원)")
    install_gate(config.hub_repo(root))

    preferred = port or config.hub_port(root)
    if not _port_open(preferred):
        return _spawn_and_wait(root, preferred)
    if _reuse_if_ours(root, preferred):
        return preferred

    # 선호 포트를 daemon.pid로 우리 것임을 확인 못함(=외부 취급) → 파생 포트로 폴백.
    derived = config.derived_port(root)
    if not _port_open(derived):
        return _spawn_and_wait(root, derived)
    if _reuse_if_ours(root, derived):
        return derived
    raise RuntimeError(
        f"허브 포트 충돌: 선호 {preferred}·파생 {derived} 모두 외부 데몬 점유"
    )


def stop_daemon(root: Path) -> None:
    """활성 Leader 세션이 있으면 거부, 없을 때만 종료(push 단절 방지).

    kill 전 identity 검증(§6.1:207): ``daemon.pid``의 PID 생존 + cmdline이 우리
    daemon(base-path) argv와 일치하는 PID만 kill한다(포트 listen 확인은 재사용
    판정과 달리 요구하지 않음 — 종료 시점엔 base-path 일치가 핵심). 검증 실패면
    kill하지 않고 pidfile만 정리한다(stale, 또는 PID 재사용된 무고한 프로세스 보호).

    identity가 확인된 pid는 kill 시도 후 **성공(returncode 0) 또는 이미 죽어있을
    때만** pidfile을 정리한다. kill이 실패했는데 pid가 여전히 살아있으면 pidfile을
    남긴다(살아있는 우리 데몬을 추적 불가 상태로 만들지 않기 위함).
    """
    from . import tmux

    if tmux._list_windows():  # 활성 윈도우 존재
        raise RuntimeError("활성 Leader 세션이 있어 daemon을 멈추지 않습니다")
    pidfile = config.daemon_pid(root)
    if not pidfile.exists():
        return
    pid = _our_daemon_pid(root)
    if pid is not None and _is_our_daemon(root, pid, None, require_listen=False):
        r = proc.run(["kill", str(pid)], check=False)
        if r.returncode == 0 or not _pid_alive(pid):
            pidfile.unlink(missing_ok=True)
        return
    pidfile.unlink(missing_ok=True)  # identity 불일치(외부/stale) → 기존대로 정리


def clone_url_for_host(root: Path) -> str:
    # 호스트 작업은 항상 file://(daemon 비의존, teardown 검사 안정).
    return config.hub_repo(root).as_uri()


def clone_url_for_container(root: Path, *, transport: str, port: int) -> str:
    # daemon 단일(ADR-0006 대안 C 기각): file:// RW 마운트는 컨테이너가 hooks/config/refs를
    # 직접 조작해 pre-receive 게이트(ADR-0007)를 우회할 수 있어 제거됐다.
    if transport != "daemon":
        raise ValueError(f"알 수 없는 transport={transport!r} (daemon만 지원)")
    return f"git://host.docker.internal:{port}/project.git"
