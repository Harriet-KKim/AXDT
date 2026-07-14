"""Tests for sot_gate.gate.evaluate_gate — 순수 코어의 fail-closed 목록(§2.6) + 분기 셋(§6 test_gate a~y).

기본 픽스처(§6 첫 줄 조건): touches_sot=True・head_ref="sot/x"・head_repo==target_repo・
결정자/승인자 != PR작성자・role_name=="admin"・is_human=True・allowlist 등재・세 판정 키(착지·산출물·승인) 일치.
각 테스트는 이 기본에서 한 요소만 바꾼다.
"""
from axdt.git_host.state import PullRequestState

from axdt.sot_gate.keys import JudgmentKey, FullBindingKey
from axdt.sot_gate.models import (
    GateStatus,
    FindingDecision,
    BlockingFinding,
    CIArtifact,
    ChannelDecision,
    ApprovalEvent,
    PRMetadata,
    GateInputs,
)
from axdt.sot_gate.gate import evaluate_gate


AUTHOR = "author-1"
REVIEWER = "reviewer-1"
TARGET_REPO = "org/repo"
DEFAULT_JUDGMENT = JudgmentKey(tree_hash="tree-1", rule_fingerprint="rule-1")


def _judgment(tree="tree-1", rule="rule-1"):
    return JudgmentKey(tree_hash=tree, rule_fingerprint=rule)


def _meta(**overrides):
    fields = dict(
        author=AUTHOR,
        head_ref="sot/x",
        head_repo=TARGET_REPO,
        head_sha="sha-1",
        state=PullRequestState.OPEN,
        touches_sot=True,
        touches_enforcement_surface=False,
    )
    fields.update(overrides)
    return PRMetadata(**fields)


def _artifact(judgment=DEFAULT_JUDGMENT, **overrides):
    fields = dict(judgment=judgment, format_ok=True, review_clear=True, open_blocking=())
    fields.update(overrides)
    return CIArtifact(**fields)


def _approval(judgment=DEFAULT_JUDGMENT, **overrides):
    fields = dict(
        approver=REVIEWER, approved_judgment=judgment, seq=1,
        approver_role="admin", approver_is_human=True, dismissed=False,
    )
    fields.update(overrides)
    return ApprovalEvent(**fields)


def _finding(judgment=DEFAULT_JUDGMENT, finding_id="F-1", digest="digest-1"):
    return FullBindingKey(judgment=judgment, finding_id=finding_id, content_digest=digest)


def _decision(key, decision=FindingDecision.ACCEPTED, author=REVIEWER, comment_id=1,
              created_at="2026-01-01T00:00:00Z", updated_at=None, deleted=False,
              author_role="admin", author_is_human=True):
    if updated_at is None:
        updated_at = created_at
    return ChannelDecision(
        key=key, decision=decision, author=author, comment_id=comment_id,
        created_at=created_at, updated_at=updated_at, deleted=deleted,
        author_role=author_role, author_is_human=author_is_human,
    )


def _inputs(**overrides):
    judgment = overrides.get("landing_judgment", DEFAULT_JUDGMENT)
    fields = dict(
        landing_judgment=judgment,
        target_repo=TARGET_REPO,
        allowlist=frozenset({REVIEWER}),
        meta=_meta(),
        artifact=_artifact(judgment),
        decisions=(),
        approvals=(_approval(judgment),),
    )
    fields.update(overrides)
    return GateInputs(**fields)


def _status(inputs):
    return evaluate_gate(inputs).status


# (a) review_clear + format_ok + 유효 승인 -> GREEN.
def test_a_all_clear_valid_approval_green():
    assert _status(_inputs()) == GateStatus.GREEN


# (b) open blocking 전부 accepted/rejected(유효 결정) -> GREEN.
def test_b_open_blocking_all_resolved_by_valid_decisions_green():
    key1 = _finding(finding_id="F-1", digest="digest-1")
    key2 = _finding(finding_id="F-2", digest="digest-2")
    artifact = _artifact(open_blocking=(BlockingFinding(key1), BlockingFinding(key2)), review_clear=False)
    decisions = (
        _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=1),
        _decision(key2, decision=FindingDecision.REJECTED, comment_id=1),
    )
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.GREEN


