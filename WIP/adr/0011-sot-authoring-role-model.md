---
id: ADR-0011
title: SoT 저술 역할 Author를 신설하고, SoT PR 발의는 Maintainer로 한정한다
status: accepted
date: 2026-07-08
related: [rule-adr-recording, rule-sot-change-user-gate, rule-protected-paths]
---

# ADR-0011: SoT 저술 역할 Author를 신설하고, SoT PR 발의는 Maintainer로 한정한다

## 상태
Accepted (2026-07-08)

## 맥락
B-1(SoT 문서 작성 대화형 스킬) 설계에서 "SoT(요구·사양·테스트설계)를 누가 저술하고, 그 변경 PR을 누가 발의하는가"의 경계를 정해야 했다. 기존 역할 모델에는 SoT 저술 전담 주체가 없었다 — 역할표는 오케스트레이션(Maintainer·Watcher)과 구현(Leader와 하위 역할)만 담았다. 한편 `rule-protected-paths`는 이미 `docs/sot/**`를 "사용자 게이트 PR로만" 쓰도록 막고 있어, Leader를 포함한 어느 역할도 SoT를 직접 push할 수 없다. 저술 주체가 비어 있으면 저술 단계의 책임과 PR 발의 권한이 불명확해진다.

## 결정
1. **SoT 저술 전용 역할 Author를 신설한다.** Author는 개발 착수 이전 저술 단계의 행위자로, B-1 대화형 스킬로 요구·사양·테스트설계 초안을 쓴다.
2. **SoT 변경 PR의 발의(생성)는 Maintainer만 한다.** Author는 초안을 저술하고, PR로 올려 사용자 게이트에 거는 것은 Maintainer가 대행한다.
3. **Leader는 SoT를 직접 push하지 않는다.** 구현 중 사양 보완이 필요하면 report에 기록해 요청하고 Maintainer가 PR화한다(`rule-sot-change-user-gate`·`rule-protected-paths` 재확인).

## 결과
**좋은 점**
- 저술 책임(Author)과 게이트 발의(Maintainer)가 분리돼, 저술 주체가 스스로 게이트를 통과시키는 우회 여지가 줄어든다.
- SoT 저술이 명시적 역할을 얻어, B-1 스킬의 실행 주체와 산출물 흐름이 역할표와 정합한다.

**대가 / 주의**
- 역할이 하나 늘어 문서 갱신이 필요하다 — 루트 `README.md` 역할표와 `rule-sot-change-user-gate`의 저술·발의 주체 문장을 이 결정과 함께 갱신한다(이 PR의 동반 변경).
- Author의 호출·구동 방식(누가 언제 Author를 띄우는가)은 B-1 스킬 설계에서 확정한다. 이 ADR은 역할과 권한 경계만 정한다.

## 검토한 대안
### 대안 A — Leader가 SoT를 직접 저술·PR
별도 역할 없이 Leader가 SoT를 쓰고 PR까지 올린다. · **기각**: `docs/sot/**` 직접 수정은 `rule-protected-paths`가 막는 우회 지점이고, 저술과 게이트 발의를 한 주체가 겸하면 사용자 게이트의 독립성이 약해진다.

### 대안 B — 새 역할 없이 기존 역할 확장
Maintainer나 Leader의 책임에 SoT 저술을 얹는다. · **기각**: 저술 단계(개발 착수 전)와 오케스트레이션·구현은 시점과 성격이 다르다. 한 역할에 섞으면 저술 책임이 흐려지고 역할표의 단계 구분이 무너진다.

## 촉발 근거 (rule-adr-recording 도그푸딩)
이 결정은 `rule-adr-recording`의 촉발 조건 중 **워크플로 규범 변경**(역할 권한·SoT 저술/발의 규범)과 **대안 기각**에 걸린다. 그래서 이 ADR로 기록하며, 이 PR은 방금 승격한 규칙을 그 첫 사례로 실증한다. 관련 결정인 "SoT PR은 요구·사양·테스트설계 3종을 항상 동반한다(Q3=B)"도 촉발감이나, 성격이 다른 문서 번들 정책이라 별도 기록 후보로 남긴다.
