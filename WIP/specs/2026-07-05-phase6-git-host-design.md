# Phase 6 — Git 호스트 연동: 호스트 추상화 설계

> 상태: **draft** (라운드3~4 합의 A~G 반영 + Phase1 귀속 정합화 반영 완료). 확정 전까지 커밋하지 않는다.
> 형판: Phase 5(agent runner) 합성·주입 패턴을 호스트 연동에 재사용 → ADR-0005.
> 대응 결정: D5(GitHub 우선, `gh` CLI), Phase 6 범위(TODO 262–268), 사용자 게이트.
> **범위 깊이 = (b)**: 인터페이스+테스트 골격 + 실 `SubprocessBackend` + `gh` 공식 문서 대조로 `GitHubAdapter` 기능완성. 실제 호스트 붙는 라이브 E2E만 Phase 9로 연기.

---

## 1. 목표와 비목표

### 목표
- 공통 **Git 호스트 인터페이스**(PR 생성 / 리뷰어 지정 / 상태·리뷰 조회 / 머지)를 정의하고, **GitHub 어댑터를 기능완성**(D5, `gh`)한다.
- **사용자 게이트**의 호스트 조각: 사용자를 리뷰어로 지정(항상 별도 명시 호출)하고, **리뷰 이벤트 커서**로 이번 라운드의 새 판정을 감지해 재개 신호를 노출한다.
- GitLab(`glab`)·Forgejo(`tea`) 어댑터를 **선언**하고, 정확한 argv/파싱은 라이브 검증 전까지 provisional로 둔다.
- 실제 호스트/네트워크 없이 **결정적으로 테스트**되도록 실행 substrate를 주입되는 `CommandBackend`로 분리(테스트=`FakeCommandBackend`). (b) 범위이므로 실 `SubprocessBackend`도 함께 구현.

### 비목표 (이 Phase에서 하지 않음)
- **오케스트레이션 일시정지/재개 루프** — Phase 8. 여기선 호스트 원시기능(조회·재개 신호·재요청)만.
- **메신저 알림** — Phase 7.
- **강제(guardrail) 층** — 이 (b) 클라이언트 증분의 비목표. 두 층으로 나뉜다.
  - ⑴ **허브 pre-receive**(Phase 3, `ADR-0007`): 경로 규칙과 **균일 ref 규칙**은 신원 무관·무인증으로 강제할 수 있으나, Leader 간 ref 격리는 신원이 필요해 advisory다(`ADR-0006`).
  - ⑵ **호스트 브랜치 보호**(Phase 6 **강제 증분**, `ADR-0009`): ①형식·②검토 required check, ③승인+dismiss-stale, `main` require-PR, `sot/<slug>` 소스브랜치, 감사 이력 보존. PR·승인·머지결과 상태가 필요한 호스트 인증 기능이라 허브로는 불가. 이 증분은 (b) 클라이언트 증분과 별개다(§7·§8).
  - `merge`는 원시기능으로만 노출하고 정책 강제는 하지 않는다.
- **호스트 인증 셋업** — `gh`/`glab`/`tea` 로그인은 호스트측 사전 준비로 가정. (참고: `gh pr edit --add-reviewer`는 팀 조회에 `read:org` 스코프가 필요할 수 있음 — `HOST_MATRIX` 검증 케이스.)
- **라이브 E2E 검증** — Phase 9 도그푸딩(가드된 스모크). provisional 항목은 `HOST_MATRIX.md`.

---

## 2. 핵심 설계 결정

### 2.1 구조 — Phase 5와 동일한 3축 합성 (Client = Adapter + Backend)
`GitHostClient`가 수명주기(PR 열기 → 리뷰어 지정 → 상태·리뷰 폴링 → 머지)를 소유하고, 변하는 축만 교체한다. `GitHostAdapter`(호스트 지식, 데이터 선언) + 주입 `CommandBackend`(실행). ADR-0005 근거 계승.

### 2.2 실행은 **한 방(one-shot) 명령**, 세션이 아니다
`CommandBackend.run(argv)` → `(stdout, stderr, exit_code, argv)`. 프로세스 실패는 raise가 아니라 `exit_code≠0`+`stderr`로 표면화.

### 2.3 PR·리뷰 상태는 **권위 결과가 아니다**
판단용 신호일 뿐, 권위는 progress(ADR-0004). stdout을 작업 결과로 파싱하지 않는다(ADR-0003).

### 2.4 호스트 명령은 **호스트측**에서 실행 (Maintainer 상주, D15 예외). Phase 3 컨테이너 substrate와 별개 층.
(용어 주의: "호스트측/호스트 머신"은 Maintainer가 상주하는 실행 환경을 뜻하고, "git 호스트"는 GitHub 등 인증된 원격을 뜻한다 — 별개 개념. `ADR-0007`의 "호스트 층"은 전자, 아래 "호스트 브랜치 보호"의 "호스트"는 후자다.)

