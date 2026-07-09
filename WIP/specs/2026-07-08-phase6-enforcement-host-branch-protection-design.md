# Phase 6 강제 증분 — SoT 완료 강제(호스트 브랜치 보호) 설계

> 상태: **revised** — Codex+Fable+사용자 3자 리뷰 통합 반영(2026-07-09). 확정 후 writing-plans로 구현(별도, Sonnet 위임). 확정 전까지 구현 금지.
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
- **판정 키** = `(SoT 트리 해시 + 적용 rule 지문)`. 재사용·무효화·③ 승인 stale의 결속 단위. **둘 다 제안된 머지 결과 상태에서 계산한다** — 트리 해시는 그 트리, 적용 rule 지문은 그 트리에 적용될 규칙 선언 기준(규칙 §27). 검사 코드·정책 자체만 신뢰 base에서 읽는다(에이전트 산출 불신, `rule-protected-paths`). "머지 결과에서 계산"(무엇을 적용하는가)과 "base에서 읽음"(검사 코드)을 혼동하지 않는다.
- **완전 결속 키** = `판정 키 + (F-n + 내용 digest)`. finding 단위 사용자 표시·대조 키. **내용 digest = (검토 축 + 참조 문서·항목 ID + 심각도 + 설명 본문)을 정규화한 해시**(규칙 §28). 정규화(공백·항목 순서·마크다운 표준화)는 단일 구현으로 고정한다 — CI 산출과 사용자 표시가 같은 값을 재현해야 대조가 안정적이다.
- 게이트 코어는 판정 키·digest를 **비교만** 한다(계산은 ② CI 몫). 다만 digest **정규화 함수**는 결정적이라 순수 코어에 두고 함께 테스트한다.

### 2.3 호스트 채널 = 구조화 PR 코멘트(append-only), 권한 = repo permission `admin`
- 사용자 결정(accepted/rejected)은 파일이 아니라 **그 PR의 구조화 코멘트**에 완전 결속 키를 참조해 남긴다(규칙 §30·31·77 — 파일 불신).
- **결정권 = 저장소 permission == `admin`.** `write`·`maintain` 제외 → PR을 여는 봇/머신 계정(보통 `write`)은 자기 PR의 blocking을 스스로 닫을 수 없다(합의 F). 판별은 `role_name`으로 한다 — 레거시 `collaborators/{login}/permission`의 `permission` 필드는 maintain을 write로, triage를 read로 뭉개므로 admin 판정에 못 쓴다(`role_name`은 정확 역할을 보고). 권한은 저장소 설정(호스트)에서 읽으므로 PR 브랜치가 위조하지 못한다.
- **승인자 신원 검증(③, CR-2).** 네이티브 "필수 승인 ≥ 1"은 write+ 아무 리뷰나 카운트하고 승인자 신원을 검증하지 않는다. 게이트가 PR 리뷰 스트림에서 승인자를 읽어 `role_name == admin` + allowlist를 확인한다. `.github/CODEOWNERS`(SoT·`.github` 경로 → 지정 admin)를 네이티브 백스톱으로 둔다(코드오너 승인 필수).
- **자기결정 차단(IM-3).** 결정·승인의 author가 PR author와 같으면 무효(admin이라도 자기 PR 자기수용 불가).
- **권한 판정 시점 = 현재.** `authorized`는 코멘트 게시 당시가 아니라 **게이트 평가 시점의 현재 권한**으로 판정한다(승격·강등이 소급 반영).
- **append-only supersession(IM-8).** 결정은 코멘트를 편집·삭제하지 않고 **새 코멘트로만** 번복·정정한다. 같은 완전 결속 키에 유효 표시가 여럿이면 스트림상 최신(seq 최대)본이 이긴다. 이미 반영된 코멘트의 편집·삭제가 감지되면 그 결정을 폐기하고 fail-closed로 재평가한다(철회가 침묵하지 않게).

