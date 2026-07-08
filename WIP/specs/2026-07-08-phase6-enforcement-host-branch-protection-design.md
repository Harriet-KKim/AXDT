# Phase 6 강제 증분 — SoT 완료 강제(호스트 브랜치 보호) 설계

> 상태: **draft** — Codex+Fable 다중모델 리뷰 대기(구현 전). 확정 전까지 구현 금지.
> 상위: `ADR-0009`(강제 증분 결정) · `ADR-0010`(호스트 추상화, (b) 클라이언트) · `ADR-0007`(층 강제, proposed).
> 권위 규칙: `docs/sot/rule/sot-readiness.md`(완료 정의·판정 키·강제 매핑) · 스킬 `sot-readiness-review`(② 검토 축·감사 로그).
> 범위: **GitHub 전용**. GitLab/Forgejo 강제는 별도 멀티호스트 Phase. 라이브 호스트 검증은 Phase 9.

---

## 1. 목표와 비목표

### 목표
- `rule-sot-readiness`가 정의한 완료 강제(**① 형식 ∧ ② 검토 ∧ ③ 승인**)를 **GitHub 호스트에서 실제로 막는 메커니즘**을 설계한다.
- 강제 계산을 **호스트 무관 순수 게이트 코어**로 두고 결정적으로 테스트한다(라이브 호스트 불필요).
- 호스트 채널(사용자 결정)·권한 확인·② 검토 CI·브랜치 보호 설정을 **주입되는 read 포트 + 선언적 셋업**으로 분리한다.
- 초기 마이그레이션 스윕과 fail-closed 롤아웃을 설계한다.

### 비목표 (이 증분에서 하지 않음)
- **GitLab/Forgejo 강제** — 별도 멀티호스트 Phase. 3-호스트 매트릭스(§4.3)는 그 Phase의 선행 스케치로만 둔다.
- **라이브 호스트 검증** — GitHub Actions 실체·`gh api` 스키마·브랜치 보호 argv는 provisional. Phase 9 도그푸딩에서 확정(강제용 `HOST_MATRIX`).
- **② 검토 판정 로직 자체** — 무엇이 finding인지, 검토 축은 스킬 `sot-readiness-review`와 규칙이 정한다. 여기서는 그 **신뢰 산출물의 형식과 게이트의 소비**만 다룬다.
- **트리거 상태 머신(일시정지·재개)** — Phase 8. 여기선 게이트가 여닫히는 판정만.
- **구현·구현 플랜** — 설계 확정·다중모델 리뷰 후 별도(Sonnet 위임).

---

## 2. 핵심 설계 결정

### 2.1 구조 — 순수 코어 + 주입 read 포트 (게이트 = 코어 + 포트)
강제 계산(`①∧②∧③`)은 호스트 지식이 없는 순수 함수 `evaluate_gate`에 두고, 호스트에서 읽는 것(CI 산출물·채널 결정·권한·승인·PR 상태)과 쓰는 것(게이트 상태 게시)만 `GateHostPorts`로 주입한다. (b)의 `GitHostClient = adapter + backend` 분리를 계승한다. 순수 코어는 지금 TDD, 포트의 GitHub 구현은 provisional.

### 2.2 판정 키와 완전 결속 키 (규칙 §27·28 계승)
- **판정 키** = `(SoT 트리 해시 + 적용 rule 지문)`. 재사용·무효화·③ 승인 stale의 결속 단위. 호스트가 제안된 머지 결과 상태에서 계산하고, 검사기·rule은 신뢰 base에서 읽는다(에이전트 산출 불신, `rule-protected-paths`).
- **완전 결속 키** = `판정 키 + (F-n + 내용 digest)`. finding 단위 사용자 표시·대조 키. **내용 digest = (검토 축 + 참조 문서·항목 ID + 심각도 + 설명 본문)을 정규화한 해시**(규칙 §28). 정규화(공백·항목 순서·마크다운 표준화)는 단일 구현으로 고정한다 — CI 산출과 사용자 표시가 같은 값을 재현해야 대조가 안정적이다.
- 게이트 코어는 판정 키·digest를 **비교만** 한다(계산은 ② CI 몫). 다만 digest **정규화 함수**는 결정적이라 순수 코어에 두고 함께 테스트한다.