### 2.5 통제 어휘로 상태를 고정
`PullRequestState`·`ReviewDecision`·`MergeMethod`. 어댑터는 호스트 값 → 이 어휘 매핑만 데이터로 선언.

### 2.6 리뷰어 지정은 **항상 별도 명시 단계**
리뷰어를 create 명령에 끼워넣지 않는다. 근거: Forgejo `tea pulls create`엔 리뷰어 플래그가 없어(사후 지정만) 세 호스트 공통 경로가 "생성 후 별도 지정"뿐이다. create에서 완전히 빼면 "조용한 미지정" 채널이 사라지고 지정 실패는 `GitHostError`로 드러난다. 리뷰어는 게이트용 **사람 1명**이라 단일 `reviewer: str`.

### 2.7 PR 핸들은 **조회(view) JSON 단일 파싱**
세 호스트의 create는 JSON을 내지 않는다(`gh pr create`는 성공 시 stdout에 PR **URL 한 줄**). `open_pull_request`는 **create→view 합성**: create로 참조(ref)만 얻고, `PullRequest` 핸들은 조회 JSON에서 구성. 파싱이 조회 한 곳으로 모인다.

### 2.8 게이트 재개는 **리뷰 이벤트 커서**로 감지 (라운드3~4 합의 A~G — 핵심)
`reviewDecision`(집계값)의 "리셋"에 의존하지 않는다. **GitHub에서 리뷰 재요청은 기존 `CHANGES_REQUESTED`를 지우지 않기** 때문이다(해제 수단은 리뷰 dismiss 또는 리뷰어의 새 리뷰 제출뿐; 재요청만으로 차단이 풀리면 보안 구멍). 그래서 라운드N의 "새 판정"은 집계 enum 비교가 아니라 **리뷰 이력 커서**로 감지한다:
- **리뷰 목록은 전체 이력 `reviews`를 본다**(합의 B). 라운드3의 `latestReviews`는 사용자당 최신 1개뿐이라, 뒤에 온 `COMMENTED`가 앞선 종결 판정(변경요청)을 가려버린다.
- 대기 시작(=`request_review` 직후) 시점에 대상 리뷰어의 **최신 리뷰 식별자**를 커서로 포착한다(리뷰가 없으면 `None`). 식별자는 **불투명 리뷰 `id`**(제출시각 `submittedAt` 아님, `PRR_` 접두 하드코딩 없음 — 합의 C).
- 재개 조건 = 대상 리뷰어의 종결 리뷰(APPROVED/CHANGES_REQUESTED)가 **`reviews` 스트림에서 커서보다 나중 위치**에 있을 때(합의 D). "id가 다르다"만으로 보면 낡은(더 앞선) 종결 리뷰가 잘못 재개를 트리거하므로 **위치**로 판정한다. 같은 `CHANGES_REQUESTED` 재발도 나중 위치라 잡힌다. `COMMENTED`는 비종결.
- `reviewRequests`는 **이질적**이다(합의 E): User/Bot는 `login`, Team은 slug/name(login 없음). 대상과 안 맞는 항목은 `GitHostError`가 아니라 **건너뛴다**. 멤버십(요청 미응답 여부)은 보조 신호(`awaiting`).
- **게이트 리뷰어 ≠ PR 작성자**(합의 F): 봇/머신 계정이 PR을 열고 사람이 게이트 리뷰어라는 배포 전제. self-request/self-review 호스트 거동은 host-verified — `HOST_MATRIX`.
- `request_review` 재호출은 리뷰어를 요청 목록에 되돌려 놓을 뿐(재요청) 판정을 리셋하지 않는다.
- **잔여 provisional(합의 G)**: GitLab/Forgejo 등가 필드, `reviews` 페이지네이션·순서, 커서 `id`가 dismiss로 사라질 때 폴백 — 모두 `HOST_MATRIX`.

---

## 3. 인터페이스 contract

