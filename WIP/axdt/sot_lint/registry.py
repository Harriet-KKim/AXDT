"""rule id 레지스트리 수집 — 스펙 §5.

검사 루트 하위 rule/*.md(README·_TEMPLATE는 parser.discover가 이미 제외)의
frontmatter `id`를 모아 집합으로 만든다. C3(*.rules 참조 무결성)가 이 집합과 대조한다.
rule/ 문서 자체는 C1~C6 검사 대상이 아니다(rule-sot-readiness 적용범위 밖).
"""
from __future__ import annotations

from axdt.sot_lint.parser import ParsedDocument

__all__ = ["collect_rule_ids"]


def collect_rule_ids(rule_documents: list[ParsedDocument]) -> frozenset[str]:
    ids: set[str] = set()
    for doc in rule_documents:
        rid = doc.frontmatter.get("id")
        if isinstance(rid, str) and rid:
            ids.add(rid)
    return frozenset(ids)
