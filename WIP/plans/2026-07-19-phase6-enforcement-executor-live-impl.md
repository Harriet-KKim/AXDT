# Phase 6 강제 게이트 실행부(GitHubGatePorts) 라이브 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **착수 시점 = Phase 9 (라이브 도그푸딩).** 이 계획의 모든 Task는 실제 GitHub 저장소·`gh` CLI 응답을 봐야 스키마가 확정되는 provisional 구현이다(스펙 §1 비목표·§8·§9). 순수 코어(`gate.py`·`controller.py`·`keys.py`·`models.py`)와 포트 계약(`ports.py`)은 이미 완성·동결이며, 이 계획은 `hosts/github.py`의 7개 `NotImplementedError` 스텁을 채우고 사전 관문 하나를 배선하는 것만 다룬다. 순수 코어 계약은 건드리지 않는다.

**Goal:** `WIP/axdt/sot_gate/hosts/github.py`의 7개 포트(`compute_landing_keys`·`read_pr_metadata`·`read_ci_artifacts`·`read_channel_decisions`·`read_approvals`·`merge_pull_request`·`verify_ruleset_config`)를 실제 `gh api` 호출로 구현하고, `axdt-critical-paths` 블록 사전 관문을 컨트롤러에 배선한다.

**Architecture:** `github.py`는 `git_host`의 `CommandBackend`(ABC)를 주입받아 gh 호출을 그 안으로 격리하고(subprocess 직접 호출 금지), (b) 클라이언트의 adapter+backend 분리를 계승한다. 각 포트는 gh 응답 JSON을 파싱해 순수 코어 계약(`models.py`의 `PRMetadata`·`ChannelDecision`·`ApprovalEvent`·`ConsistencyArtifact`·`CompletenessArtifact`, `keys.py`의 두 키)으로 매핑한다. 포트는 원시 사실만 채우고 결정권 논리곱(admin ∧ 명단 ∧ 사람)은 순수 코어가 계산한다.

**Tech Stack:** Python 3(`py -3`), `gh` CLI(`gh api`), pytest. 재사용: `axdt.git_host.backend.{CommandBackend,FakeCommandBackend,SubprocessBackend}`, `axdt.git_host.models.{PullRequest,CommandResult,GitHostError}`.

## Global Constraints

- **provisional 경계**: 아래 gh api 엔드포인트·필드·산출물 저장 위치·제안 머지 결과 취득 방법은 스펙 §8이 라이브 미확정으로 열어 둔 것이다. 각 Task의 "라이브 확정 항목"을 실측으로 메꾸기 전에는 스키마를 동결하지 않는다(스펙 §8·§10 테스트 경계).
- **테스트 경계**: 순수 코어·컨트롤러 테스트는 포트 수준 `FakeGatePorts`로 하며 그대로 둔다(회귀 152개). `github.py`는 CLI 수준 `FakeCommandBackend`로 결정적 단위 테스트하고, 최종 스키마 확정은 라이브 스모크(Phase 9)로 한다. `github.py`를 `FakeGatePorts`로 테스트하지 않는다(스펙 §6).
- **두 키 재계산 금지**: `read_approvals`의 `approved_judgment`·`approved_completeness`는 §2.3 (ㄱ) base 복원 또는 (ㄴ) 구조화 스탬프로 취득하며 머지 시점 재계산하지 않는다(규칙 ③ 위반, 스펙 54행).
- **포트는 판정하지 않는다**: `read_channel_decisions`·`read_approvals`는 `role_name`·사람 여부 원시 사실만 채운다. admin·명단·사람 논리곱은 순수 코어가 `inputs.allowlist`와 계산한다(스펙 §2.7·§4.1).
- **사전 관문 두 개는 `evaluate_gate` 밖**: `verify_ruleset_config`와 `axdt-critical-paths` 블록 판독은 컨트롤러가 머지 직전 직렬화 잠금 안에서 수행하고, 실패를 `touches_enforcement_surface=False`로 접지 않고 직접 fail-closed RED로 처리한다(스펙 §7 (ㅁ)·506행).
- **선언 단일 진실원**: 룰셋 대조 값은 `WIP/axdt/sot_gate/ENFORCEMENT_MATRIX.md`가 정본이다. `verify_ruleset_config`는 그 선언을 읽어 라이브와 대조한다(손사본 금지).

