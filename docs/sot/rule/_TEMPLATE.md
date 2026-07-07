---
id: rule-<kebab-slug>
title: <한 줄 규칙 제목 — 명령형 권장>
status: active          # active | deprecated | superseded
scope: global           # local | global — global(용어·네이밍 등 횡단)은 변경 시 완료된 req·spec·test-design 전량 재검토 대상 (rule-sot-readiness). local로 좁히려면 의도적으로 바꾼다. 미기재도 global로 취급
related: []             # 관련 rule/ADR id 목록 (예: rule-..., ADR-0001)
---

# <제목>

## 규칙문
> <지켜야 할 단일 규범을 명령형 한 문장으로. "~한다 / ~하지 않는다".>

(필요 시 부연 1~2문장. 규칙의 정확한 경계·예외를 여기서 못박는다. 한 파일 = 한 규칙.)

## 근거
- <이 규칙이 존재하는 이유. 무엇을 막고 무엇을 보장하는가.>
- <근거의 상세한 설계 논증이 ADR에 있으면 `ADR-XXXX` 로 참조 — 규칙은 "무엇을", ADR은 "왜 이렇게"를 담는다.>

## 적용범위
- **대상**: <어떤 역할·파일·경로·상황에 적용되는가>
- **예외**: <있으면 명시, 없으면 "없음">

## 예시
**준수 (✓)**
- <올바른 사례>

**위반 (✗)**
- <흔한 잘못 + 왜 위반인지>
