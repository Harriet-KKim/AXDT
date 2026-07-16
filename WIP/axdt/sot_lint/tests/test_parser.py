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


def test_utf8_bom_does_not_break_frontmatter_detection(tmp_path):
    """§A-1 — UTF-8 BOM이 붙은 파일도 frontmatter를 정상 인식해야 한다."""
    text = "---\nid: req-x\nitems: []\n---\n\n본문.\n"
    p = tmp_path / "x.md"
    p.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    doc = parser.load_document(p, "requirements")
    assert isinstance(doc, parser.ParsedDocument), doc
    assert doc.frontmatter.get("id") == "req-x"


def test_unbalanced_single_backtick_does_not_mask_following_banned_word(tmp_path):
    """§A-2 — 줄에 짝 없는 백틱 하나만 있으면 아무것도 마스킹되지 않아야 한다.

    기존 정규식은 짝이 없는 단일 백틱도 뒤에 나오는 아무 백틱과 무조건 짝지어,
    사이의 정상 텍스트(여기선 금지어 TODO)를 코드 스팬으로 잘못 감춰버렸다.
    """
    text = (
        "---\nid: req-x\nitems: []\n---\n\n"
        "이 줄에는 백틱이 ` 하나뿐이고 뒤에 TODO 라는 단어가 있다.\n"
    )
    p = tmp_path / "x.md"
    p.write_text(text, encoding="utf-8")
    doc = parser.load_document(p, "requirements")
    assert isinstance(doc, parser.ParsedDocument)
    b_text = " ".join(t for _, t in doc.body_view_b)
    assert "TODO" in b_text


def test_backtick_run_length_mismatch_does_not_mask_as_code_span(tmp_path):
    """§A-2 — 여는 백틱런과 같은 '길이'의 닫는 런이 없으면 코드 스팬이 아니다.

    길이 2로 열었는데 그 뒤에 나오는 백틱이 실제로는 길이 3인 런(부분열이 아니라
    전체가 그 길이)이면, CommonMark상 길이 2 닫는 런으로 인정되지 않는다. 기존
    정규식은 backreference로 '다음에 나오는 같은 글자수 부분열'만 찾아 이 경우도
    잘못 코드 스팬으로 인식해 TODO를 가려버렸다.
    """
    text = "---\nid: req-x\nitems: []\n---\n\n" "``TODO``` 나머지 텍스트.\n"
    p = tmp_path / "x.md"
    p.write_text(text, encoding="utf-8")
    doc = parser.load_document(p, "requirements")
    assert isinstance(doc, parser.ParsedDocument)
    b_text = " ".join(t for _, t in doc.body_view_b)
    assert "TODO" in b_text


def test_closing_fence_with_trailing_text_does_not_close_the_block(tmp_path):
    """§A-3 — 닫는 펜스는 같은 종류·길이 + 공백만 허용. trailing 비공백은 닫지 못한다."""
    text = (
        "---\nid: req-x\nitems: []\n---\n\n"
        "```python\n"
        "FR-9 안 보여야 함\n"
        "``` extra\n"
        "FR-8 도 여전히 코드 안(가짜 닫는 펜스라 아직 열려 있음)\n"
        "```\n"
        "FR-7 펜스 밖.\n"
    )
    p = tmp_path / "x.md"
    p.write_text(text, encoding="utf-8")
    doc = parser.load_document(p, "requirements")
    assert isinstance(doc, parser.ParsedDocument)

    a_text = " ".join(t for _, t in doc.body_view_a)
    assert "FR-9" not in a_text
    assert "FR-8" not in a_text  # 가짜 닫는 펜스 뒤도 여전히 코드 블록 안
    assert "FR-7" in a_text  # 진짜 닫는 펜스(bare ```) 이후는 코드 밖


def test_discover_excludes_readme_and_template(tmp_path):
    (tmp_path / "requirements").mkdir()
    (tmp_path / "requirements" / "README.md").write_text("x", encoding="utf-8")
    (tmp_path / "requirements" / "_TEMPLATE.md").write_text("x", encoding="utf-8")
    (tmp_path / "requirements" / "real.md").write_text("x", encoding="utf-8")
    found = parser.discover(tmp_path)
    names = [p.name for p in found["requirements"]]
    assert names == ["real.md"]
