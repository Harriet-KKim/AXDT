"""허브 pre-receive 판정 로직 — 수신 ref allowlist + 콘텐츠·경로 게이트(`ADR-0007` (a)+(b)).

`hub.install_gate`가 심는 얇은 sh 껍데기가 ``python -m axdt.infra.hubgate <허브 repo>``로
이 모듈을 부른다. stdin으로 pre-receive 표준 입력(``<old> <new> <ref>`` 줄들)을 받아
각 갱신을 판정하고, 하나라도 위반이면 exit 1(비영 → git이 push 전체를 거부), 전부
통과면 exit 0. 거부 사유는 **ASCII 전용** stderr(무인증 wire로 임의 로캘 클라이언트
터미널에 전달 — 현행 훅 규칙 계승).

- **(a) 수신 ref allowlist(이식)**: ``new``가 zero-SHA(삭제)면 거부, ``ref``가
  ``refs/heads/w<n>.t<n>-<slug>`` 정규식(``ALLOWED_REF_RE``) 불일치면 거부.
- **(b) 콘텐츠·경로 게이트**: (a)를 통과한 task 브랜치 push라도 변경 경로가 보호 경로를
  건드리면 거부한다. 정책은 신뢰 ref(**항상 ``main`` 버전**)의
  ``docs/sot/rule/protected-paths.md`` 안 ` ```axdt-protected-paths ` 코드펜스에서 읽는다
  (`ADR-0007` 대안 D — 후보 브랜치가 검사 규칙을 무력화하지 못하게). 정책 부재(main/
  파일/블록 없음)는 (a)-only 전환기로 (b)를 skip하고, main·파일이 존재하는데 읽기가
  실패하거나 블록이 있는데 파싱·merge-base·diff 조회가 실패하면 fail-closed(거부)한다.
"""
from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from . import naming, proc

__all__ = [
    "ALLOWED_REF_RE",
    "ZERO_SHA",
    "PolicyParseError",
    "PolicyUnavailableError",
    "Rule",
    "Policy",
    "parse_policy",
    "match_glob",
    "is_path_denied",
    "check_ref_allowlist",
    "check_update",
    "main",
]

# (a) task 브랜치 형식만 허용. 정규식 정본은 naming.IDENTIFIER_PATTERN(rule-branch-workspace-naming).
# 손사본을 두지 않고 여기서 refs/heads/ 접두를 붙여 파생한다(shared-contract-single-source).
ALLOWED_REF_RE = re.compile(r"^refs/heads/" + naming.IDENTIFIER_PATTERN + r"$")
ZERO_SHA = "0" * 40

_REF_HEADS_PREFIX = "refs/heads/"

# (b) 정책 소스: 항상 신뢰 ref(main)의 tip에서 읽는다(merge-base 커밋이 아님 — ADR-0007
# 대안 D, 후보가 옛 커밋을 분기점으로 골라 정책을 무력화하는 우회를 막는다).
# 완전지정(refs/heads/main): 짧은 "main"은 gitrevisions 우선순위상 refs/tags/main을
# 먼저 잡을 수 있다(ADR-0007:29,63 — 정책은 신뢰 ref main tip에서만 읽어야 함, F3).
_POLICY_REF = "refs/heads/main"
_POLICY_PATH = "docs/sot/rule/protected-paths.md"
_FENCE_INFO = "axdt-protected-paths"

_CLOSE_FENCE_RE = re.compile(r"^```\s*$", re.MULTILINE)
_RULE_LINE_RE = re.compile(r"^(deny|report-owns)\s+(\S+)\s*$")


class PolicyParseError(ValueError):
    """정책 블록 파싱 실패(형식 위반·미지 지시어) — 호출자는 fail-closed로 취급해야 한다."""


class PolicyUnavailableError(RuntimeError):
    """정책 파일/블록은 존재하는데 읽기가 실패(객체 손상 등) — fail-closed 신호(spec:216)."""


@dataclass(frozen=True)
class Rule:
    """정책 블록의 규칙 한 줄. ``kind``는 ``"deny"`` 또는 ``"report-owns"``."""

    kind: str
    arg: str


@dataclass(frozen=True)
class Policy:
    rules: list[Rule] = field(default_factory=list)


# --- 정책 블록 파싱(spec:220) ---


