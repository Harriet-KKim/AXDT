"""정상(위반 0·오류 0) 트리 기준선 — 개별 위반 테스트가 이 기준선에서 한 곳만 망가뜨린다."""
from __future__ import annotations

from axdt.sot_lint import cli
from axdt.sot_lint.tests._fixtures import golden_docs, write_tree


def test_golden_tree_has_no_violations_or_errors(tmp_path):
    write_tree(tmp_path, golden_docs())
    result = cli.run(tmp_path)
    assert result.errors == []
    assert result.violations == []
    assert result.ok is True
    assert result.files == 3