```python
from enum import Enum
from pathlib import Path
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass

class PullRequestState(Enum):
    OPEN = "open"; MERGED = "merged"; CLOSED = "closed"
    UNKNOWN = "unknown"               # 호스트 값이 매핑에 없음(파싱 실패 아님)

class ReviewDecision(Enum):
    PENDING = "pending"               # 판정 없음
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENTED = "commented"           # 코멘트만(비종결)

class MergeMethod(Enum):
    MERGE = "merge"; SQUASH = "squash"; REBASE = "rebase"

# 종결(대기를 끝내는) 판정. COMMENTED는 비종결.
TERMINAL_DECISIONS = frozenset({ReviewDecision.APPROVED, ReviewDecision.CHANGES_REQUESTED})

@dataclass(frozen=True)
class PullRequest:
    number: int; url: str; head: str; base: str

@dataclass(frozen=True)
class CommandResult:
    stdout: str; stderr: str; exit_code: int
    argv: list[str]                   # 실패 원인 추적용(호출된 argv)

@dataclass(frozen=True)
class ReviewEvent:
    """대상 리뷰어의 단일 리뷰(reviews 스트림 순서 보존)."""
    review_id: str                    # 불투명 리뷰 id(합의 C)
    decision: ReviewDecision

@dataclass(frozen=True)
class ReviewSnapshot:
    """대상 리뷰어 관점의 리뷰 표본 — 게이트 커서 비교용(§2.8, 합의 A/D).
    events는 reviews 전체 이력에서 대상 리뷰어 항목만 골라 순서(오래된→최신)를 보존한 것.
    커서(리뷰 id) 이후의 종결 이벤트를 '위치'로 판정해야 하므로 최신 1개가 아니라 순서열을 싣는다."""
    events: "tuple[ReviewEvent, ...]"   # 스트림 순서(오래된→최신); 없으면 빈 튜플
    awaiting: bool                       # 리뷰어가 아직 reviewRequests에 있는가(요청 미응답)

    @property
    def latest_review_id(self) -> "str | None":
        return self.events[-1].review_id if self.events else None

    def terminal_after(self, cursor_id: "str | None") -> "ReviewDecision | None":
        """커서 이후(스트림 위치 기준)의 첫 종결 판정. 없으면 None(합의 D).
        cursor_id=None이면 전체 events에서 첫 종결 판정을 본다.
        cursor_id가 events에 없으면(dismiss로 사라짐) None을 반환해 대기를 유지한다
        — dismiss 폴백은 provisional(합의 G, HOST_MATRIX)."""
        started = cursor_id is None
        for ev in self.events:
            if not started:
                if ev.review_id == cursor_id:
                    started = True
                continue
            if ev.decision in TERMINAL_DECISIONS:
                return ev.decision
        return None

@dataclass(frozen=True)
class GateResult:
    """wait_for_decision 결과. timed_out으로 '판정 확정'과 '시간초과'를 구별."""
    timed_out: bool
    state: PullRequestState
    decision: ReviewDecision

class GitHostError(RuntimeError):
    """성공을 기대한 명령이 실패했거나 성공 stdout 파싱이 실패했을 때. 필드 고정."""
    def __init__(self, argv: list[str], exit_code: int, stdout: str, stderr: str):
        self.argv, self.exit_code, self.stdout, self.stderr = argv, exit_code, stdout, stderr
        super().__init__(f"command failed (exit {exit_code}): {' '.join(argv)}\n{stderr or stdout}")
    @classmethod
    def from_result(cls, result: CommandResult) -> "GitHostError":
        return cls(result.argv, result.exit_code, result.stdout, result.stderr)

class CommandBackend(ABC):
    """호스트 CLI 실행 substrate. 테스트=FakeCommandBackend, 실사용=SubprocessBackend. one-shot."""
    @abstractmethod
    def run(self, argv: list[str], cwd: "Path | None" = None,
            env: "Mapping[str, str] | None" = None) -> CommandResult:
        """argv 실행 후 결과 반환(argv 포함). 프로세스 실패는 raise하지 않고 exit_code≠0으로 표면화."""

class GitHostAdapter(ABC):
    """Git 호스트 고유 지식. parse_*는 base 구체 메서드, 서브클래스는 데이터(cli, 필드명, 값 맵)와
    argv 빌더만. 유일한 추상 메서드는 build_* 4개."""
    name: str                         # "github" | "gitlab" | "forgejo"
    cli: str                          # "gh" | "glab" | "tea"

    # view(get-pr) JSON 필드/맵 (서브클래스 선언; provisional — HOST_MATRIX)
    _NUMBER_FIELD: str = "number"; _URL_FIELD: str = "url"
    _STATE_FIELD: str = "state";   _STATE_MAP: Mapping[str, PullRequestState] = {}
    _REVIEWS_FIELD: str = "reviews"            # 리뷰 전체 이력(순서 보존; latestReviews는 사용자당 최신뿐이라 부적합 — 합의 B)
    _REVIEW_AUTHOR_PATH: tuple = ("author", "login")   # 리뷰 항목의 리뷰어 식별
    _REVIEW_STATE_FIELD: str = "state"; _REVIEW_ID_FIELD: str = "id"   # 불투명 리뷰 id(제출시각 아님 — 합의 C)
    _REVIEW_STATE_MAP: Mapping[str, ReviewDecision] = {}
    _REVIEW_REQUESTS_FIELD: str = "reviewRequests"
    _REQUEST_LOGIN_FIELD: str = "login"        # User/Bot만; Team은 login 없음(합의 E, parse_review가 건너뜀)

    @abstractmethod
    def build_create_pr_command(self, head: str, base: str,
                                title: str, body: str) -> list[str]:
        """PR 생성 argv. body는 인자로 받아 argv에 싣는다(list argv라 셸 이스케이프 안전;
        초장문은 --body-file 사용이 provisional). 리뷰어는 포함하지 않는다(§2.6)."""
    @abstractmethod
    def build_get_pr_command(self, ref: "int | str") -> list[str]:
        """PR 조회(view) argv. ref는 호스트가 view에 받는 형태(GitHub=번호|URL, GitLab=번호 — provisional).
        JSON 출력 요청에 number,url,state,reviews,reviewRequests 포함(합의 B: latestReviews 아님)."""
    @abstractmethod
    def build_request_review_command(self, number: int, reviewer: str) -> list[str]:
        """리뷰어 추가(재요청) argv. 재호출=재요청(판정 리셋 아님, §2.8). 단일 리뷰어."""
    @abstractmethod
    def build_merge_command(self, number: int, method: MergeMethod) -> list[str]: ...

    def parse_create_ref(self, result: CommandResult) -> str:
        """create stdout → 조회용 ref. 기본: 마지막 비어있지 않은 줄(gh는 URL). 비면 GitHostError."""
        for line in reversed(result.stdout.splitlines()):
            if line.strip():
                return line.strip()
        raise GitHostError.from_result(result)

    def parse_pr(self, result: CommandResult, head: str, base: str) -> PullRequest:
        """view JSON → PullRequest(number/url). 필드 부재·형오류·비-dict JSON은 GitHostError."""
        data = self._loads(result)
        try:
            return PullRequest(number=int(data[self._NUMBER_FIELD]),
                               url=str(data[self._URL_FIELD]), head=head, base=base)
        except (KeyError, TypeError, ValueError) as e:
            raise GitHostError(result.argv, result.exit_code, result.stdout, str(e)) from e

    def parse_pr_state(self, result: CommandResult) -> PullRequestState:
        """view JSON → PR 수명 상태(모니터링용). 미지 값 → UNKNOWN."""
        data = self._loads(result)
        return self._STATE_MAP.get(str(data.get(self._STATE_FIELD)), PullRequestState.UNKNOWN)

    def parse_review(self, result: CommandResult, reviewer: str) -> ReviewSnapshot:
        """view JSON의 reviews/reviewRequests → 대상 리뷰어의 ReviewSnapshot(§2.8, 합의 A~E).
        reviews(전체 이력, 순서 보존)에서 대상 리뷰어 항목만 골라 ReviewEvent 순서열(오래된→최신)을 만들고,
        각 항목의 id·state를 뽑는다(state→ReviewDecision은 _REVIEW_STATE_MAP; 미지 값 무시하지 말고 COMMENTED로
        보수 처리할지는 서브클래스 맵이 결정). reviewRequests 멤버십으로 awaiting 판정하되,
        login 없는 이질 항목(Team 등)은 건너뛴다. JSON/구조 오류는 GitHostError."""
        ...

    def _loads(self, result: CommandResult) -> dict:
        import json
        try:
            data = json.loads(result.stdout)
        except (ValueError, TypeError) as e:
            raise GitHostError(result.argv, result.exit_code, result.stdout, str(e)) from e
        if not isinstance(data, dict):
            raise GitHostError(result.argv, result.exit_code, result.stdout, "not a JSON object")
        return data

class GitHostClient:
    """공통 Git 호스트 인터페이스 = adapter + backend 합성체. 결과 권위는 progress(ADR-0004)."""
    CLOSED_STATES = frozenset({PullRequestState.MERGED, PullRequestState.CLOSED})

    def __init__(self, adapter: GitHostAdapter, backend: CommandBackend,
                 cwd: "Path | None" = None): ...

    def open_pull_request(self, head: str, base: str,
                          title: str, body: str) -> PullRequest:
        """create→view 합성(§2.7). 어느 단계든 exit_code≠0이면 GitHostError. 리뷰어는 안 붙인다."""
    def request_review(self, pr: PullRequest, reviewer: str) -> None:
        """리뷰어 지정/재요청(멱등적 재호출=재요청; 판정 리셋 아님). 실패 시 GitHostError."""
    def poll_state(self, pr: PullRequest) -> PullRequestState:
        """PR 수명 상태 1회 조회(모니터링, 비권위). 실패 시 GitHostError."""
    def poll_review(self, pr: PullRequest, reviewer: str) -> ReviewSnapshot:
        """대상 리뷰어 리뷰 표본 1회 조회(게이트 커서용). 실패 시 GitHostError."""
    def wait_for_decision(self, pr: PullRequest, reviewer: str, timeout: float,
                          poll_interval: float = 30.0, *,
                          max_consecutive_errors: int = 3) -> GateResult:
        """게이트 재개 대기(§2.8). 시작 시 대상 리뷰어의 최신 리뷰 id를 커서로 포착 →
        커서보다 스트림상 나중의 종결 리뷰(terminal_after)가 오거나 PR이 CLOSED_STATES면
        GateResult(timed_out=False), timeout이면 GateResult(timed_out=True). COMMENTED는 비종결.
        일시 실패는 max_consecutive_errors까지 놓친 폴링으로 관용, 초과 시 GitHostError."""
    def merge(self, pr: PullRequest, method: MergeMethod = MergeMethod.SQUASH) -> None:
        """머지 원시기능(정책 게이트는 오케스트레이터). 실패 시 GitHostError.
        주의: SoT 게이트 PR은 감사 이력 보존(squash 비활성)과 충돌하므로 MergeMethod.MERGE 필수(§9)."""
```

