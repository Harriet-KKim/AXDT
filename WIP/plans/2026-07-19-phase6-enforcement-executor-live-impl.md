# Phase 6 강제 게이트 실행부(GitHubGatePorts) 라이브 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **착수 시점 = Phase 9 (라이브 도그푸딩).** 이 계획의 모든 Task는 실제 GitHub 저장소·`gh` CLI 응답을 봐야 스키마가 확정되는 provisional 구현이다(스펙 §1 비목표·§8·§9). 순수 코어(`gate.py`·`keys.py`·`models.py`)와 포트 계약(`ports.py`)의 **시그니처·데이터 모델·기존 동작은 동결**이며, 이 계획은 `hosts/github.py`의 7개 `NotImplementedError` 스텁을 채우고 두 사전 관문(룰셋 점검·critical-paths)을 배선한다. 두 사전 관문은 `controller.py`/`ports.py`의 동결 계약을 확장하므로 아래 Global Constraints의 "동결 계약 확장" 규약을 반드시 따른다(조용한 변경 금지).

**Goal:** `WIP/axdt/sot_gate/hosts/github.py`의 7개 포트를 실제 `gh api` 호출로 구현하고, 룰셋 점검·`axdt-critical-paths` 두 사전 관문을 컨트롤러 층에 배선한다.

**Architecture:** `github.py`는 `git_host`의 `CommandBackend`(ABC)를 주입받아 gh 호출을 그 안으로 격리하고(subprocess 직접 호출 금지), (b) 클라이언트의 adapter+backend 분리를 계승한다. 각 포트는 gh 응답 JSON을 파싱해 순수 코어 계약(`models.py`·`keys.py`)으로 매핑한다. 포트는 원시 사실만 채우고 결정권 논리곱(admin ∧ 명단 ∧ 사람)은 순수 코어가 계산한다.

**Tech Stack:** Python 3(`py -3`), `gh` CLI(`gh api`), pytest. 재사용: `axdt.git_host.backend.{CommandBackend,FakeCommandBackend,SubprocessBackend}`, `axdt.git_host.models.{PullRequest,CommandResult,GitHostError}`.

## Global Constraints