### 2.3 호스트 채널 = 구조화 PR 코멘트, 권한 = repo permission {maintain, admin}
- 사용자 결정(accepted/rejected)은 파일이 아니라 **그 PR의 구조화 코멘트**에 완전 결속 키를 참조해 남긴다(규칙 §30·31·77 — 파일 불신).
- 코멘트 작성자의 저장소 permission이 `maintain` 또는 `admin`일 때만 유효로 본다. `write` 제외 → PR을 여는 봇/머신 계정(보통 `write`)은 자기 PR의 blocking을 스스로 accept할 수 없다(합의 F). 권한 값은 저장소 설정(호스트)에서 읽으므로 PR 브랜치가 위조하지 못한다.
- **supersession**: 같은 완전 결속 키에 유효 표시가 여럿이면 **스트림상 최신본이 이긴다**(결정 번복·오타 정정 허용).

### 2.4 필수검사 3개 — `①형식`·`②검토`·`sot-merge-gate`
- `②검토`는 판정이 아니라 **신뢰 산출물**을 낸다: 판정 키 + open blocking 각 `(F-n + 내용 digest)` + 형식 결과. verdict는 `review_clear`/`review_blocked`만(사용자 결정은 안 실음, 규칙 §26).
- `sot-merge-gate`는 그 산출물 + 호스트 채널 결정으로 `①∧②∧③`를 계산한 **최종 통과/실패**다. 네이티브 필수검사 하나로는 accepted/rejected 오버레이를 표현할 수 없어 `②검토`와 분리한다.
- 세 검사를 브랜치 보호의 필수검사로 지정 → 셋 다 green일 때만 머지.

### 2.5 무효화와 fail-closed
- push·base 전진으로 판정 키가 바뀌면 그 키에 안 걸린 채널 결정·③ 승인은 자동 무효(규칙 §31) → red.
- fail-closed(전부 red): CI 산출물 없음·파싱 실패 / 권한 확인 실패 / 완전 결속 키 불일치 / ③ 승인의 판정 키 mismatch(규칙 §37).

### 2.6 감사 이력 보존
squash/rebase 비활성 = MERGE(머지 커밋) 강제, force-push·브랜치 삭제 차단. GitHub "Require linear history"는 머지 커밋을 금지하므로 켜지 않는다. 소스 브랜치는 `sot/<slug>` 규약(호스트 측; 허브 균일 ref는 Phase 3 몫).

---

## 3. 인터페이스 contract (순수 코어)

