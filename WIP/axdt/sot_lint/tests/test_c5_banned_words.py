"""C5 금지어 — 닫힌 목록, ASCII 대소문자무시+단어경계, 한글 정확 매칭, 펜스/인라인 제외."""
from __future__ import annotations

from axdt.sot_lint import checks, cli
from axdt.sot_lint.tests._fixtures import golden_docs, write_tree


def test_find_banned_words_ascii_case_insensitive_word_boundary():
    assert checks.find_banned_words("This is a todo item.") == ["todo"]
    assert checks.find_banned_words("TODOLIST person") == []  # 단어 경계 위반 → 비매칭


def test_find_banned_words_korean_exact_substring_match():
    assert checks.find_banned_words("추후 논의 예정") == ["추후"]
    # 정확 매칭(단어경계 아님) — 복합어 중간에 있어도 리터럴 부분열이면 매칭.
    assert checks.find_banned_words("정책추후변경예정") == ["추후"]


def test_c5_violation_reported_with_real_line_number(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "- **FR-1** 사용자는 이메일로 로그인한다.",
        "- **FR-1** 사용자는 이메일로 로그인한다. TBD 나중에 보완.",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c5 = [v for v in result.violations if v.code == "C5" and v.path.endswith("requirements/auth.md")]
    words = sorted(w for v in c5 for w in [v.message])
    assert any("TBD" in m for m in words)
    assert any("나중에" in m for m in words)
    assert all(v.line is not None for v in c5)


def test_c5_detects_banned_word_in_frontmatter(tmp_path):
    """수정 1 회귀 방지 — frontmatter(title 등)에 샌 금지어도 C4처럼 잡는다."""
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "title: 인증 요구", "title: 인증 요구 TODO"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c5 = [
        v
        for v in result.violations
        if v.code == "C5" and v.path.endswith("requirements/auth.md")
    ]
    assert len(c5) == 1
    assert "TODO" in c5[0].message
    assert c5[0].line is not None
    assert c5[0].line <= 8  # frontmatter 블록 안(문서 앞부분)


def test_c5_excludes_fence_and_inline_code(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "- **FR-1** 사용자는 이메일로 로그인한다.",
        "- **FR-1** 사용자는 이메일로 로그인한다.\n\n"
        "```\nTBD\n```\n\n"
        "인라인 `TODO` 예시.\n",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c5 = [v for v in result.violations if v.code == "C5" and v.path.endswith("requirements/auth.md")]
    assert c5 == []
