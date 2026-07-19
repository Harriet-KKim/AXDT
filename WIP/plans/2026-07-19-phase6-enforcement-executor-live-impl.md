# Phase 6 강제 게이트 실행부(GitHubGatePorts) 라이브 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **착수 시점 = Phase 9 (라이브 도그푸딩).** 이 계획의 모든 Task는 실제 GitHub 저장소·`gh` CLI 응답을 봐야 스키마가 확정되는 provisional 구현이다(스펙 §1 비목표·§8·§9). 착수 전에 아래 "활성화 전제조건 / 선행 계약 작업"을 모두 처리한다. 순수 코어(`gate.py`·`keys.py`·`models.py`)와 포트 계약(`ports.py`)의 시그니처·데이터 모델·기존 동작은 동결이며(단 `merge_pull_request`의 반환형은 §2.9가 확정한 `None→str` 예외), 이 계획은 `hosts/github.py`의 7개 `NotImplementedError` 스텁을 채우고 두 사전 관문(룰셋 점검·critical-paths)을 배선한다.

**Goal:** `WIP/axdt/sot_gate/hosts/github.py`의 7개 포트를 실제 `gh api` 호출로 구현하고, 룰셋 점검·`axdt-critical-paths` 두 사전 관문을 컨트롤러 층에 배선한다.

**Architecture:** `github.py`는 `git_host`의 `CommandBackend`(ABC)를 주입받아 gh 호출을 그 안으로 격리하고(subprocess 직접 호출 금지), (b) 클라이언트의 adapter+backend 분리를 계승한다. 각 포트는 gh 응답 JSON을 파싱해 순수 코어 계약(`models.py`·`keys.py`)으로 매핑한다. 포트는 원시 사실만 채우고 결정권 논리곱(admin ∧ 명단 ∧ 사람)은 순수 코어가 계산한다.

**Tech Stack:** Python 3(`py -3`), `gh` CLI(`gh api`), pytest. 재사용: `axdt.git_host.backend.{CommandBackend,FakeCommandBackend,SubprocessBackend}`, `axdt.git_host.models.{PullRequest,CommandResult,GitHostError}`. **pytest 실행 기준 디렉터리는 `WIP`**: `cd WIP && py -3 -m pytest axdt/sot_gate/...`(저장소 루트 아님 — `pyproject.toml`의 `testpaths=["axdt"]`, import 경로 일치).

## 활성화 전제조건 / 선행 계약 작업 (착수 전 필수)

이 항목들은 라이브 코드 이전에 처리해야 하며, 정본 개정·동결 계약 확장을 포함해 이 계획의 라이브 코드 범위를 벗어난다(사용자 게이트/별도 승인 대상). 계획은 이를 조용히 넘기지 않고 전제조건으로 명시한다.

- **P1. 정본 규칙 드리프트 정정(사용자 게이트 SoT PR).** `docs/sot/rule/sot-readiness.md` 92·105행이 "`sot/*` 보호 불요/요구하지 않음(`ADR-0009` 결정 8)"으로 남아 있으나 결정 8은 2026-07-18 개정으로 RS-C(`sot/*` force-push·삭제 차단)를 요구한다. 개정 전 활성화하면 규칙과 `verify_ruleset_config`가 반대를 가리켜 모든 머지가 막힌다. 규칙 두 문장을 결정 8·스펙 §4.1에 맞추는 SoT PR이 선행돼야 한다(`ENFORCEMENT_MATRIX.md` 전제조건과 동일).
- **P2. `verify_ruleset_config` 감시 범위 정본 개정(선택, §4.1).** 매트릭스가 "선언 전체 값 대조"를 목표로 하면 §4.1 감시 열거(362·384행)에 `require_last_push_approval`·RS-A `bypass_actors`/`rules`·RS-C 초과 대상 대조를 추가하는 정본 개정이 선행돼야 한다. 개정 없이는 매트릭스 대조가 §4.1 감시 열거에 한정된다.
- **P3. 동결 계약 확장 승인(별도 승인).** 아래 세 확장은 동결 시그니처를 바꾸므로 착수 전 승인받는다 — (a) `merge_pull_request`의 `-> None → -> str`(§2.9 확정, Task 8); (b) 두 키 취득 (ㄱ) 선택 시 컨트롤러 감사·이력 resolver 주입 계약, (ㄴ) 선택 시 불완전 스탬프의 원시 표현(Task 6); (c) `AuditRecord.base` first-parent SHA 취득 경로(Task 8). 확장을 별도 승인 작업으로 올리거나 동결 코어 밖 호스팅 래퍼에 둘지 결정한다.
- **P4. Phase 9 활성화 순서(§7).** 스펙 505행 순서 = 전제조건 확인·초기 완전성 스윕(§7) → RS-C 워크플로 전제 실증 → **RS-B 적용** → 컨트롤러 배포·기동 점검 → **RS-A 적용** → 종단 스모크. RS-A를 먼저 켜면 컨트롤러 배포가 막힌다. "라이브 캡처"에 쓸 룰셋 응답은 이 순서로 적용한 뒤 캡처한다(캡처-적용 순환 회피).