# (c) open blocking 중 하나가 미대조 -> RED.
def test_c_open_blocking_unresolved_red():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    inputs = _inputs(artifact=artifact, decisions=())
    assert _status(inputs) == GateStatus.RED


# (d) 결정자의 현재 role_name != admin / allowlist 밖 / 기계 계정 -> 결정권 미충족 -> 폐기 -> RED.
def test_d_decision_role_not_admin_red():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (_decision(key1, author_role="write"),)
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.RED


def test_d_decision_author_not_in_allowlist_red():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (_decision(key1, author="outsider"),)
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.RED


def test_d_decision_machine_account_red():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (_decision(key1, author_is_human=False),)
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.RED


# (d2) 결정자가 현재 role_name==admin ∧ allowlist 등재 ∧ 사람 -> 유효 -> GREEN.
# 게이트는 표시 시점 권한을 추적하지 않고 현재 원시 사실만 입력받으므로 승격은 소급 유효화된다(§2.7).
def test_d2_decision_currently_authorized_promotion_retroactive_green():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (_decision(key1, author_role="admin", author_is_human=True, author=REVIEWER),)
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.GREEN


# (e) supersession: 같은 완전 결속 키에 최대 comment_id가 이긴다 — 변조로 관측 가능하게(B1).
# older(낮은 comment_id, 편집됨) + newer(높은 comment_id, 깨끗) -> 최대가 이기고 깨끗 -> GREEN.
# older의 편집은 winner가 아니라 무시된다(min/first를 골랐다면 RED가 나 실패).
def test_e_supersession_max_comment_id_wins_clean_green():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (
        _decision(key1, decision=FindingDecision.REJECTED, comment_id=1, created_at="t1", updated_at="t2"),
        _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=2, created_at="t3", updated_at="t3"),
    )
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.GREEN


# (e') 반대 배치: older(깨끗) + newer(편집됨) -> 최대(newer)가 이기는데 변조 -> RED.
# 이 쌍이 max 선택을 고정한다(min/first면 GREEN이 나 실패).
def test_e_supersession_max_comment_id_wins_tampered_red():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (
        _decision(key1, decision=FindingDecision.REJECTED, comment_id=1, created_at="t1", updated_at="t1"),
        _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=2, created_at="t3", updated_at="t4"),
    )
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.RED


# (f) approved_judgment != landing_judgment -> RED.
def test_f_approved_judgment_mismatch_red():
    inputs = _inputs(approvals=(_approval(_judgment(rule="rule-mismatch")),))
    assert _status(inputs) == GateStatus.RED


# (f2) artifact.judgment != landing_judgment(트리 같고 rule 지문만 다름) -> RED — 판정 키 성분 불일치.
def test_f2_artifact_judgment_rule_fingerprint_mismatch_red():
    mismatched = _artifact(_judgment(tree="tree-1", rule="rule-2"))
    inputs = _inputs(artifact=mismatched)
    assert _status(inputs) == GateStatus.RED


# (g) artifact=None -> RED.
def test_g_artifact_none_red():
    inputs = _inputs(artifact=None)
    assert _status(inputs) == GateStatus.RED


# (h) format_ok=False -> RED.
def test_h_format_not_ok_red():
    inputs = _inputs(artifact=_artifact(format_ok=False))
    assert _status(inputs) == GateStatus.RED


# (i) 완전 결속 키의 finding_id/digest가 산출물과 다른 결정 -> 대조 실패 -> RED.
def test_i_decision_digest_mismatch_unresolved_red():
    ob_key = _finding(finding_id="F-1", digest="digest-correct")
    wrong_key = _finding(finding_id="F-1", digest="digest-WRONG")
    artifact = _artifact(open_blocking=(BlockingFinding(ob_key),), review_clear=False)
    decisions = (_decision(wrong_key),)
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.RED