```python
from enum import Enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
# PullRequest, PullRequestState는 (b) git_host 통제 어휘 재사용(models/state).

class GateStatus(Enum):
    GREEN = "green"                    # 머지 게이트 열림
    RED = "red"                        # 막힘(fail-closed 포함)

class FindingDecision(Enum):
    ACCEPTED = "accepted"              # 위험 인지 후 수용
    REJECTED = "rejected"             # 오판

@dataclass(frozen=True)
class JudgmentKey:
    """(SoT 트리 해시 + 적용 rule 지문). 재사용·무효화·승인 stale의 결속 단위."""
    tree_hash: str
    rule_fingerprint: str

@dataclass(frozen=True)
class FullBindingKey:
    """판정 키 + (F-n + 내용 digest). finding 단위 대조 키."""
    judgment: JudgmentKey
    finding_id: str                    # F-n
    content_digest: str                # 정규화 해시(§2.2)

@dataclass(frozen=True)
class BlockingFinding:
    """② CI 신뢰 산출물의 open blocking 하나. judgment는 산출물 판정 키와 동일."""
    key: FullBindingKey

@dataclass(frozen=True)
class CIArtifact:
    """②검토 CI가 낸 신뢰 산출물."""
    judgment: JudgmentKey
    format_ok: bool                    # ①형식 결과
    review_clear: bool                 # open blocking 없음
    open_blocking: "tuple[BlockingFinding, ...]"

@dataclass(frozen=True)
class ChannelDecision:
    """호스트 채널(PR 코멘트) 하나의 결정 표시."""
    key: FullBindingKey
    decision: FindingDecision
    author: str
    authorized: bool                   # 작성자 permission ∈ {maintain, admin}
    seq: int                           # 스트림 순서(최신 유효본 승, §2.3)

@dataclass(frozen=True)
class ApprovalState:
    """③ 승인 상태. 게이트도 판정 키 일치로 재확인(native dismiss-stale 위)."""
    approved_judgment: "JudgmentKey | None"   # 승인이 걸린 판정 키(없으면 None)

@dataclass(frozen=True)
class GateInputs:
    artifact: "CIArtifact | None"      # None = 산출물 없음(fail-closed)
    decisions: "tuple[ChannelDecision, ...]"
    approval: ApprovalState
    pr_state: "PullRequestState"       # (b) 통제 어휘

@dataclass(frozen=True)
class GateOutcome:
    status: GateStatus
    reason: str                        # red 사유(진단; green이면 "")

def evaluate_gate(inputs: GateInputs) -> GateOutcome:
    """①∧②∧③를 같은 판정 키에서 계산해 sot-merge-gate 상태를 낸다. 부작용 없음.
    ① = artifact.format_ok. ② = review_clear 또는 각 open_blocking이 완전 결속 키가 맞는
    유효(authorized) 결정으로 accepted/rejected(최신 seq 승). ③ = approved_judgment == artifact.judgment.
    셋이 같은 판정 키에서 참이면 GREEN, 아니면 RED(사유 기록). artifact None·형식 실패·미대조 blocking·
    승인 키 불일치는 모두 RED(fail-closed). pr_state가 OPEN이 아니면(이미 머지/닫힘) 게이트는
    적용 대상이 아니므로 RED(사유='pr not open') — 열린 PR에서만 게이트가 의미를 가진다."""

def normalize_finding_digest(axis: str, refs: "tuple[str, ...]",
                             severity: str, body: str) -> str:
    """finding 내용 digest의 정규화 해시(§2.2). 결정적 — CI 산출과 사용자 표시가 재현해야 함."""

class GateHostPorts(ABC):
    """게이트가 호스트에서 읽고/쓰는 것. GitHub 구현은 provisional(Phase 9 라이브)."""
    @abstractmethod
    def read_ci_artifact(self, pr: "PullRequest") -> "CIArtifact | None":
        """②검토 필수검사의 신뢰 산출물. 없거나 파싱 실패면 None(fail-closed)."""
    @abstractmethod
    def read_channel_decisions(self, pr: "PullRequest") -> "tuple[ChannelDecision, ...]":
        """PR 구조화 코멘트 → 결정들. 각 작성자 permission을 조회해 authorized를 채운다."""
    @abstractmethod
    def read_approval(self, pr: "PullRequest") -> "ApprovalState": ...
    @abstractmethod
    def read_pr_state(self, pr: "PullRequest") -> "PullRequestState": ...
    @abstractmethod
    def post_gate_status(self, pr: "PullRequest", outcome: "GateOutcome") -> None:
        """sot-merge-gate 필수검사 상태를 그 커밋에 게시."""

class MergeGate:
    """포트 + evaluate_gate 합성체. 호스트에서 입력을 모아 계산하고 상태를 게시."""
    def __init__(self, ports: "GateHostPorts"): ...
    def evaluate_and_post(self, pr: "PullRequest") -> "GateOutcome":
        """read_* 4개로 GateInputs 구성 → evaluate_gate → post_gate_status. 반환은 결과."""
```

### 동작 규약 (요약)
- `evaluate_gate`는 순수: 입력만으로 결과. 호스트 접근 없음.
- ② 성립 판정: `review_clear`면 즉시 성립. 아니면 `open_blocking`의 각 `FullBindingKey`에 대해 **같은 키·authorized·최신 seq** 결정을 찾아 accepted/rejected면 닫힘. 하나라도 못 찾으면 RED.
- authorized=False 결정은 대조에서 제외(권한 미확인 폐기).
- ③: `approved_judgment`가 `artifact.judgment`와 정확히 같아야 함(판정 키 mismatch면 RED).
- `MergeGate.evaluate_and_post`는 포트로 입력을 모아 순수 계산 후 게시 — 이 조립부만 호스트 의존.

---

## 4. GitHub 강제 설정과 3-호스트 매트릭스

### 4.1 main 브랜치 보호 (GitHub 확정 · argv·스키마는 provisional)
- **require-PR**: 직접 push 거부(SoT는 승인된 PR 머지로만 main 도달).
- **필수검사 3개**: `①형식`·`②검토`·`sot-merge-gate` green 필수 + "Require branches up to date"(up-to-date-before-merge).
- **승인**: 필수 승인 ≥ 1 + "Dismiss stale approvals on new commits".
- **감사 이력 보존**: repo에서 squash/rebase 머지 비활성(merge commit만) + force-push·삭제 차단. ⚠ "Require linear history"는 켜지 않는다(머지 커밋 금지라 상충).
- **소스 브랜치**: `sot/<slug>`(ruleset 브랜치명 패턴 또는 규약).