- **라이브 스키마 캡처 우선 (조기 동결 금지)**: 각 포트 Task는 **Step 0으로 라이브 `gh api` 응답을 캡처하고 스키마를 확인**한 뒤, 그 캡처를 fixture로 삼아 red 테스트를 쓴다. 추정 JSON으로 red-green을 먼저 끝내면 Phase 9가 확정해야 할 스키마를 fixture가 사실상 동결한다(스펙 §1·§8). 캡처 fixture는 `tests/fixtures/`에 실제 응답 형태로 보관한다.
- **페이지네이션 계약**: `gh api` 목록 응답(rulesets·PR files·comments·reviews)은 페이지네이션된다. Task 0의 공통 페이지네이션 헬퍼로 **전 페이지를 수집**하고, 각 포트에 다중 페이지 red 테스트를 둔다. 변경 파일의 뒤 페이지를 놓치면 `touches_sot`·`touches_enforcement_surface`가 `False`로 잘못 접혀 강제 장치 변경 PR이 pass-through되므로, fail-closed 관점에서 필수다(스펙 §2.6·§7).
- **동결 계약 확장 규약**: critical-paths 사전 관문(Task 4)과 기동 점검(Task 2)은 `controller.py`/`ports.py`의 동결 시그니처·동작을 바꾼다. 스펙 §7이 예정한 일이나 동결 계약 변경이므로, **구현 전에 둘 중 하나를 명시적으로 결정**한다 — (a) 동결 계약(포트·컨트롤러 실패 신호) 개정을 별도 승인 작업으로 올리거나, (b) 동결 코어 밖의 Phase 9 호스팅 래퍼에서 관문을 수행한다. Task 안에서 조용히 `controller.py`를 바꾸지 않는다.
- **provisional 경계**: gh api 엔드포인트·필드·산출물 저장 위치·제안 머지 결과 취득·두 키 취득 방식(ㄱ/ㄴ)·사람/기계 판별은 스펙 §8이 라이브 미확정으로 열어 둔 것이다. 각 Task의 "라이브 확정 항목"을 실측으로 메꾸기 전에는 스키마·방식을 동결하지 않는다(스펙 §8·§10).
- **테스트 경계**: 순수 코어·컨트롤러 테스트는 포트 수준 `FakeGatePorts`로 하며 그대로 둔다(회귀 152개 유지). `github.py`는 CLI 수준 `FakeCommandBackend`로 결정적 단위 테스트하고, 최종 스키마 확정은 라이브 스모크(Phase 9)로 한다. `github.py`를 `FakeGatePorts`로 테스트하지 않는다(스펙 §6).
- **두 키 재계산 금지**: `read_approvals`의 `approved_judgment`·`approved_completeness`는 §2.3 (ㄱ) base 복원 또는 (ㄴ) 구조화 스탬프로 취득하며 머지 시점 재계산하지 않는다(규칙 ③ 위반, 스펙 54행). (ㄱ)/(ㄴ) 선택은 §8 provisional이다(Task 6).
- **포트는 판정하지 않는다**: `read_channel_decisions`·`read_approvals`는 `role_name`·사람 여부·`dismissed` 등 **원시 사실만** 채운다. admin·명단·사람 논리곱과 dismissed 유효성은 순수 코어가 계산한다(스펙 §2.7·§3·§2.6 항목10).
- **사람/기계 판별(§2.7·§8)**: 결정권 = admin ∧ 명단 ∧ 사람 계정. `author_is_human`·`approver_is_human`은 동결 필수 필드다. 판별법은 §8 provisional이므로 라이브에서 결정하고, 사람·봇·판별불능을 각각 테스트하되 **판별불능은 fail-closed**로 처리한다.
- **선언 단일 진실원**: 룰셋 대조 값은 `WIP/axdt/sot_gate/ENFORCEMENT_MATRIX.md`가 정본이다. `verify_ruleset_config`는 그 선언을 값 일치까지 대조한다(손사본 금지).

---

## Task 0: CommandBackend 주입 + gh api JSON 헬퍼 + 페이지네이션

**Files:** Modify `hosts/github.py`; Test `tests/test_hosts_github.py`(신규).

**Interfaces:**
- Consumes: `axdt.git_host.backend.{CommandBackend,FakeCommandBackend}`, `axdt.git_host.models.{CommandResult,GitHostError}`.
- Produces: `GitHubGatePorts(backend: CommandBackend, repo: str)`; `_api_json(self, *args) -> dict|list`(gh api→JSON 파싱; exit≠0·malformed JSON·빈 stdout·예상 밖 top-level 타입 → `GitHostError`); `_api_paginated(self, *args) -> list`(전 페이지 수집).

- [ ] **Step 1: 실패 테스트** — `FakeCommandBackend`로 (a) 정상 JSON 파싱, (b) exit≠0 → `GitHostError`, (c) **exit 0 + malformed JSON → `GitHostError`**, (d) **빈 stdout → `GitHostError`**, (e) **top-level 타입이 기대와 다름(list 기대인데 dict) → `GitHostError`**, (f) `_api_paginated`가 2페이지 응답을 한 리스트로 합침.
- [ ] **Step 2: 실패 확인** — `py -3 -m pytest WIP/axdt/sot_gate/tests/test_hosts_github.py -v` → FAIL.
- [ ] **Step 3: 최소 구현** — 생성자에 `backend`·`repo`; `_api_json`은 `backend.run(["gh","api",*args])` 후 exit·파싱·타입 검사; `_api_paginated`는 `--paginate` 또는 Link 헤더 커서로 전 페이지 수집.
- [ ] **Step 4: 통과 확인** — pytest PASS.
- [ ] **Step 5: 커밋** — `feat(phase6): GitHubGatePorts 주입 + gh api JSON/페이지네이션 헬퍼(fail-closed 파싱)`.