# (j) head_ref가 sot/<slug> 정규식에 안 맞음 -> RED. sot/A_B・sot/x/y・sot/도 거부.
def test_j_invalid_head_ref_red():
    for bad_ref in ("sot/A_B", "sot/x/y", "sot/"):
        inputs = _inputs(meta=_meta(head_ref=bad_ref))
        assert _status(inputs) == GateStatus.RED, f"head_ref={bad_ref!r} should be RED"


# (j') A3/Fable m1: head_ref="sot/x\n" — $ 앵커가 끝개행을 통과하던 false-GREEN을 잡는다.
def test_j_head_ref_trailing_newline_red():
    inputs = _inputs(meta=_meta(head_ref="sot/x\n"))
    assert _status(inputs) == GateStatus.RED


# (k) 승인자가 role_name != admin / allowlist 밖 / 기계 계정 -> RED. 결정권 논리곱은 코어가 계산한다.
def test_k_approver_role_not_admin_red():
    inputs = _inputs(approvals=(_approval(approver_role="write"),))
    assert _status(inputs) == GateStatus.RED


def test_k_approver_not_in_allowlist_red():
    inputs = _inputs(approvals=(_approval(approver="outsider"),))
    assert _status(inputs) == GateStatus.RED


def test_k_approver_machine_account_red():
    inputs = _inputs(approvals=(_approval(approver_is_human=False),))
    assert _status(inputs) == GateStatus.RED


# (l) 결정 author == PR author -> 폐기 -> RED. 승인자 == PR author -> RED.
# B2: PR author도 admin·allowlist·human을 모두 만족시키고 **자기 동일성만** 실패 요인이 되게 한다.
# 그러면 자기결정 차단 로직을 지웠을 때 GREEN이 되어 이 규칙을 실제로 격리한다.
def test_l_decision_author_equals_pr_author_red():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (_decision(key1, author=AUTHOR, author_role="admin", author_is_human=True),)
    inputs = _inputs(
        artifact=artifact, decisions=decisions,
        allowlist=frozenset({REVIEWER, AUTHOR}),   # author도 authorization은 통과 — 자기동일성만 실패
    )
    assert _status(inputs) == GateStatus.RED


def test_l_approver_equals_pr_author_red():
    inputs = _inputs(
        approvals=(_approval(approver=AUTHOR),),
        allowlist=frozenset({REVIEWER, AUTHOR}),   # approver도 authorization은 통과 — 자기동일성만 실패
    )
    assert _status(inputs) == GateStatus.RED


# (m) 산출물 불변식 위반(review_clear=True + blocking != () 또는 그 역) -> RED.
def test_m_invariant_violation_clear_true_with_blocking_red():
    artifact = _artifact(review_clear=True, open_blocking=(BlockingFinding(_finding()),))
    inputs = _inputs(artifact=artifact)
    assert _status(inputs) == GateStatus.RED


def test_m_invariant_violation_clear_false_with_no_blocking_red():
    artifact = _artifact(review_clear=False, open_blocking=())
    inputs = _inputs(artifact=artifact)
    assert _status(inputs) == GateStatus.RED


# (n) 현재 유효본으로 선택될 결정이 편집됨(updated_at != created_at) -> RED(변조, §2.7).
def test_n_tampered_current_winner_red():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (_decision(key1, created_at="t1", updated_at="t2"),)
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.RED


# (n2) 무관한 코멘트가 편집·삭제됨(유효본도 아니고 open blocking을 닫지도 않음) -> GREEN.
def test_n2_tampered_irrelevant_comment_green():
    key1 = _finding(finding_id="F-1", digest="digest-1")
    stale_unrelated_key = _finding(finding_id="F-999", digest="digest-999")
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (
        _decision(key1, comment_id=2, created_at="t1", updated_at="t1"),          # 유효본, 변조 없음
        _decision(stale_unrelated_key, comment_id=5, created_at="t1", updated_at="t9"),  # 무관, 변조됨
    )
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.GREEN