### 동작 규약 (요약)
- `open_pull_request(head, base, title, body)` → ① `backend.run(adapter.build_create_pr_command(head, base, title, body), cwd)`; 실패 시 `GitHostError`. ② `ref = adapter.parse_create_ref(result)`. ③ `backend.run(adapter.build_get_pr_command(ref), cwd)`; 실패 시 `GitHostError`. ④ `adapter.parse_pr(...)` 반환. 리뷰어는 안 붙인다.
- `request_review(pr, reviewer)` → `backend.run(adapter.build_request_review_command(pr.number, reviewer), cwd)`, 실패 시 `GitHostError`. **재호출=재요청**(리뷰어를 요청 목록에 재등록; 기존 판정은 지우지 않음 §2.8).
- `poll_state(pr)` → `backend.run(adapter.build_get_pr_command(pr.number), cwd)` → `adapter.parse_pr_state`. 미지 값 `UNKNOWN`. 명령 실패만 `GitHostError`.
- `poll_review(pr, reviewer)` → 같은 view 명령 → `adapter.parse_review(result, reviewer)`.
- `wait_for_decision(pr, reviewer, timeout)`:
  - 시작 시 `cursor = poll_review(pr, reviewer).latest_review_id` (커서 = `request_review` 직후 상태; 리뷰 없으면 `None`).
  - `poll_interval` 간격으로: `state = poll_state`; `snap = poll_review`; `decision = snap.terminal_after(cursor)`.
    - PR 상태 ∈ `CLOSED_STATES`면 `GateResult(False, state, decision or PENDING)`.
    - `decision`이 `None`이 아니면(커서보다 나중 위치의 종결 판정 존재) `GateResult(False, state, decision)`. 같은 `CHANGES_REQUESTED` 재발도 나중 위치라 잡힘; `COMMENTED`는 `terminal_after`가 무시하므로 대기 유지(합의 D).
  - `GitHostError`는 연속 실패로 세어 `max_consecutive_errors`까지 놓친 폴링으로 관용, 초과 시 전파. 성공 시 카운터 리셋.
  - timeout 시 `GateResult(True, 마지막 state, 마지막 decision or PENDING)`.
  - **주의(비원자성)**: `open_pull_request` 성공 후 `request_review` 실패로 예외가 나면 호출자(Phase 7/8)는 `wait_for_decision`으로 진행하면 안 된다.