**라이브 확정 항목(provisional):** `gh api` 인증·`--paginate` 동작·rate-limit 처리는 라이브에서 확정(스펙 §8).

---

## Task 1: verify_ruleset_config — 값 정확 대조

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_paginated`·`ENFORCEMENT_MATRIX.md`. Produces `verify_ruleset_config(self) -> bool`.

**gh 매핑(스펙 §4.1·§8):** `gh api repos/{repo}/rulesets` + 각 id로 `rulesets/{id}`. `ENFORCEMENT_MATRIX.md`의 대조 규칙 4항목을 **값 일치까지** 검사(존재만이 아님).

- [ ] **Step 0(라이브): 실제 rulesets 응답 캡처** — 라이브 저장소에서 RS-A/RS-B/RS-C 응답을 캡처해 `tests/fixtures/rulesets_*.json`으로 저장, 필드 경로(`rules[].type`·`rules[].parameters`·`bypass_actors`) 확인.
- [ ] **Step 1: 실패 테스트(캡처 fixture 기반)** — 정상 3룰셋→`True`; **`required_approving_review_count: 2`→`False`**; **`dismiss_stale_reviews_on_push: false`→`False`**; **`allowed_merge_methods: ["squash"]`→`False`**; RS-B에 `bypass_actors` 있음→`False`; RS-A/RS-B 합쳐짐→`False`; **RS-A 부재→`False`**; RS-C 부재→`False`; **RS-C에 `pull_request` 룰 추가→`False`**; 룰셋 목록 다중 페이지.
- [ ] **Step 2: 실패 확인** — pytest FAIL.
- [ ] **Step 3: 최소 구현** — 캡처 스키마로 4항목 값 대조.
- [ ] **Step 4: 통과 확인** — pytest PASS.
- [ ] **Step 5: 커밋** — `feat(phase6): verify_ruleset_config — ENFORCEMENT_MATRIX 값 정확 대조`.

**라이브 확정 항목:** `rulesets` 응답 필드 경로·룰셋 식별(이름 vs id)은 Step 0 캡처로 확정(스펙 §8).

---

## Task 2: 기동 시 룰셋 점검 · 경보 · 실패 감사 (호스팅 배선)

**Files:** Modify `controller.py` 또는 Phase 9 호스팅 래퍼(**동결 계약 확장 규약 적용**); Test `test_controller.py` 또는 호스팅 테스트.

**Interfaces:** Consumes `verify_ruleset_config`. Produces 기동 차단 + 경보 + 실패 감사 기록.

**규칙(스펙 §4.1):** "컨트롤러는 **기동 시와 매 머지의 직렬화 잠금 안에서**" 점검하고, 불일치 시 "경보·감사 기록을 남긴다". 현재 `controller.py:50-52`는 기동 점검을 호스팅 증분(§8) 몫으로 명시 유보했다 — 매 머지 점검은 이미 있으나 기동 점검·경보·실패 감사는 없다.

- [ ] **Step 0: 동결 계약 확장 결정** — 기동 점검·경보·감사를 (a) 컨트롤러 계약 개정으로 넣을지, (b) 호스팅 래퍼에 둘지 명시 결정(Global Constraints "동결 계약 확장").
- [ ] **Step 1: 실패 테스트** — 기동 시 `verify_ruleset_config()==False`면 머지 수용 전 차단 + 감사 기록에 실패 사유; `True`면 정상 기동.
- [ ] **Step 2: 실패 확인** — pytest FAIL.
- [ ] **Step 3: 최소 구현** — 결정한 위치에 기동 점검·경보·실패 감사 배선.
- [ ] **Step 4: 통과 확인** — pytest PASS(회귀 152개 유지).
- [ ] **Step 5: 커밋** — `feat(phase6): 기동 시 룰셋 점검·경보·실패 감사 배선`.

**라이브 확정 항목:** 경보 채널(로그·메신저)은 Phase 7·8 연동으로 확정.

---

## Task 3: read_pr_metadata — PR 메타데이터 + touches_sot

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`·`_api_paginated`·`PullRequest`. Produces `read_pr_metadata(pr) -> PRMetadata`.

