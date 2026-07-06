"""마일스톤 커밋 헬퍼 — progress.md 변경을 검증된 단일 커밋으로 묶는다.

마일스톤 커밋은 중간 전이를 건너뛴다(예: 빈 양식 -> accepted, todo -> rejected가
한 커밋에 접힘). 그래서 여기서는 ``schema.ALLOWED_TRANSITIONS``로 끝점 쌍을 재검사하지
않는다 — 몇 칸을 건너뛰어도 그 자체는 위반이 아니다.

이 모듈이 강제하는 건 "몇 칸을 건너뛰어도 불변인" 성질뿐이다(거부 4종):

1. 종료 재개 — base가 이미 TERMINAL(accepted/superseded)인 task의 상태가 바뀜.
2. 행 삭제 — base에 있던 task가 new에서 사라짐.
3. 과claim — ``accepted``로 올라가는 task인데 그 커밋 트리(인덱스) 블롭 기준
   report가 done이 아니거나 id가 불일치.
4. 구조 오류 — 작업본 progress.md가 ``table.parse_progress``를 통과하지 못함.

수용(accept/reject) 판단이나 progress.md 편집, push는 이 모듈의 몫이 아니다.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from axdt.infra import config, proc
from axdt.progress import schema, table

__all__ = [
    "ProgressEvent",
    "CommitRejected",
    "diff_progress",
    "format_milestone_message",
    "milestone_commit",
]


@dataclass
class ProgressEvent:
    task: str
    before: str | None  # None -> 신규 행
    after: str
    kind: str  # "new"(before=None) | "transition"


class CommitRejected(Exception):
    """거부 4종(종료 재개·행 삭제·과claim·구조 오류) 위반 시 발생. 커밋되지 않는다."""


def diff_progress(base: list[table.TaskRow], new: list[table.TaskRow]) -> list[ProgressEvent]:
    """task id로 매칭해 base->new 변화를 이벤트로 뽑는다.

    - new에만 있는 task -> kind="new"(임의 상태 허용, 여기선 검사하지 않는다).
    - 둘 다 있고 status가 다르면 -> kind="transition".
    - status가 같으면 이벤트 없음.
    - 행 삭제(base에만 있음)는 여기서 표현하지 않는다(after가 str이라 표현 불가) —
      milestone_commit이 집합 비교로 별도 처리한다.
    """
    base_by_task = {row.task: row for row in base}
    events: list[ProgressEvent] = []
    for row in new:
        prior = base_by_task.get(row.task)
        if prior is None:
            events.append(ProgressEvent(task=row.task, before=None, after=row.status, kind="new"))
        elif prior.status != row.status:
            events.append(
                ProgressEvent(task=row.task, before=prior.status, after=row.status, kind="transition")
            )
    return events


def _before_repr(before: str | None) -> str:
    return "∅" if before is None else before  # ∅


def format_milestone_message(
    events: list[ProgressEvent],
    rejection_reasons: dict[str, str] | None = None,
    gates: tuple[str, ...] = (),
) -> str:
    """이벤트/게이트로부터 파싱 가능한(구조적) 커밋 메시지를 만든다. 자유 텍스트가 아니다."""
    if rejection_reasons is None:
        rejection_reasons = {}

    rejected_tasks = [e.task for e in events if e.after == "rejected"]
    missing = [t for t in rejected_tasks if t not in rejection_reasons]
    if missing:
        raise ValueError(f"rejection_reasons missing reason for rejected task(s): {missing!r}")

    if not events and not gates:
        raise ValueError("nothing to commit: no progress events and no gates")

    body_sections: list[str] = []

    if not events:
        # 상태 무변경 게이트 통과만 있는 커밋.
        subject = f"chore(progress): gate {gates[0]}" if len(gates) == 1 else f"chore(progress): {len(gates)} gates"
        body_sections.append("\n".join(["Gates:"] + [f"- {g}" for g in gates]))
    else:
        if len(events) == 1:
            e = events[0]
            subject = f"chore(progress): {e.task} {_before_repr(e.before)}->{e.after}"
        else:
            subject = f"chore(progress): batch {len(events)} events"
            lines = ["Events:"]
            for e in events:
                lines.append(f"- {e.task}: {_before_repr(e.before)} -> {e.after}")
            body_sections.append("\n".join(lines))

        if rejected_tasks:
            reason_lines = [f"Reason: {t} {rejection_reasons[t]}" for t in rejected_tasks]
            body_sections.append("\n".join(reason_lines))

        if gates:
            body_sections.append("\n".join(["Gates:"] + [f"- {g}" for g in gates]))

    if not body_sections:
        return subject
    return subject + "\n\n" + "\n\n".join(body_sections)


def _rel(path: Path, repo: Path) -> str:
    return Path(path).relative_to(repo).as_posix()


def _decode(output: str | bytes) -> str:
    """proc.run(text=False) 출력 정규화.

    proc.ProcResult는 내부에서 ``completed.stdout or ""``로 빈 출력을 만들기 때문에,
    ``text=False``로 호출해도 출력이 비어 있으면 ``bytes``가 아니라 ``str`` "" 로 온다.
    비어 있지 않으면 ``bytes``. 두 경우 모두 UTF-8 텍스트로 정규화한다.
    """
    return output if isinstance(output, str) else output.decode("utf-8")


def milestone_commit(
    repo: Path,
    rejection_reasons: dict[str, str] | None = None,
    extra_paths: tuple[Path, ...] = (),
    gates: tuple[str, ...] = (),
) -> None:
    """progress.md 마일스톤 변화를 검증 후 단일 커밋으로 묶는다.

    push하지 않는다, progress.md를 편집하지 않는다, 수용(accept/reject) 판단을
    하지 않는다 — 그 판단은 호출자가 이미 작업본 progress.md에 반영해 뒀다고 가정한다.
    """
    if rejection_reasons is None:
        rejection_reasons = {}

    repo = Path(repo)
    prog = config.progress_path(repo)
    rdir = config.report_dir(repo)
    rel_prog = _rel(prog, repo)

    # --- 2. base 로드: HEAD의 progress.md. 없으면(최초 커밋 등) 빈 테이블. ---
    # text=False + 수동 UTF-8 디코드: subprocess의 기본 text=True 디코드는 OS 로캘
    # (예: 한글 Windows의 cp949)을 쓰는데, git 블롭은 UTF-8이라 non-ASCII에서 깨진다.
    show = proc.run(["git", "show", f"HEAD:{rel_prog}"], cwd=repo, check=False, text=False)
    base = table.parse_progress(_decode(show.stdout)) if show.returncode == 0 else []

    # --- 3. new 로드: 작업본 progress.md. 구조 오류 -> 거부(4). ---
    new_text = prog.read_text(encoding="utf-8")
    try:
        new = table.parse_progress(new_text)
    except table.ProgressFormatError as exc:
        raise CommitRejected(f"progress.md 구조 오류: {exc}") from exc

    # --- 4. diff ---
    events = diff_progress(base, new)

    # --- 5a. 거부(1) 종료 재개, (2) 행 삭제 — 스테이징 없이도 판정 가능. ---
    base_by_task = {row.task: row for row in base}
    new_tasks = {row.task for row in new}

    violations: list[str] = []
    for event in events:
        if event.kind == "transition" and event.before in schema.TERMINAL:
            violations.append(f"terminal-resumed: {event.task} ({event.before} -> {event.after})")

    for task in sorted(set(base_by_task) - new_tasks):
        violations.append(f"row-deleted: {task}")

    if violations:
        raise CommitRejected("; ".join(violations))

    # --- 6. 스테이징(과claim 판정을 위해 먼저 인덱스에 반영). ---
    staged_paths: list[Path] = [prog]
    for event in events:
        report_path = rdir / f"{event.task}.md"
        if report_path.exists():
            staged_paths.append(report_path)
    staged_paths.extend(Path(p) for p in extra_paths)

    # 순서 보존 중복 제거.
    rel_staged = list(dict.fromkeys(_rel(p, repo) for p in staged_paths))
    proc.run(["git", "add", "--", *rel_staged], cwd=repo)

    def _unstage() -> None:
        proc.run(["git", "reset", "-q", "--", *rel_staged], cwd=repo)

    # --- 7. 거부(3) 과claim: accepted로 올라가는 task마다 커밋 트리(인덱스) 블롭 확인. ---
    rel_rdir = _rel(rdir, repo)
    overclaim: list[str] = []
    for event in events:
        if event.after != "accepted":
            continue
        rel_report = f"{rel_rdir}/{event.task}.md"
        blob = proc.run(["git", "show", f":{rel_report}"], cwd=repo, check=False, text=False)
        if blob.returncode != 0:
            overclaim.append(f"unverified(report missing): {event.task}")
            continue
        try:
            report = table.parse_report(_decode(blob.stdout))
        except table.ReportFormatError:
            overclaim.append(f"unverified(report malformed): {event.task}")
            continue
        if report.id != event.task or report.status != "done":
            overclaim.append(f"overclaim: {event.task} (report.status={report.status!r})")

    if overclaim:
        _unstage()
        raise CommitRejected("; ".join(overclaim))

    # --- 8. 메시지 생성. rejected인데 사유 없으면 ValueError(스테이징 되돌리고 전파). ---
    try:
        message = format_milestone_message(events, rejection_reasons, gates)
    except ValueError:
        _unstage()
        raise

    # --- 9. 커밋. 자유 -m이 아니라 생성 메시지를 파일로 넘긴다(git commit -F). ---
    diff_check = proc.run(["git", "diff", "--cached", "--quiet"], cwd=repo, check=False)
    allow_empty = diff_check.returncode == 0  # 스테이징할 변화가 없음(게이트 전용 커밋 등).

    fd, tmp_msg_path = tempfile.mkstemp(prefix="axdt-milestone-commit-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(message)
        commit_argv = ["git", "commit", "-F", tmp_msg_path]
        if allow_empty:
            commit_argv.append("--allow-empty")
        # text=False: 성공 시 git이 커밋 메시지(비-ASCII 포함)를 stdout에 echo하는데,
        # 이 출력을 쓰지 않으므로 OS 로캘 디코드 문제를 아예 피한다.
        proc.run(commit_argv, cwd=repo, text=False)
    finally:
        os.remove(tmp_msg_path)