## Global Constraints

- **라이브 스키마 캡처 우선 (조기 동결 금지)**: 각 포트 Task는 **Step 0으로 라이브 `gh api` 응답을 캡처하고 스키마를 확인**한 뒤, 그 캡처를 fixture로 삼아 red 테스트를 쓴다. 추정 JSON으로 red-green을 먼저 끝내면 Phase 9가 확정해야 할 스키마를 fixture가 사실상 동결한다(스펙 §1·§8). 캡처 fixture는 `tests/fixtures/`에 실제 응답 형태로 보관한다. (사전 관문·헬퍼 Task는 포트가 아니라 캡처 대상이 다르다 — 아래 각 Task가 명시한다.)
- **페이지네이션 계약**: `gh api` 목록 응답(rulesets·PR files·comments·reviews)은 페이지네이션된다. Task 0의 공통 페이지네이션 헬퍼로 **전 페이지를 수집**하고, 각 포트에 다중 페이지 red 테스트를 둔다. 변경 파일의 뒤 페이지를 놓치면 `touches_sot`·`touches_enforcement_surface`가 `False`로 잘못 접혀 강제 장치·SoT 변경 PR이 pass-through되므로, fail-closed 관점에서 필수다(스펙 §2.6·§7).
- **동결 계약 확장 규약**: critical-paths 사전 관문(Task 4)·기동 점검(Task 2)·머지 반환형(Task 8)·두 키 취득(Task 6)은 `controller.py`/`ports.py`의 동결 시그니처·동작을 바꾼다. P3에서 승인/래퍼 결정을 선행하고, Task 안에서 조용히 바꾸지 않는다.
- **provisional 경계**: gh api 엔드포인트·필드·산출물 저장 위치·제안 머지 결과 취득·두 키 취득 방식(ㄱ/ㄴ)·사람/기계 판별은 스펙 §8이 라이브 미확정으로 열어 둔 것이다. 각 Task의 "라이브 확정 항목"을 실측으로 메꾸기 전에는 스키마·방식을 동결하지 않는다(스펙 §8·§10).
- **테스트 경계**: 순수 코어·컨트롤러 테스트는 포트 수준 `FakeGatePorts`로 하며 그대로 둔다(회귀 152개 유지). `github.py`는 CLI 수준 `FakeCommandBackend`로 결정적 단위 테스트하고, 최종 스키마 확정은 라이브 스모크(Phase 9)로 한다. `github.py`를 `FakeGatePorts`로 테스트하지 않는다(스펙 §6).
- **두 키 재계산 금지**: `read_approvals`의 두 키는 §2.3 (ㄱ) base 복원 또는 (ㄴ) 구조화 스탬프로 취득하며 머지 시점 재계산하지 않는다(규칙 ③ 위반). (ㄱ)/(ㄴ) 선택·표현은 §8 provisional(Task 6·P3).
- **포트는 판정하지 않는다**: `read_channel_decisions`·`read_approvals`는 `role_name`·사람 여부·`dismissed`·스탬프 유무 등 **원시 사실만** 채운다. admin·명단·사람 논리곱, dismissed 유효성, 스탬프 무효 판정은 순수 코어가 한다(스펙 §2.7·§3·§2.6 항목10).
- **사람/기계 판별(§2.7·§8)**: 결정권 = admin ∧ 명단 ∧ 사람 계정. `author_is_human`·`approver_is_human`은 동결 필수 필드다. 판별법은 §8 provisional이므로 라이브에서 결정하고, 사람·봇·**판별불능은 fail-closed**로 이어지는 값으로 채운다.
- **선언 단일 진실원**: 룰셋 대조 값은 `ENFORCEMENT_MATRIX.md`의 `axdt-enforcement-matrix` 기계판독 블록이 정본이다. `verify_ruleset_config`는 그 블록을 파싱해 값 일치까지 대조한다(손사본 금지, Task 1).

