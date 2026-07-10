"""C6 수용 기준 채워짐 — 체크박스 앵커 규칙(★ "- [ ]"로 시작하는 줄, 첫 ID 토큰 매핑)."""
from __future__ import annotations

from axdt.sot_lint import cli
from axdt.sot_lint.tests._fixtures import golden_docs, write_tree


def test_c6_missing_checkbox_for_declared_item(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "items: [FR-1]", "items: [FR-1, FR-2]"
    ).replace(
        "- **FR-1** 사용자는 이메일로 로그인한다.",
        "- **FR-1** 사용자는 이메일로 로그인한다.\n- **FR-2** 추가 요구.",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c6 = [v for v in result.violations if v.code == "C6" and "FR-2" in v.message]
    assert len(c6) == 1
    assert "체크박스" in c6[0].message
    assert c6[0].line is None


def test_c6_empty_checkbox_content(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.", "- [ ] **FR-1**"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c6 = [
        v
        for v in result.violations
        if v.code == "C6" and v.path.endswith("requirements/auth.md")
    ]
    assert len(c6) == 1
    assert "비어" in c6[0].message
    assert c6[0].line is not None


def test_c6_placeholder_checkbox_content(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.",
        "- [ ] **FR-1** <판정 기준.>",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c6 = [
        v
        for v in result.violations
        if v.code == "C6" and v.path.endswith("requirements/auth.md")
    ]
    assert len(c6) == 1
    assert "플레이스홀더" in c6[0].message


def test_c6_banned_word_checkbox_content(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.", "- [ ] **FR-1** TBD"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c6 = [
        v
        for v in result.violations
        if v.code == "C6" and v.path.endswith("requirements/auth.md")
    ]
    assert len(c6) == 1
    assert "금지어" in c6[0].message


def test_c6_checkbox_inside_fence_does_not_count(tmp_path):
    """펜스 안의 '- [ ]'는 뷰A에서 마스킹돼 실제 체크박스로 인정되지 않는다."""
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.",
        "```\n- [ ] **FR-1** 이건 예시 코드일 뿐.\n```\n",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c6 = [
        v
        for v in result.violations
        if v.code == "C6" and v.path.endswith("requirements/auth.md")
    ]
    assert len(c6) == 1
    assert "체크박스" in c6[0].message  # 대응 체크박스 없음(펜스 안은 무효)


def test_c6_inline_code_only_content_not_flagged_as_empty(tmp_path):
    """수정 2 회귀 방지 — 수용 기준을 인라인 코드로만 채워도 '비어 있음' 오탐 없음(뷰A 판정)."""
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.",
        "- [ ] **FR-1** `token != null`",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c6 = [
        v
        for v in result.violations
        if v.code == "C6" and v.path.endswith("requirements/auth.md")
    ]
    assert c6 == []


def test_c6_passes_when_all_items_have_filled_checkboxes(tmp_path):
    write_tree(tmp_path, golden_docs())
    result = cli.run(tmp_path)
    assert not [v for v in result.violations if v.code == "C6"]