# (n3) 낡은 판정 키에 붙은 결정이 변조됨 -> 현재 대조 대상이 아니므로 GREEN.
def test_n3_tampered_stale_judgment_key_green():
    stale_judgment = JudgmentKey(tree_hash="tree-OLD", rule_fingerprint="rule-OLD")
    current_key = _finding(finding_id="F-1", digest="digest-1")
    stale_key = _finding(judgment=stale_judgment, finding_id="F-1", digest="digest-1")
    artifact = _artifact(open_blocking=(BlockingFinding(current_key),), review_clear=False)
    decisions = (
        _decision(current_key, comment_id=1, created_at="t1", updated_at="t1"),   # 유효본, 변조 없음
        _decision(stale_key, comment_id=2, created_at="t1", updated_at="t9"),      # 낡은 판정 키, 변조됨
    )
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.GREEN


# (n4) 유효본을 닫던 결정이 삭제됨 -> 대조에서 빠져 open blocking이 미대조 -> RED(항목 8, 변조 아님).
def test_n4_valid_decision_deleted_unresolved_red():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (_decision(key1, comment_id=1, deleted=True),)
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.RED


# (o) pr_state != OPEN -> RED('pr not open').
def test_o_pr_not_open_red_with_exact_reason():
    inputs = _inputs(meta=_meta(state=PullRequestState.CLOSED))
    outcome = evaluate_gate(inputs)
    assert outcome.status == GateStatus.RED
    assert outcome.reason == "pr not open"


# (p) 같은 완전 결속 키・동일 comment_id 상충 결정 -> 미해결로 RED(결정론).
def test_p_conflicting_decisions_same_comment_id_red():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (
        _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=5, author=REVIEWER),
        _decision(key1, decision=FindingDecision.REJECTED, comment_id=5, author="reviewer-2"),
    )
    inputs = _inputs(
        artifact=artifact,
        decisions=decisions,
        allowlist=frozenset({REVIEWER, "reviewer-2"}),
    )
    assert _status(inputs) == GateStatus.RED


# (p2) A2/Fable M1: valid 후보 중 동일 comment_id 중복이면 **결정값이 같아도** 순서 무관 RED.
# 하나가 편집돼 있어 이전 구현은 [clean,tampered]에서 winner=clean으로 GREEN을 냈다(순서 의존).
def test_p2_duplicate_comment_id_same_decision_order_independent_red():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    clean = _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=5,
                      author=REVIEWER, created_at="t1", updated_at="t1")
    tampered = _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=5,
                         author="reviewer-2", created_at="t1", updated_at="t2")
    allow = frozenset({REVIEWER, "reviewer-2"})
    for decisions in ((clean, tampered), (tampered, clean)):
        inputs = _inputs(artifact=artifact, decisions=decisions, allowlist=allow)
        assert _status(inputs) == GateStatus.RED, f"order {decisions} should be RED"


# (p3) A2/Codex 시나리오2: 동일 comment_id 상충(5,5)이 최대 comment_id(6, 정상) 아래에 있어도 RED.
# 이전 구현은 winner=id6(정상)만 봐서 놓쳤다.
def test_p3_conflict_below_max_comment_id_red():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (
        _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=5,
                  author=REVIEWER, created_at="t1", updated_at="t1"),
        _decision(key1, decision=FindingDecision.REJECTED, comment_id=5,
                  author="reviewer-2", created_at="t1", updated_at="t1"),
        _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=6,
                  author=REVIEWER, created_at="t2", updated_at="t2"),
    )
    allow = frozenset({REVIEWER, "reviewer-2"})
    inputs = _inputs(artifact=artifact, decisions=decisions, allowlist=allow)
    assert _status(inputs) == GateStatus.RED


# (q) head_repo != target_repo(포크) -> RED.
def test_q_fork_red():
    inputs = _inputs(meta=_meta(head_repo="someone-else/fork"))
    assert _status(inputs) == GateStatus.RED


