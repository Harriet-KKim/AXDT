"""axdt CLI — `axdt <domain> <verb>` 디스패치.

console_script 진입점(pyproject: axdt = axdt.cli:main).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from axdt.infra import (
    config,
    container,
    cron,
    hub,
    leader,
    naming,
    tmux,
    workspace,
)
from axdt.infra.naming import NamingError
from axdt.progress import commit, lint, recover

__all__ = ["main", "build_parser"]


def _ident(value: str) -> naming.Identifier:
    return naming.parse(value)


# --- 핸들러 (각자 exit code 반환) ---

def _verify_naming(args, root) -> int:
    try:
        naming.validate(args.identifier)
    except NamingError as e:
        print(f"invalid: {e}", file=sys.stderr)
        return 1
    print(f"ok: {args.identifier}")
    return 0


def _leader_up(args, root) -> int:
    leader.up(root, _ident(args.identifier), base=args.base, tag=args.tag)
    return 0


def _leader_down(args, root) -> int:
    leader.down(root, _ident(args.identifier), force=args.force)
    return 0


def _workspace_create(args, root) -> int:
    workspace.provision(root, _ident(args.identifier), base=args.base, force=args.force)
    return 0


def _workspace_rm(args, root) -> int:
    workspace.teardown(root, _ident(args.identifier), force=args.force)
    return 0


def _container_build(args, root) -> int:
    container.build_image(root, args.tag)
    return 0


def _container_stop(args, root) -> int:
    container.stop(_ident(args.identifier))
    return 0


def _container_rm(args, root) -> int:
    container.rm(_ident(args.identifier))
    return 0


def _tmux_ensure(args, root) -> int:
    tmux.ensure_session()
    return 0


def _tmux_send(args, root) -> int:
    i = _ident(args.identifier)
    win = tmux.resolve_window(i)
    if win is None:
        print(f"윈도우 없음: {i.value}", file=sys.stderr)
        return 1
    text = args.text + ("\n" if args.submit else "")
    tmux.send_text(win, text)
    return 0


def _tmux_capture(args, root) -> int:
    log = config.capture_log(root, _ident(args.identifier))
    text, _ = tmux.read_increment(log, 0)
    print(text)
    return 0


def _hub_init(args, root) -> int:
    hub.init(root, seed_from=args.seed_from, empty=args.empty)
    return 0


def _hub_serve(args, root) -> int:
    hub.serve(root, transport=config.transport())
    return 0


def _hub_stop_daemon(args, root) -> int:
    hub.stop_daemon(root)
    return 0


def _cron_install(args, root) -> int:
    cron.install(args.every, args.cmd, cwd=args.cwd)
    return 0


def _cron_uninstall(args, root) -> int:
    cron.uninstall()
    return 0


def _progress_lint(args, root) -> int:
    findings = lint.lint(config.progress_path(root), config.report_dir(root))
    for f in findings:
        print(f"{f.severity} {f.code} {f.task}: {f.message}")
    return 1 if any(f.severity == "ERROR" for f in findings) else 0


def _progress_status(args, root) -> int:
    state = recover.reconstruct(config.progress_path(root), config.report_dir(root))
    print(recover.format_summary(state))
    return 0


def _progress_commit(args, root) -> int:
    reasons = {}
    for r in (args.reason or []):
        task, _, reason = r.partition("=")
        reasons[task] = reason
    gates = tuple(args.gate or ())

    try:
        if args.dry_run:
            plan = commit.plan_milestone(root, reasons, gates=gates)
            for e in plan.events:
                print(f"{e.task}: {e.before}->{e.after}")
            print(f"staged: {', '.join(plan.staged)}")
            print(plan.message)
        else:
            commit.milestone_commit(root, reasons, gates=gates)
    except commit.CommitRejected as e:
        print(f"거부: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="axdt")
    domains = p.add_subparsers(dest="domain", required=True)

    # verify-naming
    vn = domains.add_parser("verify-naming")
    vn.add_argument("identifier")
    vn.set_defaults(func=_verify_naming)

    # hub
    hp = domains.add_parser("hub").add_subparsers(dest="verb", required=True)
    hi = hp.add_parser("init")
    hi.add_argument("--seed-from", dest="seed_from", default=None)
    hi.add_argument("--empty", action="store_true")
    hi.set_defaults(func=_hub_init)
    hp.add_parser("serve").set_defaults(func=_hub_serve)
    hp.add_parser("stop-daemon").set_defaults(func=_hub_stop_daemon)

    # workspace
    wp = domains.add_parser("workspace").add_subparsers(dest="verb", required=True)
    wc = wp.add_parser("create")
    wc.add_argument("identifier")
    wc.add_argument("--base", default="main")
    wc.add_argument("--force", action="store_true")
    wc.set_defaults(func=_workspace_create)
    wr = wp.add_parser("rm")
    wr.add_argument("identifier")
    wr.add_argument("--force", action="store_true")
    wr.set_defaults(func=_workspace_rm)

    # container
    cp = domains.add_parser("container").add_subparsers(dest="verb", required=True)
    cb = cp.add_parser("build")
    cb.add_argument("--tag", default="dev")
    cb.set_defaults(func=_container_build)
    cs = cp.add_parser("stop")
    cs.add_argument("identifier")
    cs.set_defaults(func=_container_stop)
    cr = cp.add_parser("rm")
    cr.add_argument("identifier")
    cr.set_defaults(func=_container_rm)

    # tmux
    tp = domains.add_parser("tmux").add_subparsers(dest="verb", required=True)
    tp.add_parser("ensure").set_defaults(func=_tmux_ensure)
    ts = tp.add_parser("send")
    ts.add_argument("identifier")
    ts.add_argument("text")
    ts.add_argument("--submit", action="store_true")
    ts.set_defaults(func=_tmux_send)
    tc = tp.add_parser("capture")
    tc.add_argument("identifier")
    tc.set_defaults(func=_tmux_capture)

    # cron
    crp = domains.add_parser("cron").add_subparsers(dest="verb", required=True)
    ci = crp.add_parser("install")
    ci.add_argument("--every", type=int, required=True)
    ci.add_argument("--cmd", required=True)
    ci.add_argument("--cwd", default=None)
    ci.set_defaults(func=_cron_install)
    crp.add_parser("uninstall").set_defaults(func=_cron_uninstall)

    # progress
    pp = domains.add_parser("progress").add_subparsers(dest="verb", required=True)
    pp.add_parser("lint").set_defaults(func=_progress_lint)
    pp.add_parser("status").set_defaults(func=_progress_status)
    pc = pp.add_parser("commit")
    pc.add_argument("--reason", action="append")
    pc.add_argument("--gate", action="append")
    pc.add_argument("--dry-run", action="store_true")
    pc.set_defaults(func=_progress_commit)

    # leader
    lp = domains.add_parser("leader").add_subparsers(dest="verb", required=True)
    lu = lp.add_parser("up")
    lu.add_argument("identifier")
    lu.add_argument("--base", default="main")
    lu.add_argument("--tag", default="dev")
    lu.set_defaults(func=_leader_up)
    ld = lp.add_parser("down")
    ld.add_argument("identifier")
    ld.add_argument("--force", action="store_true")
    ld.set_defaults(func=_leader_down)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:  # argparse 인자 오류
        return int(e.code) if e.code is not None else 2
    root = Path(config.project_root())
    try:
        return args.func(args, root)
    except NamingError as e:
        print(f"invalid identifier: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