### 2.4 병합-필수 검사 = `sot-merge-gate` 하나; `②검토`는 입력 (CR-3)
- `②검토`는 판정이 아니라 **신뢰 산출물**을 낸다: 판정 키 + open blocking 각 `(F-n + 내용 digest)` + 형식 결과. verdict는 `review_clear`/`review_blocked`만(사용자 결정은 안 실음, 규칙 §26).
- `sot-merge-gate`는 그 산출물 + 호스트 채널 결정으로 `①∧②∧③`를 계산한 **최종 통과/실패**이며, **병합을 여는 유일한 필수검사**다.
- **데드락 회피(CR-3).** `②검토`의 검사 상태 의미는 그대로 둔다(재정의하지 않음 — 다른 소비자에 사이드이펙트). 대신 `②검토`를 병합-필수 집합에서 빼고, **병합 초록 조건을 `sot-merge-gate` 하나가 "②검토 산출 결과 + accept/reject 반영"으로 계산**한다. 그러면 open blocking이 남아 `②검토`가 `review_blocked`여도, 전부 수용되면 `sot-merge-gate`가 green이 되어 영구 데드락이 없다. `②검토` 산출물이 없거나 기형이면 `sot-merge-gate`가 fail-closed red이므로 `②검토`는 전이적으로 필수다.
- `①형식`은 `sot-merge-gate`가 `artifact.format_ok`로 흡수한다(단조 신호라 별도 가시 검사로 둬도 데드락 없음).

### 2.5 무효화와 fail-closed
- push·base 전진으로 판정 키가 바뀌면 그 키에 안 걸린 채널 결정·③ 승인은 자동 무효(규칙 §31) → red.
- fail-closed(전부 red): CI 산출물 없음·파싱 실패 / **산출물 불변식 위반**(`review_clear != (open_blocking 빔)` — IM-4) / 권한 확인 실패 / 완전 결속 키 불일치 / ③ 승인의 판정 키 mismatch / **승인자가 `admin` 아님** / **head ref가 `sot/<slug>` 아님**(IM-1) / **반영된 결정 코멘트의 편집·삭제 감지**(IM-8) (규칙 §37).

### 2.6 감사 이력 보존
squash/rebase 비활성 = MERGE(머지 커밋) 강제, `main`·`sot/*` force-push·브랜치 삭제 차단. GitHub "Require linear history"는 머지 커밋을 금지하므로 켜지 않는다. 소스 브랜치 `sot/<slug>` 규약은 **네이티브 head 브랜치 패턴 조건이 없음이 확인**됐으므로 **게이트가 head ref를 대조**해 강제한다(§2.7·§3; 허브 균일 ref는 Phase 3 몫).

### 2.7 게이트 신뢰 뿌리 — 필수검사 위조·워크플로 자체수정 차단 (CR-1)
- **위조 확인.** push 권한자면 `POST /repos/{owner}/{repo}/statuses/{sha}`로 **임의 context명 + state=success** 커밋 상태를 게시할 수 있음이 확인됐다. 이름으로만 매칭하는 필수 커밋 상태는 write 봇이 위조해 우회할 수 있다.
- **신뢰 실행.** `②검토`·`sot-merge-gate`는 **리포지토리 룰셋의 required workflow**로 실행하고 그 정의를 **신뢰 소스 repo/ref에서 가져온다** — PR이 워크플로 정의를 못 고치고, 항상 실행되며(필터 무시), 만족이 소스 위치에 결속돼 PR이 추가한 동명 워크플로로 위조되지 않는다.
- **base 실행 + 데이터만 read.** 검사는 `pull_request_target`/`merge_group`로 **base(신뢰) ref의 워크플로**를 실행한다(확인: pull_request_target은 기본 브랜치 문맥에서 실행). `②검토`는 PR 코드를 실행하지 않고 SoT 트리 **데이터만** 읽는다(PR head 데이터라도 실행하지 않음).
- **정의 변경은 admin 결정.** `.github/**`(워크플로·CODEOWNERS·게이트 정의)를 CODEOWNERS로 지정 admin에 묶어, 그 경로를 건드리는 PR은 admin 승인을 요구한다.
- **신뢰 App expected source.** 필수검사의 expected source를 **제네릭 GitHub Actions 앱이 아닌 전용 신뢰 App**으로 고정한다(같은 저장소 브랜치 PR엔 시크릿이 전달되므로, App 토큰을 base-only 실행에 가둔다). 전용 App·룰셋 셋업은 provisional(§8, Phase 9 라이브).

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
    """②검토 CI가 낸 신뢰 산출물.
    불변식(IM-4): review_clear == (open_blocking == ()). 위반 산출물은 기형으로 간주,
    evaluate_gate가 RED(fail-closed) — review_clear=True인데 blocking이 남거나 그 역은 통과 금지."""
    judgment: JudgmentKey
    format_ok: bool                    # ①형식 결과
    review_clear: bool                 # open blocking 없음 (== len(open_blocking)==0)
    open_blocking: "tuple[BlockingFinding, ...]"

