"""axdt.protocol.inject — ``IDLE`` 게이트 뒤에서 메시지를 주입하는 골격.

라이브 배선(실제 세션에 대고 ``poll_state`` → ``clear_input`` →
``send_text`` → ``submit`` → 이탈 관측을 실행하는 것)은 아직 하지 않는다.
상태판정(``IDLE`` 게이트) 자체가 Phase 5의 훅 기반 재설계 대상이라(§8.3a
재-시퀀싱, ``WIP/handoff-state-detection-redesign.md``), 지금 배선하면
재설계 후 다시 바꿔야 한다. 이 모듈은 계약(타입·시그니처·게이트 규칙·
docstring)만 확정한다(§4.1).

측정되지 않은 거동(예: ``BUSY`` 세션에 프롬프트를 밀어넣으면 무슨 일이
벌어지는지)을 참으로 단정하지 않는다 — docstring은 §4.1이 정한 규약을
서술할 뿐, 실측 결과를 서술하지 않는다.
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from axdt.agent_runner.runner import AgentRunner
    # ProjectLock: §4.1이 참조하는 타입이나 이 코드베이스에는 아직 없다
    # (실측: 저장소 전체에 ProjectLock 정의가 없음, 2026-07 기준). 정의될
    # 모듈이 정해지면 여기서 실제 import로 바꾼다. 그때까지는 아래
    # inject()의 ``lock`` 인자 주석이 그 자리를 대신한다.

__all__ = ["InjectResult", "inject"]


class InjectResult(Enum):
    """``inject()``의 결과. §4.1 상태 게이트 표 + 제출 증거 표."""

    SENT = "sent"                  # 제출 후 IDLE 이탈 관측
    UNCONFIRMED = "unconfirmed"    # 제출했으나 증거 미관측. 계측일 뿐 분기 아님(§4.1)
    DEFERRED = "deferred"          # BUSY·STARTING, 또는 락 획득 실패
    UNAVAILABLE = "unavailable"    # ERROR·STOPPED. 재기동이 먼저
    NEEDS_HUMAN = "needs_human"    # WAITING_INPUT. 승인이 걸려 있다


def inject(
    lock: "ProjectLock",
    runner: "AgentRunner",
    message: str,
    *,
    confirm_timeout_s: float,
) -> InjectResult:
    """``IDLE`` 게이트를 통과한 세션에 message를 주입하고 제출 증거를 관측한다.

    수행 순서(§4.1):

    1. ``runner.poll_state()``로 게이트한다. ``IDLE``이 아니면 즉시 표의
       결과를 반환한다 — ``BUSY``/``STARTING`` → ``DEFERRED``,
       ``WAITING_INPUT`` → ``NEEDS_HUMAN``, ``ERROR``/``STOPPED`` →
       ``UNAVAILABLE``.
    2. 입력창을 비우기(``clear_input``) 직전에 **재폴링**한다. 게이트 통과
       뒤 세션이 ``WAITING_INPUT``으로 전이했다면, 삭제 키+Enter가 권한
       프롬프트에 대한 응답(의도치 않은 승인)이 될 수 있다. 재폴링에서
       ``IDLE``이 아니면 아무것도 보내지 않고 그 상태의 결과를 반환한다.
    3. ``clear_input()``으로 입력창의 잔류물을 지운다 — 이전 주입자가
       타이핑 중 죽었거나 경합에서 진 경우의 접합(A본문+B본문 한 줄 제출)
       을 막는다. 삭제 키는 ``Esc``를 쓰지 않는다(§4.1 — 이 TUI들에서
       ``Esc``는 생성 인터럽트/다이얼로그 닫기를 겸한다).
    4. ``send_text(message)``로 본문(개행 없는 단일행)을 ``send-keys -l``
       경로로 보낸다. 제출 개행은 붙이지 않는다.
    5. ``submit()``을 별도 키 이벤트로 보낸다. 타이핑과 제출을 분리해야
       제출이 독립 사건으로 관측 가능해진다.
    6. ``submit()`` 반환 후 상한 ``confirm_timeout_s`` 동안 ``IDLE``에서의
       이탈을 관측한다. ``BUSY``/``WAITING_INPUT``으로 전이 → ``SENT``.
       ``ERROR``/``STOPPED``로 전이 → ``UNAVAILABLE``. 상한까지 ``IDLE``
       유지 → ``UNCONFIRMED``.

    락 규율: 이 함수는 락을 **잡지 않고 이미 잡힌 것을 받는다** — 1의 첫
    ``poll_state()`` 게이트부터 5의 ``submit()`` 반환까지가 한 임계구역이고,
    내부에서 다시 잡으면 교착하거나 TOCTOU가 열린다(§7.3). 보유 상한을
    넘긴 경우의 처리는 호출자(락 획득자) 쪽 책임이다.

    멱등 없음: 이 함수는 캡처 로그를 읽지 않는다 — "이미 보냈는가"를 로그로
    확인하지 않는다. 멱등은 이 층에 없다. 그 위의 수렴 층(``converge``)이
    "다음 주기가 같은 관측이면 같은 지시를 다시 낸다"로 흡수한다(§4.1).
    ``SKIPPED``나 ``already_sent`` 같은 결과가 없는 이유이기도 하다.

    Args:
        lock: 이미 획득된 프로젝트 락(``ProjectLock``). 이 함수는 락을
            잡지도 놓지도 않는다 — 호출자가 관리한다.
        runner: 대상 세션의 ``AgentRunner``.
        message: 주입할 단일행 메시지(``message.render_*``의 결과).
        confirm_timeout_s: 제출 증거를 관측할 상한(초).

    스켈레톤: 라이브 ``IDLE`` 게이트 배선은 Phase 5 훅 기반 ``poll_state``
    재설계 이후 구현한다(§8.3a 재-시퀀싱,
    ``WIP/handoff-state-detection-redesign.md``). 지금은 호출 시
    ``NotImplementedError``를 던진다.
    """
    raise NotImplementedError(
        "inject: 라이브 IDLE 게이트 배선은 Phase 5 훅 기반 poll_state "
        "재설계 이후 구현한다 — §8.3a 재-시퀀싱, "
        "WIP/handoff-state-detection-redesign.md"
    )
