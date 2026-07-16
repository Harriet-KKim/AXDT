"""axdt.protocol.message — 단일행 프로토콜 메시지 렌더링.

Leader 세션에 주입할 assign/reject/note 메시지를 만든다. 순수 문자열
조립만 하고 IO·상태 조회는 하지 않는다(측정과 무관, §4.1 "메시지 형식 —
단일행, 참조 중심").

메시지는 한 줄이고 탭·캐리지리턴도 없다. 개행·탭·``\r``이 있으면
``tmux.send_text()``가 ``send-keys``가 아니라 ``paste-buffer`` 경로를 타서,
붙여넣기가 TUI에서 자리표시자로 접힐 수 있다(실측: ``tmux.py``가 셋 모두에
paste-buffer를 쓴다).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["KINDS", "token", "render_assign", "render_reject", "render_note"]

KINDS = ("assign", "reject", "note")


def _ensure_single_line(body: str) -> None:
    """body에 개행·탭·캐리지리턴이 있으면 ValueError.

    단일행 불변식을 지키는 내부 헬퍼. render_* 함수들이 조립한 본문에 대해
    호출한다(§4.1). ``\\r``도 막는 이유: ``tmux.py``는 ``\\n``·``\\r``·``\\t``
    셋 모두에서 ``send-keys``가 아니라 paste-buffer 경로를 탄다(실측).
    """
    if "\n" in body or "\t" in body or "\r" in body:
        raise ValueError(
            "message body must be a single line without tabs, newlines, "
            f"or carriage returns: {body!r}"
        )


def token(kind: str, task: str, body: str) -> str:
    """``[axdt:<kind>:<task>:<hash8>]`` — 사람이 읽는 표식.

    ``hash8``은 ``sha256(f"{kind}|{task}|{body}")``의 앞 8자(소문자 16진수)
    다. 구분자 ``|``를 넣는 이유: 넣지 않고 이으면 slug가 숫자로 끝나는
    task에서 경계가 모호해진다(§4.1).

    이 값은 **멱등 키가 아니다**. 어떤 분기도 토큰의 로그 존재 여부를 보지
    않는다 — 사람이 로그에서 메시지를 식별하는 표식이자 렌더링을 고정하는
    테스트 수단일 뿐이다(§4.1 "토큰은 남기되 오라클이 아니다").

    ``kind``가 ``KINDS``(``assign``·``reject``·``note``) 밖이면 ValueError.
    ``task``에 개행·탭·캐리지리턴이 있어도 ValueError(단일행 불변식이 토큰
    전체에 적용된다). ``task``는 ``naming.Identifier`` 문법
    (``w<n>.t<n>-<slug>``)을 전제하며 ``:``·``]``를 포함하지 않아야 한다 —
    토큰의 구분자·닫힘괄호와 충돌하므로, 그 보장은 **호출자 책임**이다(여기
    서는 검사하지 않는다).
    """
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {KINDS}")
    _ensure_single_line(task)
    digest = hashlib.sha256(f"{kind}|{task}|{body}".encode()).hexdigest()
    hash8 = digest[:8]
    return f"[axdt:{kind}:{task}:{hash8}]"


def render_assign(task: str, plan: Path) -> str:
    """task 배정 메시지. 단일행.

    목표와 완료 조건은 plan 파일에 있다 — 본 함수는 전달 형식만 만들고,
    durable 기록(plan 자체)은 이 함수의 소관이 아니다(§4.1).

    ``plan``은 항상 POSIX 구분자(``/``)로 렌더한다(``plan.as_posix()``) —
    Windows에서 ``str(plan)``은 ``\\``를 써서 §4.1 예시(``docs/interim/
    plan/...``)와 어긋난다. 플랫폼에 무관하게 같은 메시지를 낸다.
    """
    body = f"task 배정. {plan.as_posix()} 를 읽고 착수하라."
    _ensure_single_line(body)
    return f"{token('assign', task, body)} {body}"


def render_reject(task: str, reason_commit: str) -> str:
    """report 반려 메시지. 단일행.

    반려 사유 자체는 Phase 4가 정한 대로 ``rejected`` 전이의 마일스톤 커밋
    메시지에 있다 — 본 함수는 그 커밋을 가리키기만 하고, 사유의 durable
    기록은 Phase 4 소관이다(§4.1).
    """
    body = (
        f"report 반려. 커밋 {reason_commit} 의 메시지에서 사유를 확인하고 "
        "재작업하라."
    )
    _ensure_single_line(body)
    return f"{token('reject', task, body)} {body}"


def render_note(text: str) -> str:
    """자유 텍스트 노트. ``task`` 자리에는 ``-``를 쓴다(§4.1).

    text에 개행·탭이 있으면 ValueError(단일행 불변식).

    호출자 책임(여기서는 검사하지 않는다): text가 상태 마커 문자열(예:
    ``Error:``)을 포함하면 안 된다 — 어댑터의 ``detect_state``가 transcript
    에서 그런 문자열을 찾으므로, 에코되면 상태 판정이 오염된다(§4.1 "자유
    텍스트가 상태 마커 문자열을 품으면 안 된다").
    """
    _ensure_single_line(text)
    return f"{token('note', '-', text)} {text}"