@dataclass(frozen=True)
class ChannelDecision:
    """호스트 채널(PR 코멘트) 하나의 결정 표시(append-only)."""
    key: FullBindingKey
    decision: FindingDecision
    author: str
    authorized: bool                   # 평가 시점 현재 role_name == "admin" (§2.3)
    seq: int                           # 스트림 순서(최신 유효본 승, §2.3)
    tampered: bool = False             # 반영된 코멘트가 편집·삭제됨(IM-8) → 존재 시 fail-closed

@dataclass(frozen=True)
class ApprovalState:
    """③ 승인 상태. 게이트가 판정 키 일치 + 승인자 신원을 재확인(native dismiss-stale·승인 수 위).
    approved_judgment 출처(IM-5): 집계 상태가 아니라 승인 리뷰가 걸린 커밋의 제안된 머지 결과
    트리 + 적용 rule 지문에서 포트가 재구성한다. 실제 read 구현은 후속 증분(설계는 의존만 고정)."""
    approved_judgment: "JudgmentKey | None"   # 승인이 걸린 판정 키(없으면 None)
    approver: "str | None" = None             # 승인자 로그인(없으면 None)
    approver_is_admin: bool = False           # 평가 시점 role_name == "admin"

@dataclass(frozen=True)
class GateInputs:
    artifact: "CIArtifact | None"      # None = 산출물 없음(fail-closed)
    decisions: "tuple[ChannelDecision, ...]"
    approval: ApprovalState
    pr_state: "PullRequestState"       # (b) 통제 어휘
    head_ref: str                      # PR 소스 브랜치(sot/<slug> 대조, IM-1)
    pr_author: str                     # 자기결정·자기승인 차단(IM-3)

@dataclass(frozen=True)
class GateOutcome:
    status: GateStatus
    reason: str                        # red 사유(진단; green이면 "")

def evaluate_gate(inputs: GateInputs) -> GateOutcome:
    """①∧②∧③를 같은 판정 키에서 계산해 sot-merge-gate 상태를 낸다. 부작용 없음.
    ① = artifact.format_ok. ② = review_clear(불변식 성립 시) 또는 각 open_blocking이 완전 결속 키가
    맞는 유효 결정으로 accepted/rejected(authorized ∧ author≠pr_author ∧ 미변조 ∧ 최신 seq 승).
    ③ = approved_judgment == artifact.judgment ∧ approver_is_admin ∧ approver≠pr_author.
    셋이 같은 판정 키에서 참 ∧ head_ref가 sot/<slug>이면 GREEN, 아니면 RED(사유 기록).
    RED(fail-closed): artifact None / 불변식 위반(review_clear≠open_blocking빔) / 형식 실패 /
    미대조 blocking / 승인 키 불일치 / 승인자 비-admin / head_ref 불일치 / 변조(edited·deleted) 결정 존재 /
    pr_state가 OPEN 아님('pr not open'). 열린 PR에서만 게이트가 의미를 가진다."""

DIGEST_ALGO = "sha256"                  # 해시 알고리즘 고정(Minor)
DIGEST_VERSION = 1                      # 정규화 규약 버전 — 바뀌면 digest도 바뀜

def normalize_finding_digest(axis: str, refs: "tuple[str, ...]",
                             severity: str, body: str) -> str:
    """finding 내용 digest의 정규화 해시(§2.2). 결정적 — CI 산출과 사용자 표시가 재현해야 함.
    정규화(고정): 유니코드 NFC → 개행 LF 통일 → 앞뒤 공백 제거·연속 공백 1칸 축약 →
    refs 정렬(중복 제거) → 필드를 US(0x1f) 구분자로 (DIGEST_VERSION, axis, refs, severity, body)
    직렬화 → DIGEST_ALGO 해시. 구분자·정렬·유니코드·버전을 못 박아 동치 입력이 같은 digest를 낸다."""

