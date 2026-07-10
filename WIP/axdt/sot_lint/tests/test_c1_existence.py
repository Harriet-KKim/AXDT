"""C1 존재 — requirements·specification·test-design 각각 items 선언 문서 최소 1개."""
from __future__ import annotations

from axdt.sot_lint import cli
from axdt.sot_lint.tests._fixtures import SPEC_AUTH, TD_AUTH, golden_docs, write_tree


def test_c1_violates_when_kind_directory_is_entirely_missing(tmp_path):
    docs = golden_docs()
    del docs["requirements/auth.md"]  # requirements 디렉터리 자체가 안 생김
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c1 = [v for v in result.violations if v.code == "C1"]
    assert len(c1) == 1
    assert c1[0].line is None
    assert c1[0].path.endswith("requirements")


def test_c1_passes_when_each_kind_has_at_least_one_items_document(tmp_path):
    write_tree(tmp_path, golden_docs())
    result = cli.run(tmp_path)
    assert not [v for v in result.violations if v.code == "C1"]


def test_c1_document_with_empty_items_does_not_satisfy_c1_but_is_not_itself_a_violation(
    tmp_path,
):
    docs = {
        "requirements/empty.md": (
            "---\nid: req-empty\nitems: []\nrelated: []\nrules: []\n---\n\n본문.\n"
        ),
        "specification/auth.md": SPEC_AUTH.replace("covers: [FR-1]", "covers: []"),
        "test-design/auth.md": TD_AUTH.replace("covers: [FR-1, SP-1]", "covers: []"),
    }
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c1 = [v for v in result.violations if v.code == "C1"]
    assert len(c1) == 1
    assert c1[0].path.endswith("requirements")
    # items:[]인 문서 자체는 통과(개별 위반 없음) — 종류 수준에서만 위반.
    assert not [v for v in result.violations if v.path.endswith("empty.md")]
