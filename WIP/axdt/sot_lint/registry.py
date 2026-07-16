"""rule 레지스트리 수집 — 스펙 §5.

검사 루트 하위 rule/*.md(README·_TEMPLATE는 parser.discover가 이미 제외)의
frontmatter `id`를 집합으로, `id`→`status` 매핑을 별도로 모은다. C3(*.rules 참조
무결성)가 참조 rule id의 실재뿐 아니라 `status: active` 여부까지 이 매핑으로 대조한다
(status 누락·비문자열은 fail-closed로 None → 비활성 취급 → 위반).
rule/ 문서 자체는 C1~C6 검사 대상이 아니다(rule-sot-readiness 적용범위 밖).
"""
from __future__ import annotations

from axdt.sot_lint.parser import ParsedDocument

__all__ = ["collect_rule_ids", "find_duplicate_rule_ids", "collect_rule_statuses"]


def collect_rule_ids(rule_documents: list[ParsedDocument]) -> frozenset[str]:
    ids: set[str] = set()
    for doc in rule_documents:
        rid = doc.frontmatter.get("id")
        if isinstance(rid, str) and rid:
            ids.add(rid)
    return frozenset(ids)


def find_duplicate_rule_ids(rule_documents: list[ParsedDocument]) -> dict[str, list[str]]:
    """같은 id를 선언한 rule 파일이 둘 이상이면 {id: [path, ...]}로 반환(§A-6).

    collect_rule_ids는 같은 id를 조용히 하나의 집합으로 병합하지만, 중복 id는
    C3가 참조하는 rule catalog를 모호하게 만든다(어느 파일을 가리키는지 결정 불능).
    빈 dict가 아니면 cli.run()이 이를 린트 위반으로 표면화한다.
    """
    by_id: dict[str, list[str]] = {}
    for doc in rule_documents:
        rid = doc.frontmatter.get("id")
        if isinstance(rid, str) and rid:
            by_id.setdefault(rid, []).append(doc.path)
    return {rid: paths for rid, paths in by_id.items() if len(paths) > 1}


def collect_rule_statuses(rule_documents: list[ParsedDocument]) -> dict[str, str | None]:
    """id -> status 매핑(다중모델 리뷰 라운드5) — C3의 `rules` 참조 해소가 이 매핑을 쓴다.

    C3는 `rules`가 가리키는 rule이 **status: active**일 때만 유효한 참조로 인정한다.
    deprecated·superseded인 rule은 실재하더라도 더 이상 참조 대상이 아니다. status가
    없거나 문자열이 아니면(기형) **fail-closed**로 None을 기록한다 — "active로 확인할
    수 없다"를 "존재하지 않는다"와 똑같이 위반 처리하기 위함이다(active임을 적극적으로
    확인하지 못하면 통과시키지 않는다). id 자체가 dict에 없으면 rule id가 아예
    존재하지 않는 것이고, 값이 None이면 존재하지만 상태를 신뢰할 수 없는 것이다 —
    두 경우 모두 C3에서는 "active 아님"으로 같이 취급된다.
    """
    statuses: dict[str, str | None] = {}
    for doc in rule_documents:
        rid = doc.frontmatter.get("id")
        if not (isinstance(rid, str) and rid):
            continue
        status = doc.frontmatter.get("status")
        statuses[rid] = status if isinstance(status, str) and status else None
    return statuses