def _extract_fenced_block(text: str, info_string: str) -> str | None:
    """코드펜스 정보문자열(예: ``axdt-protected-paths``)로 블록 본문을 선택한다.

    같은 파일의 다른 정보문자열 블록(예: ``axdt-critical-paths``)이나 코드펜스 밖
    본문은 절대 선택되지 않는다 — 여는 펜스 줄 자체가 ``info_string``과 정확히
    일치해야 매치한다. 여는 펜스가 없으면 None. 여는 펜스는 있는데 닫는 펜스가
    없으면(미종결) 형식 오류로 :class:`PolicyParseError`.
    """
    m = re.compile(r"^```" + re.escape(info_string) + r"\s*$", re.MULTILINE).search(text)
    if m is None:
        return None
    start = m.end()
    m2 = _CLOSE_FENCE_RE.search(text, start)
    if m2 is None:
        raise PolicyParseError(f"unterminated fenced block: {info_string!r}")
    return text[start : m2.start()]


def parse_policy(text: str) -> Policy | None:
    """``protected-paths.md`` 전체 텍스트에서 ``axdt-protected-paths`` 블록을 파싱한다.

    블록 자체가 없으면 None(호출자는 (b)를 skip — (a)-only 전환기, spec:221).
    블록은 있는데 파싱 오류(형식 위반·미지 지시어)면 :class:`PolicyParseError`
    (호출자는 fail-closed로 거부, spec:216).
    """
    block = _extract_fenced_block(text, _FENCE_INFO)
    if block is None:
        return None
    rules: list[Rule] = []
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = _RULE_LINE_RE.match(line)
        if m is None:
            raise PolicyParseError(f"malformed policy line: {raw_line!r}")
        rules.append(Rule(kind=m.group(1), arg=m.group(2)))
    return Policy(rules=rules)


# --- glob 문법(spec:218, 정본=SoT 블록 헤더) ---
# `**` = 구분자(`/`) 포함 0개 이상 세그먼트. `*` = 한 세그먼트 내 0개 이상 문자(구분자 제외).
# fnmatch는 쓰지 않는다(그 `*`가 `/`도 삼켜 report-owns 하위 디렉터리 경계를 못 지킨다).


def _translate_literal_segment(segment: str) -> str:
    """`/`가 없는 한 세그먼트를 정규식으로: `*` -> `[^/]*`, 그 외는 escape."""
    out: list[str] = []
    for ch in segment:
        out.append("[^/]*" if ch == "*" else re.escape(ch))
    return "".join(out)


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """SoT glob 패턴을 정규식으로 컴파일(전체일치 전제, 호출자는 ``fullmatch`` 사용).

    F7: 안전은 호출자의 ``fullmatch``에 전적으로 의존한다 — 이 함수가 만드는 정규식은
    부분매칭(``.search``/``.match``)에 쓰면 의도치 않은 부분 문자열 매칭으로 정책을
    무력화할 수 있다. 모듈 접근은 유지하되(테스트·내부용) 오용 방지를 위해
    ``__all__``에는 올리지 않는다 — 공개 API는 :func:`match_glob`.
    """
    segments = pattern.split("/")
    n = len(segments)
    pieces: list[str] = []
    for i, seg in enumerate(segments):
        if seg == "**":
            is_first = i == 0
            is_last = i == n - 1
            if is_first and is_last:
                # 패턴 전체가 "**" 하나뿐: 무엇이든(빈 문자열·개행 포함) 매칭.
                # `.*`는 개행을 빠뜨려(DOTALL 아님) 개행 포함 경로(diff -z가 raw
                # 전달)가 bare `deny **`를 비껴간다 → `[\s\S]*`로 개행까지 포함.
                pieces.append("[\\s\\S]*")
            elif is_first:
                # 선행 "**": 뒤에 오는 리터럴 세그먼트 앞에 0개 이상 "seg/" 반복.
                pieces.append("(?:[^/]+/)*")
            elif is_last:
                # 후행 "**": 앞 리터럴에 0개 이상 "/seg" 반복(각 반복이 자기 구분자를 포함).
                pieces.append("(?:/[^/]+)*")
            else:
                # 중간 "**": 앞 리터럴과의 경계 슬래시를 이 조각이 직접 소유해야
                # 0-세그먼트일 때 양쪽 슬래시가 하나로 합쳐진다(경계 사례의 핵심).
                pieces.append("/(?:[^/]+/)*")
        else:
            frag = _translate_literal_segment(seg)
            if i == 0:
                pieces.append(frag)
            elif segments[i - 1] == "**":
                # 직전이 "**" 조각이면 그 조각이 이미 경계 슬래시를 스스로 공급했다.
                pieces.append(frag)
            else:
                pieces.append("/" + frag)
    return re.compile("".join(pieces))


