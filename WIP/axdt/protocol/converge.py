"""axdt.protocol.converge — 관측→지시 결정 골격.

Leader 세션·report·progress로부터 한 주기의 관측(``Observation``)을 만들고,
그 관측에서 필요한 지시(배정/반려) 또는 블로커를 결정한다(§4.1).

멱등은 메시지 단위가 아니라 상태 수렴이다 — "이 지시를 보냈던가"가 아니라
"이 지시가 지금도 필요한가"를 묻는다(§11 결정 지점). 그래서 이 층에는 전달
기록도, 재시도 횟수도 없다. 같은 관측은 같은 지시를 낳고, 지시가 이미
전달돼 상태가 실제로 바뀌었다면 다음 주기의 관측 자체가 달라져 지시도
달라진다.

``Observation``의 생산자인 ``observe()``는 Phase 4(``recover``)의
``reconstruct``·canonical report 접근자와 Phase 5(``AgentState``) 판정에
의존한다. 그 통합이 아직이므로, 이 모듈은 타입·시그니처·docstring만
확정하고 본문은 스켈레톤이다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from axdt.agent_runner.state import AgentState

__all__ = [
    "Observation",
    "Instruction",
    "Blocker",
    "Decision",
    "materialize_report",
    "probe_report_blob",
    "rejecting_commit",
    "rework_pushed",
    "observe",
    "needed_instruction",
]


@dataclass(frozen=True)
class Observation:
    """한 task에 대한 한 주기의 관측 스냅샷. §4.1 결정표의 입력."""

    task: str
    plan_exists: bool
    progress: str | None
    """progress.md 행의 status. 행이 없으면 None."""
    report: str | None
    """recover.TaskState.report (canonical report.status). 부재·파손이면 None."""
    report_invalid: bool
    """canonical report가 있으나 파싱실패/id불일치/비통제 status."""
    rework_pushed: bool | None
    """progress != "rejected"면 None.

    progress == "rejected"인데 (a) 반려 커밋을 못 찾거나, (b) 현재 자재화
    report가 부재하거나, (c) 반려 커밋은 찾았지만 그 커밋 트리에 report
    블롭이 없어 비교 불가면 None — 세 경우 모두 "박제와 다름=참"으로
    오판하지 않는다(§4.1 결정표 행 8).
    """
    session: AgentState
    """세션의 현재 상태(poll_state 결과)."""


@dataclass(frozen=True)
class Instruction:
    """보낼 지시(배정 또는 반려) 메시지. ``message.render_*``의 결과를 담는다."""

    message: str


@dataclass(frozen=True)
class Blocker:
    """자동 처리할 수 없어 사람에게 올리는 사유."""

    reason: str
    obs: Observation


# 결정표의 출력은 세 갈래다. "보낼 것 없음"과 "사람을 불러야 함"은 다르다
# (§11 결정 지점: "needed_instruction의 반환은 세 갈래다").
Decision = Instruction | Blocker | None


def materialize_report(
    root: Path, task: str
) -> Literal["ok", "absent", "unavailable"]:
    """허브 task 브랜치의 report 블롭을 작업트리에 자재화한다(§4.1).

    ``git fetch <허브경로> '+refs/heads/<BR>:refs/remotes/hub/<BR>'`` 후
    ``git show``로 읽어 임시 파일에 쓰고, 성공한 경우에만 같은 디렉터리
    안에서 원자적 rename(``os.replace``)으로 대상 경로에 놓는다.
    ``git show > 대상파일``처럼 직접 리다이렉트하지 않는다 — show가
    실패해도 리다이렉트가 실행 전에 대상을 0바이트로 절단해
    "unavailable=작업트리 불변" 계약을 깬다.

    결과는 셋으로 가른다:
    - ``"ok"``: fetch 성공 + 경로가 트리에 존재 + show 성공. 자재화 완료.
    - ``"absent"``: ``git ls-remote``로 브랜치 부재를 확증했거나, fetch는
      성공했는데 그 커밋 트리에 경로가 없음. 이때만 작업트리 파일을
      **삭제**한다(빈·낡은 파일은 무효 판정이나 오판된 완료로 이어진다).
    - ``"unavailable"``: 브랜치는 있는데 fetch가 실패(일시 오류). 작업트리를
      건드리지 않는다.

    부재와 일시 실패 모두 ``git show``의 종료 코드로는 못 가른다(둘 다
    exit 128) — ``ls-remote``의 **출력**(부재 브랜치는 exit 0에 빈 출력)과
    fetch 후 ``git cat-file -e``의 경로 존재 확인으로 가른다.

    스켈레톤: 허브 fetch·원자적 자재화는 Phase 4 recover 통합 시
    구현한다. 지금은 호출 시 NotImplementedError를 던진다.
    """
    raise NotImplementedError(
        "materialize_report: 허브 fetch·원자적 자재화는 Phase 4 recover "
        "통합 시 구현한다(§4.1)"
    )


def probe_report_blob(
    root: Path, task: str
) -> str | Literal["absent", "unavailable"]:
    """허브 task 브랜치 report 블롭의 git object-id만 읽어 온다.

    **작업트리를 쓰지 않는다.** ``git fetch`` 후
    ``git rev-parse refs/remotes/hub/<BR>:<path>``로 블롭 object-id만 얻는다
    (파일 미기록). object-id(내용 주소, SHA)이므로 같은 내용은 같은 id,
    다른 내용은 다른 id다 — 바이트 동일성 대조를 구성적으로 준다.

    결과:
    - object-id(str): 블롭 존재.
    - ``"absent"``: ``ls-remote``로 브랜치 부재 확증, 또는 fetch 성공 후
      ``cat-file -e``가 경로 부재.
    - ``"unavailable"``: 브랜치는 있는데 fetch 실패(일시 오류).
      ``materialize_report``와 같은 오라클(ls-remote 출력·cat-file 확인)로
      가른다.

    ``rev-parse``는 반드시 **종료 코드**로 성공을 판정한다 — 실패 시(부재
    등) exit 128이면서도 stdout에 리터럴 인자를 에코하므로, exit 미검사로
    stdout만 읽으면 가짜 해시가 나온다.

    스켈레톤: materialize_report와 동일한 허브 접근 계층에 속하므로 Phase 4
    recover 통합 시 함께 구현한다. 지금은 호출 시 NotImplementedError를
    던진다.
    """
    raise NotImplementedError(
        "probe_report_blob: 허브 blob object-id 조회는 Phase 4 recover "
        "통합 시 구현한다(§4.1, §7.4)"
    )


def rejecting_commit(repo: Path, task: str) -> str | None:
    """이 task를 ``rejected``로 전이시킨 최신 마일스톤 커밋의 sha.

    ``git log``로 커밋 메시지를 라이브 조회해 찾는다(별도 저장소·캐시
    없음). ``format_milestone_message``(``commit.py``)가 내는 두 형식을
    모두 인식해야 한다:

    - 단일 이벤트: subject ``chore(progress): <task> <before>-><after>``
      (화살표 앞뒤 공백 없음).
    - 배치: subject ``chore(progress): batch <n> events`` + 본문 줄
      ``- <task>: <before> -> <after>``(화살표 앞뒤 공백 있음).

    ``after == "rejected"``인 전이만 잡는다 — 재개 전이(``rejected->
    in-progress``)는 제외한다. task id는 정확히 앵커링해서 ``w1.t1``이
    ``w1.t10``의 접두 문자열로 오매칭되지 않게 한다. 자유 텍스트
    ``Reason:`` 줄과 배치의 ``Gates:`` 하이픈 줄은 이벤트 줄 형태
    (``- <task>: <s> -> <e>``)와 다르므로 앵커만으로 자연히 배제된다.
    ``before``는 ``∅``일 수 있다(신규 행이 곧장 ``rejected``로 시작한
    경우, ``commit._before_repr``).

    같은 task가 여러 번 반려됐으면 **최신** 커밋의 sha를 쓴다.

    못 찾으면 ``None`` — 호출자(``observe``)는 이를 받아
    ``Observation.rework_pushed``를 ``None``으로 두고, 결정표는 행
    8(블로커)로 올린다(§4.1).

    스켈레톤: git log 라이브 조회·마일스톤 메시지 파서 구현은 Phase 4
    recover/commit 통합 시 구현한다. 지금은 호출 시 NotImplementedError를
    던진다.
    """
    raise NotImplementedError(
        "rejecting_commit: git log 라이브 조회·마일스톤 메시지 파서 구현은 "
        "Phase 4 recover/commit 통합 시 채운다(§5)"
    )


def rework_pushed(repo: Path, task: str, reject_sha: str) -> bool | None:
    """자재화한 report 블롭이 ``reject_sha``에 박제된 report 블롭과 다른가.

    main과 task 브랜치는 어느 방향으로도 서로의 조상이 아니므로 조상
    관계로는 풀 수 없다 — 블롭 내용(object-id) 비교로 판정한다. 전제:
    현재 report가 이미 자재화되어 있다(``materialize_report``가
    ``"unavailable"``이면 ``observe``는 애초에 여기까지 오지 않는다).

    반환은 ``bool | None`` 세 갈래다:

    - ``True``/``False``: 반려 커밋 트리에 report 블롭이 있어 비교 가능.
    - ``None``: **반려 커밋 트리에 report 블롭이 없으면**(``git show
      <reject_sha>:<path>`` 실패) ``True``가 아니라 ``None``을 돌려준다
      (→ 행 8 블로커). 여기를 ``True``로 두면 §4.1이 이름 붙인 B-1
      증상(반려가 재작업 완료로 오판돼 미전달)이 재발한다.

    현재 자재화된 report가 확인된 부재인 경우, ``observe``는 애초에 이
    함수를 부르지 않고 ``rework_pushed=None``으로 둔다(→ 행 8) — 부재를
    "박제와 다름=재작업"으로 오판하지 않기 위해서다.

    스켈레톤: git show/rev-parse 기반 블롭 비교 구현은 Phase 4
    recover/commit 통합 시 구현한다. 지금은 호출 시 NotImplementedError를
    던진다.
    """
    raise NotImplementedError(
        "rework_pushed: 반려 커밋 트리의 report 블롭과의 object-id 비교 "
        "구현은 Phase 4 recover/commit 통합 시 채운다(§4.1, §5)"
    )


def observe(root: Path, task: str, session: AgentState) -> Observation | None:
    """``materialize_report`` → ``recover.reconstruct`` → plan 존재 →
    ``rework_pushed`` 순으로 한 task의 Observation을 만든다.

    프로젝트 락 안에서 돌고 milestone commit에 선행한다 — 커밋이 자재화한
    블롭을 박제하기 때문이다(§4.1·§4.5·§7.4).

    ``materialize_report``가 ``"unavailable"``이면 신뢰할 Observation을
    만들 수 없으므로 **None을 반환한다** — 호출자는 이번 주기를 건너뛰고
    (다음 fetch에 자가 복구), 반복되면 블로커로 올린다. 낡은 블롭으로
    판단하느니 미룬다.

    progress 행이 없는 task는 ``reconstruct``에 없으므로 ``progress=None``
    으로 두고, report는 자재화 후 직접 읽는다. 이를 위해 ``recover``가
    canonical report 읽기의 공개 접근자를 노출해야 한다 — 현재
    ``_read_canonical_report``는 비공개다(§4.1 결정표 행 12가 plan 유무로
    블로커를 내지만 Observation 자체는 일관되게 채운다).

    ``progress.md`` 자체가 파손돼 ``reconstruct``가
    ``table.ProgressFormatError``를 던지면 None으로 뭉개지 않고
    **전파한다** — None은 "일시적 관측 불가라 이번만 건너뜀"인데, 파손은
    그것과 달리 사람이 봐야 할 블로커이므로 호출자가 관측 불가와 구별해
    올린다.

    스켈레톤: Phase 4 recover.reconstruct·공개 접근자 통합, Phase 5
    AgentState 판정 통합 이후 구현한다. 지금은 호출 시 NotImplementedError
    를 던진다.
    """
    raise NotImplementedError(
        "observe: Phase 4 recover.reconstruct 통합 + Phase 5 AgentState "
        "판정 통합 이후 구현한다(§4.1)"
    )


def needed_instruction(obs: Observation) -> Decision:
    """§4.1 결정표를 obs에 적용해 다음 지시를 정한다.

    결정표는 ``progress`` 범주를 1차 키로 하는 상호배타 구조로 확정되어
    있다(§11 결정 지점: "결정표는 progress 범주를 1차 키로 하는 상호배타
    구조로 짠다" — progress로 분할되는 네 구간은 서로 배타적이고, 무효 행
    (§4.1 결정표 행 7)과 catch-all 행(행 18)만 구간 분할이 아니라 순서로
    자리를 지킨다). 마지막 catch-all 덕에 구성상 전함수(total function)다
    — 모든 obs에 대해 Instruction/Blocker/None 중 하나를 반환한다.

    이 함수는 ``Observation``의 순수 함수이며 측정이나 타 Phase에 의존하지
    않는다. 결정표 자체는 확정이나(§11), 그 회귀 테스트(§8.1 FakeBackend)와
    실제 관측원 ``observe()``가 함께 놓일 때 구현해야 의미가 있고, §4.1이
    이미 겪은 가림 버그를 재현 없이 피하려면 그 통합 작업에서 결정 로직을
    채우는 편이 안전하다. **측정 의존이 아니라 범위·위험 결정이다.**

    스켈레톤: 지금은 호출 시 NotImplementedError를 던진다.
    """
    raise NotImplementedError(
        "needed_instruction: §4.1 결정표 자체는 확정이나(§11), 이 함수는 "
        "Observation의 순수 함수라 측정에 의존하지 않는다 — 그 회귀 "
        "테스트(§8.1 FakeBackend)·실제 observe()와 함께 놓일 때 구현하는 "
        "것이 범위·위험상 안전해 그 통합 작업에서 채운다(§4.1)"
    )
