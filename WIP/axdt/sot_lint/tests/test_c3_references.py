"""C3 참조 무결성 — covers(spec→req, td→req/spec)·rules(→registry), 교차 topic 접두."""
from __future__ import annotations

from axdt.sot_lint import cli
from axdt.sot_lint.tests._fixtures import golden_docs, write_tree


def test_c3_covers_target_document_missing(tmp_path):
    docs = golden_docs()
    docs["test-design/auth.md"] = docs["test-design/auth.md"].replace(
        "covers: [FR-1, SP-1]", "covers: [nope:FR-1]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3"]
    missing = [v for v in c3 if "없음" in v.message and "dangling" not in v.message]
    assert len(missing) == 1
    assert "nope" in missing[0].message


def test_c3_covers_dangling_item_reference(tmp_path):
    docs = golden_docs()
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "covers: [FR-1]", "covers: [FR-2]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3"]
    dangling = [v for v in c3 if "dangling" in v.message]
    assert len(dangling) == 1
    assert "FR-2" in dangling[0].message


def test_c3_covers_cross_topic_prefix_resolves(tmp_path):
    docs = golden_docs()
    docs["requirements/other.md"] = (
        "---\nid: req-other\nitems: [FR-5]\nrelated: []\nrules: []\n---\n\n"
        "## 기능 요구\n- **FR-5** 다른 topic의 요구.\n\n"
        "## 수용 기준\n- [ ] **FR-5** 판정.\n"
    )
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "covers: [FR-1]", "covers: [FR-1, other:FR-5]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3" and "other" in v.message]
    assert c3 == []


def test_c3_rules_dangling_and_resolved(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "rules: []", "rules: [rule-foo, rule-does-not-exist]"
    )
    docs["rule/foo.md"] = "---\nid: rule-foo\ntitle: 예시 규칙\nstatus: active\n---\n\n## 규칙문\n> 예시.\n"
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3" and "rules=" in v.message]
    assert len(c3) == 1
    assert "rule-does-not-exist" in c3[0].message
    assert "rule-foo" not in c3[0].message


def test_c3_covers_unrecognized_id_pattern_is_flagged(tmp_path):
    # BAD-1: FR/NFR/SP 어느 패턴에도 안 맞음.
    # auth:TD-1: spec.covers는 요구(FR/NFR)만 가리킬 수 있으므로 TD 접두는 해소 불가.
    docs = golden_docs()
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "covers: [FR-1]", "covers: [FR-1, BAD-1, auth:TD-1]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    unknown = [
        v
        for v in result.violations
        if v.code == "C3" and "형식을 알 수 없음" in v.message
    ]
    assert len(unknown) == 2
    assert any("BAD-1" in v.message for v in unknown)
    assert any("TD-1" in v.message for v in unknown)


def test_c3_covers_with_unresolved_placeholder_is_c4_not_c3(tmp_path):
    docs = golden_docs()
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "covers: [FR-1]", "covers: [<FR-n>]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3_on_spec = [
        v
        for v in result.violations
        if v.code == "C3" and v.path.endswith("specification/auth.md") and "covers=" in v.message
    ]
    assert c3_on_spec == []
    c4_on_spec = [
        v for v in result.violations if v.code == "C4" and v.path.endswith("specification/auth.md")
    ]
    assert len(c4_on_spec) == 1