---

## Task 0: CommandBackend 주입 + gh api JSON 헬퍼

**Files:**
- Modify: `WIP/axdt/sot_gate/hosts/github.py` (생성자 + 헬퍼 추가)
- Test: `WIP/axdt/sot_gate/tests/test_hosts_github.py` (신규)

**Interfaces:**
- Consumes: `axdt.git_host.backend.CommandBackend`·`FakeCommandBackend`, `axdt.git_host.models.{CommandResult,GitHostError}`.
- Produces: `GitHubGatePorts(backend: CommandBackend, repo: str)` 생성자. `_api_json(self, *args) -> dict|list`(gh api 호출→JSON 파싱, exit≠0이면 `GitHostError`, JSON 파싱 실패도 `GitHostError`). 이후 모든 Task가 이 헬퍼를 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성** — `FakeCommandBackend`에 gh 응답을 스크립트하고 `_api_json`이 argv를 바르게 만들고 stdout JSON을 파싱하는지, exit≠0이면 `GitHostError`를 던지는지.
- [ ] **Step 2: 실패 확인** — `py -3 -m pytest WIP/axdt/sot_gate/tests/test_hosts_github.py -v` → 생성자 인자 불일치로 FAIL.
- [ ] **Step 3: 최소 구현** — 생성자에 `backend`·`repo` 저장. `_api_json`은 `backend.run(["gh","api",*args])` 호출, `result.exit_code != 0`이면 `GitHostError.from_result(result)`, 성공 stdout을 `json.loads`(예외를 `GitHostError`로 포장).
- [ ] **Step 4: 통과 확인** — 위 pytest PASS.
- [ ] **Step 5: 커밋** — `feat(phase6): GitHubGatePorts에 CommandBackend 주입 + gh api JSON 헬퍼`.

**라이브 확정 항목(provisional):** `gh api`의 정확한 인증·페이지네이션·rate-limit 처리는 라이브에서 확정한다(스펙 §8).

---

## Task 1: verify_ruleset_config — 룰셋 대조

