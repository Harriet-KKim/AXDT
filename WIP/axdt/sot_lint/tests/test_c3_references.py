"""C3 참조 무결성 — covers(spec→req, td→req/spec)·rules(→registry), 교차 topic 접두."""
from __future__ import annotations

from axdt.sot_lint import cli
from axdt.sot_lint.tests._fixtures import golden_docs, write_tree


def test_c3_covers_target_document_missing(tmp_path):
    docs = golden_docs()
    docs["test-design/auth.md"] = docs["test-design/auth.md"].replace(
        "covers: [FR-1, SP-1]", "covers: [nope:FR-1]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3"]
    missing = [v for v in c3 if "없음" in v.message and "dangling" not in v.message]
    assert len(missing) == 1
    assert "nope" in missing[0].message


def test_c3_covers_dangling_item_reference(tmp_path):
    docs = golden_docs()
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "covers: [FR-1]", "covers: [FR-2]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3"]
    dangling = [v for v in c3 if "dangling" in v.message]
    assert len(dangling) == 1
    assert "FR-2" in dangling[0].message


def test_c3_covers_cross_topic_prefix_resolves(tmp_path):
    docs = golden_docs()
    docs["requirements/other.md"] = (
        "---\nid: req-other\nitems: [FR-5]\nrelated: []\nrules: []\n---\n\n"
        "## 기능 요구\n- **FR-5** 다른 topic의 요구.\n\n"
        "## 수용 기준\n- [ ] **FR-5** 판정.\n"
    )
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "covers: [FR-1]", "covers: [FR-1, other:FR-5]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3" and "other" in v.message]
    assert c3 == []


def test_c3_rules_dangling_and_resolved(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "rules: []", "rules: [rule-foo, rule-does-not-exist]"
    )
    docs["rule/foo.md"] = "---\nid: rule-foo\ntitle: 예시 규칙\nstatus: active\n---\n\n## 규칙문\n> 예시.\n"
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3" and "rules=" in v.message]
    assert len(c3) == 1
    assert "rule-does-not-exist" in c3[0].message
    assert "rule-foo" not in c3[0].message