- `merge(pr, method)` → `backend.run(adapter.build_merge_command(...), cwd)`, 실패 시 `GitHostError`. 선조건은 호출자 책임(§2.3). SoT 게이트 PR은 `MergeMethod.MERGE`(§9).

---

## 4. 어댑터 (호출 규약 구현)

| 항목 | GitHubAdapter | GitLabAdapter | ForgejoAdapter |
|---|---|---|---|
| `name` / `cli` | `github` / `gh` | `gitlab` / `glab` | `forgejo` / `tea` |
| create argv | `gh pr create --head H --base B --title T --body BODY` | `glab mr create --source-branch H --target-branch B --title T --description BODY` | `tea pulls create --head H --base B --title T --description BODY` |
| create stdout | PR **URL 한 줄** → `parse_create_ref` | URL/id (provisional) | id (provisional) |
| get(view) argv | `gh pr view REF --json number,url,state,reviews,reviewRequests` | `glab mr view N -F json` | `tea pulls N --output json` |
| view ref 형태 | 번호·**URL**·branch 수용 | **번호**(URL 미수용 → URL서 번호 파싱) provisional | 번호 provisional |
| request-review argv | `gh pr edit N --add-reviewer R` (`read:org` 주의) | `glab mr update N --reviewer +R` | `tea pulls edit N --add-reviewers R` |
| merge argv | `gh pr merge N --squash\|--merge\|--rebase` | `glab mr merge N …` | `tea pulls merge N …` |
| state 맵 | OPEN/MERGED/CLOSED | opened/merged/closed | provisional |
| 리뷰 판정 | `reviews[].state`(전체 이력·순서): APPROVED/CHANGES_REQUESTED/COMMENTED | provisional | provisional |
| 리뷰 id / 리뷰어 | `reviews[].id`(불투명) / `reviews[].author.login` | provisional | provisional |

> **확정(계약)**: 통제 어휘 3종; 리뷰어는 create 제외·`request_review`(단일, 추가) 전담; body는 builder 인자→argv; PR 핸들은 create→view 조회 JSON 단일 파싱; **게이트 재개는 리뷰 `id` 커서 + 스트림 위치**(집계 리셋 아님, `latestReviews` 아님 §2.8); `parse_*`는 base 구체 메서드; 미지 값→`UNKNOWN`/`PENDING`; JSON·필드·명령 실패→`GitHostError`(argv 포함); `wait_for_decision`은 `GateResult(timed_out)`로 시간초과 명시.
> **provisional(라이브 — `HOST_MATRIX.md`)**: 정확한 서브커맨드·플래그·JSON 스키마. 확인점 — ① `gh pr create`에 `--json` 없음(URL만). ② `glab mr view`는 URL 미수용 → 번호 파싱 필요. ③ Forgejo는 `pulls` 계열. ④ `glab --reviewer R`은 교체, `+R`이 추가. ⑤ `gh pr edit --add-reviewer`는 팀 조회에 `read:org` 필요 가능(대안 `gh api …/requested_reviewers`). ⑥ `reviews`/`reviewRequests` JSON 스키마(리뷰 `id`·`author.login`·`state` 필드명)와 GitLab/Forgejo 등가 필드; `reviews` 페이지네이션·정렬 순서; `reviewRequests`의 Team(login 없음) 형태. GitLab·Forgejo 값 맵은 라이브에서 확정.