**Files:** Modify `hosts/github.py`(`verify_ruleset_config`); Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`, `ENFORCEMENT_MATRIX.md` 선언. Produces `verify_ruleset_config(self) -> bool`.

**gh 매핑(스펙 §4.1·§8):** `gh api repos/{repo}/rulesets` → 활성 룰셋 목록, 각 id로 `gh api repos/{repo}/rulesets/{id}` → 상세. `ENFORCEMENT_MATRIX.md`의 대조 규칙 4항목을 검사: RS-A/RS-B 분리 · RS-B `bypass_actors == []` · RS-B 필수 파라미터(`required_approving_review_count`·`dismiss_stale_reviews_on_push`·`allowed_merge_methods:["merge"]`·`non_fast_forward`·`deletion`) 존재 · RS-C 존재·`sot/*`·`non_fast_forward`+`deletion`·`bypass_actors == []`. 하나라도 어긋나면 `False`.

- [ ] **Step 1: 실패 테스트** — 3개 룰셋 정상 JSON→`True`; RS-B에 `bypass_actors` 있음→`False`; RS-A/RS-B 합쳐짐→`False`; RS-C 없음→`False`; RS-B 필수 파라미터 누락→`False`.
- [ ] **Step 2: 실패 확인** — pytest FAIL(`NotImplementedError`).
- [ ] **Step 3: 최소 구현** — 위 gh 호출로 룰셋 상세를 모아 4항목 검사, 전부 만족 시 `True`.
- [ ] **Step 4: 통과 확인** — pytest PASS.
- [ ] **Step 5: 커밋** — `feat(phase6): verify_ruleset_config — 라이브 룰셋을 ENFORCEMENT_MATRIX와 대조`.

**라이브 확정 항목:** `rulesets` 응답의 정확한 필드 경로(예 `rules[].parameters`)·룰셋 식별(이름 vs id)·TOCTOU 창 좁히기(룰셋 변경 감시)는 라이브에서 확정(스펙 §4.1·§8).

---

## Task 2: read_pr_metadata — PR 메타데이터 + touches_sot

**Files:** Modify `hosts/github.py`(`read_pr_metadata`); Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`, `PullRequest`. Produces `read_pr_metadata(pr) -> PRMetadata`.

**gh 매핑(스펙 §2.6·§8, 조사 A-2):** `gh api repos/{repo}/pulls/{n}` → `author`(user.login)·`head_ref`(head.ref)·`head_repo`(head.repo.full_name)·`head_sha`(head.sha)·`state`(OPEN/MERGED/CLOSED→`PullRequestState`). 제안된 머지 결과의 변경 경로 집합을 얻어(예 `pulls/{n}/files`, provisional) `target-content projection`(`docs/sot/{requirements,specification,test-design}` 콘텐츠에서 `README.md`·`_TEMPLATE.md` 제외)과 교차하면 `touches_sot=True`. `touches_enforcement_surface`는 Task 3에서 채운다.

- [ ] **Step 1: 실패 테스트** — PR JSON→필드 매핑; 변경분에 `docs/sot/specification/spec.md` 있으면 `touches_sot=True`; `README.md`만이면 `False`; state 매핑.
- [ ] **Step 2: 실패 확인** — pytest FAIL.
- [ ] **Step 3: 최소 구현** — PR 조회 파싱 + 변경 경로 projection 교차. `head_sha`는 조회 시점 head.sha(머지 head 고정용).
- [ ] **Step 4: 통과 확인** — pytest PASS.
- [ ] **Step 5: 커밋** — `feat(phase6): read_pr_metadata — PR 메타데이터 + touches_sot projection 교차`.

**라이브 확정 항목:** 제안 머지 결과 변경분 취득 방법(merge preview vs 로컬 merge), `pulls/{n}/files` 페이지네이션·rename 표기는 라이브에서 확정(스펙 §8·524행).

---

## Task 3: critical-paths 블록 사전 관문 → touches_enforcement_surface

**Files:** Modify `hosts/github.py`(블록 읽기·glob 매칭·`read_pr_metadata` 확장); Modify `controller.py`(사전 관문 배선); Test `test_hosts_github.py`·`test_controller.py`.

**Interfaces:** Consumes 신뢰 base(`main`)의 `docs/sot/rule/protected-paths.md`. Produces glob 매칭기 + `touches_enforcement_surface` 판정 + 컨트롤러의 fail-closed 사전 관문.

**규칙(스펙 §7·506행, `protected-paths.md` 블록 문법):** ` ```axdt-critical-paths ` 펜스 블록을 **신뢰 base(`main`) 버전**으로 읽는다(후보 PR 버전 금지 — 자기수정 우회 차단). `critical <glob>` 줄만 유효, `**`=구분자 포함, `*`=한 세그먼트 내, trailing `**`=디렉터리 자체+하위. 변경 경로는 rename의 이전·이후 합집합 모두에 glob 적용. 블록 부재·기형·유효 `critical` 행 0개면 `touches_enforcement_surface=False`로 접지 않고 컨트롤러가 `evaluate_gate` 이전 사전 관문에서 직접 fail-closed RED.

- [ ] **Step 1: 실패 테스트(파싱·매칭)** — 블록 파싱; glob 매칭(`WIP/axdt/sot_gate/**`가 `.../github.py` 매칭, trailing `**` 디렉터리 자체 매칭); 블록 부재/기형→예외 신호.
- [ ] **Step 2: 실패 테스트(컨트롤러 배선)** — 블록 못 읽으면 `merge_if_green`이 머지 안 하고 fail-closed RED; touches_enforcement_surface만 참인 PR이 포크 거부+결정권자 승인 관문을 통과/차단.
- [ ] **Step 3: 실패 확인** — pytest FAIL.
- [ ] **Step 4: 최소 구현** — base 블록 읽기(`gh api .../contents/docs/sot/rule/protected-paths.md?ref=main`, provisional) → 파싱 → glob 매칭 → `touches_enforcement_surface`; 컨트롤러에 사전 관문 추가(블록 읽기 실패→RED).
- [ ] **Step 5: 통과 확인** — pytest PASS(순수 코어 회귀 포함).
- [ ] **Step 6: 커밋** — `feat(phase6): critical-paths 블록 사전 관문 배선 + glob 매칭`.

**라이브 확정 항목:** base 파일 읽기 엔드포인트·인코딩(base64 contents API), 변경분 취득은 라이브에서 확정(스펙 §524행·§8).

---

## Task 4: read_channel_decisions — PR 코멘트 + role_name

**Files:** Modify `hosts/github.py`(`read_channel_decisions`); Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`. Produces `read_channel_decisions(pr) -> tuple[ChannelDecision, ...]`.

**gh 매핑(스펙 §2.7·§4.1, 조사 A-4):** `gh api repos/{repo}/issues/{n}/comments` → append-only 코멘트 스트림. 구조화 코멘트(완전 결속 키 + accepted/rejected 스탬프)를 파싱해 `ChannelDecision(key, decision, author, comment_id, created_at, updated_at, deleted, author_role, author_is_human)`. `author_role`은 `gh api repos/{repo}/collaborators/{login}/permission`의 **`role_name`**(레거시 `permission` 금지 — maintain을 write로 뭉갬). 원시 사실만 채우고 결정권 논리곱은 코어가 계산.

- [ ] **Step 1: 실패 테스트** — 구조화 코멘트→`ChannelDecision` 매핑; `updated_at != created_at`→편집 표기; `role_name`→`author_role`; 비구조화 코멘트 무시.
- [ ] **Step 2: 실패 확인** — pytest FAIL.
- [ ] **Step 3: 최소 구현** — 코멘트 조회 + 스탬프 파싱 + `role_name` 조회.
- [ ] **Step 4: 통과 확인** — pytest PASS.
- [ ] **Step 5: 커밋** — `feat(phase6): read_channel_decisions — 구조화 코멘트 + role_name 원시 사실`.

**라이브 확정 항목:** 코멘트 스키마·편집/삭제 감지 방식(타임스탬프 vs 이벤트)·페이지네이션은 라이브에서 확정(스펙 §8·519행).

---

## Task 5: read_approvals — 리뷰 스트림 + 두 키 스탬프

**Files:** Modify `hosts/github.py`(`read_approvals`); Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`. Produces `read_approvals(pr) -> tuple[ApprovalEvent, ...]`.

**gh 매핑(스펙 §2.3·§8, 조사 A-5):** `gh api repos/{repo}/pulls/{n}/reviews` → 승인 리뷰 스트림 전체. 각 승인을 `ApprovalEvent(approver, approved_judgment, approved_completeness, seq, approver_role, approver_is_human, dismissed)`. **두 키는 재계산 금지** — 스켈레톤은 §2.3 (ㄴ) 구조화 스탬프(승인 본문에 두 키를 명시한 기계판독 스탬프)를 의도하며, 두 키 스탬프가 모두 없는 승인은 무효. GitHub 승인 객체가 승인 시점 base를 안 실어 (ㄱ) 대신 (ㄴ) 선택(라이브에서 (ㄱ)/(ㄴ) 최종 채택). `dismissed`면 제외. `approver_role`은 Task 4와 같은 `role_name`.

- [ ] **Step 1: 실패 테스트** — 두 키 스탬프 있는 승인→`ApprovalEvent`; 스탬프 없는 승인→무효(배제); dismissed→제외; 여러 승인 전량 반환(대표 선정 금지).
- [ ] **Step 2: 실패 확인** — pytest FAIL.
- [ ] **Step 3: 최소 구현** — reviews 조회 + 스탬프 파싱(두 키) + `role_name`.
- [ ] **Step 4: 통과 확인** — pytest PASS.
- [ ] **Step 5: 커밋** — `feat(phase6): read_approvals — 리뷰 스트림 + 두 키 구조화 스탬프`.

**라이브 확정 항목:** 두 키 취득 (ㄱ) base 복원 vs (ㄴ) 스탬프 최종 채택, 승인 본문 편집 탐지(REST가 편집 시각 미노출)는 라이브에서 확정(스펙 §8·520행).

---

## Task 6: read_ci_artifacts — 산출물 저장소 조회

**Files:** Modify `hosts/github.py`(`read_ci_artifacts`); Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`. Produces `read_ci_artifacts(pr) -> tuple[ConsistencyArtifact|None, CompletenessArtifact|None]`.

**gh 매핑(스펙 §4.2·§8, 조사 A-3/C):** ②검토 CI의 두 신뢰 산출물을 **산출물 저장소**에서 읽는다(커밋 상태 금지 — push 권한자 위조 가능). 정합성=`ConsistencyArtifact(judgment, format_ok, review_clear, open_blocking)`, 완전성=`CompletenessArtifact(sweep_key, completeness_clear, open_blocking)`. 각자 없거나 파싱 실패면 그 자리 `None`(fail-closed). 불변식 `clear == (open_blocking == ())` 위반은 반환하되 순수 코어가 RED 처리.

- [ ] **Step 1: 실패 테스트** — 두 산출물 정상→매핑; 정합성만 있음→`(artifact, None)`; 파싱 실패→`None`; 각 `open_blocking`의 `FullBindingKey` 매핑.
- [ ] **Step 2: 실패 확인** — pytest FAIL.
- [ ] **Step 3: 최소 구현** — 산출물 저장소 조회 + JSON→데이터클래스 매핑, 부재/실패→None.
- [ ] **Step 4: 통과 확인** — pytest PASS.
- [ ] **Step 5: 커밋** — `feat(phase6): read_ci_artifacts — 두 신뢰 산출물 조회 + fail-closed`.

**라이브 확정 항목:** 산출물 저장 위치·JSON 스키마·쓰기 통제(신뢰 CI 신원/서명)는 하중을 받는 보안 요소로 라이브에서 확정(스펙 §4.2·§8·521행). ②검토 CI 워크플로 자체(GitHub Actions, base 통제)는 별도 산출물이다.

---

## Task 7: merge_pull_request — head 고정 머지 + 머지 커밋 SHA

**Files:** Modify `hosts/github.py`(`merge_pull_request`); Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`, `HeadMovedError`. Produces `merge_pull_request(pr, judgment, completeness, head_sha) -> None`(라이브에서 머지 커밋 SHA 반환으로 확장, 스펙 §2.9).

**gh 매핑(스펙 §2.5·§2.9·§8, 조사 A-6):** `gh api -X PUT repos/{repo}/pulls/{n}/merge`, `merge_method=merge`, **`sha={head_sha}`**(평가 스냅샷값, 재조회 금지). head가 그새 움직여 호스트가 거부하면(`405` 등) `HeadMovedError`로 번역해 던진다(반환 None 유지). base 부동은 RS-A 배타성+직렬화가 보장(REST에 base 고정 수단 없음).

- [ ] **Step 1: 실패 테스트** — 정상 머지→`merge_method=merge`·`sha=head_sha` argv 확인; head sha 불일치 거부(`405`)→`HeadMovedError`; 그 밖 실패→`GitHostError`.
- [ ] **Step 2: 실패 확인** — pytest FAIL.
- [ ] **Step 3: 최소 구현** — PUT merge 호출, head 불일치 코드→`HeadMovedError`.
- [ ] **Step 4: 통과 확인** — pytest PASS.
- [ ] **Step 5: 커밋** — `feat(phase6): merge_pull_request — head 고정 머지 + HeadMovedError 번역`.

**라이브 확정 항목:** 머지 API 정확한 거부 코드 분기(`405` vs `409`)·머지 커밋 SHA 반환 확장(§2.9)·`AuditRecord.base` first-parent 기록은 라이브에서 확정(스펙 §2.9·118행·§8).

---

## Task 8: compute_landing_keys — 제안 머지 결과 두 키

**Files:** Modify `hosts/github.py`(`compute_landing_keys`); Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json` + 두 키 계산 로직(`keys.py`의 성분 규약 참조). Produces `compute_landing_keys(pr) -> tuple[JudgmentKey, CompletenessSweepKey]`.

**gh 매핑(스펙 §2.3·§4.2·§8, 조사 D):** 제안된 머지 결과(`merge(base, head)`) 상태에서 판정 키 4성분(projection 트리 해시·적용 rule 지문·`review_policy_epoch`·규칙 카탈로그 manifest digest)과 완전성 스윕 키 3성분(projection 트리 해시·활성 카탈로그 입력 digest·epoch)을 계산. 성분 정의·정규화·직렬화는 규칙 `rule-sot-readiness` §②가 정본이고 게이트는 불투명 비교만. 적용 rule 지문·활성 카탈로그는 머지 결과에서, 검사 코드·정책은 신뢰 base(`main`)에서 읽는다.

- [ ] **Step 1: 실패 테스트** — 결정성(같은 머지 결과=같은 두 키); projection 트리만 바뀌면 두 키 모두 변화; rule 본문만 편집하면 완전성 스윕 키만 변화; README/_TEMPLATE 제외.
- [ ] **Step 2: 실패 확인** — pytest FAIL.
- [ ] **Step 3: 최소 구현** — 제안 머지 결과 취득 + 두 키 성분 계산(정규화는 규칙 정본 재사용).
- [ ] **Step 4: 통과 확인** — pytest PASS.
- [ ] **Step 5: 커밋** — `feat(phase6): compute_landing_keys — 제안 머지 결과 두 키 계산`.

**라이브 확정 항목:** 제안 머지 결과 취득 방법(gh merge preview vs 로컬 git merge)은 스펙이 선택하지 않은 provisional의 핵심이다(스펙 §8·523행). `sot_lint`와 공유하는 정규화 구현의 단일화 여부도 라이브에서 확정.

---

## 라이브 스모크(Phase 9, 계약 테스트 뒤)

단위 테스트(`FakeCommandBackend`) 통과 후, 실제 공개 저장소에 RS-A/RS-B/RS-C를 걸고 컨트롤러를 배포해 `gh api` 스키마를 실측 확정한다(스펙 §9). 확정된 스키마로 각 Task의 "라이브 확정 항목"을 메꾸고 provisional 표기를 제거한다. 이 시점에 `ADR-0009`·`ADR-0007`을 proposed→accepted로 올린다(강제 CODE 착지).

## Self-Review (계획 대 스펙)

- **스펙 커버리지**: 7개 포트 전부 Task 1~2·4~8, 사전 관문 Task 3, 룰셋 대조 Task 1, 산출물 Task 6 — §3 계약·§2.x·§4.x 매핑됨.
- **provisional 명시**: 각 Task에 "라이브 확정 항목"을 두어 스펙 §8 목록(gh 스키마·산출물 저장·머지 결과 취득·변경분·두 키 취득)을 빠짐없이 표기.
- **타입 일관성**: 반환형은 `models.py`·`keys.py` 동결 계약 그대로. 새 타입 없음.