# (r) touches_sot=False ∧ touches_enforcement_surface=False -> 산출물・승인 없어도 OPEN이면 GREEN(pass-through).
def test_r_pass_through_no_artifact_no_approvals_green():
    inputs = _inputs(
        meta=_meta(touches_sot=False, touches_enforcement_surface=False),
        artifact=None,
        approvals=(),
    )
    assert _status(inputs) == GateStatus.GREEN


# (s) touches_sot=False이고 pr_state != OPEN -> RED.
def test_s_not_sot_but_not_open_red():
    inputs = _inputs(meta=_meta(touches_sot=False, state=PullRequestState.CLOSED))
    outcome = evaluate_gate(inputs)
    assert outcome.status == GateStatus.RED
    assert outcome.reason == "pr not open"


# (t) 승인이 여러 개: 유효 하나 + 무효 여럿 -> GREEN. 전부 dismissed -> RED.
def test_t_multiple_approvals_one_valid_green():
    approvals = (
        _approval(approver="outsider"),
        _approval(dismissed=True),
        _approval(approver=REVIEWER),
    )
    inputs = _inputs(approvals=approvals)
    assert _status(inputs) == GateStatus.GREEN


def test_t_multiple_approvals_all_dismissed_red():
    approvals = (
        _approval(dismissed=True),
        _approval(dismissed=True, approver="reviewer-2"),
    )
    inputs = _inputs(approvals=approvals, allowlist=frozenset({REVIEWER, "reviewer-2"}))
    assert _status(inputs) == GateStatus.RED


# (u) approvals=()(승인 없음) -> RED.
def test_u_no_approvals_red():
    inputs = _inputs(approvals=())
    assert _status(inputs) == GateStatus.RED


# (v) touches_enforcement_surface=True・포크 -> RED — ①② 없이도 포크 거부.
def test_v_enforcement_surface_fork_red():
    inputs = _inputs(
        meta=_meta(touches_sot=False, touches_enforcement_surface=True, head_repo="fork/x"),
    )
    assert _status(inputs) == GateStatus.RED


# (w) touches_enforcement_surface=True・포크 아님・결정권자 승인 존재 -> GREEN(산출물・①②를 요구하지 않는다).
def test_w_enforcement_surface_authorized_approval_green():
    inputs = _inputs(
        meta=_meta(touches_sot=False, touches_enforcement_surface=True),
        artifact=None,
        approvals=(_approval(),),
    )
    assert _status(inputs) == GateStatus.GREEN


# (x) touches_enforcement_surface=True・결정권자 승인 없음(또는 승인자 결정권 미충족, 또는 승인자==PR작성자) -> RED.
def test_x_enforcement_surface_no_approvals_red():
    inputs = _inputs(
        meta=_meta(touches_sot=False, touches_enforcement_surface=True),
        artifact=None,
        approvals=(),
    )
    assert _status(inputs) == GateStatus.RED


def test_x_enforcement_surface_approver_not_authorized_red():
    inputs = _inputs(
        meta=_meta(touches_sot=False, touches_enforcement_surface=True),
        artifact=None,
        approvals=(_approval(approver_role="write"),),
    )
    assert _status(inputs) == GateStatus.RED


def test_x_enforcement_surface_approver_equals_author_red():
    # B2: approver=AUTHOR도 admin·allowlist·human을 만족 — 자기동일성만 실패 요인.
    inputs = _inputs(
        meta=_meta(touches_sot=False, touches_enforcement_surface=True),
        artifact=None,
        approvals=(_approval(approver=AUTHOR),),
        allowlist=frozenset({REVIEWER, AUTHOR}),
    )
    assert _status(inputs) == GateStatus.RED


# (y) touches_sot=False・touches_enforcement_surface=False・OPEN -> GREEN(pass-through, (r) 재확인).
def test_y_pass_through_with_artifact_and_approvals_present_green():
    inputs = _inputs(meta=_meta(touches_sot=False, touches_enforcement_surface=False))
    assert _status(inputs) == GateStatus.GREEN


# --- B3: 세 분기 배타 경계·우선순위 ---

