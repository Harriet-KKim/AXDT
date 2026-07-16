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


# --- §A-6: 중복 rule id 검출 ---


def test_find_duplicate_rule_ids_detects_same_id_in_two_files(tmp_path):
    rule_dir = tmp_path / "rule"
    rule_dir.mkdir()
    (rule_dir / "a.md").write_text("---\nid: rule-foo\n---\n\n본문\n", encoding="utf-8")
    (rule_dir / "b.md").write_text("---\nid: rule-foo\n---\n\n본문\n", encoding="utf-8")

    documents, errors, _ = parser.load_all(tmp_path)
    assert errors == []
    dups = registry.find_duplicate_rule_ids(documents["rule"])
    assert set(dups.keys()) == {"rule-foo"}
    assert len(dups["rule-foo"]) == 2


def test_find_duplicate_rule_ids_empty_when_ids_differ(tmp_path):
    rule_dir = tmp_path / "rule"
    rule_dir.mkdir()
    (rule_dir / "a.md").write_text("---\nid: rule-foo\n---\n\n본문\n", encoding="utf-8")
    (rule_dir / "b.md").write_text("---\nid: rule-bar\n---\n\n본문\n", encoding="utf-8")

    documents, errors, _ = parser.load_all(tmp_path)
    assert errors == []
    assert registry.find_duplicate_rule_ids(documents["rule"]) == {}


def test_find_duplicate_rule_ids_ignores_missing_or_non_string_id(tmp_path):
    rule_dir = tmp_path / "rule"
    rule_dir.mkdir()
    (rule_dir / "a.md").write_text("---\ntitle: id 없음\n---\n\n본문\n", encoding="utf-8")
    (rule_dir / "b.md").write_text("---\ntitle: 역시 없음\n---\n\n본문\n", encoding="utf-8")

    documents, errors, _ = parser.load_all(tmp_path)
    assert errors == []
    assert registry.find_duplicate_rule_ids(documents["rule"]) == {}


# --- 다중모델 리뷰(라운드5): id -> status 매핑, C3의 active-only 참조에 쓰인다 ---


def test_collect_rule_statuses_maps_id_to_declared_status(tmp_path):
    rule_dir = tmp_path / "rule"
    rule_dir.mkdir()
    (rule_dir / "a.md").write_text(
        "---\nid: rule-a\nstatus: active\n---\n\n본문\n", encoding="utf-8"
    )
    (rule_dir / "b.md").write_text(
        "---\nid: rule-b\nstatus: deprecated\n---\n\n본문\n", encoding="utf-8"
    )

    documents, errors, _ = parser.load_all(tmp_path)
    assert errors == []
    statuses = registry.collect_rule_statuses(documents["rule"])
    assert statuses == {"rule-a": "active", "rule-b": "deprecated"}


def test_collect_rule_statuses_is_none_for_missing_or_non_string_status(tmp_path):
    """status가 없거나(fail-closed) 문자열이 아니면 None으로 기록해 active로 오인하지 않는다."""
    rule_dir = tmp_path / "rule"
    rule_dir.mkdir()
    (rule_dir / "nostat.md").write_text(
        "---\nid: rule-nostat\n---\n\n본문\n", encoding="utf-8"
    )
    (rule_dir / "badstat.md").write_text(
        "---\nid: rule-badstat\nstatus: [active]\n---\n\n본문\n", encoding="utf-8"
    )

    documents, errors, _ = parser.load_all(tmp_path)
    assert errors == []
    statuses = registry.collect_rule_statuses(documents["rule"])
    assert statuses == {"rule-nostat": None, "rule-badstat": None}