def match_glob(pattern: str, path: str) -> bool:
    return glob_to_regex(pattern).fullmatch(path) is not None


# --- 규칙 평가(spec:217, 논리곱·deny 우선) ---


def is_path_denied(path: str, policy: Policy, identifier: str) -> bool:
    """한 변경 경로가 정책상 거부되는지. deny가 최우선, 그다음 report-owns 경계.

    ``identifier``는 push ref의 전체 task 식별자(``w<n>.t<n>-<slug>``, slug 포함) —
    report-owns가 그 식별자와 정확히 일치하는 파일명만 허용한다(타 task report 위조 차단,
    ref 위장 자체는 하드닝 연기 대상).
    """
    for rule in policy.rules:
        if rule.kind == "deny" and match_glob(rule.arg, path):
            return True
    for rule in policy.rules:
        if rule.kind == "report-owns":
            dir_ = rule.arg.rstrip("/")
            prefix = dir_ + "/"
            # <dir> 자체 경로(디렉터리가 파일로 대체되는 변경)도 거부한다(spec:217
            # "<dir> 아래 변경은 <dir>/w<n>.t<n>-<slug>.md만 허용" — F5).
            if path == dir_ or path.startswith(prefix):
                expected = f"{dir_}/{identifier}.md"
                if path != expected:
                    return True
    return False


# --- (a) 수신 ref allowlist(spec:213) ---


def _is_zero_sha(value: str) -> bool:
    """삭제(zero-SHA) 판정을 해시 길이와 무관하게(F6: SHA-256 저장소는 64-제로)."""
    return bool(value) and set(value) == {"0"}


def check_ref_allowlist(new: str, ref: str) -> str | None:
    """(a) 판정. 문제 없으면 None, 위반이면 ASCII 거부 사유."""
    if _is_zero_sha(new):
        return f"ref deletion rejected ({ref})"
    if ALLOWED_REF_RE.match(ref) is None:
        return f"ref rejected - not in task-branch allowlist ({ref})"
    return None


def _identifier_from_ref(ref: str) -> str:
    # (a)를 통과한 ref만 여기 도달하므로 refs/heads/ 접두는 항상 있다.
    return ref[len(_REF_HEADS_PREFIX) :]


# --- (b) git 조회 헬퍼 ---


def _read_policy_text(repo: Path) -> str | None:
    """정책 텍스트를 신뢰 ref(refs/heads/main) tip에서 읽는다.

    부재(main 없음·정책 파일 없음)는 None(전환기 skip, spec:221).
    조회/읽기 오류(repo·ref 이상, blob 존재하나 show 실패)는 PolicyUnavailableError
    (fail-closed, spec:216). 부재와 오류는 git exit code로 구분한다 — show-ref는
    부재 시 rc=1(그 외 비영은 오류), ls-tree는 부재 시 rc=0+빈출력(비영은 오류).
    """
    # 1. main ref 존재: rc0 존재 / rc1 부재(skip) / 그 외 오류(fail-closed).
    r = proc.run(
        ["git", "-C", str(repo), "show-ref", "--verify", "--quiet", _POLICY_REF],
        check=False,
    )
    if r.returncode == 1:
        return None
    if r.returncode != 0:
        raise PolicyUnavailableError(f"show-ref failed for {_POLICY_REF} (rc={r.returncode})")
    # 2. 정책 blob 존재: ls-tree로 부재(rc0·빈출력)와 오류(rc≠0)를 구분(cat-file -e는
    #    파일 부재도 손상도 rc≠0이라 구분 불가 → ls-tree 채택).
    r = proc.run(
        ["git", "-C", str(repo), "ls-tree", _POLICY_REF, "--", _POLICY_PATH],
        check=False,
    )
    if r.returncode != 0:
        raise PolicyUnavailableError(
            f"ls-tree failed for {_POLICY_REF}:{_POLICY_PATH} (rc={r.returncode})"
        )
    if not r.stdout.strip():
        return None
    # 3. 내용 읽기: 존재 확인됐으므로 실패는 fail-closed.
    r = proc.run(
        ["git", "-C", str(repo), "show", f"{_POLICY_REF}:{_POLICY_PATH}"], check=False
    )
    if r.returncode != 0:
        raise PolicyUnavailableError(
            f"git show failed for {_POLICY_REF}:{_POLICY_PATH} (rc={r.returncode})"
        )
    return r.stdout