# B3(a) 이중 플래그: touches_sot ∧ touches_enforcement_surface -> SoT 검사가 적용(상위집합, 안전).
# artifact=None이면 SoT는 RED다 — enforcement 분기가 먼저였다면 결정권자 승인만으로 GREEN이 났을 것.
def test_b3_dual_flag_sot_takes_priority_red():
    inputs = _inputs(
        meta=_meta(touches_sot=True, touches_enforcement_surface=True),
        artifact=None,
        approvals=(_approval(),),
    )
    assert _status(inputs) == GateStatus.RED


# B3(b) pass-through의 무시 값: 두 플래그 False면 head_ref 규약 위반·포크여도 OPEN이면 GREEN.
# 항목 2·3을 pass-through에서 잘못 검사하는 구현을 잡는다.
def test_b3_pass_through_ignores_head_ref_and_fork_green():
    inputs = _inputs(
        meta=_meta(touches_sot=False, touches_enforcement_surface=False,
                   head_ref="not-a-sot-branch", head_repo="someone/fork"),
        artifact=None,
        approvals=(),
    )
    assert _status(inputs) == GateStatus.GREEN


# B3(c) enforcement의 stale judgment 무시: approved_judgment != landing_judgment여도 GREEN.
# 이 분기는 판정 키 일치를 요구하지 않는다(요구하는 잘못된 구현을 잡는다).
def test_b3_enforcement_ignores_stale_judgment_green():
    inputs = _inputs(
        meta=_meta(touches_sot=False, touches_enforcement_surface=True),
        artifact=None,
        approvals=(_approval(_judgment(rule="rule-DIFFERENT")),),
    )
    assert _status(inputs) == GateStatus.GREEN


# --- B4: 나머지 테스트 과약속 보강 ---

# (i2) finding_id만 다른 결정 -> 대조 실패 -> RED(현재 (i)는 digest 변형만 검증).
def test_i2_decision_finding_id_mismatch_unresolved_red():
    ob_key = _finding(finding_id="F-1", digest="digest-1")
    wrong_key = _finding(finding_id="F-2", digest="digest-1")
    artifact = _artifact(open_blocking=(BlockingFinding(ob_key),), review_clear=False)
    decisions = (_decision(wrong_key),)
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.RED


# (n2') 무관한 코멘트가 **삭제**됨(유효본도 아니고 open blocking을 닫지도 않음) -> GREEN(현재 (n2)는 편집만).
def test_n2_deleted_irrelevant_comment_green():
    key1 = _finding(finding_id="F-1", digest="digest-1")
    unrelated = _finding(finding_id="F-999", digest="digest-999")
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (
        _decision(key1, comment_id=2, created_at="t1", updated_at="t1"),      # 유효본, 깨끗
        _decision(unrelated, comment_id=5, deleted=True),                     # 무관, 삭제됨
    )
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.GREEN


# --- T1: winner 선택이 max(comment_id)임을 고정 (valid[-1]/min mutation을 잡는다) ---
# valid 후보를 **입력 순서와 comment_id 순서가 어긋나게**(큰 id를 앞에) 배치한다.
# max 구현: 항상 id2를 winner로 고른다. valid[-1] 구현: 입력 마지막(id1)을 고른다.
def test_t1_max_comment_id_winner_clean_green():
    # 입력=(id2 clean, id1 tampered): max=id2(clean) -> GREEN. valid[-1]=id1(tampered) -> RED(실패).
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (
        _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=2, created_at="t3", updated_at="t3"),
        _decision(key1, decision=FindingDecision.REJECTED, comment_id=1, created_at="t1", updated_at="t2"),
    )
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.GREEN


def test_t1_max_comment_id_winner_tampered_red():
    # 입력=(id2 tampered, id1 clean): max=id2(tampered) -> RED. valid[-1]=id1(clean) -> GREEN(실패).
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (
        _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=2, created_at="t3", updated_at="t4"),
        _decision(key1, decision=FindingDecision.REJECTED, comment_id=1, created_at="t1", updated_at="t1"),
    )
    inputs = _inputs(artifact=artifact, decisions=decisions)
    assert _status(inputs) == GateStatus.RED


