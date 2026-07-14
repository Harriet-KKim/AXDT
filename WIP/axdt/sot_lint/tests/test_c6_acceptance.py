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


def test_c6_prose_before_self_id_still_maps(tmp_path):
    """라운드10~11 규범 — 체크박스 내용 앞에 산문이 와도 첫 bare ID 토큰(자기 항목)에 매핑된다."""
    docs = golden_docs()
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "- [ ] **SP-1** POST /login이 200과 토큰을 반환한다.",
        "- [ ] 판정 대상 **SP-1**은 200과 토큰을 반환한다.",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c6 = [v for v in result.violations if v.code == "C6" and v.path.endswith("specification/auth.md")]
    assert c6 == []


def test_c6_prefixed_reference_before_self_id_is_skipped(tmp_path):
    """라운드11 — `topic:ID` 접두 참조는 매핑 후보에서 제외(§A-4 대칭). 접두 참조가
    자기 ID보다 앞에 와도 bare 자기 ID(SP-1)에 매핑돼 오탐하지 않는다."""
    docs = golden_docs()
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "- [ ] **SP-1** POST /login이 200과 토큰을 반환한다.",
        "- [ ] auth:FR-1 대비 **SP-1**이 200과 토큰을 반환한다.",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c6 = [v for v in result.violations if v.code == "C6" and v.path.endswith("specification/auth.md")]
    assert c6 == []


def test_c6_different_kind_bare_id_first_mismaps(tmp_path):
    """라운드11 — 다른 종류의 **bare** ID가 자기 ID보다 앞에 오면 그 토큰에 매핑돼
    자기 항목(SP-1)의 수용 기준으로 인식되지 않는다(문서화된 형식 관례 위반 케이스)."""
    docs = golden_docs()
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "- [ ] **SP-1** POST /login이 200과 토큰을 반환한다.",
        "- [ ] **FR-1** 관련 SP-1이 200과 토큰을 반환한다.",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c6 = [v for v in result.violations if v.code == "C6" and "SP-1" in v.message]
    assert len(c6) == 1
    assert "체크박스" in c6[0].message


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
        "- [ ] **FR-1** {{판정 기준}}",
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


def test_c6_delimiter_only_content_flagged_as_empty(tmp_path):
    """R3 리뷰 — ID + 부호(백틱·콜론·대시)만 있고 실제 단어가 없으면 '비어 있음'.

    공백만 제거하던 기존 판정은 이런 부호-only를 '내용 있음'으로 통과시켰다.
    실제 단어(글자·숫자·한글)가 하나라도 있으면(인라인 코드 안이라도) 통과한다.
    """
    for filler in ("`FR-1`", "**FR-1** :", "**FR-1** —"):
        docs = golden_docs()
        docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
            "- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.", f"- [ ] {filler}"
        )
        write_tree(tmp_path, docs)

        result = cli.run(tmp_path)
        c6 = [
            v
            for v in result.violations
            if v.code == "C6" and v.path.endswith("requirements/auth.md")
        ]
        assert len(c6) == 1, filler
        assert "비어" in c6[0].message, filler


def test_c6_passes_when_all_items_have_filled_checkboxes(tmp_path):
    write_tree(tmp_path, golden_docs())
    result = cli.run(tmp_path)
    assert not [v for v in result.violations if v.code == "C6"]


# --- A1: C6은 '## 수용 기준' 레벨2 제목 정확 일치 섹션 하위 체크박스로 한정 ---


def test_c6_checkbox_outside_acceptance_section_is_not_counted(tmp_path):
    """다른 섹션(예: '## 절차 원칙')의 체크박스는 수용 기준으로 세지 않는다."""
    docs = golden_docs()
    docs["requirements/auth.md"] = (
        docs["requirements/auth.md"]
        .replace("items: [FR-1]", "items: [FR-1, FR-2]")
        .replace(
            "- **FR-1** 사용자는 이메일로 로그인한다.",
            "- **FR-1** 사용자는 이메일로 로그인한다.\n- **FR-2** 추가 요구.",
        )
        .replace(
            "## 수용 기준\n- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.",
            "## 절차 원칙\n- [ ] **FR-2** 엉뚱한 섹션의 체크박스.\n\n"
            "## 수용 기준\n- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.",
        )
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c6 = [v for v in result.violations if v.code == "C6" and v.path.endswith("requirements/auth.md")]
    assert len(c6) == 1
    assert "FR-2" in c6[0].message
    assert "체크박스" in c6[0].message
    assert not any("FR-1" in v.message for v in c6)


def test_c6_checked_checkbox_is_accepted(tmp_path):
    """체크 상태([x]/[X])는 무관 — 채워졌는지만 본다."""
    for box in ("[x]", "[X]"):
        docs = golden_docs()
        docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
            "- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.",
            f"- {box} **FR-1** 로그인 성공 시 세션 토큰이 발급된다.",
        )
        write_tree(tmp_path, docs)

        result = cli.run(tmp_path)
        c6 = [
            v
            for v in result.violations
            if v.code == "C6" and v.path.endswith("requirements/auth.md")
        ]
        assert c6 == [], box


def test_c6_missing_acceptance_section_yields_single_violation(tmp_path):
    """items를 선언한 문서에 '## 수용 기준' 섹션 자체가 없으면 항목별이 아닌 1건만 낸다."""
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "\n## 수용 기준\n- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.\n", "\n"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c6 = [v for v in result.violations if v.code == "C6" and v.path.endswith("requirements/auth.md")]
    assert len(c6) == 1
    assert "수용 기준 섹션 없음" in c6[0].message
    assert c6[0].line is None


def test_c6_fake_heading_inside_fence_does_not_satisfy_section_requirement(tmp_path):
    """코드펜스 안의 가짜 '## 수용 기준'은 제목으로 세지 않는다 — 섹션 없음 판정."""
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "## 수용 기준\n- [ ] **FR-1** 로그인 성공 시 세션 토큰이 발급된다.\n",
        "```\n## 수용 기준\n- [ ] **FR-1** 이건 예시일 뿐.\n```\n"
        "- [ ] **FR-1** 실제로는 어느 섹션에도 속하지 않음.\n",
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c6 = [v for v in result.violations if v.code == "C6" and v.path.endswith("requirements/auth.md")]
    assert len(c6) == 1
    assert "수용 기준 섹션 없음" in c6[0].message
