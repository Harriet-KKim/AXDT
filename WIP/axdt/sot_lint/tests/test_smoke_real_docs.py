"""★ 스모크 — 저장소 실제 docs/sot/를 검사: errors=0, _TEMPLATE.md 전역 제외로 C4 안 터짐.

C1(항목 선언 문서 없음)은 현재 실제로 위반날 수 있다(실 콘텐츠 문서가 아직 없고
템플릿뿐이므로) — 이는 정상이며 이 테스트가 보는 범위가 아니다.
"""
from __future__ import annotations

from pathlib import Path

from axdt.sot_lint import cli

# 이 파일: <repo>/WIP/axdt/sot_lint/tests/test_smoke_real_docs.py
# parents[0]=tests [1]=sot_lint [2]=axdt [3]=WIP [4]=<repo root>
_REPO_ROOT = Path(__file__).resolve().parents[4]


def test_real_sot_tree_has_no_execution_errors_and_templates_are_excluded():
    root = _REPO_ROOT / "docs" / "sot"
    assert root.is_dir(), f"실제 docs/sot 트리를 찾을 수 없음: {root}"

    result = cli.run(root)

    assert result.errors == [], f"실행 오류가 있으면 안 됨: {result.errors}"
    template_violations = [v for v in result.violations if v.path.endswith("_TEMPLATE.md")]
    assert template_violations == [], f"_TEMPLATE.md는 전역 제외돼야 함: {template_violations}"
    readme_violations = [v for v in result.violations if v.path.endswith("README.md")]
    assert readme_violations == [], f"README.md는 전역 제외돼야 함: {readme_violations}"


def test_real_sot_tree_lint_is_deterministic():
    root = _REPO_ROOT / "docs" / "sot"
    r1 = cli.run(root)
    r2 = cli.run(root)
    assert r1.violations == r2.violations
    assert r1.errors == r2.errors
