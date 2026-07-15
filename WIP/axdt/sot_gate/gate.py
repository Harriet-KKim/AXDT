"""evaluate_gate — SoT 완료 강제 게이트의 순수 코어(§2.6, §3). 호스트 접근 없음, 부작용 없음.

분기는 셋이다(§2.6):
  - meta.state != OPEN                 -> RED('pr not open')
  - meta.touches_sot                   -> SoT 검사(①②③ 전부, fail-closed 항목 1~11)
  - meta.touches_enforcement_surface    -> 강제-필수 경로 검사(①② 없이): 포크 거부 + 결정권자 승인
  - 그 밖                               -> GREEN (pass-through)

결정권(admin ∧ 명단 ∧ 사람)은 원시 사실로부터 코어가 계산한다:
  authorized(x) = (x.*_role == 'admin') ∧ (x.author/approver in inputs.allowlist) ∧ x.*_is_human
"""
import re

from axdt.git_host.state import PullRequestState

from axdt.sot_gate.models import GateStatus, GateOutcome, GateInputs, SOT_BRANCH_RE

_SOT_BRANCH_RE = re.compile(SOT_BRANCH_RE)


def _green() -> GateOutcome:
    return GateOutcome(status=GateStatus.GREEN, reason="")


def _red(reason: str) -> GateOutcome:
    return GateOutcome(status=GateStatus.RED, reason=reason)


def _authorized(role: str, actor: str, is_human: bool, allowlist: "frozenset[str]") -> bool:
    """authorized(x) = (x.*_role == 'admin') ∧ (x.author/approver in allowlist) ∧ x.*_is_human (§2.7)."""
    return role == "admin" and actor in allowlist and is_human


def _valid_sot_approval_exists(inputs) -> bool:
    """③ = 유효 승인 존재.
    유효 승인 = approved_judgment == landing_judgment ∧ authorized(approval)
               ∧ approver != meta.author ∧ not dismissed."""
    author = inputs.meta.author
    for approval in inputs.approvals:
        if approval.dismissed:
            continue
        if approval.approved_judgment != inputs.landing_judgment:
            continue
        if approval.approver == author:
            continue
        if not _authorized(approval.approver_role, approval.approver, approval.approver_is_human, inputs.allowlist):
            continue
        return True
    return False


def _resolve_open_blocking(inputs, artifact) -> "GateOutcome | None":
    """각 open_blocking을 유효 결정으로 대조한다(항목 8·11·9). 위반이 없으면 None.

    유효 결정 = 완전 결속 키 일치 ∧ authorized(decision) ∧ author != meta.author
               ∧ not deleted ∧ comment_id 최대.

    검사 순서(A5: fail-closed 번호 순서에 맞춤 — 모두 RED라 안전엔 무해):
      항목 8  미대조 — 유효 결정이 하나도 없는 open_blocking (모든 blocking 먼저)
      항목 11 결정론 — 같은 완전 결속 키의 valid 후보 중 동일 comment_id가 둘 이상이면
              (결정값이 같든 다르든) 미해결 RED. winner 선정 이전에 검사한다(§3 계약).
              valid(authorized·자기결정 아님·not deleted) 한정 — 미인가·자기결정·삭제 후보를
              넣으면 결정권 없는 계정이 상충 하나로 PR을 영구 차단하는 서비스 거부가 된다(§2.7).
      항목 9  변조 — 현재 유효본(유일 최대 comment_id winner)이 updated_at != created_at (§2.7 좁은 정의)
    """
    author = inputs.meta.author
    allowlist = inputs.allowlist

    # 항목 8: 모든 open_blocking의 미대조를 먼저 검사하고, 통과분의 valid 후보를 보존한다.
    resolved = []                       # 각 open_blocking의 valid 후보 리스트(순서 보존)
    for blocking in artifact.open_blocking:
        candidates = [d for d in inputs.decisions if d.key == blocking.key]
        valid = [
            d for d in candidates
            if not d.deleted
            and d.author != author
            and _authorized(d.author_role, d.author, d.author_is_human, allowlist)
        ]
        if not valid:
            return _red("unresolved blocking finding")
        resolved.append(valid)

    # 항목 11: valid 후보 중 동일 comment_id 중복이면 결정값 무관 미해결 RED(winner 선정 이전).
    for valid in resolved:
        comment_ids = [d.comment_id for d in valid]
        if len(set(comment_ids)) != len(comment_ids):
            return _red("conflicting decisions at same comment_id")

    # 항목 9: 유일 최대 comment_id winner의 변조 검사.
    for valid in resolved:
        winner = max(valid, key=lambda d: d.comment_id)
        if winner.updated_at != winner.created_at:
            return _red("tampered decision")

    return None