# --- T3: 항목 8 "전 blocking" 수량자 고정 (open_blocking[:1] mutation을 잡는다) ---
# blocking 2개, 첫째는 유효 결정으로 닫히고 **둘째는 미대조** -> RED. [:1] 구현이면 둘째를 놓쳐 GREEN(실패).
def test_t3_second_blocking_unresolved_red():
    key0 = _finding(finding_id="F-1", digest="digest-1")
    key1 = _finding(finding_id="F-2", digest="digest-2")
    artifact = _artifact(open_blocking=(BlockingFinding(key0), BlockingFinding(key1)), review_clear=False)
    decisions = (_decision(key0, decision=FindingDecision.ACCEPTED, comment_id=1),)  # key1엔 결정 없음
    inputs = _inputs(artifact=artifact, decisions=decisions)
    outcome = evaluate_gate(inputs)
    assert outcome.status == GateStatus.RED
    assert outcome.reason == "unresolved blocking finding"


# --- T4: enforcement 분기의 dismissed 제외 고정 (dismissed continue 제거 mutation을 잡는다) ---
# 포크 아님·승인이 dismissed된 결정권자 승인 하나뿐 -> RED. dismissed 제외를 지우면 유효로 봐 GREEN(실패).
def test_t4_enforcement_dismissed_only_approval_red():
    inputs = _inputs(
        meta=_meta(touches_sot=False, touches_enforcement_surface=True),
        artifact=None,
        approvals=(_approval(dismissed=True),),   # admin·allowlist·human·비자기승인이지만 dismissed
    )
    outcome = evaluate_gate(inputs)
    assert outcome.status == GateStatus.RED
    assert outcome.reason == "no authorized approval"


# --- T5: A5 진단 순서(8->11->9, 그리고 blocking 검사가 승인 검사보다 먼저)를 복합 reason으로 고정 ---
# (1) blocking 둘: 하나는 미대조(항목 8), 다른 하나는 유효본 변조(항목 9). 변조 blocking을
#     open_blocking 앞에 둬도 8이 9보다 먼저 -> reason == "unresolved blocking finding".
def test_t5_item8_before_item9_reason():
    key_tampered = _finding(finding_id="F-1", digest="digest-1")
    key_unresolved = _finding(finding_id="F-2", digest="digest-2")
    artifact = _artifact(
        open_blocking=(BlockingFinding(key_tampered), BlockingFinding(key_unresolved)),
        review_clear=False,
    )
    decisions = (
        _decision(key_tampered, comment_id=1, created_at="t1", updated_at="t2"),  # 유효본, 변조됨(항목 9)
        # key_unresolved엔 유효 결정 없음(항목 8)
    )
    inputs = _inputs(artifact=artifact, decisions=decisions)
    outcome = evaluate_gate(inputs)
    assert outcome.status == GateStatus.RED
    assert outcome.reason == "unresolved blocking finding"   # 8이 9보다 먼저


# (2) blocking 하나가 동일 comment_id 중복(항목 11)이고 동시에 유효 승인 없음(항목 10) ->
#     blocking 검사(11)가 승인 검사(10)보다 먼저 -> reason == "conflicting decisions at same comment_id".
def test_t5_item11_before_item10_reason():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (
        _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=5,
                  author=REVIEWER, created_at="t1", updated_at="t1"),
        _decision(key1, decision=FindingDecision.REJECTED, comment_id=5,
                  author="reviewer-2", created_at="t1", updated_at="t1"),
    )
    inputs = _inputs(
        artifact=artifact,
        decisions=decisions,
        allowlist=frozenset({REVIEWER, "reviewer-2"}),
        approvals=(),   # 유효 승인 없음(항목 10)
    )
    outcome = evaluate_gate(inputs)
    assert outcome.status == GateStatus.RED
    assert outcome.reason == "conflicting decisions at same comment_id"   # 11이 10보다 먼저