---

## 5. 패키지 레이아웃 (D12 → `WIP/`)

```
WIP/axdt/git_host/
  __init__.py
  state.py            # PullRequestState, ReviewDecision, MergeMethod, TERMINAL_DECISIONS
  models.py           # PullRequest, CommandResult, ReviewEvent, ReviewSnapshot, GateResult, GitHostError
  backend.py          # CommandBackend(ABC) + FakeCommandBackend + SubprocessBackend
  client.py           # GitHostClient
  adapters/
    __init__.py; base.py            # GitHostAdapter(ABC)
    github.py         # GitHubAdapter (gh) — 기능완성
    gitlab.py; forgejo.py           # provisional
  HOST_MATRIX.md; README.md
  tests/
    __init__.py; test_state.py; test_models.py; test_backend.py
    test_adapters.py; test_client.py
```

`SubprocessBackend`는 `subprocess.run` 얇은 래퍼(실제 CLI 실행), (b) 범위 포함.

---

## 6. 테스트 (계약 고정)

- **test_state**: 어휘 안정성(3종 열거); `TERMINAL_DECISIONS`가 APPROVED·CHANGES_REQUESTED만 담음(COMMENTED 제외).
- **test_models**: `GitHostError` 필드 보존; `CommandResult.argv` 보존; `PullRequest`/`ReviewEvent`/`ReviewSnapshot`/`GateResult` 불변; `ReviewSnapshot.latest_review_id`(빈 events→None); **`ReviewSnapshot.terminal_after`**: (i) cursor=None서 종결 반환, (ii) 커서 이후 위치의 종결만 반환, (iii) 커서보다 앞선(이전 위치) 종결은 무시→None, (iv) COMMENTED 무시, (v) 커서 id가 events에 없으면→None.
- **test_backend**: `FakeCommandBackend` 스크립트+호출 기록·`exit_code≠0` 표면화; `SubprocessBackend`는 자명 명령(`python -c`)으로 stdout·exit·argv 캡처 검증.
- **test_adapters**:
  - 추상(TypeError); argv 빌더(create=리뷰어·`--json` 없음·body 포함, get=REF·JSON 필드에 `reviews`, request-review=단일 추가, merge=방식별).
  - `parse_create_ref`(URL→ref; 빈 stdout→`GitHostError`).
  - `parse_pr`(JSON→핸들; **필드 부재/비-int number/비-dict JSON→`GitHostError`**, 원시 예외 누출 없음).
  - `parse_pr_state`(매핑; 미지→`UNKNOWN`).
  - `parse_review`(합의 A~E): `reviews`에서 대상 리뷰어 항목만 골라 **순서 보존 ReviewEvent 순서열**(id·판정); 다른 리뷰어 항목 제외; `reviewRequests` 멤버십→`awaiting`; **login 없는 이질 항목(Team) 건너뜀**(에러 아님); 리뷰 없음→`(events=(), awaiting)`.
- **test_client** (`FakeCommandBackend`):
  - `open_pull_request`: **create→view 2단 호출**(두 argv 기록) → 조회 JSON 핸들.
  - `request_review`: 단일 추가 호출; 실패→`GitHostError`.
  - `poll_state`/`poll_review`: 매핑·스냅샷; 비권위.
  - `wait_for_decision` (커서·스트림 위치):
    - (a) 커서=None서 새 `APPROVED`→`GateResult(timed_out=False, APPROVED)`.
    - (b) 커서 이후 위치의 `CHANGES_REQUESTED`→종결 반환.
    - (c) PR `MERGED`/`CLOSED`→종결 반환.
    - (d) **낡음 회귀(합의 D 핵심)**: 종결 리뷰가 커서와 **동일 위치이거나 그보다 앞선** 경우 즉시반환 안 함(대기 유지).
    - (e) **재발 포착**: 커서보다 **나중 위치**의 `CHANGES_REQUESTED`면 판정값이 같아도 종결.
    - (f) 커서보다 나중 위치의 `COMMENTED`는 비종결→대기 유지.
    - (g) **timeout 구별**: 미도달 시 `GateResult(timed_out=True)`.
    - (h) 일시 `GitHostError`가 `max_consecutive_errors` 이내면 관용·초과면 전파.
  - `merge`: 방식별 argv; 선조건 강제 안 함.
  - **실패 표면화**: 각 명령 `exit_code≠0`→`GitHostError`(argv 등 필드 보존).