class GateHostPorts(ABC):
    """게이트가 호스트에서 읽고/쓰는 것. GitHub 구현은 provisional(Phase 9 라이브)."""
    @abstractmethod
    def read_ci_artifact(self, pr: "PullRequest") -> "CIArtifact | None":
        """②검토 필수검사의 신뢰 산출물. 없거나 파싱 실패면 None(fail-closed)."""
    @abstractmethod
    def read_channel_decisions(self, pr: "PullRequest") -> "tuple[ChannelDecision, ...]":
        """PR 구조화 코멘트(append-only) → 결정들. 각 작성자 role_name을 조회해 현재 권한 기준
        authorized(==admin)를 채우고, 반영된 코멘트의 편집·삭제를 tampered로 표시(IM-8)."""
    @abstractmethod
    def read_approval(self, pr: "PullRequest") -> "ApprovalState":
        """승인 리뷰 스트림 → 승인 판정 키(승인 커밋의 머지 결과서 재구성) + 승인자 신원·admin 여부(CR-2·IM-5)."""
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
- 사전 게이트: `pr_state != OPEN` → RED('pr not open'); `head_ref`가 `sot/<slug>` 아님 → RED; `artifact` 불변식(`review_clear == (open_blocking 빔)`) 위반 → RED.
- ② 성립 판정: `review_clear`면 즉시 성립. 아니면 `open_blocking`의 각 `FullBindingKey`에 대해 **같은 키·authorized·author≠pr_author·미변조·최신 seq** 결정을 찾아 accepted/rejected면 닫힘. 하나라도 못 찾으면 RED.
- 대조 제외: authorized=False(현재 admin 아님)·`author == pr_author`(자기결정)·`tampered=True`. 변조 결정이 하나라도 존재하면 즉시 RED(철회가 침묵하지 않게).
- ③: `approved_judgment == artifact.judgment` ∧ `approver_is_admin` ∧ `approver != pr_author`. 하나라도 아니면 RED.
- `MergeGate.evaluate_and_post`는 포트로 입력을 모아 순수 계산 후 게시 — 이 조립부만 호스트 의존.

---

## 4. GitHub 강제 설정과 3-호스트 매트릭스

### 4.1 main 브랜치 보호 (룰셋 우선 · argv·스키마는 provisional)
- **require-PR**: 직접 push 거부(SoT는 승인된 PR 머지로만 main 도달).
- **병합-필수 검사**: `sot-merge-gate` green 필수 + "Require branches up to date". `②검토`·`①형식`은 신뢰 실행되지만 병합-필수 집합엔 `sot-merge-gate`만 둔다(§2.4 데드락 회피). 커밋 상태 위조 차단을 위해 이름 매칭 필수 커밋 상태 대신 **리포지토리 룰셋 required workflow(신뢰 소스 ref) + 신뢰 App expected source**로 건다(§2.7).
- **승인**: 필수 승인 ≥ 1 + "Dismiss stale approvals on new commits" + `.github/CODEOWNERS`(SoT·`.github`→지정 admin) "Require review from Code Owners". 게이트가 승인자 `role_name==admin`을 추가 검증(네이티브 승인 수는 신원 무검증).
- **감사 이력 보존**: repo에서 squash/rebase 머지 비활성(merge commit만) + `main`·`sot/*` force-push·삭제 차단. ⚠ "Require linear history"는 켜지 않는다(머지 커밋 금지라 상충).
- **소스 브랜치**: `sot/<slug>` — 네이티브 head 패턴 조건이 없으므로 게이트가 `head_ref`를 대조(§2.6·§3).

### 4.2 ② 검토 CI 계약 (룰셋 required workflow · 실체 provisional)
- 트리거: SoT 경로(requirements·specification·test-design) 변경 PR. **신뢰 소스 ref의 워크플로를 `pull_request_target`/`merge_group`로 실행**(PR이 정의를 못 고침, §2.7). PR 코드를 실행하지 않고 SoT 트리 데이터만 read.
- **적용 rule 지문을 제안된 머지 결과 상태에서 계산**(그 트리에 적용될 규칙 기준). 검사 코드·정책만 신뢰 base에서 읽음 — "머지 결과에서 계산"과 "base에서 읽음"을 혼동하지 않는다(IM-6, 규칙 §27).
- 콘텐츠당 1회: 같은 판정 키의 통과 산출이 있으면 재실행 스킵(규칙 §28).
- 산출 = 검사 상태 + 신뢰 산출물(판정 키 + open blocking `[F-n+digest]` + 형식 결과, 불변식 §2.5). verdict는 `review_clear`/`review_blocked`만. 산출은 **전용 신뢰 App 정체성**으로 게시(위조 가능한 커밋 상태와 구분).
- 실행은 작성 세션과 분리(자기검토 편향 방지). 실행 모델·프롬프트는 감사 로그(비신뢰 사본)에 기록.

