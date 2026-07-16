"""axdt.roles.spec 자체검증 — role-responsibilities.md 표와의 등가를 값 단위로
직접 대조한다.

아래 ``_parse_role_table``은 권위 문서(``docs/sot/rule/role-responsibilities.md``)의
"## 역할 명세" 표를 실제로 파싱해 ``ROLES``와 대조한다(§8.2) — 표 값을 코드에
재하드코딩하면 표만 바뀌어도 테스트가 조용히 통과해 계약 검사가 무의미해지므로,
파싱 결과를 직접 오라클로 쓴다.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from axdt.roles.spec import ROLES, SUBAGENT_ROLES, Capability, Enforcement, RoleKind

_SUPERSCRIPT_DIGITS = "⁰¹²³⁴⁵⁶⁷⁸⁹"


def _find_worktree_root() -> Path:
    """axdt/roles/tests/ (이 파일의 위치)에서 워크트리 루트를 찾는다.

    이 파일은 ``WIP/axdt/roles/tests/test_spec.py``에 있고, ``WIP``는 여기서
    3단계 위(tests -> roles -> axdt -> WIP), 워크트리 루트는 그 부모다
    (``docs/sot/rule/``이 ``WIP``의 형제 디렉터리에 있다). 그 경로에
    ``docs/sot/rule/role-responsibilities.md``가 없으면(레이아웃이 바뀌었거나
    다른 위치에서 실행된 경우) ``git rev-parse --show-toplevel``로 구한다.
    """
    candidate = Path(__file__).resolve().parents[4]
    if (candidate / "docs" / "sot" / "rule" / "role-responsibilities.md").is_file():
        return candidate
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


ROLE_RESPONSIBILITIES_MD = (
    _find_worktree_root() / "docs" / "sot" / "rule" / "role-responsibilities.md"
)


def _clean_cell(cell: str) -> str:
    """셀에서 백틱·위첨자 각주 마커·둘레 공백을 제거한다. ``${task}``는 그대로 둔다."""
    cell = cell.strip()
    cell = cell.replace("`", "")
    cell = "".join(ch for ch in cell if ch not in _SUPERSCRIPT_DIGITS)
    return cell.strip()


def _parse_role_table(md_path: Path) -> dict[str, tuple[str, ...]]:
    """``## 역할 명세`` 섹션의 표를 파싱해 역할 id -> 쓰기 경로(glob) 튜플로 돌려준다.

    데이터 행만 골라낸다: 역할 id 셀(1열)이 백틱으로 감싸진 행만 취급한다 —
    헤더 행("역할 id")과 구분선 행("---")은 백틱이 없어 자연히 제외된다.
    쓰기 경로 셀(5열)은 ``,``로 분할해 항목별로 같은 정리를 적용하고,
    ``(없음)``은 빈 튜플로 둔다.
    """
    text = md_path.read_text(encoding="utf-8")
    section_match = re.search(r"^## 역할 명세.*?(?=^## |\Z)", text, re.M | re.S)
    if section_match is None:
        raise AssertionError(f"'## 역할 명세' section not found in {md_path}")
    section = section_match.group(0)

    roles: dict[str, tuple[str, ...]] = {}
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = line.split("|")
        if len(cells) < 6:
            continue
        role_id_raw = cells[1].strip()
        if not (role_id_raw.startswith("`") and role_id_raw.endswith("`")):
            continue  # 헤더·구분선·기타 비-데이터 행
        role_id = _clean_cell(cells[1])
        paths_cell = _clean_cell(cells[5])
        if paths_cell == "(없음)":
            paths: tuple[str, ...] = ()
        else:
            paths = tuple(
                item
                for item in (_clean_cell(p) for p in paths_cell.split(","))
                if item
            )
        roles[role_id] = paths
    return roles


def _frontmatter_id(text: str) -> str | None:
    """마크다운 앞머리(``---`` ~ ``---``) 안의 ``id:`` 값만 읽는다(본문은 안 본다)."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    header = text[3:end]
    m = re.search(r"^id:\s*(\S+)\s*$", header, re.M)
    return m.group(1) if m else None