---

## Task 0: CommandBackend 주입 + gh api JSON/페이지네이션 헬퍼

**Files:** Modify `hosts/github.py`; Test `tests/test_hosts_github.py`(신규).

**Interfaces:** Consumes `axdt.git_host.backend.{CommandBackend,FakeCommandBackend}`·`axdt.git_host.models.{CommandResult,GitHostError}`. Produces `GitHubGatePorts(backend, repo)`; `_api_json(*args) -> dict|list`(exit≠0·malformed JSON·빈 stdout·예상 밖 top-level 타입 → `GitHostError`); `_api_paginated(*args) -> list`(전 페이지 수집).

- [ ] **Step 0(라이브): 페이지네이션 실제 출력 확인** — `gh api --paginate`(또는 `--slurp`/Link 헤더)의 실제 다중 페이지 출력 형태를 캡처해 `_api_paginated`가 합칠 형식을 확정.
- [ ] **Step 1: 실패 테스트** — (a) 정상 JSON, (b) exit≠0→`GitHostError`, (c) exit 0 + malformed JSON→`GitHostError`, (d) 빈 stdout→`GitHostError`, (e) top-level 타입 불일치(list 기대에 dict)→`GitHostError`, (f) `_api_paginated`가 캡처한 2페이지 응답을 한 리스트로 합침.
- [ ] **Step 2~4: 실패 확인 → 구현 → 통과.** Run: `cd WIP && py -3 -m pytest axdt/sot_gate/tests/test_hosts_github.py -v`.
- [ ] **Step 5: 커밋** — `feat(phase6): GitHubGatePorts 주입 + gh api JSON/페이지네이션 헬퍼(fail-closed 파싱)`.

**라이브 확정 항목:** `gh api` 인증·페이지네이션 실제 형식·rate-limit은 Step 0 캡처로 확정(스펙 §8).

---

## Task 1: verify_ruleset_config — 선언 블록 파싱 + 값 정확 대조

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_paginated`·`ENFORCEMENT_MATRIX.md`의 `axdt-enforcement-matrix` 블록. Produces `verify_ruleset_config() -> bool` + 선언 블록 파서.

**gh 매핑(스펙 §4.1·§8):** `gh api repos/{repo}/rulesets` + 각 id로 `rulesets/{id}`. `axdt-enforcement-matrix` 블록을 파싱해 대조 기준을 얻고(코드 상수 하드코딩 금지, 손사본 방지), 대조 규칙 4항목을 **값 일치까지** 검사. `<controller-actor-id>`는 런타임 컨트롤러 계정 `actor_id`로 결합.

- [ ] **Step 0(라이브): rulesets 응답 캡처** — P4 순서로 RS-A/RS-B/RS-C를 적용한 뒤 응답을 `tests/fixtures/rulesets_*.json`으로 캡처, 필드 경로(`rules[].type`·`rules[].parameters`·`bypass_actors`) 확인.
- [ ] **Step 1a: 선언 블록 파서 red** — 정상 블록 파싱; 블록 부재·중복·미종결 펜스·문법 위반·유효 `ruleset` 행 0개 → fail-closed(대조 실패 신호).
- [ ] **Step 1b: 대조 red(캡처 fixture 기반)** — 정상 3룰셋→`True`; `required_approving_review_count: 2`→`False`; `dismiss_stale_reviews_on_push: false`→`False`; `allowed_merge_methods: ["squash"]`→`False`; **RS-B에 `non_fast_forward`/`deletion` 누락→`False`**; RS-B에 `bypass_actors` 있음→`False`; RS-A/RS-B 합쳐짐→`False`; RS-A 부재→`False`; RS-C 부재→`False`; RS-C에 `pull_request` 룰 추가→`False`; **RS-C `bypass_actors` 비어있지 않음→`False`**; 룰셋 목록 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): verify_ruleset_config — 선언 블록 파싱 + 값 정확 대조`.