# (3) 8 before 11 (다중 blocking): 앞 blocking은 항목 11(유효 후보 중 동일 comment_id 중복),
#     뒤 blocking은 항목 8(유효 결정 없음=미대조). 코드는 항목 8을 **전 blocking**에 대해 먼저
#     검사하므로 -> reason == "unresolved blocking finding". "앞 blocking의 11을 뒤 blocking의 8보다
#     먼저 검사"하는 mutation이면 "conflicting..."이 나와 실패한다.
def test_t5_item8_before_item11_reason():
    key_dup = _finding(finding_id="F-1", digest="digest-1")
    key_unresolved = _finding(finding_id="F-2", digest="digest-2")
    artifact = _artifact(
        open_blocking=(BlockingFinding(key_dup), BlockingFinding(key_unresolved)),
        review_clear=False,
    )
    decisions = (
        _decision(key_dup, decision=FindingDecision.ACCEPTED, comment_id=5,
                  author=REVIEWER, created_at="t1", updated_at="t1"),
        _decision(key_dup, decision=FindingDecision.REJECTED, comment_id=5,
                  author="reviewer-2", created_at="t1", updated_at="t1"),
        # key_unresolved엔 유효 결정 없음(항목 8)
    )
    inputs = _inputs(
        artifact=artifact,
        decisions=decisions,
        allowlist=frozenset({REVIEWER, "reviewer-2"}),
    )
    outcome = evaluate_gate(inputs)
    assert outcome.status == GateStatus.RED
    assert outcome.reason == "unresolved blocking finding"   # 8이 11보다 먼저


# (4) 11 before 9 (단일 blocking): 동일 comment_id 중복(항목 11)이면서 그 최대-comment_id winner가
#     변조(항목 9)도 성립. 코드는 winner 선정(항목 9) 이전에 항목 11을 검사하므로 ->
#     reason == "conflicting decisions at same comment_id". "항목 9를 11보다 먼저 검사"하는 mutation이면
#     "tampered decision"이 나와 실패한다. (두 후보 모두 변조로 둬 max가 어느 쪽을 골라도 9가 성립하게 한다.)
def test_t5_item11_before_item9_reason():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (
        _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=5,
                  author=REVIEWER, created_at="t1", updated_at="t2"),      # 변조
        _decision(key1, decision=FindingDecision.REJECTED, comment_id=5,
                  author="reviewer-2", created_at="t1", updated_at="t2"),  # 변조
    )
    inputs = _inputs(
        artifact=artifact,
        decisions=decisions,
        allowlist=frozenset({REVIEWER, "reviewer-2"}),
    )
    outcome = evaluate_gate(inputs)
    assert outcome.status == GateStatus.RED
    assert outcome.reason == "conflicting decisions at same comment_id"   # 11이 9보다 먼저


# (5) 9 before 10 (단일 blocking): 유일 winner가 변조(항목 9)이면서 동시에 유효 승인 없음(항목 10).
#     코드는 blocking 해소(항목 8·11·9)를 승인 검사(항목 10)보다 먼저 하므로 -> reason == "tampered decision".
#     "항목 10 검사를 항목 9(=blocking 해소) 앞으로" 옮기는 mutation이면 "no valid approval"이 나와 실패한다.
def test_t5_item9_before_item10_reason():
    key1 = _finding()
    artifact = _artifact(open_blocking=(BlockingFinding(key1),), review_clear=False)
    decisions = (
        _decision(key1, decision=FindingDecision.ACCEPTED, comment_id=1,
                  created_at="t1", updated_at="t2"),   # 유효본 유일, 변조됨(항목 9)
    )
    inputs = _inputs(
        artifact=artifact,
        decisions=decisions,
        approvals=(),   # 유효 승인 없음(항목 10)
    )
    outcome = evaluate_gate(inputs)
    assert outcome.status == GateStatus.RED
    assert outcome.reason == "tampered decision"   # 9가 10보다 먼저
