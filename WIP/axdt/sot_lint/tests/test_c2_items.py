"""C2 — 항목 ID 규약·유일성·본문↔items 집합 일치·id↔topic (스펙 §4 C2)."""
from __future__ import annotations

from axdt.sot_lint import cli
from axdt.sot_lint.tests._fixtures import SPEC_AUTH, TD_AUTH, golden_docs, write_tree


def test_c2_invalid_item_id_format(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "items: [FR-1]", "items: [FR-1, FR-x]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c2 = [v for v in result.violations if v.code == "C2"]
    fmt = [v for v in c2 if "형식" in v.message and "FR-x" in v.message]
    assert len(fmt) == 1
    assert fmt[0].line is None


def test_c2_comma_string_hint_in_message(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "items: [FR-1]", "items: FR-1, FR-2"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c2 = [v for v in result.violations if v.code == "C2"]
    comma_hits = [v for v in c2 if "콤마" in v.message]
    assert len(comma_hits) == 1


def test_c2_duplicate_topic_id_across_kinds(tmp_path):
    # specification/auth.md가 자기 종류 규약을 어기며 FR-1을 items에 겹쳐 선언
    # -> (topic="auth", id="FR-1")이 requirements/auth.md와 중복.
    docs = golden_docs()
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "items: [SP-1]", "items: [SP-1, FR-1]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    dup = [v for v in result.violations if v.code == "C2" and "중복 선언" in v.message]
    assert len(dup) == 2
    assert {v.path for v in dup} == {
        (tmp_path / "requirements" / "auth.md").as_posix(),
        (tmp_path / "specification" / "auth.md").as_posix(),
    }


def test_c2_undeclared_in_body_has_real_line_number(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "- **FR-1** 사용자는 이메일로 로그인한다.",
        "- **FR-1** 사용자는 이메일로 로그인한다.\n- **FR-2** 추가 기능 설명.",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    undeclared = [
        v
        for v in result.violations
        if v.code == "C2" and "본문에 등장하나 items에 선언되지 않음" in v.message
    ]
    assert len(undeclared) == 1
    assert undeclared[0].line is not None


def test_c2_phantom_item_declared_but_absent_from_body(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "items: [FR-1]", "items: [FR-1, FR-9]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    phantom = [v for v in result.violations if v.code == "C2" and "phantom" in v.message]
    assert len(phantom) == 1
    assert phantom[0].line is None
    assert "FR-9" in phantom[0].message


def test_c2_id_topic_mismatch(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "id: req-auth", "id: req-wrong"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    mismatch = [
        v for v in result.violations if v.code == "C2" and "topic" in v.message and "불일치" in v.message
    ]
    assert len(mismatch) == 1
    assert mismatch[0].line is None


def test_c2_missing_id_is_violation(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "id: req-auth\n", ""
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    id_viol = [
        v
        for v in result.violations
        if v.code == "C2" and v.path.endswith("requirements/auth.md") and "id" in v.message
    ]
    assert len(id_viol) == 1
    assert id_viol[0].line is None


def test_c2_non_string_id_is_violation(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "id: req-auth", "id: 123"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    id_viol = [
        v
        for v in result.violations
        if v.code == "C2"
        and v.path.endswith("requirements/auth.md")
        and "규약과 불일치" in v.message
    ]
    assert len(id_viol) == 1


def test_c2_phantom_avoided_when_item_only_referenced_via_inline_code(tmp_path):
    """★ 뷰A(코드펜스만 제외, 인라인 포함)를 C2가 쓴다는 것의 직접 증거."""
    docs = {
        "requirements/x.md": (
            "---\nid: req-x\nitems: [FR-1]\nrelated: []\nrules: []\n---\n\n"
            "본문에서 `FR-1`은 인라인 코드로만 언급된다.\n\n"
            "## 수용 기준\n- [ ] **FR-1** 기준 텍스트.\n"
        ),
        "specification/auth.md": SPEC_AUTH.replace("covers: [FR-1]", "covers: []"),
        "test-design/auth.md": TD_AUTH.replace("covers: [FR-1, SP-1]", "covers: [SP-1]"),
    }
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c2_on_x = [v for v in result.violations if v.code == "C2" and v.path.endswith("x.md")]
    assert c2_on_x == []