`FakeCommandBackend`는 argv에 대응하는 결과를 큐/맵으로 스크립트하고 호출을 기록해 결정적으로 검증한다.

---

## 7. 산출물 체크리스트 (TODO Phase 6 매핑)

- [ ] GitHub 1차 완성 → `adapters/github.py` + 실 `SubprocessBackend`. **`gh` 문서(pr create/view/edit/merge, `--json` 필드 특히 `reviews`) 대조 검증** 포함((b) 조건).
- [ ] 사용자 게이트(호스트 조각) → `request_review`(지정·재요청) + `poll_review`/`wait_for_decision`(리뷰 커서 재개 신호). 루프는 Phase 8, 알림은 Phase 7.
- [ ] 호스트 추상화 → `adapters/base.py` + `client.py` + `state.py` + `models.py`.
- [ ] GitLab/Forgejo 어댑터 → provisional(`+` 추가·`pulls` 명령·URL→번호 파싱 주의).
- [ ] 호스트 차이 검증 매트릭스 → `HOST_MATRIX.md`.
- [ ] ADR → `WIP/adr/0008-git-host-abstraction.md` (0006은 Phase 3 예약).
- [ ] 단위 테스트 + `README.md`.
- [ ] **강제 증분(별개 sub-spec + `WIP/adr/0009-sot-readiness-host-enforcement.md`)** — 호스트 브랜치 보호 강제(rule-sot-readiness 강제 매핑: `main` require-PR, ①형식·②검토 required check, ③승인+dismiss-stale, `sot/<slug>` 소스브랜치, 감사 이력 보존) + 초기 마이그레이션 스윕 + fail-closed + **최종 게이트 검사**(네이티브 required check로는 `accepted`/`rejected` 게이트식을 표현 못 하므로 CI 산출물+사용자 결정으로 정책 계산) + 강제용 `HOST_MATRIX` 행. **이 (b) 클라이언트 증분과 별개.** **Phase 6 완료 = 클라이언트 증분 ∧ 강제 증분**; **Phase 8(D6 트리거) 선행조건 = 강제 증분.**

---

## 8. 다음 단계 접합

- **Phase 7(메신저)**: 게이트 도달 시 `open_pull_request` → `request_review(pr, user)` 후 알림 발송. `COMMENTED`만으론 재개 안 됨(정식 승인/변경요청 필요)을 알림·README에 표면화.
- **Phase 8(오케스트레이션)**: 라운드N = `request_review(pr, user)`(재요청) → `wait_for_decision(pr, user, timeout)`(내부에서 커서 포착). `GateResult.timed_out`으로 "판정 확정 vs 계속 대기"를 구별해 일시정지/재개 제어. 변경요청 반복도 리뷰 `id`·스트림 위치가 매 라운드 갱신돼 자연히 잡힌다.
- **강제 층(3주체)**: 클라이언트 원시기능 **소비** = Phase 7·8; **허브 경로/균일-ref 강제** = Phase 3(`ADR-0007`); **호스트 브랜치 보호 강제** = **Phase 6 강제 증분**(`ADR-0009`, §7). Phase 6 클라이언트의 상대는 허브가 아니라 **호스트**다(`ADR-0006`: GitHub는 허브 위 별도 원격).
  - **ref 강제의 축**: 허브는 **신원 무관 규칙**(경로·균일 ref)만 강제하고 **신원 기반**(Leader 간 ref 격리)은 advisory다(`ADR-0006`).
  - **허브 `main` ref 보호**: "`main` require-PR"은 *호스트* main에만 참이다. 허브(무인증 daemon)의 main은 어떤 클론이든 직접 push 가능하다. 이를 **균일 ref 규칙**으로 막는다 — daemon 경로의 `main` 직접 push 거부 + Maintainer/미러 전용 갱신(**Phase 3 몫**). 상세·인수는 별도 핸드오프 `WIP/handoff-hub-main-ref-protection.md`.

---

## 9. 확정된 결정

- **범위 깊이 = (b)**: 골격 + 실 `SubprocessBackend` + `gh` 문서 대조 기능완성, 라이브 E2E는 Phase 9.
- **Forgejo 전송 = `tea` CLI** (HTTP 분기 연기).
- **merge = 순수 원시기능.** 정책은 3주체가 나눠 강제(호출순서=오케스트레이터 Phase 8 / 허브 경로·ref=Phase 3 / 호스트 브랜치 보호=Phase 6 강제 증분, `ADR-0009`). 시그니처 유지하되 기본값 `SQUASH`는 감사 이력 보존(squash 비활성)과 충돌하므로 **SoT 게이트 PR은 `MergeMethod.MERGE` 필수**(README/`HOST_MATRIX` 표면화).
- **ADR 번호 = 0008**(호스트 추상화; 0006은 Phase 3 예약). **강제 증분 = 신규 0009**(0007 확장 대신 — 0007은 phase3 세션이 정식화 중이라 브랜치 편집 충돌 회피).
- **귀속(Phase1 정합)**: 호스트 브랜치 보호 강제 = **Phase 6**(강제 증분). 현행 규칙 `rule-sot-readiness` 강제 매핑과 정합. 허브 경로/균일-ref만 Phase 3.
- **게이트 커서 = 리뷰 `id` + 스트림 위치**(합의 A~G): `reviews` 전체 이력, 불투명 리뷰 id 커서, 커서보다 나중 위치의 종결 판정으로 재개, `reviewRequests` 이질 항목 건너뜀, 리뷰어≠작성자 전제.

