"""템플릿 플레이스홀더 마이그레이션 회귀 — A2·D24, 다중모델 리뷰 라운드7~8.

세 콘텐츠 템플릿(`_TEMPLATE.md`)의 미기재 자리는 `{{...}}`여야 하며(구형 `<...>` 금지),
템플릿을 실제 콘텐츠로 복제하면 미치환 `{{...}}`를 C4가 위반으로 잡아야 한다.
구형 `<...>`는 C4가 못 잡아(자동링크·제네릭 오탐 회피) 미기재 문서가 조용히 통과했다 —
템플릿이 구형 문법으로 남으면 그 구멍이 복원되므로 여기서 고정한다.
"""
from __future__ import annotations

import re
from pathlib import Path

from axdt.sot_lint import cli
from axdt.sot_lint.tests._fixtures import golden_docs, write_tree

_REPO_ROOT = Path(__file__).resolve().parents[4]
_KINDS = ("requirements", "specification", "test-design")
# 세 템플릿에는 정당한 angle-pair(<https://…> 자동링크·Map<K,V> 제네릭 등)가 하나도 없으므로
# angle-pair 전면 금지로 회귀를 잡는다. 훗날 템플릿이 정당한 <…>를 쓰면 명시적 allowlist를 둔다.
_LEGACY_PLACEHOLDER_RE = re.compile(r"<[^<>\n]+>")


def _template_text(kind: str) -> str:
    return (_REPO_ROOT / "docs" / "sot" / kind / "_TEMPLATE.md").read_text(encoding="utf-8")


def test_legacy_placeholder_regex_catches_old_tokens():
    # 회귀 정규식이 실제 구형 토큰을 잡는지 pin(<topic>·<…>가 돌아오면 잡혀야 한다)
    for tok in ("<topic>", "<…>", "<판정 기준.>", "<제목>"):
        assert _LEGACY_PLACEHOLDER_RE.search(tok), f"구형 토큰 {tok!r}를 회귀 정규식이 못 잡음"


def test_templates_use_double_brace_and_have_no_legacy_placeholder():
    for kind in _KINDS:
        text = _template_text(kind)
        assert "{{" in text, f"{kind} 템플릿이 {{...}} 플레이스홀더를 안 쓴다"
        m = _LEGACY_PLACEHOLDER_RE.search(text)
        assert m is None, f"{kind} 템플릿에 구형 <...> angle-pair 잔재: {m.group(0) if m else ''!r}"


def test_template_copies_trip_c4_on_unfilled_placeholders(tmp_path):
    # 템플릿을 실제 콘텐츠 파일로 복제(파일명 변경 → 린트 대상)
    docs = {f"{kind}/draft.md": _template_text(kind) for kind in _KINDS}
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    # frontmatter title은 인용돼 YAML 파싱이 되어야 한다(파싱 오류 아닌 C4 위반으로 잡힘)
    assert not result.errors, f"템플릿 복제본이 파싱 오류를 냄(frontmatter 인용 누락?): {result.errors}"
    for kind in _KINDS:
        c4 = [
            v
            for v in result.violations
            if v.code == "C4" and v.path.endswith(f"{kind}/draft.md")
        ]
        assert c4, f"{kind} 템플릿 복제본의 미치환 {{...}}를 C4가 못 잡음"


def test_legacy_angle_placeholder_in_body_is_not_c4_violation(tmp_path):
    """구형 `<판정 기준.>` 산문은 C4 위반이 아니다 — 플레이스홀더 문법은 `{{...}}`뿐.

    라운드8 N7 — lint 스펙 §8 red vector가 "`<판정 기준.>` 비위반"을 규정하는데 대응 테스트가 없었다.
    """
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
    assert c4 == [], f"구형 <...> 산문을 C4가 잘못 위반 처리: {[v.message for v in c4]}"