**gh 매핑(스펙 §2.6·§8):** PR 조회 → `author`·`head_ref`·`head_repo`·`head_sha`·`state`. 제안된 머지 결과의 변경 경로 집합을 페이지네이션으로 전량 수집해 `target-content projection`(`docs/sot/{requirements,specification,test-design}`에서 `README.md`·`_TEMPLATE.md` 제외)과 교차하면 `touches_sot=True`. `touches_enforcement_surface`는 Task 4에서 채운다.

- [ ] **Step 0(라이브): PR 조회·변경분 응답 캡처** — 실제 PR의 조회 JSON과 변경 파일 목록(다중 페이지 포함)을 fixture로 캡처.
- [ ] **Step 1: 실패 테스트** — 필드 매핑; `docs/sot/specification/spec.md` 변경→`touches_sot=True`; `README.md`만→`False`; **변경 파일 2페이지 중 SoT 파일이 2페이지에 있어도 감지**; state 매핑.
- [ ] **Step 2~4: 실패 확인 → 구현 → 통과.**
- [ ] **Step 5: 커밋** — `feat(phase6): read_pr_metadata — PR 메타데이터 + touches_sot(전 페이지)`.

**라이브 확정 항목:** 제안 머지 결과 변경분 취득 방법(merge preview vs 로컬 merge)·`pulls/{n}/files` 페이지·rename 표기는 Step 0 캡처로 확정(스펙 §8·524행).

---

## Task 4: critical-paths 사전 관문 → touches_enforcement_surface

**Files:** Modify `hosts/github.py`(블록 읽기·glob 매칭·`read_pr_metadata` 확장); **동결 계약 확장 규약 적용** — Modify `controller.py`(사전 관문 배선) 또는 호스팅 래퍼; Test `test_hosts_github.py`·`test_controller.py`.