### 4.3 3-호스트 강제 매트릭스 (미래 멀티호스트 Phase 선행 스케치 — 이 증분 범위 밖)

| 강제 요구(호스트 중립) | GitHub (확정) | GitLab (provisional) | Forgejo (provisional) |
|---|---|---|---|
| require-PR | ruleset "Require PR before merging" | protected branch: main "Allowed to push = No one" | branch protection: push 비활성 + require PR |
| 병합-필수 검사 | 룰셋 required workflow(신뢰 ref) + `sot-merge-gate` 필수 + 신뢰 App expected source | ⚠ external status checks는 **Ultimate** 티어 → 하위 티어는 파이프라인 1검사로 합산 폴백 | "Enable Status Check" + 필수검사(GitHub 근접) |
| up-to-date | "Require branches up to date" | merged-results/rebase 요건 | "Block merge on outdated branch" |
| 승인 + dismiss-stale + 승인자 검증 | "Require approvals" + "Dismiss stale approvals" + CODEOWNERS + 게이트 role_name==admin | approval rules + "Remove approvals on push" | "Enable Approvals" + "Dismiss stale approvals" |
| 감사 이력 보존 | squash/rebase 비활성(merge commit만) + `main`·`sot/*` force-push·삭제 차단, linear-history 금지 | MR "Squash = Do not allow" + merge commit; force-push 차단 | merge commit만 활성 + force-push·삭제 차단 |
| 소스 브랜치 `sot/<slug>` | 게이트가 head_ref 대조(네이티브 head 패턴 없음) | push rule 정규식(프리미엄) 또는 규약 | 규약(강제 제한적) |
| 채널 결정 read + 권한 | PR comments(append-only) + `role_name`==admin + 게이트 승인자 검증 | MR notes + access level(50=Owner) | PR comments + admin(**maintain 구분 흐릿**) |

> GitLab 티어 의존(external status checks=Ultimate, 브랜치명 push rule=Premium)이 최대 변수. Forgejo는 상태검사·dismiss-stale에서 GitHub에 근접하나 권한이 write/admin뿐이라 maintain 경계가 흐릿하다(이 설계는 admin 전용이라 오히려 이식 단순).

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

