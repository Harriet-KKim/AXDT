"""C4 미치환 플레이스홀더 — 정규식 경계(red 테스트) + frontmatter/본문 범위 + 펜스·인라인 제외."""
from __future__ import annotations

from axdt.sot_lint import cli
from axdt.sot_lint.tests._fixtures import golden_docs, write_tree


def test_c4_matches_placeholder_with_trailing_text(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.",
        "- [ ] **FR-1** <판정 기준.>",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c4 = [
        v
        for v in result.violations
        if v.code == "C4" and v.path.endswith("requirements/auth.md")
    ]
    assert any("판정 기준" in v.message for v in c4)


def test_c4_does_not_match_less_than_with_spaces(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "- **FR-1** 사용자는 이메일로 로그인한다.",
        "- **FR-1** 응답 지연은 a < b 조건을 만족해야 한다.",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c4 = [v for v in result.violations if v.code == "C4" and v.path.endswith("requirements/auth.md")]
    assert c4 == []


def test_c4_does_not_match_less_than_without_closing_bracket(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "- **FR-1** 사용자는 이메일로 로그인한다.",
        "- **FR-1** 조건 x<y를 만족해야 한다.",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c4 = [v for v in result.violations if v.code == "C4" and v.path.endswith("requirements/auth.md")]
    assert c4 == []


def test_c4_frontmatter_placeholder_detected_with_real_line(tmp_path):
    docs = golden_docs()
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "covers: [FR-1]", "covers: [<FR-n>]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c4 = [
        v
        for v in result.violations
        if v.code == "C4" and v.path.endswith("specification/auth.md")
    ]
    assert len(c4) == 1
    assert c4[0].line is not None
    assert c4[0].line <= 8  # frontmatter 블록 안(문서 앞부분)


def test_c4_placeholder_inside_fence_and_inline_excluded_from_body_scan(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "- **FR-1** 사용자는 이메일로 로그인한다.",
        "- **FR-1** 사용자는 이메일로 로그인한다.\n\n"
        "```\n"
        "예시: <아직-안-채움>\n"
        "```\n\n"
        "인라인 예시 `<아직-안-채움>` 도 있음.\n",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c4_body = [
        v
        for v in result.violations
        if v.code == "C4" and v.path.endswith("requirements/auth.md") and v.line is not None and v.line > 8
    ]
    assert c4_body == []
