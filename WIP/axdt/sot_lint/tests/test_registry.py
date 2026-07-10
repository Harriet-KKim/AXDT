"""rule id 레지스트리 수집(스펙 §5) — README/_TEMPLATE 제외."""
from __future__ import annotations

from axdt.sot_lint import parser, registry


def test_collect_rule_ids_excludes_readme_and_template(tmp_path):
    rule_dir = tmp_path / "rule"
    rule_dir.mkdir()
    (rule_dir / "foo.md").write_text("---\nid: rule-foo\n---\n\n본문\n", encoding="utf-8")
    (rule_dir / "README.md").write_text(
        "---\nid: rule-should-not-count\n---\n\n본문\n", encoding="utf-8"
    )
    (rule_dir / "_TEMPLATE.md").write_text(
        "---\nid: rule-<slug>\n---\n\n본문\n", encoding="utf-8"
    )

    documents, errors, _ = parser.load_all(tmp_path)
    assert errors == []
    ids = registry.collect_rule_ids(documents["rule"])
    assert ids == frozenset({"rule-foo"})


def test_collect_rule_ids_ignores_missing_or_non_string_id(tmp_path):
    rule_dir = tmp_path / "rule"
    rule_dir.mkdir()
    (rule_dir / "noid.md").write_text("---\ntitle: id 없음\n---\n\n본문\n", encoding="utf-8")
    documents, errors, _ = parser.load_all(tmp_path)
    assert errors == []
    assert registry.collect_rule_ids(documents["rule"]) == frozenset()
