---
id: rule-subagent-no-direct-communication
title: sub-agent는 서로 직접 통신하지 않는다 — Leader가 허브로 중계한다
status: active
related: [rule-leader-coordination-via-maintainer, ADR-0003]
---

# sub-agent는 서로 직접 통신하지 않는다 — Leader가 허브로 중계한다

## 규칙문
> Developer·Reviewer·Tester(sub-agent)는 **서로 직접 통신하지 않는다**. 각 sub-agent는 자신을 호출한 **Leader에게만 응답**하고, Leader가 산출물을 받아 다음 sub-agent로 **중계**한다(허브 구조). 구현→리뷰→수정 루프는 Leader가 매개한다.

## 근거
- sub-agent 간 직접 통신을 막으면 상호작용 그래프가 **Leader 중심 별형(star)** 으로 단순해져 책임·격리·추적이 명확해진다.
- 모든 산출물이 Leader를 거치므로, 어떤 결과가 누구에게 갔는지 **단일 지점에서 통제·기록**된다 — Leader가 구현→리뷰→수정 루프의 통제권을 갖는다.

## 적용범위
- **대상**: 한 worktree 내 Leader와 그 sub-agent(Developer/Reviewer/Tester).
- **예외**: 없음.

## 예시
**준수 (✓)**
- Developer가 구현을 Leader에 반환 → Leader가 Reviewer에 전달 → 리뷰 결과를 Leader가 받아 Developer에 수정 지시.

**위반 (✗)**
- Developer가 Reviewer를 직접 호출해 리뷰를 주고받음. → 허브 우회. Leader가 루프를 통제·기록하지 못한다.