def test_roles_has_exactly_five_known_keys():
    assert set(ROLES) == {"maintainer", "leader", "developer", "reviewer", "tester"}


def test_every_role_has_nonempty_system_prompt():
    for role in ROLES.values():
        assert role.system_prompt.strip(), f"{role.name}: system_prompt is empty"


def test_every_role_refs_role_responsibilities():
    for role in ROLES.values():
        assert "rule-role-responsibilities" in role.rule_refs, role.name


def test_reviewer_is_read_only_with_no_writable_paths():
    reviewer = ROLES["reviewer"]
    assert reviewer.capability is Capability.READ_ONLY
    assert reviewer.writable_paths == ()


def test_read_only_roles_have_no_writable_paths():
    # §8.2 계약의 일반형: capability == READ_ONLY 이면 writable_paths == () 다.
    # reviewer 고정 테스트만으로는 향후 다른 READ_ONLY 역할이 추가돼도 이
    # 함의(implication)를 놓칠 수 있어, 전 역할을 순회해 일반적으로 검사한다.
    for name, role in ROLES.items():
        if role.capability is Capability.READ_ONLY:
            assert role.writable_paths == (), (
                f"{name}: capability=READ_ONLY 이지만 writable_paths="
                f"{role.writable_paths!r} (비어있지 않음)"
            )


def test_reviewer_enforcement_is_gated_not_mechanical():
    # §8.3a 측정 전이므로 MECHANICAL로 확정하지 않는다
    # (스펙 §2.3.2, role-responsibilities.md 각주 ⁴).
    assert ROLES["reviewer"].enforcement is Enforcement.GATED


def test_subagent_roles_matches_kind_subagent():
    expected = {role for role in ROLES.values() if role.kind is RoleKind.SUBAGENT}
    assert set(SUBAGENT_ROLES) == expected
    assert {role.name for role in SUBAGENT_ROLES} == {
        "developer",
        "reviewer",
        "tester",
    }


# --- role-responsibilities.md 표와의 값 등가 대조 (역할별) ---


def test_maintainer_matches_role_responsibilities_table():
    m = ROLES["maintainer"]
    assert m.kind is RoleKind.SESSION
    assert m.capability is Capability.HOST_CONTROL
    assert m.enforcement is Enforcement.ABSENT
    assert m.writable_paths == (
        "docs/interim/progress.md",
        "docs/interim/plan/**",
        "docs/interim/sot-readiness-review.md",
        "docs/interim/**/README.md",
        "docs/interim/**/_TEMPLATE.md",
        "docs/interim/ADR/*.md",
    )
    assert m.model_hint is None


def test_leader_matches_role_responsibilities_table():
    leader = ROLES["leader"]
    assert leader.kind is RoleKind.SESSION
    assert leader.capability is Capability.WRITE_WORKSPACE
    assert leader.enforcement is Enforcement.GATED
    assert leader.writable_paths == (
        "src/**",
        "test/**",
        "docs/interim/report/${task}.md",
    )
    assert leader.model_hint is None


def test_developer_matches_role_responsibilities_table():
    developer = ROLES["developer"]
    assert developer.kind is RoleKind.SUBAGENT
    assert developer.capability is Capability.WRITE_WORKSPACE
    assert developer.enforcement is Enforcement.ADVISORY
    assert developer.writable_paths == ("src/**", "test/**")
    assert developer.model_hint is None


def test_tester_matches_role_responsibilities_table():
    tester = ROLES["tester"]
    assert tester.kind is RoleKind.SUBAGENT
    assert tester.capability is Capability.WRITE_WORKSPACE
    assert tester.enforcement is Enforcement.ADVISORY
    assert tester.writable_paths == ("test/**",)
    assert tester.model_hint is None