### 4.2 ② 검토 CI 계약 (실행기 = GitHub Actions, 실체 provisional)
- 트리거: SoT 경로(requirements·specification·test-design) 변경 PR.
- 판정 키를 제안된 머지 결과 상태에서 계산, 검사기·rule은 신뢰 base에서 읽음.
- 콘텐츠당 1회: 같은 판정 키의 통과 산출이 있으면 재실행 스킵(규칙 §28).
- 산출 = 필수검사 상태 + 신뢰 산출물(판정 키 + open blocking `[F-n+digest]` + 형식 결과). verdict는 `review_clear`/`review_blocked`만.
- 실행은 작성 세션과 분리(자기검토 편향 방지). 실행 모델·프롬프트는 감사 로그(비신뢰 사본)에 기록.

### 4.3 3-호스트 강제 매트릭스 (미래 멀티호스트 Phase 선행 스케치 — 이 증분 범위 밖)

| 강제 요구(호스트 중립) | GitHub (확정) | GitLab (provisional) | Forgejo (provisional) |
|---|---|---|---|
| require-PR | ruleset "Require PR before merging" | protected branch: main "Allowed to push = No one" | branch protection: push 비활성 + require PR |
| 필수검사 3개 | "Require status checks" + 3 contexts | ⚠ 개별 external status checks는 프리미엄 → CE는 파이프라인 1검사로 3잡 합산 폴백 | "Enable Status Check" + 3 contexts(GitHub 근접) |
| up-to-date | "Require branches up to date" | merged-results/rebase 요건 | "Block merge on outdated branch" |
| 승인 + dismiss-stale | "Require approvals" + "Dismiss stale approvals" | approval rules + "Remove approvals on push" | "Enable Approvals" + "Dismiss stale approvals" |
| 감사 이력 보존 | squash/rebase 비활성(merge commit만) + force-push·삭제 차단, linear-history 금지 | MR "Squash = Do not allow" + merge commit; force-push 차단 | merge commit만 활성 + force-push·삭제 차단 |
| 소스 브랜치 `sot/<slug>` | ruleset 브랜치명 패턴 | push rule 정규식(프리미엄) 또는 규약 | 규약(강제 제한적) |
| 채널 결정 read + 권한 | issue comments + collaborator permission {maintain, admin} | MR notes + access level(40=Maintainer/50=Owner) | PR comments + write/admin(**maintain 구분 흐릿**) |

> GitLab 티어 의존(개별 필수검사·브랜치명 강제가 프리미엄)이 최대 변수. Forgejo는 상태검사·dismiss-stale에서 GitHub에 근접하나 권한이 write/admin뿐이라 maintain 경계가 흐릿하다.

---

## 5. 패키지 레이아웃 (D12 → `WIP/`)

```
WIP/axdt/sot_gate/
  __init__.py
  keys.py             # JudgmentKey, FullBindingKey, normalize_finding_digest
  models.py           # CIArtifact, BlockingFinding, ChannelDecision, ApprovalState,
                      #   GateInputs, GateOutcome, GateStatus, FindingDecision
  gate.py             # evaluate_gate(순수) + MergeGate(포트 합성)
  ports.py            # GateHostPorts(ABC) + FakeGatePorts(테스트)
  hosts/
    __init__.py; github.py            # GitHubGatePorts (gh api) — provisional
  ENFORCEMENT_MATRIX.md; README.md
  tests/
    __init__.py; test_keys.py; test_models.py
    test_gate.py; test_ports.py
```

> `sot_gate`는 (b) `git_host`의 통제 어휘(`PullRequest`/`PullRequestState`)를 소비하되 강제 계산은 독립. `GitHubGatePorts`는 얇은 `gh api` 래퍼(브랜치 보호 설정은 코드가 아니라 선언적 셋업 문서 + `ENFORCEMENT_MATRIX`).

---

## 6. 테스트 (계약 고정)

- **test_keys**: `JudgmentKey`/`FullBindingKey` 불변·동등성; `normalize_finding_digest` 결정성(공백·항목 순서·마크다운 변형이 같은 digest를 내는가; 축·심각도·본문이 다르면 다른 digest).
- **test_models**: 데이터클래스 불변; `GateInputs`/`GateOutcome` 구성.
- **test_gate** (`evaluate_gate` 순수):
  - (a) `review_clear` + ①형식 통과 + ③ 승인 키 일치 → GREEN.
  - (b) open blocking 전부 accepted/rejected(authorized·키 일치) → GREEN.
  - (c) open blocking 중 하나가 미대조(결정 없음) → RED.
  - (d) 결정은 있으나 authorized=False → 폐기 → RED.
  - (e) **supersession**: 같은 완전 결속 키에 rejected 후 accepted(더 큰 seq) → accepted 적용.
  - (f) ③ `approved_judgment` ≠ `artifact.judgment`(판정 키 mismatch) → RED.
  - (g) `artifact=None`(산출물 없음) → RED(fail-closed).
  - (h) `format_ok=False` → RED.
  - (i) 완전 결속 키의 finding_id/digest가 산출물과 다른 결정 → 대조 실패 → RED.
