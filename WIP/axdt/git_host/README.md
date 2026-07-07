# axdt.git_host

**목적:** GitHub·GitLab·Forgejo를 동일 인터페이스로 다루는 공통 Git 호스트 추상 (Phase 6). PR 열기·리뷰어 지정·상태/리뷰 폴링·머지를 제공한다. GitHub는 `gh` 공식 문서 대조로 기능완성, GitLab/Forgejo는 구조만 선언한 provisional이다(`HOST_MATRIX.md`). 설계: `WIP/specs/2026-07-05-phase6-git-host-design.md`.

## 구성
- `state.py` — `PullRequestState`·`ReviewDecision`·`MergeMethod` 통제 어휘.
- `models.py` — `PullRequest`·`CommandResult`·`ReviewEvent`·`ReviewSnapshot`·`GateResult`·`GitHostError`.
- `backend.py` — `CommandBackend` ABC + 테스트용 `FakeCommandBackend` + 실사용 `SubprocessBackend`.
- `adapters/base.py` — `GitHostAdapter` ABC(호스트 고유 지식). `parse_*`는 base가 구체 구현하고, 서브클래스는 데이터(cli, 필드명, 값 맵)와 `build_*` argv 빌더만 제공한다.
- `adapters/github.py` — `GitHubAdapter`(기능완성).
- `adapters/gitlab.py`, `adapters/forgejo.py` — `GitLabAdapter`/`ForgejoAdapter`(provisional).
- `client.py` — `GitHostClient`(adapter + backend 합성, 동기 폴링 수명주기).
- `HOST_MATRIX.md` — 호스트별 provisional 검증 매트릭스.
- `tests/` — 계약 고정 단위 테스트.

## 핵심 계약
- 합성: `GitHostClient(adapter, backend)`. 실행 substrate는 주입한다 — 실사용은 `SubprocessBackend`, 테스트는 `FakeCommandBackend`.
- 실행은 세션이 아니라 **한 방(one-shot) 명령**이다. 프로세스 실패는 raise가 아니라 `exit_code != 0` + `stderr`로 표면화되고, `GitHostClient`가 이를 `GitHostError`로 승격한다.
- 리뷰어 지정은 PR 생성에 끼워넣지 않고 항상 `request_review`로 별도 지정한다.
- PR 핸들은 create→view 합성으로 얻는다: create는 JSON을 내지 않는(호스트 공통) 대신 참조만 반환하고, `PullRequest`는 뒤이은 view 조회 JSON에서 구성한다.
- 게이트 재개는 집계 상태 리셋이 아니라 **리뷰 id 커서 + 스트림 위치**로 판정한다(`wait_for_decision` 시작 시 커서를 포착하고, 그보다 나중 위치의 종결 판정이 오면 재개).
- 조회 결과(`poll_state`/`poll_review`)는 모니터링용 신호일 뿐이다 — 권위 있는 작업 결과는 progress이고(ADR-0004), stdout을 결과로 파싱하지 않는다(ADR-0003).

## 구성/주입은 ADR-0005 재사용
어댑터(호스트 지식) + 백엔드(실행) 합성과 백엔드 주입 패턴은 Phase 5 agent runner(`ADR-0005`)의 구조를 그대로 재사용한 것이다. 이 추상화 자체의 결정은 `ADR-0010`에 있다.

## 사용자 게이트 흐름
```
open_pull_request(head, base, title, body) -> PullRequest
request_review(pr, user)                  -> None
wait_for_decision(pr, user, timeout)       -> GateResult
```
`GateResult.timed_out`으로 "판정 확정"과 "시간초과"를 구별한다. `timed_out=False`면 `decision`(APPROVED/CHANGES_REQUESTED, 또는 PR이 닫혀서 온 PENDING)을 읽고, `timed_out=True`면 대기를 이어가거나 재알림한다.

## 주의(캐비어트)
- **COMMENTED는 게이트를 재개하지 않는다.** 종결 판정은 APPROVED/CHANGES_REQUESTED뿐이다. 리뷰를 재요청(`request_review` 재호출)해도 이전 판정은 리셋되지 않는다 — 재요청은 리뷰어를 요청 목록에 다시 올릴 뿐이다.
- **게이트 리뷰어는 PR 작성자와 달라야 한다.** PR은 봇/머신 계정이 열고, 사람이 게이트 리뷰어를 맡는 배포를 전제한다.
- **SoT 게이트 PR은 `MergeMethod.MERGE`로 머지해야 한다.** `merge()`의 기본값 `SQUASH`는 감사 이력 보존과 충돌한다.

## Phase 8 핸드오프(잔여 한계)
- **일시적 빈 reviews와 진입 커서:** `wait_for_decision`은 시작 시 대상 리뷰어의 최신 리뷰 id를 커서로 포착한다. 호스트가 일시적으로 빈 `reviews`를 반환하면 커서가 `None`이 되고, 이 경우 직전 라운드의 낡은 종결 판정이 새 라운드의 종결로 오재개될 수 있다. 이 계층에서는 "진짜로 리뷰가 없음"과 "일시적으로 비어 보임"을 완벽히 구분할 수 없다 — Phase 8에서 호출자가 라운드 컨텍스트(예: 이번 라운드 시작 시각/기대 리뷰어)를 넘겨 보강한다.
- **재요청과 커서 포착 사이의 판정 race:** `request_review` 직후 `wait_for_decision` 진입 전 극히 짧은 창에서 리뷰어가 즉시 판정하면 그 판정이 커서 시점 이전에 들어올 수 있다. 스펙 정의상 이 경우는 종결로 오인되지 않고 `timed_out=True`(대기 지속/재알림)로 안전하게 커버된다 — 데이터 유실이 아니라 한 번 더 대기하는 보수적 동작이다.

## 사용 예시
```python
from axdt.git_host.client import GitHostClient
from axdt.git_host.backend import FakeCommandBackend
from axdt.git_host.adapters.github import GitHubAdapter
from axdt.git_host.state import MergeMethod

client = GitHostClient(GitHubAdapter(), FakeCommandBackend(results=[...]))

pr = client.open_pull_request(head="sot/my-change", base="main",
                              title="SoT change", body="...")
client.request_review(pr, "alice")
result = client.wait_for_decision(pr, "alice", timeout=3600)

if not result.timed_out and result.decision.value == "approved":
    client.merge(pr, MergeMethod.MERGE)
```

## 테스트
`cd WIP && py -3 -m pytest axdt/git_host -v`
