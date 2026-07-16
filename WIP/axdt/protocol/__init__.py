"""Phase 2 — Leader 배정/반려 프로토콜(메시지 렌더링·주입·수렴).

이 패키지의 세 모듈:
- ``message.py``: 단일행 메시지 포맷(assign/reject/note). 측정과 무관한
  순수 문자열 조립이라 실제로 구현되어 있다.
- ``inject.py``: ``IDLE`` 게이트 뒤에서 메시지를 주입하는 계약(타입·시그니처
  ·docstring). 라이브 배선은 상태판정(``poll_state``)의 Phase 5 훅 기반
  재설계 이후로 미룬다 — 지금은 골격뿐이다.
- ``converge.py``: 관측(``Observation``)에서 필요한 지시를 결정하는 계약.
  관측의 생산자가 Phase 4(recover)·Phase 5(AgentState) 통합에 의존하므로
  지금은 골격뿐이다.

근거: ``WIP/specs/2026-07-09-phase2-roles-and-protocol-design.md`` §4.1·§5.
"""