**규칙(스펙 §7·506행, `protected-paths.md` 블록 문법):** ` ```axdt-critical-paths ` 블록을 **신뢰 base(`main`) 버전**으로 읽는다(후보 PR 버전 금지). `critical <glob>` 줄만 유효, `**`=구분자 포함, `*`=한 세그먼트 내, trailing `**`=디렉터리 자체+하위. **변경 경로는 rename의 이전·이후 경로 합집합 모두에 glob 적용**(critical 경로를 비critical로 옮겨 분류 회피 차단 — 근거: `docs/sot/rule/protected-paths.md:48` 강제-필수 경로 블록). 블록 부재·기형·유효 `critical` 행 0개면 `touches_enforcement_surface=False`로 접지 않고 컨트롤러가 `evaluate_gate` 이전 사전 관문에서 직접 fail-closed RED(`protected-paths.md:57-58`).

- [ ] **Step 0: 동결 계약 확장 결정** — 사전 관문의 RED 실패 신호를 컨트롤러 계약에 넣을지, 호스팅 래퍼에 둘지 명시 결정(포트/컨트롤러에 현재 이 실패 신호 계약이 없음, `ports.py:28`·`controller.py:92`).
- [ ] **Step 1: 실패 테스트(파싱·매칭)** — 블록 파싱; glob 매칭(`WIP/axdt/sot_gate/**`가 `.../github.py` 매칭, trailing `**` 디렉터리 자체 매칭); **rename 이전 경로가 critical이면 매칭**; 블록 부재/기형→예외 신호.
- [ ] **Step 2: 실패 테스트(관문 배선)** — 블록 못 읽으면 `merge_if_green`이 머지 안 하고 fail-closed RED; touches_enforcement_surface만 참인 PR이 포크 거부+결정권자 승인 관문을 통과/차단.
- [ ] **Step 3~5: 실패 확인 → 구현 → 통과(회귀 152 유지) → 커밋** `feat(phase6): critical-paths 사전 관문 + glob 매칭(rename 합집합)`.

**라이브 확정 항목:** base 파일 읽기 엔드포인트·인코딩(contents API base64)·변경분 취득은 Step 0 캡처로 확정(스펙 §524·§8).

---

## Task 5: read_channel_decisions — PR 코멘트 + role_name + 사람 판별

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`·`_api_paginated`. Produces `read_channel_decisions(pr) -> tuple[ChannelDecision, ...]`.

**gh 매핑(스펙 §2.7·§4.1·§8):** `gh api repos/{repo}/issues/{n}/comments`(전 페이지) → 구조화 코멘트 파싱 → `ChannelDecision(key, decision, author, comment_id, created_at, updated_at, deleted, author_role, author_is_human)`. `author_role`은 `collaborators/{login}/permission`의 **`role_name`**(레거시 `permission` 금지). **`author_is_human`은 사람/기계 판별(§8 provisional)로 채운다.** 원시 사실만 채우고 결정권 논리곱은 코어가 계산.

- [ ] **Step 0(라이브): comments·permission·user 응답 캡처** — 코멘트 스트림·`role_name`·계정 유형(User/Bot) 응답을 fixture로 캡처, 사람/기계 판별 사실(예 `type` 필드) 확인.
- [ ] **Step 1: 실패 테스트** — 구조화 코멘트→매핑; `updated_at != created_at`→편집 표기; `role_name`→`author_role`; **계정 유형이 사람→`author_is_human=True`, 봇→`False`, 판별불능→코어 fail-closed로 이어지는 값**; 비구조화 코멘트 무시; 코멘트 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_channel_decisions — 구조화 코멘트 + role_name + 사람 판별`.

**라이브 확정 항목:** 코멘트 스키마·편집/삭제 감지 방식·사람/기계 판별 사실은 Step 0 캡처로 확정(스펙 §8·519행).

---

## Task 6: read_approvals — 리뷰 스트림 + 두 키 취득(라이브 결정) + dismissed 보존

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`·`_api_paginated`. Produces `read_approvals(pr) -> tuple[ApprovalEvent, ...]`.

**gh 매핑(스펙 §2.3·§8):** `gh api repos/{repo}/pulls/{n}/reviews`(전 페이지) → 승인 스트림 **전체**를 `ApprovalEvent(approver, approved_judgment, approved_completeness, seq, approver_role, approver_is_human, dismissed)`로 반환. **어느 승인이 유효한지는 게이트가 판정 — 포트는 대표 선정·필터링을 하지 않는다**(`ports.py:51-55`). `dismissed` 승인도 **`dismissed=True`로 채워 전량 반환**(제외는 코어 몫, `models.py:69`·§2.6 항목10). 두 키는 재계산 금지.

- [ ] **Step 0: 두 키 취득 방식 라이브 결정 게이트** — §2.3 (ㄱ) base 복원 / (ㄴ) 구조화 스탬프 중 하나를 라이브 실측으로 **선택**한다(§8 provisional). 선택 전에는 특정 방식을 필수 계약으로 red 테스트에 고정하지 않는다. reviews 응답·(선택 시) 스탬프 형식을 fixture로 캡처.
- [ ] **Step 1: 실패 테스트(방식 선택 후)** — 여러 승인 **전량 반환**(대표 선정 금지); **dismissed 승인 → `dismissed=True`로 반환(제외 아님)**; 선택한 방식으로 두 키 취득; (ㄴ) 선택 시 **두 키 스탬프 중 하나라도 빠지면 무효**(단일 스탬프만 있는 승인→무효), 둘 다 있으면 유효; reviews 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_approvals — 스트림 전량 반환 + dismissed 보존 + 두 키(선택 방식)`.

**라이브 확정 항목:** (ㄱ)/(ㄴ) 최종 채택, 승인 본문 편집 탐지(REST 편집 시각 미노출)는 Step 0 결정·캡처로 확정(스펙 §8·520행).

---

## Task 7: read_ci_artifacts — 산출물 저장소 조회

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`. Produces `read_ci_artifacts(pr) -> tuple[ConsistencyArtifact|None, CompletenessArtifact|None]`.

**gh 매핑(스펙 §4.2·§8):** ②검토 CI의 두 신뢰 산출물을 산출물 저장소에서 읽는다(커밋 상태 금지). 정합성=`ConsistencyArtifact(judgment, format_ok, review_clear, open_blocking)`, 완전성=`CompletenessArtifact(sweep_key, completeness_clear, open_blocking)`. 각자 없거나 파싱 실패면 `None`(fail-closed). 불변식 위반은 반환하되 코어가 RED.

- [ ] **Step 0(라이브): 산출물 저장 위치·형식 캡처** — ②CI 산출물의 저장 위치·JSON 스키마·쓰기 신원을 fixture로 캡처.
- [ ] **Step 1: 실패 테스트** — 두 산출물 정상→매핑; 정합성만→`(artifact, None)`; 파싱 실패→`None`; `FullBindingKey` 매핑.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_ci_artifacts — 두 신뢰 산출물 + fail-closed`.

**라이브 확정 항목:** 산출물 저장 위치·JSON 스키마·쓰기 통제(신뢰 CI 신원/서명)는 하중을 받는 보안 요소로 Step 0·라이브에서 확정(스펙 §4.2·§8·521행).

---

## Task 8: merge_pull_request — head 고정 머지 + 머지 커밋 SHA 반환

**Files:** Modify `hosts/github.py`(반환형 확장) + `controller.py` 감사 기록(**동결 계약 확장 규약**); Test `test_hosts_github.py`·`test_controller.py`.

**Interfaces:** Consumes `_api_json`·`HeadMovedError`. Produces **`merge_pull_request(pr, judgment, completeness, head_sha) -> str`(머지 커밋 SHA)** — 동결 계약의 `-> None`을 §2.9 확정 결정대로 `None→SHA`로 확장한다.

**gh 매핑(스펙 §2.5·§2.9·§8):** `gh api -X PUT repos/{repo}/pulls/{n}/merge`, `merge_method=merge`, **`sha={head_sha}`**(평가 스냅샷값, 재조회 금지). §2.9는 이미 "라이브 `merge_pull_request`가 머지 API 응답의 **머지 커밋 SHA를 반환**"하고 컨트롤러가 그 커밋의 first-parent를 base SHA로 감사 기록에 넣는다고 **확정**했다(provisional은 API 필드·거부 코드지 SHA 반환 결정이 아님). head가 움직여 거부되면 `HeadMovedError`.

- [ ] **Step 0(라이브): merge API 응답·거부 코드 캡처** — 정상 머지 응답(머지 커밋 SHA 필드)·head 불일치 거부 코드를 fixture로 캡처.
- [ ] **Step 1: 실패 테스트** — 정상 머지→`merge_method=merge`·`sha=head_sha` argv 확인 + **반환값이 머지 커밋 SHA**; head sha 불일치 거부→`HeadMovedError`; 그 밖 실패→`GitHostError`; **컨트롤러 감사 기록의 `base`가 머지 커밋 first-parent SHA**(§2.9).
- [ ] **Step 2~5: 실패 확인 → 구현(반환형 `None→str` 마이그레이션 + 컨트롤러 감사 확장) → 통과 → 커밋** `feat(phase6): merge_pull_request — 머지 커밋 SHA 반환 + first-parent base 감사(§2.9)`.

**라이브 확정 항목:** 거부 코드 정확 분기(`405` vs `409`)·머지 커밋 SHA 필드 경로는 Step 0 캡처로 확정(스펙 §2.9·118행·§8).

---

## Task 9: compute_landing_keys — 제안 머지 결과 두 키

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json` + 두 키 성분 규약(`keys.py`). Produces `compute_landing_keys(pr) -> tuple[JudgmentKey, CompletenessSweepKey]`.

**gh 매핑(스펙 §2.3·§4.2·§8):** 제안된 머지 결과(`merge(base, head)`)에서 판정 키 4성분·완전성 스윕 키 3성분 계산. 성분 정의·정규화는 규칙 `rule-sot-readiness` §②가 정본이고 게이트는 불투명 비교만. 적용 rule 지문·활성 카탈로그는 머지 결과에서, 검사 코드·정책은 신뢰 base(`main`)에서 읽는다.

- [ ] **Step 0(라이브): 제안 머지 결과 취득 방법 결정·캡처** — gh merge preview vs 로컬 git merge 중 선택(§8 provisional 핵심)하고 트리·카탈로그 입력을 캡처.
- [ ] **Step 1: 실패 테스트** — 결정성(같은 머지 결과=같은 두 키); projection 트리 변경→두 키 모두 변화; **적용(선언) rule 본문 편집→판정 키·완전성 스윕 키 모두 변화**; **미선언(미적용) rule 본문 편집→완전성 스윕 키만 변화**(스펙 §4.2 근거); **`review_policy_epoch` 변경→두 키 모두 변화**; **rule 카탈로그 manifest digest 변경→판정 키만 변화**; **활성 카탈로그 입력 digest 변경→완전성 스윕 키만 변화**; README/_TEMPLATE 제외.
- [ ] **Step 2~5: 실패 확인 → 구현(정규화는 규칙 정본 재사용) → 통과 → 커밋** `feat(phase6): compute_landing_keys — 제안 머지 결과 두 키(성분별 무효화)`.

**라이브 확정 항목:** 제안 머지 결과 취득 방법은 스펙이 선택하지 않은 §8 provisional의 핵심이다(523행). `sot_lint`와 공유하는 정규화 구현의 단일화 여부도 Step 0에서 확정.

---

## 라이브 스모크(Phase 9, 계약 테스트 뒤)

각 Task의 Step 0 캡처와 단위 테스트가 끝나면, 실제 공개 저장소에 RS-A/RS-B/RS-C를 걸고 컨트롤러를 배포해 `gh api` 스키마를 실측 확정한다(스펙 §9). 확정 스키마로 각 Task의 "라이브 확정 항목"을 메꾸고 provisional 표기를 제거한다. 이 시점에 `ADR-0009`·`ADR-0007`을 proposed→accepted로 올린다(강제 CODE 착지). rename 이전·이후 합집합 등 보수적 신규 세부는 라이브 확정 시 스펙 §8에 역기입한다.

## Self-Review (계획 대 스펙)

- **스펙 커버리지**: 7개 포트 전부 Task 1·3·5~9, 두 사전 관문 Task 2·4 — §3 계약·§2.x·§4.x 매핑됨.
- **provisional 명시**: 각 포트 Task에 Step 0(라이브 캡처)과 "라이브 확정 항목"을 두어 스펙 §8 목록(gh 스키마·산출물 저장·머지 결과 취득·변경분·두 키 취득·사람 판별)을 조기 동결 없이 표기.
- **동결 계약 존중**: 동결 시그니처 변경(Task 2·4·8)은 "동결 계약 확장" 규약으로 별도 승인/래퍼 결정을 선행. §2.9가 확정한 `merge → SHA` 반환형 변경만 계약에 반영.
- **타입 일관성**: 반환형은 `models.py`·`keys.py` 동결 계약 그대로(단 `merge_pull_request`는 §2.9 확정대로 `None→str`).
