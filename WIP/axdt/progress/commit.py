"""마일스톤 커밋 헬퍼 — progress.md 변경을 검증된 단일 커밋으로 묶는다.

마일스톤 커밋은 중간 전이를 건너뛴다(예: 빈 양식 -> accepted, todo -> rejected가
한 커밋에 접힘). 그래서 여기서는 ``schema.ALLOWED_TRANSITIONS``로 끝점 쌍을 재검사하지
않는다 — 몇 칸을 건너뛰어도 그 자체는 위반이 아니다.

이 모듈이 강제하는 건 "몇 칸을 건너뛰어도 불변인" 성질뿐이다(거부 4종 + §4.1 행-형식):

1. 종료 재개 — base가 이미 TERMINAL(accepted/superseded)인 task의 상태가 바뀜.
2. 행 삭제 — base에 있던 task가 new에서 사라짐.
3. 과claim — ``accepted``로 올라가는 task인데 그 커밋 트리(인덱스) 블롭 기준
   report가 done이 아니거나 id가 불일치.
4. 구조 오류 — 작업본 progress.md가 ``table.parse_progress``를 통과하지 못함, 또는
   (통과는 하되) §4.1 행-형식 lint ERROR(비통제 status·task id 형식·wave 접두
   불일치·updated 날짜 형식) — 단 이번 조작이 바꾼 행에 한해 스코핑(§2.5). 중복
   task id(``dup-task``)는 스코핑과 무관하게 무조건 거부(progress.md 자체의
   무결성 위반). §4.2 report 문제(누락·frontmatter·id불일치)·§4.3 정합 매트릭스는
   여기서 거부하지 않는다(Leader 소유 또는 이미 과claim이 처리 — 경고+라우팅).

수용(accept/reject) 판단이나 progress.md 편집, push는 이 모듈의 몫이 아니다.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from axdt.infra import config, proc
from axdt.progress import lint, schema, table

__all__ = [
    "ProgressEvent",
    "CommitRejected",
    "MilestonePlan",
    "diff_progress",
    "format_milestone_message",
    "milestone_commit",
    "plan_milestone",
]


@dataclass
class ProgressEvent:
    task: str
    before: str | None  # None -> 신규 행
    after: str
    kind: str  # "new"(before=None) | "transition"


class CommitRejected(Exception):
    """거부 4종(종료 재개·행 삭제·과claim·구조 오류) 위반 시 발생. 커밋되지 않는다."""


@dataclass
class MilestonePlan:
    events: list[ProgressEvent]
    staged: list[str]  # 스테이징될 repo-상대 posix 경로들(progress.md + 존재하는 event report + extra_paths)
    message: str


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
    missing = [t for t in rejected_tasks if not rejection_reasons.get(t, "").strip()]
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


# §4.1 행-형식 lint ERROR 중 "스테이징 불필요 거부" 단계에서 스코핑해 반영할 코드.
_SCOPED_ROW_LINT_CODES = frozenset({"bad-status", "bad-task-id", "wave-mismatch", "bad-updated"})


def _lint_scoped_violations(prog: Path, rdir: Path, changed: set[str]) -> list[str]:
    """§4.1 행-형식 lint ERROR를 이번 조작의 거부 사유로 변환(스코핑 적용).

    - ``dup-task``: 무조건 위반(중복은 progress.md 자체의 무결성 위반이라 스코핑 무관).
    - ``bad-status``/``bad-task-id``/``wave-mismatch``/``bad-updated``: 이번 조작이
      바꾼 task(``changed``)에 한해서만 위반.
    - 그 외 코드(``report-frontmatter``/``report-id-mismatch``/``report-status``/
      ``orphan-report``/``pair``/``table-structure``)는 여기서 다루지 않는다 — §4.2
      report 문제는 Leader 소유(경고+라우팅, 거부 아님), §4.3 pair는 over-claim이
      이미 accepted 열을 처리하고 나머지는 WARN, table-structure는 이미 parse
      단계(``table.ProgressFormatError``)에서 걸린다.
    """
    violations: list[str] = []
    for f in lint.lint(prog, rdir):
        if f.severity != "ERROR":
            continue
        if f.code == "dup-task":
            violations.append(f"lint-dup-task: {f.task}: {f.message}")
        elif f.code in _SCOPED_ROW_LINT_CODES and f.task in changed:
            violations.append(f"lint-{f.code}: {f.task}: {f.message}")
    return violations


def plan_milestone(
    repo: Path,
    rejection_reasons: dict[str, str] | None = None,
    extra_paths: tuple[Path, ...] = (),
    gates: tuple[str, ...] = (),
) -> MilestonePlan:
    """git 인덱스를 건드리지 않고(git add/commit 없이) "무엇이 커밋될지" 미리 계산한다.

    milestone_commit과 동일한 base 로드·diff·경로계산 규칙을 쓰되, 스테이징이
    선행돼야 판정 가능한 거부(3. 과claim)는 여기서 검사하지 않는다 — dry-run은
    미리보기일 뿐, 실제 스테이징·커밋 시점 검사(milestone_commit)를 대체하지 않는다.
    스테이징 불필요한 거부(1. 종료 재개, 2. 행 삭제, 4. 구조 오류)는 그대로 적용한다.
    """
    if rejection_reasons is None:
        rejection_reasons = {}

    repo = Path(repo)
    prog = config.progress_path(repo)
    rdir = config.report_dir(repo)
    rel_prog = _rel(prog, repo)

    # --- base 로드: HEAD의 progress.md. 없으면(최초 커밋 등) 빈 테이블. ---
    show = proc.run(["git", "show", f"HEAD:{rel_prog}"], cwd=repo, check=False, text=False)
    base = table.parse_progress(_decode(show.stdout)) if show.returncode == 0 else []

    # --- new 로드: 작업본 progress.md. 구조 오류 -> 거부(4). ---
    new_text = prog.read_text(encoding="utf-8")
    try:
        new = table.parse_progress(new_text)
    except table.ProgressFormatError as exc:
        raise CommitRejected(f"progress.md 구조 오류: {exc}") from exc

    # --- diff ---
    events = diff_progress(base, new)

    # --- 거부(1) 종료 재개, (2) 행 삭제 — 스테이징 없이도 판정 가능. ---
    base_by_task = {row.task: row for row in base}
    new_tasks = {row.task for row in new}

    violations: list[str] = []
    for event in events:
        if event.kind == "transition" and event.before in schema.TERMINAL:
            violations.append(f"terminal-resumed: {event.task} ({event.before} -> {event.after})")

    for task in sorted(set(base_by_task) - new_tasks):
        violations.append(f"row-deleted: {task}")

    # --- 거부(4') §4.1 행-형식 lint ERROR(스코핑) — 이번 조작이 바꾼 행만. ---
    changed = {event.task for event in events}
    violations.extend(_lint_scoped_violations(prog, rdir, changed))

    if violations:
        raise CommitRejected("; ".join(violations))

    # --- 스테이징될 경로 목록 계산(실제 git add는 하지 않는다). ---
    staged_paths: list[Path] = [prog]
    for event in events:
        report_path = rdir / f"{event.task}.md"
        if report_path.exists():
            staged_paths.append(report_path)
    staged_paths.extend(Path(p) for p in extra_paths)

    # 순서 보존 중복 제거.
    rel_staged = list(dict.fromkeys(_rel(p, repo) for p in staged_paths))

    # --- 메시지 생성. rejected인데 사유 없으면 ValueError(스테이징한 게 없으니 되돌릴 것도 없다). ---
    message = format_milestone_message(events, rejection_reasons, gates)

    return MilestonePlan(events=events, staged=rel_staged, message=message)


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

    # --- 5b. 거부(4') §4.1 행-형식 lint ERROR(스코핑) — 이번 조작이 바꾼 행만. ---
    changed = {event.task for event in events}
    violations.extend(_lint_scoped_violations(prog, rdir, changed))

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

    # --- 9. 커밋. 자유 -m이 아니라 생성 메시지를 파일로 넘긴다(git commit -F).
    #     우리 경로(rel_staged: progress.md + 관련 report + extra_paths)만 커밋한다 --
    #     호출자가 미리 스테이징해 둔 무관 파일이 이 마일스톤 커밋에 함께 쓸리지
    #     않도록 pathspec으로 한정한다(over-claim이 인덱스 블롭을 읽는 순서·로직은
    #     이미 위에서 끝났으므로 여기서는 건드리지 않는다).
    diff_check = proc.run(
        ["git", "diff", "--cached", "--quiet", "--", *rel_staged], cwd=repo, check=False
    )
    allow_empty = diff_check.returncode == 0  # 우리 경로에 스테이징된 변화가 없음(게이트 전용 등).

    fd, tmp_msg_path = tempfile.mkstemp(prefix="axdt-milestone-commit-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(message)
        if allow_empty:
            # 우리 경로에 변화가 없음(게이트 전용 커밋 등) -- pathspec 없이 기존 동작
            # 그대로 유지.
            commit_argv = ["git", "commit", "-F", tmp_msg_path, "--allow-empty"]
        else:
            # 우리 경로에 실제 변화 있음 -- pathspec으로 한정해 무관 스테이징 파일을
            # 이 커밋에서 배제한다.
            commit_argv = ["git", "commit", "-F", tmp_msg_path, "--", *rel_staged]
        # text=False: 성공 시 git이 커밋 메시지(비-ASCII 포함)를 stdout에 echo하는데,
        # 이 출력을 쓰지 않으므로 OS 로캘 디코드 문제를 아예 피한다.
        proc.run(commit_argv, cwd=repo, text=False)
    finally:
        os.remove(tmp_msg_path)
