"""frontmatter 파싱 오류 경로(§3.1) + 본문 두 텍스트 뷰(§3.3) 검증."""
from __future__ import annotations

from axdt.sot_lint import parser


def test_frontmatter_missing_no_leading_delimiter(tmp_path):
    p = tmp_path / "x.md"
    p.write_text("# frontmatter 없음\n본문\n", encoding="utf-8")
    result = parser.load_document(p, "requirements")
    assert isinstance(result, parser.ParseError)
    assert result.code == "E_FRONTMATTER_MISSING"


def test_frontmatter_missing_unterminated(tmp_path):
    p = tmp_path / "x.md"
    p.write_text("---\nid: req-x\n\n본문 계속\n", encoding="utf-8")
    result = parser.load_document(p, "requirements")
    assert isinstance(result, parser.ParseError)
    assert result.code == "E_FRONTMATTER_MISSING"


def test_yaml_malformed(tmp_path):
    p = tmp_path / "x.md"
    p.write_text("---\nid: [unterminated\n---\n\n본문\n", encoding="utf-8")
    result = parser.load_document(p, "requirements")
    assert isinstance(result, parser.ParseError)
    assert result.code == "E_YAML_MALFORMED"


def test_yaml_not_a_mapping(tmp_path):
    p = tmp_path / "x.md"
    p.write_text("---\n- 리스트임\n- 매핑 아님\n---\n\n본문\n", encoding="utf-8")
    result = parser.load_document(p, "requirements")
    assert isinstance(result, parser.ParseError)
    assert result.code == "E_YAML_MALFORMED"


def test_yaml_duplicate_key_rejected(tmp_path):
    p = tmp_path / "x.md"
    p.write_text("---\nid: req-x\nid: req-y\nitems: []\n---\n\n본문\n", encoding="utf-8")
    result = parser.load_document(p, "requirements")
    assert isinstance(result, parser.ParseError)
    assert result.code == "E_YAML_DUPLICATE_KEY"


def test_body_views_mask_fence_and_inline_differently(tmp_path):
    text = (
        "---\n"
        "id: req-x\n"
        "items: []\n"
        "---\n"
        "\n"
        "일반 텍스트 `FR-1` 인라인.\n"
        "```\n"
        "코드 안 FR-2 <미치환>\n"
        "```\n"
        "펜스 밖 FR-3.\n"
    )
    p = tmp_path / "x.md"
    p.write_text(text, encoding="utf-8")
    doc = parser.load_document(p, "requirements")
    assert isinstance(doc, parser.ParsedDocument)

    a = dict(doc.body_view_a)
    b = dict(doc.body_view_b)

    # 인라인 코드: 뷰A는 보존(phantom 오탐 방지), 뷰B는 마스킹(C4·C5용)
    assert "FR-1" in a[6]
    assert "FR-1" not in b[6]

    # 코드펜스 내부: 뷰A·뷰B 둘 다 제외
    assert "FR-2" not in a[8]
    assert "FR-2" not in b[8]

    # 펜스 밖은 그대로
    assert "FR-3" in a[10]
    assert "FR-3" in b[10]

    # 줄 번호는 원문 기준 그대로(마스킹이 줄을 없애지 않음)
    assert [n for n, _ in doc.body_view_a] == [n for n, _ in doc.body_view_b]


def test_tilde_fence_masks_like_backtick_fence(tmp_path):
    text = "---\nid: req-x\nitems: []\n---\n\n~~~\nFR-9 안 보여야 함\n~~~\n뒤 FR-8.\n"
    p = tmp_path / "x.md"
    p.write_text(text, encoding="utf-8")
    doc = parser.load_document(p, "requirements")
    assert isinstance(doc, parser.ParsedDocument)
    a_text = " ".join(t for _, t in doc.body_view_a)
    assert "FR-9" not in a_text
    assert "FR-8" in a_text


def test_discover_excludes_readme_and_template(tmp_path):
    (tmp_path / "requirements").mkdir()
    (tmp_path / "requirements" / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / "requirements" / "_TEMPLATE.md").write_text("x", encoding="utf-8")
    (tmp_path / "requirements" / "real.md").write_text("x", encoding="utf-8")
    found = parser.discover(tmp_path)
    names = [p.name for p in found["requirements"]]
    assert names == ["real.md"]