- **test_ports** (`FakeGatePorts` + `MergeGate`):
  - `evaluate_and_post`가 read_* 4개로 입력을 모아 `evaluate_gate` 결과를 `post_gate_status`에 전달(스크립트·호출 기록으로 검증).
  - 포트 read 실패(예: 산출물 None) → RED 게시.

---

## 7. 초기 마이그레이션 · 롤아웃

- **활성화 = 규칙 §64의 강제 도입 시점.** 기존 완료 문서 전량을 **축3(교차 정합성) 한정으로 최초 1회 스윕** → `rules` 선언 완전성 확립(미선언 rule 의존을 finding으로 걷어냄).
- **마이그레이션 워크플로**: ② 검토 CI를 축3 한정 모드로 전량 1회 실행 → 판정 키·baseline finding을 정상 신뢰 채널로 게시. Maintainer가 accept/reject/resolve로 닫는다.
- **활성화 순서**: 브랜치 보호를 먼저 켜도 안전 — fail-closed라 게이트 green 전엔 *머지만* 막히고 기존 main 내용은 그대로다.
- **test-design 공백 = 엄격 차단 + 백필**: req+spec만으로 완료됐던 문서는 test-design(`ADR-0008`)이 빠져 fail-closed(미완료)로 떨어진다. 유예 없이 test-design 작성 전까지 미완료로 두고 백필한다("`ADR-0008` 대가"). 게이트가 신규 도입이라 영향분은 작을 것으로 본다.

---

## 8. provisional (라이브 — 강제용 `ENFORCEMENT_MATRIX.md`)

- GitHub Actions 워크플로 실체(② 검토 실행기·판정 키 계산 잡·게이트 잡).
- `gh api` 스키마: PR 코멘트 조회, `collaborators/{login}/permission`, 승인 상태·check-run 게시.
- 브랜치 보호 설정 argv(ruleset vs classic protection), squash 비활성·linear-history off의 정확 설정 경로.
- 판정 키(트리 해시·rule 지문)의 정확한 계산 정의(호스트가 머지 결과 상태에서).
- 콘텐츠당 1회 재사용의 판정 키 조회 방식(체크런 이력 대 산출물).
- GitLab/Forgejo 전부(별도 멀티호스트 Phase).

---

## 9. 다음 단계 접합

- **Phase 8(오케스트레이션)**: 게이트 green/red를 소비해 개발 시작 트리거(D6)와 일시정지·재개를 제어. blocking이 이미 착수된 작업에 미치는 효과는 트리거 상태 머신(Phase 8).
- **Phase 9(라이브 도그푸딩)**: GitHub 실제 저장소에 브랜치 보호·워크플로 적용, `gh api` 스키마·설정 argv 확정, `ENFORCEMENT_MATRIX` 라이브 검증.
- **미래 멀티호스트 Phase**: GitLab/Forgejo 강제 realization(§4.3 매트릭스가 선행 스케치).
- **Phase 3**: 허브 `main` ref 보호(균일 ref 규칙)는 이 호스트 강제와 별개 층(`ADR-0007`).

---

## 10. 확정된 결정

- **범위 = GitHub 전용 강제**; GitLab/Forgejo는 별도 멀티호스트 Phase, 라이브는 Phase 9.
- **호스트 채널 = 구조화 PR 코멘트**, 권한 = repo permission `{maintain, admin}`(write 제외).
- **필수검사 3개** = `①형식`·`②검토`·`sot-merge-gate`; 게이트 잡이 `①∧②∧③` 오버레이 계산.
- **감사 이력 보존** = MERGE 강제·force-push 차단·linear-history 금지.
- **마이그레이션** = 축3 1회 스윕 + fail-closed; **test-design 공백 = 엄격 차단 + 백필**.
- **테스트 경계** = `evaluate_gate`·`normalize_finding_digest`는 순수 TDD; 포트 GitHub 구현·설정·워크플로는 provisional.