def test_c3_rules_reference_to_deprecated_rule_is_violation(tmp_path):
    """다중모델 리뷰(라운드5) 반영 — `rules`가 가리키는 rule은 status: active여야 통과.

    deprecated인 rule은 실재하더라도(존재 자체는 맞음) 더 이상 유효한 참조 대상이
    아니므로 C3 위반이어야 한다.
    """
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "rules: []", "rules: [rule-old]"
    )
    docs["rule/old.md"] = (
        "---\nid: rule-old\ntitle: 낡은 규칙\nstatus: deprecated\n---\n\n## 규칙문\n> 예시.\n"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3" and "rules=" in v.message]
    assert len(c3) == 1
    assert "rule-old" in c3[0].message
    assert "active" in c3[0].message


def test_c3_rules_reference_to_superseded_rule_is_violation(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "rules: []", "rules: [rule-old]"
    )
    docs["rule/old.md"] = (
        "---\nid: rule-old\ntitle: 대체된 규칙\nstatus: superseded\n---\n\n## 규칙문\n> 예시.\n"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3" and "rules=" in v.message]
    assert len(c3) == 1
    assert "rule-old" in c3[0].message


def test_c3_rules_reference_to_active_rule_passes(tmp_path):
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "rules: []", "rules: [rule-ok]"
    )
    docs["rule/ok.md"] = (
        "---\nid: rule-ok\ntitle: 유효 규칙\nstatus: active\n---\n\n## 규칙문\n> 예시.\n"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3" and "rules=" in v.message]
    assert c3 == []


def test_c3_rules_reference_to_rule_with_missing_status_is_fail_closed(tmp_path):
    """status 필드 자체가 없는 rule은 active로 확인할 수 없으므로 fail-closed로 위반."""
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "rules: []", "rules: [rule-nostat]"
    )
    docs["rule/nostat.md"] = "---\nid: rule-nostat\ntitle: 상태 없음\n---\n\n## 규칙문\n> 예시.\n"
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3" and "rules=" in v.message]
    assert len(c3) == 1
    assert "rule-nostat" in c3[0].message


def test_c3_rules_reference_to_rule_with_malformed_status_is_fail_closed(tmp_path):
    """status가 문자열이 아니면(기형) active로 인정하지 않는다(fail-closed)."""
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "rules: []", "rules: [rule-bad]"
    )
    docs["rule/bad.md"] = (
        "---\nid: rule-bad\ntitle: 기형 상태\nstatus: [active]\n---\n\n## 규칙문\n> 예시.\n"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3" and "rules=" in v.message]
    assert len(c3) == 1
    assert "rule-bad" in c3[0].message


def test_c3_rules_reference_to_case_variant_status_is_fail_closed(tmp_path):
    """status는 정확히 소문자 `active`만 인정한다 — `Active`·`ACTIVE` 등 대소문자
    변형은 active로 확인하지 못하므로 fail-closed 위반(정확일치 의미론 회귀 방어)."""
    docs = golden_docs()
    docs["requirements/auth.md"] = docs["requirements/auth.md"].replace(
        "rules: []", "rules: [rule-caps]"
    )
    docs["rule/caps.md"] = (
        "---\nid: rule-caps\ntitle: 대문자 상태\nstatus: Active\n---\n\n## 규칙문\n> 예시.\n"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3 = [v for v in result.violations if v.code == "C3" and "rules=" in v.message]
    assert len(c3) == 1
    assert "rule-caps" in c3[0].message


def test_c3_covers_unrecognized_id_pattern_is_flagged(tmp_path):
    # BAD-1: FR/NFR/SP 어느 패턴에도 안 맞음.
    # auth:TD-1: spec.covers는 요구(FR/NFR)만 가리킬 수 있으므로 TD 접두는 해소 불가.
    docs = golden_docs()
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "covers: [FR-1]", "covers: [FR-1, BAD-1, auth:TD-1]"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    unknown = [
        v
        for v in result.violations
        if v.code == "C3" and "형식을 알 수 없음" in v.message
    ]
    assert len(unknown) == 2
    assert any("BAD-1" in v.message for v in unknown)
    assert any("TD-1" in v.message for v in unknown)


def test_c3_duplicate_rule_id_across_files_is_surfaced_as_violation(tmp_path):
    """§A-6 — 서로 다른 rule 파일이 같은 id를 선언하면 카탈로그가 모호해지므로
    린트 위반으로 표면화해야 한다(기존엔 collect_rule_ids가 조용히 병합해 놓쳤다)."""
    docs = golden_docs()
    docs["rule/foo.md"] = (
        "---\nid: rule-dup\ntitle: 하나\nstatus: active\n---\n\n## 규칙문\n> 예시.\n"
    )
    docs["rule/bar.md"] = (
        "---\nid: rule-dup\ntitle: 둘\nstatus: active\n---\n\n## 규칙문\n> 예시.\n"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    dup = [v for v in result.violations if "rule-dup" in v.message and "중복" in v.message]
    assert len(dup) == 2
    assert {v.path for v in dup} == {
        (tmp_path / "rule" / "foo.md").as_posix(),
        (tmp_path / "rule" / "bar.md").as_posix(),
    }


def test_c3_distinct_rule_ids_do_not_trigger_duplicate_violation(tmp_path):
    docs = golden_docs()
    docs["rule/foo.md"] = (
        "---\nid: rule-foo\ntitle: 하나\nstatus: active\n---\n\n## 규칙문\n> 예시.\n"
    )
    docs["rule/bar.md"] = (
        "---\nid: rule-bar\ntitle: 둘\nstatus: active\n---\n\n## 규칙문\n> 예시.\n"
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    dup = [v for v in result.violations if "중복" in v.message and ("rule-foo" in v.message or "rule-bar" in v.message)]
    assert dup == []


def test_c3_covers_with_unresolved_placeholder_is_c4_not_c3(tmp_path):
    docs = golden_docs()
    # YAML 플로우 시퀀스 안 `{...}`는 인용해야 플로우 매핑으로 오인되지 않는다.
    docs["specification/auth.md"] = docs["specification/auth.md"].replace(
        "covers: [FR-1]", 'covers: ["{{FR-n}}"]'
    )
    write_tree(tmp_path, docs)

    result = cli.run(tmp_path)
    c3_on_spec = [
        v
        for v in result.violations
        if v.code == "C3" and v.path.endswith("specification/auth.md") and "covers=" in v.message
    ]
    assert c3_on_spec == []
    c4_on_spec = [
        v for v in result.violations if v.code == "C4" and v.path.endswith("specification/auth.md")
    ]
    assert len(c4_on_spec) == 1
