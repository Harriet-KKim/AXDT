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


def test_c2_invalid_cross_kind_item_does_not_create_false_duplicate(tmp_path):
    """§A-5 회귀 — specification이 규약을 어기고 FR-1을 items에 넣어도, own_re 검증을
    통과하지 못한 선언은 declarations에 들어가지 않아 requirements의 진짜 FR-1과
    거짓 중복을 만들지 않는다(형식 위반 자체는 그대로 남는다).

    (이전 버전은 declarations.append가 own_re 검증보다 먼저 실행돼, 바로 이 시나리오
    에서 requirements/auth.md·specification/auth.md 양쪽에 "중복 선언" 위반을
    2건 잘못 냈다 — 그 잘못된 기대치를 이 테스트가 대체한다.)
    """
    docs = golden_docs()
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "items: [SP-1]", "items: [SP-1, FR-1]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    dup = [v for v in result.violations if v.code == "C2" and "중복 선언" in v.message]
    assert dup == []
    fmt = [
        v
        for v in result.violations
        if v.code == "C2" and "형식" in v.message and "FR-1" in v.message
    ]
    assert len(fmt) == 1


def test_c2_same_document_repeated_valid_id_is_still_a_duplicate(tmp_path):
    """§A-5 회귀 가드 — 진짜 중복(같은 문서가 유효한 ID를 items에 두 번 선언)은
    declarations.append 순서를 고친 뒤에도 여전히 잡혀야 한다."""
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "items: [FR-1]", "items: [FR-1, FR-1]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    dup = [v for v in result.violations if v.code == "C2" and "중복 선언" in v.message]
    assert len(dup) >= 1
    assert all(v.path.endswith("requirements/auth.md") for v in dup)


def test_c2_prefixed_reference_not_treated_as_self_declaration(tmp_path):
    """§A-4 회귀 — `topic:ID` 접두 참조는 본문에서 그 문서 고유 선언처럼 취급되면
    안 된다. 기존 버그는 접두를 무시하고 순수 ID 부분만 매칭해, 다른 topic의 항목을
    가리키는 참조(`auth:FR-1`)를 이 문서 자신의 미선언 항목처럼 오탐했다.
    """
    docs = golden_docs()
    docs["requirements/other.md"] = (
        "---\nid: req-other\nitems: [FR-5]\nrelated: []\nrules: []\n---\n\n"
        "## 기능 요구\n- **FR-5** 다른 topic의 요구.(참고: auth:FR-1)\n\n"
        "## 수용 기준\n- [ ] **FR-5** 판정.\n"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    undeclared_on_other = [
        v
        for v in result.violations
        if v.code == "C2" and v.path.endswith("other.md") and "FR-1" in v.message
    ]
    assert undeclared_on_other == []


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