## 10. 교차검증 반영 이력

**라운드2 (2026-07-05)**: create가 JSON 미출력 → create→view 합성(§2.7); 리뷰어 fallback 과설계 → 플래그 폐기·`request_review` 단일화(§2.6); `GitHostError` 필드 고정; `poll_interval=30s`·일시 실패 관용; `glab +R`·`tea pulls` 정확도.

**라운드3 (2026-07-06)**:
- **재요청=판정 리셋 전제가 거짓**(GitHub은 dismiss로만 해제) → `wait_for_decision`을 집계 enum 비교에서 **리뷰 id 커서**로 교체(§2.8), `request_review`의 리셋 문구 삭제.
- **N1** `latestReviews` 폴백이 view 필드에 없어 실현 불가 → view argv에 `latestReviews,reviewRequests` 추가, `parse_review` 신설(게이트 전용), `parse_pr_state`는 상태만.
- **N2** `wait_for_decision` timeout 반환 모호 → `GateResult(timed_out)` 명시 신호.
- **body 모순** → body를 `build_create_pr_command` 인자로(argv, list-exec라 이스케이프 안전; 초장문 `--body-file`은 provisional).
- **parse 예외 누출** → `parse_pr`/`_loads`의 필드 부재·형오류·비-dict를 `GitHostError`로 포장; `CommandResult.argv`로 실패 argv 보존.
- **Minor** → `gh` `read:org` 주의, GitLab view는 URL 미수용(번호 파싱), `poll_state` cwd 일관.

**라운드4 합의 A~G (2026-07-07, Codex+Fable 수렴)**:
- **B** `latestReviews`(사용자당 최신) → **`reviews`(전체 이력)**: 뒤에 온 COMMENTED가 앞선 종결 판정을 가리는 문제 제거. view argv·`_REVIEWS_FIELD`·§4 표 반영.
- **C** 커서 신원 `submittedAt` → **불투명 리뷰 `id`**(`PRR_` 접두 하드코딩 없음). `_REVIEW_ID_FIELD`.
- **D** 비교 "id가 다르다" → **"커서보다 `reviews` 스트림상 나중 위치의 종결 판정"**: 낡은(앞선) 종결의 오재개 방지. `ReviewSnapshot` 계약 재설계 — `latest_review_id/decision`(최신 1개) → **`events` 순서열 + `terminal_after(cursor_id)`**(Codex 단서: 기존 계약은 "커서 이후 종결"을 표현 못 함). `ReviewEvent` 신설, `TERMINAL_DECISIONS` 모듈 상수화, `wait_for_decision` 동작규약·§6 테스트 갱신.
- **E** `reviewRequests` 이질성(User/Bot=login, Team=login 없음) → 대상과 안 맞는 항목 **건너뜀**(GitHostError 아님). `parse_review` 명세.
- **F** **게이트 리뷰어 ≠ PR 작성자**(봇/머신 계정) 배포 전제 → `HOST_MATRIX`.
- **G** 잔여 provisional: GitLab/Forgejo 등가 필드, `reviews` 페이지네이션·순서, 커서 id dismiss 폴백(`terminal_after`는 커서 부재 시 None으로 대기 유지).

**Phase1 귀속 정합화 (2026-07-07, Codex+Fable 수렴 (A))**:
- `rule-sot-readiness` 강제 매핑이 호스트 브랜치 보호(①②③ required check·승인+dismiss-stale·`main` require-PR·`sot/<slug>`·감사 이력 보존)를 **Phase 6**에 배정하는데, 현행 §1/§8/§9는 "강제=Phase 3"이라 적어 충돌 → **(A) Phase 6이 흡수**로 정합화. 근거: 무인증 허브는 PR·승인·머지결과 상태가 없어 이 강제를 표현 못 함(능력 부재); §1이 인용한 `ADR-0007`이 오히려 호스트 브랜치 보호를 "Phase 6 이후"로 분류(오인용).
- **순차 분리**: 귀속은 Phase 6으로 교정하되 강제 층은 **별도 증분(§7 + ADR 0009)**으로 분리 — (b) 클라이언트 계약(§2.1~§3)은 불변.
- 리라벨: §1 비목표(두 층 분리), §8(3주체 + 상대는 호스트 + ref 신원-축 + 허브 main), §9(merge 3주체 + MERGE 각주), §2.4(용어 각주). 직교 결함 **허브 main ref 보호** = Phase 3 몫으로 핸드오프.