**라이브 확정 항목:** `rulesets` 응답 필드 경로·룰셋 식별(이름 vs id)은 Step 0 캡처로 확정(스펙 §8).

---

## Task 2: 룰셋 점검 배선 — 기동 + 매 머지 실패 경보·감사 (호스팅)

**Files:** Modify `controller.py` 또는 Phase 9 호스팅 래퍼(**P3 동결 계약 확장**); Test `test_controller.py` 또는 호스팅 테스트.

**규칙(스펙 §4.1·363행):** "기동 시와 매 머지의 직렬화 잠금 안에서" 점검하고, **불일치 시 경보·감사 기록**. `controller.py:50-52`는 기동 점검·경보·실패 감사를 호스팅 증분 몫으로 유보했고, 현재 `merge_if_green`(115-117행)은 룰셋 실패 시 감사 없이 RED만 반환한다.

- [ ] **Step 0: 배선 위치 결정(P3)** — 컨트롤러 계약 개정 vs 호스팅 래퍼.
- [ ] **Step 1: 실패 테스트** — 기동 시 `verify_ruleset_config()==False`→머지 수용 전 차단 + 실패 사유 감사; **매 머지 점검 실패→경보 + 실패 감사 기록**(기동만이 아니라 매 머지도); `True`→정상.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과(회귀 152 유지) → 커밋** `feat(phase6): 룰셋 점검 배선 — 기동+매 머지 실패 경보·감사`.

**라이브 확정 항목:** 경보 채널(로그·메신저)은 Phase 7·8 연동으로 확정.

---

## Task 3: read_pr_metadata — PR 메타데이터 + touches_sot (rename 포함)

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`·`_api_paginated`·`PullRequest`. Produces `read_pr_metadata(pr) -> PRMetadata`.

**gh 매핑(스펙 §2.6·§8):** PR 조회 → `author`·`head_ref`·`head_repo`·`head_sha`·`state`. 제안된 머지 결과 변경 경로를 전 페이지 수집해 `target-content projection`(`docs/sot/{requirements,specification,test-design}`에서 `README.md`·`_TEMPLATE.md` 제외)과 교차하면 `touches_sot=True`. **rename은 이전·이후 경로 합집합 모두에 적용**(Task 4 헬퍼 공유) — 구경로가 projection 내면 삭제도 SoT 변경이다.

- [ ] **Step 0(라이브): PR 조회·변경분 응답 캡처** — 조회 JSON·변경 파일 목록(다중 페이지·rename 포함)을 fixture로 캡처.
- [ ] **Step 1: 실패 테스트** — 필드 매핑; `docs/sot/specification/spec.md` 변경→`True`; `README.md`만→`False`; **rename 구경로가 projection 내(신경로 밖)→`touches_sot=True`**; 변경 파일 2페이지 중 SoT가 2페이지에 있어도 감지; state 매핑.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_pr_metadata — touches_sot(전 페이지·rename 합집합)`.

**라이브 확정 항목:** 제안 머지 결과 변경분 취득 방법·`pulls/{n}/files` 페이지·rename 표기는 Step 0 캡처로 확정(스펙 §8·524행).

---

## Task 4: critical-paths 사전 관문 → touches_enforcement_surface

**Files:** Modify `hosts/github.py`(블록 읽기·glob 매칭·rename 합집합 헬퍼); **P3 동결 계약 확장** — Modify `controller.py`(잠금 안 사전 관문) 또는 호스팅 래퍼; Test `test_hosts_github.py`·`test_controller.py`.