def _merge_base(repo: Path, new: str) -> str | None:
    """``git merge-base refs/heads/main <new>``. 공통 조상 없으면(실패) None."""
    r = proc.run(
        ["git", "-C", str(repo), "merge-base", _POLICY_REF, new], check=False
    )
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def _changed_paths(repo: Path, base: str, new: str) -> list[str] | None:
    """``git diff -z --name-only <base> <new>``(NUL 구분). 실패면 None(fail-closed)."""
    r = proc.run(
        ["git", "-C", str(repo), "diff", "-z", "--name-only", base, new], check=False
    )
    if r.returncode != 0:
        return None
    return [p for p in r.stdout.split("\0") if p]


# --- 갱신 하나 판정(오케스트레이션, spec:212-221 판정순서) ---


def check_update(repo: Path, old: str, new: str, ref: str) -> str | None:
    """(a)+(b)를 순서대로 판정. 통과면 None, 위반이면 ASCII 거부 사유."""
    reason = check_ref_allowlist(new, ref)
    if reason is not None:
        return reason

    try:
        policy_text = _read_policy_text(repo)
    except PolicyUnavailableError as exc:
        return f"protected-paths policy read failed, fail-closed: {exc}"
    if policy_text is None:
        return None  # 정책 파일/main 부재 → (a)-only 전환기, (b) skip(spec:221)

    try:
        policy = parse_policy(policy_text)
    except PolicyParseError as exc:
        return f"protected-paths policy parse error, fail-closed: {exc}"

    if policy is None:
        return None  # 블록 없음 → (b) skip(spec:221)

    base = _merge_base(repo, new)
    if base is None:
        return f"no merge base with main, fail-closed ({ref})"

    changed = _changed_paths(repo, base, new)
    if changed is None:
        return f"failed to collect changed paths, fail-closed ({ref})"

    identifier = _identifier_from_ref(ref)
    for path in changed:
        if is_path_denied(path, policy, identifier):
            return f"push denied: protected path changed ({path})"
    return None


# --- 엔트리(``python -m axdt.infra.hubgate <repo>``) ---


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m axdt.infra.hubgate <repo>", file=sys.stderr)
        return 1
    repo = Path(args[0])

    ok = True
    for raw_line in sys.stdin:
        line = raw_line.rstrip("\r\n")
        if not line.strip():
            continue
        parts = line.split(" ", 2)
        if len(parts) != 3:
            # F8: 견고성 — 형식 위반 줄도 traceback 없이 ASCII 사유로 거부한다.
            print("AXDT hub: malformed pre-receive line", file=sys.stderr)
            ok = False
            continue
        old, new, ref = parts
        reason = check_update(repo, old, new, ref)
        if reason is not None:
            # ASCII 전용 stderr(spec:212) — reason엔 (a) ref나 (b) 경로가 그대로
            # 삽입돼 비ASCII일 수 있다. 유출 경계는 여기(단일 choke point)뿐이고,
            # check_update가 반환하는 reason 문자열 자체는 그대로 둔다.
            safe = reason.encode("ascii", "backslashreplace").decode("ascii")
            # R3-2: backslashreplace는 비ASCII만 escape한다 — ASCII 제어문자(개행 등)는
            # 그대로 통과해, 개행 포함 경로(diff -z가 raw 전달)가 가짜 "AXDT hub: ..."
            # 줄을 stderr에 위조할 수 있다. backslashreplace가 만든 `\xNN`은 출력 가능
            # 문자뿐이라 이 2차 치환이 그걸 다시 건드리지 않는다.
            safe = re.sub(r"[\x00-\x1f\x7f]", lambda m: "\\x%02x" % ord(m.group(0)), safe)
            print(f"AXDT hub: {safe}", file=sys.stderr)
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