def test_all_role_specs_are_frozen():
    for role in ROLES.values():
        try:
            role.name = "mutated"  # type: ignore[misc]
        except Exception:
            continue
        raise AssertionError(f"{role.name}: RoleSpec is not frozen")


# --- role-responsibilities.md 표를 실제로 파싱해 대조(계약 검사, §8.2) ---
#
# 위의 test_*_matches_role_responsibilities_table 테스트들은 표 값을 코드에
# 재하드코딩한 것이라 표만 바뀌면 조용히 통과한다. 아래 테스트는 표 자체를
# 파싱해 spec.py와 대조하므로 표가 바뀌면 반드시 반영해야 통과한다.


def test_parse_role_table_covers_all_roles():
    parsed = _parse_role_table(ROLE_RESPONSIBILITIES_MD)
    assert set(parsed) == set(ROLES), (
        f"role-responsibilities.md 표의 역할 id 집합 {set(parsed)!r}이 "
        f"ROLES {set(ROLES)!r}와 다르다"
    )


def test_parse_role_table_writable_paths_equal_spec_py():
    parsed = _parse_role_table(ROLE_RESPONSIBILITIES_MD)
    mismatches = [
        f"{name}: table={parsed[name]!r} != spec.py={role.writable_paths!r}"
        for name, role in ROLES.items()
        if parsed.get(name) != role.writable_paths
    ]
    assert not mismatches, (
        "role-responsibilities.md 표와 axdt/roles/spec.py의 writable_paths가 "
        "등가가 아니다:\n" + "\n".join(mismatches)
    )


# --- rule_refs 실재 검사(§8) ---


def test_all_rule_refs_point_to_existing_rule_docs_with_matching_id():
    rule_dir = ROLE_RESPONSIBILITIES_MD.parent  # docs/sot/rule/
    missing: list[str] = []
    mismatched: list[str] = []
    for role in ROLES.values():
        for rule_id in role.rule_refs:
            assert rule_id.startswith("rule-"), (
                f"{role.name}: rule_refs id {rule_id!r} does not start with 'rule-'"
            )
            slug = rule_id[len("rule-") :]
            path = rule_dir / f"{slug}.md"
            if not path.is_file():
                missing.append(f"{role.name}: {rule_id} -> {path} (not found)")
                continue
            found_id = _frontmatter_id(path.read_text(encoding="utf-8"))
            if found_id != rule_id:
                mismatched.append(
                    f"{role.name}: {rule_id} -> {path} has frontmatter id={found_id!r}"
                )
    assert not missing, "rule_refs가 가리키는 문서가 없다:\n" + "\n".join(missing)
    assert not mismatched, (
        "rule_refs id와 문서 frontmatter id가 다르다:\n" + "\n".join(mismatched)
    )


# --- 프롬프트 섹션 헤더의 rule 태그 <= rule_refs (§3) ---

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_SECTION_RULE_TAG_RE = re.compile(
    r"^\s*#{2,}\s+.*\((rule-[a-z0-9-]+)\)\s*$", re.MULTILINE
)


def test_prompt_section_rule_tags_subset_of_rule_refs():
    """프롬프트가 인용하는 rule은 그 역할의 rule_refs에 있어야 한다(§3).

    섹션 헤더(``## ... (rule-xxx)``)만 대상으로 삼는다 — 블록쿼트·본문의
    상호참조 언급은 창작 규범 인용이 아니라 다른 rule을 설명 목적으로 인용한
    것일 수 있어 대상에서 제외한다.
    """
    for name, role in ROLES.items():
        prompt_path = _PROMPTS_DIR / f"{name}.md"
        text = prompt_path.read_text(encoding="utf-8")
        tags = set(_SECTION_RULE_TAG_RE.findall(text))
        missing = tags - set(role.rule_refs)
        assert tags <= set(role.rule_refs), (
            f"{name}: prompt section headers tag rule ids not in rule_refs: "
            f"{missing!r}"
        )