- **test_keys**: `JudgmentKey`/`FullBindingKey` 불변·동등성; `normalize_finding_digest` 결정성(공백·항목 순서·마크다운·**유니코드 NFC·개행(CRLF↔LF)** 변형이 같은 digest; 축·참조·심각도·본문이 다르면 다른 digest; `DIGEST_VERSION` 변경 시 digest 달라짐).
- **test_models**: 데이터클래스 불변; `GateInputs`/`GateOutcome` 구성.
- **test_gate** (`evaluate_gate` 순수, 기본 입력은 head_ref=`sot/x`·pr_author≠결정자·승인자 admin):
  - (a) `review_clear` + ①형식 통과 + ③ 승인 키 일치·승인자 admin·head sot/* → GREEN.
  - (b) open blocking 전부 accepted/rejected(authorized·author≠pr_author·키 일치) → GREEN.
  - (c) open blocking 중 하나가 미대조(결정 없음) → RED.
  - (d) 결정은 있으나 authorized=False(현재 admin 아님) → 폐기 → RED.
  - (e) **supersession**: 같은 완전 결속 키에 rejected 후 accepted(더 큰 seq) → accepted 적용.
  - (f) ③ `approved_judgment` ≠ `artifact.judgment`(판정 키 mismatch) → RED.
  - (g) `artifact=None`(산출물 없음) → RED(fail-closed).
  - (h) `format_ok=False` → RED.
  - (i) 완전 결속 키의 finding_id/digest가 산출물과 다른 결정 → 대조 실패 → RED.
  - (j) `head_ref`가 `sot/<slug>` 아님 → RED (IM-1).
  - (k) 승인자 `approver_is_admin=False` → RED (CR-2).
  - (l) 결정 `author == pr_author`(자기결정) → 폐기 → RED; ③ 승인자 == pr_author → RED (IM-3).
  - (m) 산출물 불변식 위반(`review_clear=True`+blocking≠∅, 또는 `False`+∅) → RED (IM-4).
  - (n) `tampered=True` 결정 존재(반영 코멘트 편집·삭제) → RED (IM-8).
  - (o) `pr_state != OPEN` → RED('pr not open').
  - (p) 같은 완전 결속 키·동일 seq 상충 결정 → 결정론적 처리(동점은 미해결로 RED).
- **test_ports** (`FakeGatePorts` + `MergeGate`):
  - `evaluate_and_post`가 read_* 4개로 입력을 모아 `evaluate_gate` 결과를 `post_gate_status`에 전달(스크립트·호출 기록으로 검증).
  - 포트 read 실패(예: 산출물 None) → RED 게시.

---

## 7. 초기 마이그레이션 · 롤아웃

- **활성화 = 규칙 §64의 강제 도입 시점.** 기존 완료 문서 전량을 **축3(교차 정합성) 한정으로 최초 1회 스윕** → `rules` 선언 완전성 확립(미선언 rule 의존을 finding으로 걷어냄).
- **마이그레이션 워크플로**: ② 검토 CI를 축3 한정 모드로 전량 1회 실행 → 판정 키·baseline finding을 **전용 마이그레이션 PR의 구조화 코멘트**(동일 호스트 채널, append-only)로 게시. 기존 main 문서엔 PR이 없으므로 이 PR을 채널로 연다(규칙 §77, 파일 결정 금지). admin이 accept/reject로 닫는다(FindingDecision엔 RESOLVED 없음 — 'resolve' 어휘 폐기).
- **활성화 순서**: 브랜치 보호를 먼저 켜도 안전 — fail-closed라 게이트 green 전엔 *머지만* 막히고 기존 main 내용은 그대로다.
- **test-design 공백 = 엄격 차단 + 백필**: req+spec만으로 완료됐던 문서는 test-design(`ADR-0008`)이 빠져 fail-closed(미완료)로 떨어진다. 유예 없이 test-design 작성 전까지 미완료로 두고 백필한다("`ADR-0008` 대가"). 게이트가 신규 도입이라 영향분은 작을 것으로 본다.

---

## 8. provisional (라이브 — 강제용 `ENFORCEMENT_MATRIX.md`)

- GitHub Actions 워크플로 실체(② 검토 실행기·판정 키 계산 잡·게이트 잡).
- `gh api` 스키마: PR 코멘트 조회, `collaborators/{login}/permission`, 승인 상태·check-run 게시.
- 브랜치 보호 설정 argv(ruleset vs classic protection), squash 비활성·linear-history off의 정확 설정 경로.
- **신뢰 뿌리**: 전용 GitHub App(check-run 게시·expected source) 셋업·키 관리; 룰셋 required workflow의 신뢰 소스 ref 지정; 같은 저장소 브랜치 PR의 시크릿 노출을 base-only(pull_request_target/merge_group) 실행으로 가두는 실체.
- `role_name` 조회(`collaborators/{login}/permission`)·CODEOWNERS 적용·리뷰 스트림 승인자 신원 read의 정확 스키마.
- 코멘트 편집·삭제(tampered) 감지 방식(webhook 이벤트/타임스탬프 비교).
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
- **호스트 채널 = 구조화 PR 코멘트(append-only)**; 권한 = repo permission `admin`(`role_name` 판별; write·maintain 제외). 승인자 신원을 게이트가 검증 + CODEOWNERS 백스톱. 권한은 현재 시점 판정, 자기결정 차단.
- **병합-필수 검사 = `sot-merge-gate` 하나**(오버레이 `①∧②∧③`); `①형식`·`②검토`는 입력이며 데드락 회피 위해 병합-필수 아님. 위조 차단 = 룰셋 required workflow(신뢰 소스 ref) + 신뢰 App expected source + `.github/**` CODEOWNERS.
- **감사 이력 보존** = MERGE 강제·`main`/`sot/*` force-push 차단·linear-history 금지. 소스 브랜치 `sot/<slug>`는 게이트가 head_ref 대조(네이티브 head 패턴 없음).
- **마이그레이션** = 축3 1회 스윕 + fail-closed; 결정 채널 = 전용 마이그레이션 PR 코멘트(accept/reject); **test-design 공백 = 엄격 차단 + 백필**.
- **테스트 경계** = `evaluate_gate`·`normalize_finding_digest`는 순수 TDD; 포트 GitHub 구현·설정·워크플로·신뢰 App은 provisional.
