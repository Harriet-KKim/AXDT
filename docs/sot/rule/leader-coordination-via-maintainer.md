---
id: rule-leader-coordination-via-maintainer
title: Leader 간 조율은 Maintainer를 경유한다
status: active
related: [rule-subagent-no-direct-communication, rule-progress-single-writer, ADR-0003]
---

# Leader 간 조율은 Maintainer를 경유한다

## 규칙문
> Leader는 다른 Leader와 **어떤 채널로도 직접 통신하지 않는다**(tmux·파일·report 우회·메신저·PR 댓글·공유 산출물에 남기는 직접 지시 포함). workspace 간 의존성·조율이 필요하면 **Maintainer를 경유**한다 — Leader는 report로 올리고, Maintainer가 판단해 관련 Leader에 tmux로 지시한다.

## 근거
- Leader는 각자 격리된 workspace/컨테이너에 종속된다(D3). Leader 간 직접 통신은 그 **격리를 깨고** 의존 그래프를 얽히게 한다.
- 조율을 Maintainer로 모으면, 전체 진척·의존을 아는 **단일 오케스트레이터**가 일관되게 중재한다 — 의존·대기 관계가 한 주체에 모여 교착·중복 작업을 막는다.

## 적용범위
- **대상**: 모든 Leader 쌍(서로 다른 workspace든 같은 wave든). API 합의·공통 파일/스펙 충돌 등 모든 상호 조율 포함.
- **예외**: 없음 — 직접 통신이 불가피한 긴급 상황이라도 **즉시 Maintainer에 report로 올려 경유로 전환**한다(임의 직접 조율 금지).

## 예시
**준수 (✓)**
- Leader A가 "B의 API 확정 필요"를 report에 기록 → Maintainer가 읽고 **수용(progress 반영)** 후 B에 tmux로 지시, 결과를 A 작업에 반영.

**위반 (✗)**
- Leader A가 Leader B 세션에 직접 send-keys/파일로 요청. → 격리·경유 원칙 위반, Maintainer가 의존을 못 본다.
