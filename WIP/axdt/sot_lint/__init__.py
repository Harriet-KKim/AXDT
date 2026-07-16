"""sot-lint — SoT 완료 판정 ① 형식(기계 검증) 검사기.

`docs/sot/rule/sot-readiness.md`의 "① 형식"을 그대로 구현하는 결정적 검사기다.
requirements·specification·test-design에 대해 C1~C6(존재/항목ID·유일성·본문일치/
참조무결성/플레이스홀더/금지어/수용기준)을 검사한다. rule/은 id 레지스트리
수집에만 쓰인다(검사 대상 아님).

공개 API: run(root) -> LintResult, main(argv) -> int(cli 재노출).
"""
from __future__ import annotations

from axdt.sot_lint.checks import Violation
from axdt.sot_lint.cli import LintResult, main, run
from axdt.sot_lint.parser import ParseError

__all__ = ["run", "LintResult", "Violation", "ParseError", "main"]