**규칙(스펙 §7·506행, `protected-paths.md`):** ` ```axdt-critical-paths ` 블록을 **신뢰 base(`main`) 버전**으로 읽는다. `critical <glob>` 줄만 유효, glob 의미는 `protected-paths.md:50-53`. **변경 경로는 rename 이전·이후 합집합 모두에 glob 적용**(근거: `protected-paths.md:48`; 단 블록 문법 절 56-59행에는 rename 의미가 없어, 이 합집합은 계약 우선 원칙상 red 이전에 §8 결정으로 기록한다 — P3/라이브 스모크 역기입). 블록 부재·기형·유효 `critical` 행 0개면 `evaluate_gate` 이전 사전 관문에서 직접 fail-closed RED(`protected-paths.md:57-58`).

- [ ] **Step 0: 배선 위치 결정(P3) + §7 (ㅁ) 제약** — 사전 관문 RED 실패 신호를 컨트롤러 계약에 넣을지/래퍼에 둘지. 단 §7 (ㅁ)(스펙 506행)은 블록 판독을 "머지 직전 **잠금 안** 사전 관문"으로 요구하고 직렬화 잠금은 `merge_if_green` 내부(controller.py:114)에 있으므로, 래퍼 선택 시 잠금 통합 방안을 함께 정한다(사실상 (a) 편향).
- [ ] **Step 0b(라이브): base 블록 읽기 응답 캡처** — `contents/...?ref=main`의 인코딩(base64) 응답을 fixture로 캡처.
- [ ] **Step 1: 실패 테스트(파싱·매칭)** — 블록 파싱; glob 매칭(`WIP/axdt/sot_gate/**`가 `.../github.py` 매칭, trailing `**` 디렉터리 자체); **rename 이전 경로가 critical→매칭**; 블록 부재/기형→예외 신호.
- [ ] **Step 2: 실패 테스트(관문 배선)** — 블록 못 읽으면 `merge_if_green`이 머지 안 하고 잠금 안에서 fail-closed RED; touches_enforcement_surface만 참인 PR이 포크 거부+결정권자 승인 관문 통과/차단.
- [ ] **Step 3~5: 실패 확인 → 구현 → 통과(회귀 152 유지) → 커밋** `feat(phase6): critical-paths 잠금 안 사전 관문 + glob(rename 합집합)`.

**라이브 확정 항목:** base 파일 읽기 엔드포인트·인코딩·변경분 취득은 Step 0b 캡처로 확정(스펙 §524·§8).

---

## Task 5: read_channel_decisions — PR 코멘트 + role_name + 사람 판별 + 스탬프 문법

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`·`_api_paginated`. Produces `read_channel_decisions(pr) -> tuple[ChannelDecision, ...]`.

**gh 매핑(스펙 §2.7·§4.1·§8):** `issues/{n}/comments`(전 페이지) → 구조화 코멘트 파싱 → `ChannelDecision(...)`. `author_role`은 `collaborators/{login}/permission`의 `role_name`(레거시 `permission` 금지). `author_is_human`은 사람/기계 판별(§8). **구조화 코멘트 스탬프 문법**(필드명·버전·완전 결속 키·accepted/rejected)은 producer(사람 채널)와 consumer가 공유하는 **버전된 형식**으로 정의한다(스펙 98행은 개념만). 원시 사실만 채우고 결정권 논리곱은 코어.

- [ ] **Step 0(라이브): comments·permission·계정유형 응답 캡처 + 스탬프 문법 확정** — 응답을 fixture로 캡처하고 버전된 스탬프 문법·예시를 정의.
- [ ] **Step 1: 실패 테스트** — 구조화 코멘트→매핑; `updated_at != created_at`→편집 표기; `role_name`→`author_role`; 계정 사람→`author_is_human=True`, 봇→`False`, 판별불능→코어 fail-closed로 이어지는 값; **unknown version·중복 필드·부분 키·기형 스탬프→무시 또는 fail-closed(코어 판정용 원시값)**; 비구조화 코멘트 무시; 코멘트 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_channel_decisions — role_name·사람 판별·버전 스탬프 문법`.

**라이브 확정 항목:** 코멘트 스키마·편집/삭제 감지·사람/기계 판별 사실은 Step 0 캡처로 확정(스펙 §8·519행).

---

## Task 6: read_approvals — 스트림 전량 + 두 키 취득(라이브 결정) + dismissed·무효 보존

**Files:** Modify `hosts/github.py` (+ P3에 따라 `ports.py`/생성자 계약); Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`·`_api_paginated`. Produces `read_approvals(pr) -> tuple[ApprovalEvent, ...]`.

**gh 매핑(스펙 §2.3·§8):** `pulls/{n}/reviews`(전 페이지) → 승인 스트림 **전체**를 `ApprovalEvent`로 반환. 어느 승인이 유효한지는 게이트가 판정 — 포트는 대표 선정·필터링을 하지 않는다(`ports.py:51-55`). `dismissed` 승인도 `dismissed=True`로 전량 반환.

- [ ] **Step 0: 두 키 취득 방식·무효 표현 라이브 결정(P3)** — §2.3 (ㄱ) base 복원(컨트롤러 감사·first-parent 이력 resolver 주입 계약 필요) / (ㄴ) 구조화 스탬프 중 선택. **(ㄴ) 선택 시**: 두 키 스탬프가 하나라도 빠진 "무효 승인"을 `ApprovalEvent`(두 키 non-optional, `models.py:64`)로 어떻게 표현할지 결정 — 임의 제외(필터링 금지 위반)·임의 키 합성(재계산 금지 위반) 대신, **착지 키와 절대 일치하지 않는 센티널 키로 채워 전량 반환**(게이트의 키 불일치 판정에 자연 흡수)하거나 포트 제외를 명시 허용하는 계약 개정 중 택일. reviews 응답·스탬프 형식을 fixture로 캡처.
- [ ] **Step 1: 실패 테스트(방식 결정 후)** — 여러 승인 전량 반환(대표 선정 금지); dismissed→`dismissed=True` 반환(제외 아님); 선택 방식으로 두 키 취득; (ㄴ) 선택 시 두 키 스탬프 **하나라도 빠지면** 결정한 무효 표현(센티널 등)으로 반환(단일 스탬프만 있는 승인→무효 표현), 둘 다 있으면 유효; reviews 다중 페이지.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_approvals — 스트림 전량 + dismissed·무효 보존 + 두 키(결정 방식)`.

**라이브 확정 항목:** (ㄱ)/(ㄴ) 최종 채택·무효 표현·승인 본문 편집 탐지는 Step 0 결정·캡처로 확정(스펙 §8·520행).

---

## Task 7: read_ci_artifacts — 산출물 조회 + 쓰기 신뢰 통제

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json`. Produces `read_ci_artifacts(pr) -> tuple[ConsistencyArtifact|None, CompletenessArtifact|None]`.

**gh 매핑(스펙 §4.2·§8):** ②검토 CI의 두 신뢰 산출물을 산출물 저장소에서 읽는다(커밋 상태 금지). 없거나 파싱 실패면 `None`(fail-closed). **쓰기 신뢰 모델이 진짜 방어선** — 신뢰된 ② CI 신원만 산출물을 쓸 수 있어야 한다(저장 위치 ACL 또는 CI 신원 서명; 스펙 401·521행 "하중을 받는 보안 요소"). 두 키 대조는 재전송 방지용일 뿐 위조 방지가 아니다.

- [ ] **Step 0(라이브): 저장 위치·형식·쓰기 통제 선택·캡처** — 산출물 저장 위치·JSON 스키마·쓰기 신원(ACL/서명)을 선택하고 배타적 쓰기 통제를 실증. fixture 캡처.
- [ ] **Step 1: 실패 테스트** — 두 산출물 정상→매핑; 정합성만→`(artifact, None)`; 파싱 실패→`None`; `FullBindingKey` 매핑; **위조 산출물·잘못된 서명·일반 PR 신원 쓰기→fail-closed(수용 안 됨)** 음성 시험.
- [ ] **Step 2~5: 실패 확인 → 구현 → 통과 → 커밋** `feat(phase6): read_ci_artifacts — 두 산출물 + 쓰기 신뢰 통제·음성 시험`.

**라이브 확정 항목:** 저장 위치·스키마·쓰기 통제 방식은 Step 0 선택·실증으로 확정(스펙 §4.2·§8·521행).

---

## Task 8: merge_pull_request — head 고정 머지 + 머지 커밋 SHA + base 취득

**Files:** Modify `hosts/github.py`(반환형) · **`ports.py`(ABC 시그니처·docstring)** · **`ports.py`의 `FakeGatePorts`(SHA 반환 scripting)** · `controller.py`(감사 기록) · Test `test_hosts_github.py`·**`test_ports.py`**·`test_controller.py`. (P3 동결 계약 확장 — §2.9 확정.)

**Interfaces:** Produces `merge_pull_request(pr, judgment, completeness, head_sha) -> str`(머지 커밋 SHA) — 동결 `-> None`을 §2.9 확정대로 확장. `FakeGatePorts`·컨트롤러·계약 테스트를 함께 마이그레이션한다.

**gh 매핑(스펙 §2.5·§2.9·§8):** `PUT repos/{repo}/pulls/{n}/merge`, `merge_method=merge`, `sha={head_sha}`(스냅샷값, 재조회 금지). 응답의 머지 커밋 SHA 반환. **`AuditRecord.base` = 머지 커밋 first-parent SHA인데 머지 응답에 first-parent가 없으므로 취득 방법을 확정한다**(P3-c) — `MergeResult(merge_sha, base_sha)` 확장, 또는 머지 후 커밋 조회 1회(`commits/{sha}` parents[0]), 또는 별도 기록 계약 중 택일. head 이동 거부→`HeadMovedError`.

- [ ] **Step 0(라이브): merge 응답·거부 코드·parent 조회 캡처** — 정상 머지 응답(머지 커밋 SHA)·head 불일치 거부 코드·first-parent 취득 경로를 fixture로 캡처.
- [ ] **Step 1: 실패 테스트** — 정상 머지→argv(`merge_method=merge`·`sha=head_sha`) + **반환값=머지 커밋 SHA**; head 불일치→`HeadMovedError`; 그 밖 실패→`GitHostError`; **`FakeGatePorts`가 SHA 반환**; **컨트롤러 감사 `base`=머지 커밋 first-parent SHA**; `test_ports`의 반환형 계약 회귀.
- [ ] **Step 2~5: 실패 확인 → 구현(`None→str` 마이그레이션: github·ports ABC·Fake·controller·test_ports) → 통과 → 커밋** `feat(phase6): merge_pull_request None→str(§2.9) + first-parent base 감사`.

**라이브 확정 항목:** 거부 코드 분기(`405`/`409`)·머지 SHA 필드·first-parent 취득 경로는 Step 0 캡처로 확정(스펙 §2.9·118행·§8).

---

## Task 9: compute_landing_keys — 제안 머지 결과 두 키 + trusted epoch + 골든 벡터

**Files:** Modify `hosts/github.py`; Test `test_hosts_github.py`.

**Interfaces:** Consumes `_api_json` + trusted epoch provider + 두 키 성분 규약(`keys.py`·규칙 정본). Produces `compute_landing_keys(pr) -> tuple[JudgmentKey, CompletenessSweepKey]`.

**gh 매핑(스펙 §2.3·§4.2, 규칙 sot-readiness.md 35·41·52·53·55행):** 제안된 머지 결과(`merge(base, head)`)에서 두 키 성분 계산. 성분·정규화·digest 규약은 규칙 §②가 정본이고 게이트는 불투명 비교만. **`review_policy_epoch`는 trusted 실행 환경 성분**(모델 revision·실행기 버전·프롬프트·추론 설정; 규칙 41·46행)을 포함하므로 **trusted epoch provider**가 필요하다. **실행기(판정 키 계산기)·검토 스킬 같은 정책 파일은 신뢰 base에서 읽고, 검토 대상 SoT/rule 콘텐츠는 머지 결과에서 취한다**(규칙 55행 구분 — "검사 코드·정책=base / 대상=머지 결과"). 규칙 42행이 요구하는 **정규화·digest 골든 벡터를 단일 구현으로 산출·고정**(Phase 6 conformance)해 ② CI와의 digest 일치를 라이브 전에 보장한다.

- [ ] **Step 0(라이브): 제안 머지 결과 취득 방법 결정·trusted epoch provider 확정** — gh merge preview vs 로컬 git merge 선택(§8 핵심), trusted epoch 성분(실행기 revision 등) 취득 경로 확정, 골든 벡터 산출.
- [ ] **Step 1: 실패 테스트** — 결정성(같은 머지 결과=같은 두 키); projection 트리 변경→두 키 모두; **적용(선언·active local) rule 본문 편집→판정 키·완전성 스윕 키 모두**; **미선언(inactive) rule 본문 편집→완전성 스윕 키만**(규칙 35행 "active local"); `review_policy_epoch`(실행기 revision) 변경→두 키 모두; **rule catalog manifest digest 변경(=비활성 rule의 path·scope·status 변경)→판정 키만**(활성 rule frontmatter 편집은 내용을 바꿔 활성 카탈로그 입력 digest도 함께 바꾸므로 manifest-only 변이는 비활성 rule로만 구성 가능, 규칙 53·35행); 활성 카탈로그 입력 digest 변경→완전성 스윕 키만; **정규화 골든 벡터 일치·BOM/CRLF/NFC·UTF-8 실패·framing/value-domain**(규칙 42행); README/_TEMPLATE 제외.
- [ ] **Step 2~5: 실패 확인 → 구현(정규화·digest는 규칙 정본 단일 구현 재사용) → 통과 → 커밋** `feat(phase6): compute_landing_keys — 두 키·trusted epoch·골든 벡터`.

**라이브 확정 항목:** 제안 머지 결과 취득 방법·trusted epoch provider는 §8 provisional의 핵심(523행). `sot_lint`·② CI와 공유하는 정규화 구현 단일화는 Step 0에서 확정.

---

## 라이브 스모크 (Phase 9, 계약 테스트 뒤 — §7 순서)

전제조건(P1~P4) 확인 후, 스펙 §7·505행 순서로 활성화한다: **초기 완전성 스윕(§7) → RS-C 워크플로 전제 실증 → RS-B 적용·캡처 → 컨트롤러 배포·기동 점검 → RS-A 적용·캡처 → 종단 스모크.** 확정 스키마로 각 Task의 "라이브 확정 항목"을 메꾸고 provisional 표기를 제거한다. 이 시점에 `ADR-0009`·`ADR-0007`을 proposed→accepted로 올린다. Task 3·4의 rename 합집합 등 정본에 명문 근거가 얇은 세부는 스펙 §8·`protected-paths.md`에 역기입한다.

## Self-Review (계획 대 스펙)

- **스펙 커버리지**: 7개 포트 전부 Task 1·3·5~9, 두 사전 관문 Task 2·4 — §3 계약·§2.x·§4.x 매핑. 선행 전제조건 P1~P4로 정본 개정·동결 확장·활성화 순서를 명시.
- **provisional 명시**: 포트 Task마다 Step 0(라이브 캡처/결정)과 "라이브 확정 항목"을 두어 §8 목록(gh 스키마·산출물 저장·머지 결과 취득·변경분·두 키 취득·사람 판별)을 조기 동결 없이 표기. (헬퍼 Task 0·배선 Task 2·4는 포트가 아니라 Step 0의 캡처/결정 대상이 다름을 각 Task가 명시 — 모든 Task에 동일 Step 0이 있다는 뜻이 아니다.)
- **동결 계약 존중**: 동결 시그니처 변경(Task 2·4·6·8)은 P3에서 승인/래퍼 결정을 선행. §2.9가 확정한 `merge → str` 반환형만 계약에 반영하고 `ports.py`·`FakeGatePorts`·`test_ports.py`까지 마이그레이션 범위에 포함.
- **타입 일관성**: 반환형은 `models.py`·`keys.py` 동결 계약 그대로(단 `merge_pull_request`는 §2.9 확정 `None→str`).