def _evaluate_sot(inputs) -> GateOutcome:
    """SoT 검사 — §2.6의 fail-closed 목록(항목 2~11)을 순서대로."""
    meta = inputs.meta

    if not _SOT_BRANCH_RE.fullmatch(meta.head_ref):                       # 항목 2
        # fullmatch: `$` 앵커가 끝개행("sot/x\n")을 통과하던 false-GREEN 방지(A3, §2.6)
        return _red("invalid head_ref")

    if meta.head_repo != inputs.target_repo:
        return _red("fork")                                               # 항목 3

    artifact = inputs.artifact
    if artifact is None:
        return _red("no artifact")                                        # 항목 4

    if artifact.review_clear != (len(artifact.open_blocking) == 0):
        return _red("artifact invariant violated")                        # 항목 5

    if not artifact.format_ok:
        return _red("format not ok")                                      # 항목 6

    if artifact.judgment != inputs.landing_judgment:
        return _red("artifact judgment mismatch")                         # 항목 7

    blocking_violation = _resolve_open_blocking(inputs, artifact)          # 항목 8·9·11
    if blocking_violation is not None:
        return blocking_violation

    if not _valid_sot_approval_exists(inputs):
        return _red("no valid approval")                                  # 항목 10

    return _green()


def _evaluate_enforcement_surface(inputs) -> GateOutcome:
    """강제-필수 경로 검사(①② 없이): head_repo == target_repo ∧ 결정권자 승인 존재, 아니면 RED."""
    meta = inputs.meta

    if meta.head_repo != inputs.target_repo:
        return _red("fork")

    author = meta.author
    for approval in inputs.approvals:
        if approval.dismissed:
            continue
        if approval.approver == author:
            continue
        if _authorized(approval.approver_role, approval.approver, approval.approver_is_human, inputs.allowlist):
            return _green()

    return _red("no authorized approval")


def evaluate_gate(inputs: GateInputs) -> GateOutcome:
    """①∧②∧③를 착지 판정 키에서 계산한다. 부작용 없음(§3).

    사전 분기(§2.6 "분기는 셋이다"):
      - meta.state != OPEN                     -> RED('pr not open')
      - meta.touches_sot                       -> 아래 SoT 검사(①②③ 전부)
      - meta.touches_enforcement_surface       -> 강제-필수 경로 검사(①② 없이):
           head_repo == target_repo ∧ (authorized(승인) ∧ approver != meta.author
           ∧ not dismissed)  아니면 RED
      - 그 밖                                   -> GREEN (pass-through)

    결정권(admin ∧ 명단 ∧ 사람)은 원시 사실로부터 코어가 계산한다:
      authorized(x) = (x.*_role == 'admin') ∧ (x.author/approver in inputs.allowlist)
                      ∧ x.*_is_human

    SoT 검사 — §2.6의 fail-closed 목록을 순서대로:
      항목 2  head_ref가 SOT_BRANCH_RE에 fullmatch되지 않음
      항목 3  head_repo != target_repo (포크)
      항목 4  artifact is None
      항목 5  산출물 불변식 위반: review_clear != (open_blocking == ())
      항목 6  artifact.format_ok 거짓 (= ①형식)
      항목 7  artifact.judgment != landing_judgment
      항목 8·11·9  각 open_blocking을 유효 결정으로 대조 (= ②검토)
           유효 결정 = 완전 결속 키 일치 ∧ authorized(decision)
                      ∧ author != meta.author ∧ not deleted ∧ comment_id 최대
           같은 완전 결속 키의 valid 후보 중 동일 comment_id가 둘 이상이면 미해결 RED(결정론, 항목 11)
           변조 = 현재 유효본으로 선택될 결정이 updated_at != created_at -> RED (항목 9, §2.7)
      항목 10  유효 승인 존재 (= ③승인)
           유효 승인 = approved_judgment == landing_judgment ∧ authorized(approval)
                      ∧ approver != meta.author ∧ not dismissed
    """
    meta = inputs.meta

    if meta.state != PullRequestState.OPEN:
        return _red("pr not open")

    if meta.touches_sot:
        return _evaluate_sot(inputs)

    if meta.touches_enforcement_surface:
        return _evaluate_enforcement_surface(inputs)

    return _green()
