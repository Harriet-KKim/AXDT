---
id: ADR-0012
title: SoT 항목 선언을 frontmatter items로 명시한다
status: accepted
date: 2026-07-09
decision: D21
related: [rule-sot-readiness, rule-adr-recording, ADR-0008]
---

# ADR-0012: SoT 항목 선언을 frontmatter items로 명시한다

## 상태
Accepted (2026-07-09) · 관련 결정 D21 — 게이트 PR #9 병합으로 사용자 승인 완료.

## 맥락
완료 판정 ①(형식)은 requirements·specification·test-design의 항목(`FR-n`·`NFR-n`·`SP-n`·`TD-n`)이 선언돼 있는지, 문서 간 참조(`covers`)가 실재 항목을 가리키는지 결정적으로 검사해야 한다. 그런데 같은 굵은 표기 `**FR-1**`이 정의 자리(선언)와 재등장 자리(수용 기준·추적성 표·커버리지 목표 = 참조)에 모두 나온다. 본문 산문에서 "어느 등장이 선언인가"를 규칙으로 가르는 방식은 섹션·문맥 추정에 의존해 취약하고, 템플릿 구조가 바뀌면 깨진다. 검사기(sot-lint)가 이 위에서 존재·유일성·참조 무결성을 판정하려면 선언의 정본이 모호하지 않아야 한다.

## 결정
SoT 항목 선언의 정본을 본문이 아니라 각 문서 frontmatter의 `items` 목록에 둔다. `items`는 그 문서가 선언하는 항목 ID의 목록이다.
- 존재(①)·항목 ID 규약·`(topic, ID)` 유일성은 `items`로 판정한다.
- 참조 무결성은 `covers`(및 `rules`)를 대상 문서의 `items`(및 rule id 레지스트리)와 대조하는 frontmatter↔frontmatter 검사로 한다.
- 본문의 항목 ID 등장은 그 문서 고유 종류 ID에 한해 `items`와 집합 일치를 대조한다(미선언·phantom 적발). 어느 등장이 "선언"인지는 가리지 않는다.

반영: 템플릿 3종에 `items` 추가 + `rule-sot-readiness` ① 문구 정합화(본 PR). 검사기 스펙은 `WIP/drafts/sot-lint-spec-draft.md`.

## 결과
**좋은 점**
- 선언/참조 구분을 산문에서 없앤다 — 존재·참조 무결성이 결정적 대조가 된다.
- 검사기(sot-lint)가 단순해지고 재현 가능해진다.
- 중복 선언(`(topic, ID)` 충돌)·dangling 참조를 구조적으로 잡는다.

**대가 / 주의**
- 저술 스킬(B-1)이 항목마다 `items`를 채워야 한다(약간의 저술 부담·본문과의 이중 관리). 본문↔items 집합 일치 검사가 그 어긋남을 잡아 상쇄한다.
- 항목 ID가 frontmatter와 본문 두 곳에 존재한다(정본은 frontmatter).

## 검토한 대안
### 대안 A — 산문 heuristic 분류
본문에서 섹션·문맥으로 선언/참조를 추정한다. · **기각**: 같은 `**FR-1**`이 여러 자리에 나와 규칙이 취약하고, 템플릿 진화에 깨진다.

### 대안 B — inline marker
본문 항목에 선언을 표시하는 표식을 붙인다. · **기각**: 파싱이 여전히 본문 산문에 의존하고, 저술자가 표식을 빠뜨리면 조용히 틀린다.
