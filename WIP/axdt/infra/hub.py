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
    return [
        "git", "daemon",
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


def _head_sha(url: str) -> str | None:
    """url의 HEAD sha(``git ls-remote``). 조회 실패(비영 종료·빈 출력)면 None."""
    r = proc.run(["git", "ls-remote", url, "HEAD"], check=False)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return r.stdout.strip().splitlines()[0].split()[0]


def _serves_our_hub(root: Path, port: int) -> bool:
    """port가 우리 허브(root의 project.git)를 서빙 중인지 identity로 확인.

    호스트에서 ``git://127.0.0.1:<port>/project.git``의 HEAD sha와 우리 로컬 허브
    (``file://``)의 HEAD sha를 비교한다. 둘 다 조회되고 같으면 우리 허브(True).
    """
    remote_sha = _head_sha(f"git://127.0.0.1:{port}/project.git")
    local_sha = _head_sha(clone_url_for_host(root))
    return remote_sha is not None and local_sha is not None and remote_sha == local_sha


def _spawn_and_wait(root: Path, port: int) -> int:
    import subprocess

    pidfile = config.daemon_pid(root)
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(
        daemon_argv(root, port),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    pidfile.write_text(str(p.pid))
    for _ in range(50):  # 최대 ~5s readiness 대기
        if _port_open(port):
            return port
        time.sleep(0.1)
    raise RuntimeError(f"git daemon 기동 실패(port {port})")


def serve(root: Path, *, transport: str, port: int | None = None) -> int:
    """git daemon을 백그라운드 기동하고 readiness까지 대기(transport는 daemon 단일).

    선호 포트(``port`` 또는 ``config.hub_port``)가 이미 우리 데몬으로 서빙 중이면
    재사용한다(identity를 ``_serves_our_hub``로 확인). 비어 있으면 그 포트에서
    기동한다. 외부(비-AXDT) daemon이 선호 포트를 점유 중이면, 프로젝트 경로 해시로
    결정적으로 파생한 포트(``config.derived_port``)로 폴백한다 — 그 파생 포트마저
    외부 daemon이 점유(그리고 우리 허브가 아님) 중이면 RuntimeError.

    기동 전 pre-receive 게이트를 멱등 재설치한다(기존 허브·재기동 대비 — install_gate는
    덮어써도 안전). 반환: 실제로 선택된 포트(항상 int).
    """
    if transport != "daemon":
        raise ValueError(f"알 수 없는 transport={transport!r} (daemon만 지원)")
    install_gate(config.hub_repo(root))

    preferred = port or config.hub_port(root)
    if _port_open(preferred) and _serves_our_hub(root, preferred):
        return preferred
    if not _port_open(preferred):
        return _spawn_and_wait(root, preferred)

    # 선호 포트를 외부 데몬이 점유 → 결정적 파생 포트로 폴백.
    derived = config.derived_port(root)
    if _port_open(derived):
        if _serves_our_hub(root, derived):
            return derived
        raise RuntimeError(
            f"허브 포트 충돌: 선호 {preferred}·파생 {derived} 모두 외부 데몬 점유"
        )
    return _spawn_and_wait(root, derived)


def stop_daemon(root: Path) -> None:
    """활성 Leader 세션이 있으면 거부, 없을 때만 종료(push 단절 방지)."""
    from . import tmux

    if tmux._list_windows():  # 활성 윈도우 존재
        raise RuntimeError("활성 Leader 세션이 있어 daemon을 멈추지 않습니다")
    pidfile = config.daemon_pid(root)
    if not pidfile.exists():
        return
    pid = int(pidfile.read_text().strip())
    proc.run(["kill", str(pid)], check=False)
    pidfile.unlink(missing_ok=True)


def clone_url_for_host(root: Path) -> str:
    # 호스트 작업은 항상 file://(daemon 비의존, teardown 검사 안정).
    return config.hub_repo(root).as_uri()


def clone_url_for_container(root: Path, *, transport: str, port: int) -> str:
    # daemon 단일(ADR-0006 대안 C 기각): file:// RW 마운트는 컨테이너가 hooks/config/refs를
    # 직접 조작해 pre-receive 게이트(ADR-0007)를 우회할 수 있어 제거됐다.
    if transport != "daemon":
        raise ValueError(f"알 수 없는 transport={transport!r} (daemon만 지원)")
    return f"git://host.docker.internal:{port}/project.git"
