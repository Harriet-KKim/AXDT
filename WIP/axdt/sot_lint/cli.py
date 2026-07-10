"""sot-lint CLI — `python -m axdt.sot_lint [경로] [--json]` (스펙 §6).

텍스트/JSON 출력과 종료코드를 담당한다. 검사 로직 자체는 parser·registry·checks에 있다.
`run()`이 공개 API(결과 객체 LintResult)이며 axdt.sot_lint가 그대로 재노출한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from axdt.sot_lint import checks, parser, registry
from axdt.sot_lint.checks import Violation
from axdt.sot_lint.parser import ParseError

__all__ = ["LintResult", "run", "build_parser", "main", "to_json"]

_SCHEMA_VERSION = 1
_DEFAULT_ROOT = "docs/sot"


@dataclass(frozen=True)
class LintResult:
    root: str
    files: int
    violations: list[Violation]
    errors: list[ParseError]

    @property
    def ok(self) -> bool:
        return not self.violations and not self.errors


def _violation_sort_key(v: Violation) -> tuple:
    # line=None이 항상 먼저 오도록 (line is not None)을 1차 정렬키로 끼워 넣는다.
    return (v.path, v.line is not None, v.line if v.line is not None else 0, v.code, v.message)


def _error_sort_key(e: ParseError) -> tuple:
    return (e.path, e.code, e.message)


def run(root: Path) -> LintResult:
    """root(기본 docs/sot/) 하위 SoT 트리에 C1~C6·참조 무결성 검사를 실행.

    같은 입력에는 항상 같은 출력(violations/errors 정렬 포함, 스펙 §7 결정성).
    """
    root = Path(root)
    documents, errors, errored_topics = parser.load_all(root)
    rule_ids = registry.collect_rule_ids(documents["rule"])
    violations = checks.run_checks(documents, root, rule_ids, errored_topics)
    # summary.files = 파싱을 시도한 전체 문서 수(4종 = req·spec·td·rule 포함, 성공+오류).
    # C1~C6 검사는 3종(req·spec·td)만 도는 것과 구분된다 — rule/은 id 레지스트리 수집용.
    files = sum(len(v) for v in documents.values()) + len(errors)
    return LintResult(
        root=root.as_posix(),
        files=files,
        violations=sorted(violations, key=_violation_sort_key),
        errors=sorted(errors, key=_error_sort_key),
    )


def to_json(result: LintResult) -> dict:
    by_code: dict[str, int] = {}
    for v in result.violations:
        by_code[v.code] = by_code.get(v.code, 0) + 1
    return {
        "schema_version": _SCHEMA_VERSION,
        "ok": result.ok,
        "violations": [
            {"path": v.path, "line": v.line, "code": v.code, "message": v.message}
            for v in result.violations
        ],
        "errors": [{"path": e.path, "code": e.code, "message": e.message} for e in result.errors],
        "summary": {
            "files": result.files,
            "violations": len(result.violations),
            "errors": len(result.errors),
            "by_code": dict(sorted(by_code.items())),
        },
    }


def _format_text(result: LintResult) -> str:
    lines: list[str] = []
    for v in result.violations:
        if v.line is None:
            lines.append(f"{v.path} · {v.code} · {v.message}")
        else:
            lines.append(f"{v.path}:{v.line} · {v.code} · {v.message}")
    for e in result.errors:
        lines.append(f"{e.path} · {e.code} · {e.message}")
    lines.append(
        f"--- files={result.files} violations={len(result.violations)} errors={len(result.errors)}"
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m axdt.sot_lint")
    p.add_argument("path", nargs="?", default=_DEFAULT_ROOT, help="검사 루트(기본 docs/sot/)")
    p.add_argument("--json", action="store_true", help="JSON 스키마로 출력")
    return p


def main(argv: list[str] | None = None) -> int:
    # Windows cp949 파이프 등에서 한글·· 같은 non-ASCII 출력이 UnicodeEncodeError로
    # 죽는 걸 막는다(Linux/UTF-8 환경에서는 무해한 재설정) — axdt.cli.main과 동일 패턴.
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass

    args = build_parser().parse_args(argv)
    result = run(Path(args.path))

    if args.json:
        print(json.dumps(to_json(result), ensure_ascii=False, indent=2))
    else:
        print(_format_text(result))

    if result.errors:
        return 2
    if result.violations:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
